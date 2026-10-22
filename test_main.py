import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from main import CROP_IMAGE_TOOL, ImageCropper, crop_image, imread_unicode, imwrite_unicode


ROOT = Path(__file__).resolve().parent


class HeadlessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.output = self.root / "crops"

    def image(self, name, height, width):
        path = self.input / name
        pixels = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
        self.assertTrue(imwrite_unicode(path, pixels))
        return path, pixels

    def cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, input=stdin,
        )

    def test_tiles_cover_images_without_gui_and_round_trip(self):
        images = [self.image("test.png", 7, 10), self.image("small.png", 2, 3),
                  self.image("\u6e2c\u8a66.png", 8, 8)]
        cropper = ImageCropper(str(self.input), 4, str(self.output))
        gui_calls = ("namedWindow", "resizeWindow", "setWindowTitle", "getWindowImageRect",
                     "setMouseCallback", "imshow", "waitKey", "destroyWindow", "destroyAllWindows")
        with patch.multiple("main.cv2", **{
            name: unittest.mock.Mock(side_effect=AssertionError("GUI called"))
            for name in gui_calls
        }), patch("main.get_available_screen_size", side_effect=AssertionError("Screen queried")):
            cropper.run_headless()
            final = self.root / "final"
            cropper.paste_back(str(final))

        metadata = json.loads((self.output / "crops.json").read_text(encoding="utf-8"))
        for path, pixels in images:
            coverage = np.zeros(pixels.shape[:2], dtype=np.uint8)
            crops = metadata[str(path)]
            self.assertEqual(len(crops), ((pixels.shape[0] + 3) // 4) * ((pixels.shape[1] + 3) // 4))
            for index, crop in enumerate(crops):
                x, y, w, h = (crop[key] for key in ("x", "y", "w", "h"))
                self.assertEqual(crop["id"], f"{path.stem}_{index:03d}")
                np.testing.assert_array_equal(
                    imread_unicode(self.output / f"{crop['id']}.png"), pixels[y:y+h, x:x+w])
                coverage[y:y+h, x:x+w] += 1
            np.testing.assert_array_equal(coverage, np.ones_like(coverage))
            np.testing.assert_array_equal(imread_unicode(final / path.name), pixels)

    def test_cli_headless_and_paste(self):
        path, pixels = self.image("test.png", 7, 10)
        result = self.cli("--headless", "--tile", "-i", path, "--size", 4, "-o", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Saved 6 crops", result.stdout)
        final = self.root / "final"
        result = self.cli("--headless", "--paste", "-o", self.output, "--output-final", final)
        self.assertEqual(result.returncode, 0, result.stderr)
        np.testing.assert_array_equal(imread_unicode(final / path.name), pixels)

    def test_cli_rejects_nonpositive_size(self):
        for size in (0, -1):
            with self.subTest(size=size):
                result = self.cli("--headless", "--tile", "--size", size, "-o", self.output)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--size must be greater than zero", result.stderr)
        self.assertFalse(self.output.exists())

    def test_empty_input(self):
        result = self.cli("--headless", "--tile", "-i", self.input, "-o", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No images found.", result.stdout)

    def test_unreadable_image_is_skipped(self):
        (self.input / "bad.png").write_bytes(b"not an image")
        path, _ = self.image("good.png", 2, 3)
        cropper = ImageCropper(str(self.input), 4, str(self.output))
        cropper.run_headless()
        self.assertEqual(list(cropper.all_crops), [str(path)])

    def test_write_failure_does_not_record_unsaved_crops(self):
        self.image("test.png", 2, 3)
        cropper = ImageCropper(str(self.input), 4, str(self.output))
        with patch("main.imwrite_unicode", return_value=False):
            with self.assertRaisesRegex(OSError, "Could not write crop image"):
                cropper.run_headless()
        self.assertFalse((self.output / "crops.json").exists())

    def request(self, path, crops):
        return {"input_path": str(path), "output_dir": str(self.output), "crops": crops}

    def test_agent_anchors_odd_sizes_and_clipping_without_gui(self):
        path, pixels = self.image("\u6e2c\u8a66.png", 7, 10)
        specs = [
            {"anchor": "top_left", "position": [3, 2], "size": 5},
            {"anchor": "center", "position": [5, 4], "size": 5},
            {"anchor": "center", "position": [0, 0], "size": 5},
            {"anchor": "top_left", "position": [8, 6], "size": 4},
            {"anchor": "top_left", "position": [-1, -2], "size": 4},
            {"anchor": "center", "position": [5, 4], "size": 4},
        ]
        expected = [(3, 2, 5, 5), (3, 2, 5, 5), (0, 0, 3, 3),
                    (8, 6, 2, 1), (0, 0, 3, 2), (3, 2, 4, 4)]
        with patch("main.ImageCropper.run", side_effect=AssertionError("Interactive mode")), \
                patch("main.get_available_screen_size", side_effect=AssertionError("Screen queried")), \
                patch("main.cv2.namedWindow", side_effect=AssertionError("GUI called")), \
                patch("builtins.print", side_effect=AssertionError("Function printed")):
            result = crop_image(**self.request(path, specs))
        for crop, rectangle in zip(result["crops"], expected):
            self.assertEqual(tuple(crop[key] for key in ("x", "y", "w", "h")), rectangle)
            x, y, w, h = rectangle
            np.testing.assert_array_equal(imread_unicode(crop["path"]), pixels[y:y+h, x:x+w])
        metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
        self.assertEqual(metadata[str(path)], [
            {key: value for key, value in crop.items() if key != "path"}
            for crop in result["crops"]
        ])

    def test_agent_cli_file_stdin_and_schema(self):
        path, _ = self.image("test.png", 7, 10)
        payload = self.request(path, [{"anchor": "center", "position": [5, 4], "size": 4}])
        request_path = self.root / "request.json"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
        file_result = self.cli("--headless", "--request", request_path)
        stdin_result = self.cli("--headless", "--request", "-", stdin=json.dumps(payload))
        for result in (file_result, stdin_result):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertEqual(json.loads(result.stdout)["crops"][0]["x"], 3)
        self.assertEqual(json.loads(file_result.stdout), json.loads(stdin_result.stdout))
        schema_result = self.cli("--describe-tool")
        self.assertEqual(schema_result.returncode, 0, schema_result.stderr)
        self.assertEqual(json.loads(schema_result.stdout), CROP_IMAGE_TOOL)

    def test_agent_rejects_invalid_specs_before_any_writes(self):
        path, _ = self.image("test.png", 7, 10)
        valid = {"anchor": "top_left", "position": [0, 0], "size": 4}
        invalid_specs = [
            [], {}, [None], [dict(valid, anchor="guess")],
            [dict(valid, position=[1.5, 2])], [dict(valid, position=[True, 2])],
            [dict(valid, position=[1])], [dict(valid, position="1,2")],
            [dict(valid, size=True)], [dict(valid, size=0)], [dict(valid, size=-1)],
            [dict(valid, size=2.5)], [dict(valid, extra=1)],
            [{"position": [0, 0], "size": 4}],
            [valid, dict(valid, position=[10, 0])],
            [dict(valid, position=[-4, 0])],
            [dict(valid, position=[0, 7])],
        ]
        for specs in invalid_specs:
            with self.subTest(specs=specs):
                with self.assertRaises(ValueError):
                    crop_image(**self.request(path, specs))
                self.assertFalse(self.output.exists())

    def test_agent_cli_errors_are_json_and_nonzero(self):
        for payload in ("{", "[]", "{}", '{"unexpected": 1}',
                        json.dumps(self.request(self.input / "missing.png", [
                            {"anchor": "center", "position": [0, 0], "size": 4}]))):
            with self.subTest(payload=payload):
                result = self.cli("--headless", "--request", "-", stdin=payload)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error", json.loads(result.stderr))
        self.assertFalse(self.output.exists())

    def test_headless_requires_explicit_operation(self):
        for args in (("--headless",), ("--request", "-"), ("--tile",),
                     ("--headless", "--request", "-", "--tile")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)

    def test_agent_replaces_only_target_metadata_and_pastes(self):
        first, _ = self.image("first.png", 7, 10)
        second, pixels = self.image("second.png", 7, 10)
        spec = {"anchor": "top_left", "position": [0, 0], "size": 4}
        crop_image(**self.request(first, [spec]))
        crop_image(**self.request(second, [spec, spec]))
        result = crop_image(**self.request(second, [dict(spec, position=[5, 3])]))
        saved = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
        self.assertEqual(set(saved), {str(first), str(second)})
        self.assertEqual(len(saved[str(second)]), 1)
        edited = np.full((4, 4, 3), 127, dtype=np.uint8)
        self.assertTrue(imwrite_unicode(result["crops"][0]["path"], edited))
        final = self.root / "final"
        ImageCropper(str(self.input), output_dir=str(self.output)).paste_back(str(final))
        pixels[3:7, 5:9] = edited
        np.testing.assert_array_equal(imread_unicode(final / second.name), pixels)


if __name__ == "__main__":
    unittest.main()
