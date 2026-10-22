import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from main import ImageCropper, imread_unicode, imwrite_unicode


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

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True,
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
        result = self.cli("--headless", "-i", path, "--size", 4, "-o", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Saved 6 crops", result.stdout)
        final = self.root / "final"
        result = self.cli("--headless", "--paste", "-o", self.output, "--output-final", final)
        self.assertEqual(result.returncode, 0, result.stderr)
        np.testing.assert_array_equal(imread_unicode(final / path.name), pixels)

    def test_cli_rejects_nonpositive_size(self):
        for size in (0, -1):
            with self.subTest(size=size):
                result = self.cli("--headless", "--size", size, "-o", self.output)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--size must be greater than zero", result.stderr)
        self.assertFalse(self.output.exists())

    def test_empty_input(self):
        result = self.cli("--headless", "-i", self.input, "-o", self.output)
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


if __name__ == "__main__":
    unittest.main()
