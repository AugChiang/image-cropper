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

### Controls

| Key | Action |
| :--- | :--- |
| **Mouse Wheel** | Zoom in/out |
| **Left Click** | Place a crop stamp |
| **Scrollbars** | Drag to pan when zoomed in |
| **`Z`** | Undo the last crop on the current image |
| **`R`** | Reset all crops on the current image |
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
