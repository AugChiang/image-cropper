# ImageCropper

An interactive, high-performance tool for batch-processing image crops using a fixed-size "stamp" approach. 
Built with OpenCV, it supports zooming, panning, and precise crop selection.

## Key Features

- **Fixed-Size Stamp:** Quickly generate uniform crops (default 512x512) centered on your mouse click.
- **Interactive Navigation:** Zoom with the mouse wheel and pan using custom scrollbars or window resizing.
- **Batch Processing:** Seamlessly iterate through entire directories of images.
- **Metadata Export:** Saves crop coordinates and identifiers to a JSON file for easy integration with downstream tasks.
- **Undo/Reset:** Quick shortcuts to correct mistakes during the cropping process.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AugChiang/ImageCropper.git
   cd ImageCropper
   ```

2. **Install dependencies:**
   It is recommended to use a virtual environment or Conda.
   ```bash
   pip install -r requirements.txt
   ```

## How to Use

Launch the cropper by pointing it to a directory or a specific image file:

```bash
python main.py -i ./input --size 512
```

You can customize the behavior using command-line arguments:

- `-i`, `--input`: Path to an image file or a directory (default: `./input`).
- `--size`: The width and height of the crop stamp (default: `512`).
- `-o`, `--output`: Filename for the JSON metadata (default: `./output_crops`).
- `--headless`: Run without a window using `--request`, `--tile`, or `--paste`.
- `--request PATH`: Read agent crop arguments from a JSON file (`-` reads stdin).
- `--describe-tool`: Print the `crop_image` function's argument schema as JSON and exit.

### Headless Mode

AI agents can call `crop_image` directly or pass the same arguments as JSON to
the command line. Get the machine-readable function name, description, and JSON
argument schema with:

```bash
python main.py --describe-tool
```

Every crop must explicitly provide all three fields:

| Field | Meaning |
| :--- | :--- |
| `anchor` | `"top_left"` or `"center"`; never inferred from the numbers |
| `position` | Two integers: `[x1, y1]` for `top_left`, or `[cx, cy]` for `center` |
| `size` | Positive integer: the **full square side length**, not a radius or half-size |

Coordinates are zero-based pixels in the **original image**, independent of any
preview scaling. The origin `(0, 0)` is at the top-left; x increases to the right
and y increases downward. For `top_left`, the requested rectangle is
`[x1, x1 + size) × [y1, y1 + size)`. For `center`, first calculate
`x1 = cx - size // 2` and `y1 = cy - size // 2`, then use the same rectangle.
Right and bottom bounds are exclusive. Integer division also defines odd sizes:
center `[5, 5]` with size `5` selects pixels `[3:8, 3:8]`.

Rectangles are intersected with the image bounds, without shifting or padding.
Negative coordinates are accepted if the rectangle overlaps the image. For
example, center `[0, 0]` with size `5` produces a `3 × 3` crop at `[0, 0]`.
A rectangle entirely outside the image is an error. All crop specifications
are validated before writing any files. Missing fields, unknown fields,
fractional coordinates, booleans, and nonpositive sizes are rejected.

Python function call (returns a JSON-serializable dictionary and prints nothing):

```python
from main import crop_image

result = crop_image(
    input_path="input/photo.png",
    output_dir="output_crops",
    crops=[
        {"anchor": "top_left", "position": [100, 200], "size": 512},
        {"anchor": "center", "position": [356, 456], "size": 512},
    ],
)
```

These two specifications describe the same rectangle. A function-call dispatcher
can pass decoded arguments using `crop_image(**arguments)`.

For the CLI, save the arguments object as `request.json`:

```json
{
  "input_path": "input/photo.png",
  "output_dir": "output_crops",
  "crops": [
    {"anchor": "top_left", "position": [100, 200], "size": 512},
    {"anchor": "center", "position": [356, 456], "size": 512}
  ]
}
```

```bash
python main.py --headless --request request.json
```

Alternatively, pipe that JSON object into `python main.py --headless --request -`.
The payload contains the function arguments only; do not wrap it in a function
name or an `arguments` field. Paths are relative to the current working directory,
including when the JSON file is elsewhere. `output_dir` defaults to `output_crops`;
`input_path` and a nonempty `crops` array are required. Each request targets one
image; call again for other images. `-i`, `-o`, and `--size` apply to interactive
or tiling mode; request mode takes these values exclusively from the JSON payload.

Success prints one JSON object to stdout and exits with status `0`:

```json
{
  "input_path": "input/photo.png",
  "output_dir": "output_crops",
  "metadata_path": "output_crops/crops.json",
  "crops": [
    {"x": 100, "y": 200, "w": 512, "h": 512, "id": "photo_000", "path": "output_crops/photo_000.png"},
    {"x": 100, "y": 200, "w": 512, "h": 512, "id": "photo_001", "path": "output_crops/photo_001.png"}
  ]
}
```

Paths use the platform's path separators. Returned `x`, `y`, `w`, `h` are the
**actual clipped** top-left coordinates and dimensions. PNGs and `crops.json`
use the interactive mode's metadata format, so they support `--paste`.
A request replaces the saved selections for its input image, retaining metadata
for other images. Include all desired crops for that image in one call. Files
with matching IDs are overwritten; leftover PNGs from older selections are not
deleted and are not used by `--paste`. Use separate output directories for images
with the same filename stem. Request errors print `{"error": "..."}` to stderr
and exit with status `2`; Python calls raise `ValueError`, `TypeError`, or `OSError`.
I/O errors during saving can leave partially written files.

Automatic tiling is a separate, explicit operation:

```bash
python main.py --headless --tile -i ./input --size 512 -o ./output_crops
```

Each image is tiled from left to right, then top to bottom, with no overlap.
Tiles at the right and bottom edges are clipped to the image bounds; images
smaller than `--size` produce one crop. The stamp size must be greater than zero.
Running `--headless` alone reports an error; an operation must be supplied.

To paste processed crops back into the originals without opening a window:

```bash
python main.py --headless --paste -o ./output_crops --output-final ./output_final
```

`--paste` performs reconstruction only and does not generate new crops.

### Controls

| Key | Action |
| :--- | :--- |
| **Mouse Wheel** | Zoom in/out |
| **Left Click** | Place a crop stamp |
| **Scrollbars** | Drag to pan when zoomed in |
| **`Z`** | Undo the last crop on the current image |
| **`R`** | Reset all crops on the current image |
| **`B`** | Save current crops and move to the previous image |
| **`N`** or **`Enter`** | Save current crops and move to the next image |
| **`Q`** or **`Esc`** | Save progress and exit |

## How It Works

1. **Input Discovery:** The tool scans the provided path for common image formats (`.jpg`, `.png`, `.webp`, etc.).
2. **Interactive Viewport:** It creates a normalized window that handles high-resolution images by scaling them to fit your screen initially.
3. **Stamp Logic:** When you click, the tool calculates the bounding box of the crop based on the requested `--size`, ensuring it stays within the image boundaries even if you click near the edges.
4. **Saving:**
   - Individual crop images are saved as `.png` files in the `output_crops/` directory.
   - A `crops.json` (or specified output) file is updated with the coordinates (`x, y, w, h`) and IDs for every crop made across the session.


## Requirements

- Python 3.x
- OpenCV (`opencv-python`)
- NumPy
