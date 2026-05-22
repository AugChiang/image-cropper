import cv2
import json
import os
import argparse
import glob
import numpy as np


BAR_T = 20 # Scrollbar thickness
INIT_W, INIT_H = 1280, 720 # Default window size
IMG_FILE_EXTS = ['*.jpg', '*.png', '*.jpeg', '*.webp']

class ImageCropper:
    """
    An interactive tool for cropping images using a fixed-size 'stamp' approach.
    Supports zooming, panning with custom scrollbars, and batch processing.
    """
    def __init__(self, input_path, stamp_size=512, output_dir="output_crops"):
        """
        Initialize the ImageCropper.

        Args:
            input_path (str): Path to an image file or a directory containing images.
            stamp_size (int): The fixed size (width and height) of the cropping stamp.
            output_dir (str): Path to the directory where crops and metadata will be saved.
        """
        self.input_path = input_path
        self.stamp_size = stamp_size
        self.output_dir = output_dir
        self.output_json = os.path.join(output_dir, "crops.json")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
        self.image_list = self._get_image_list(input_path)
        self.all_crops = {}
        if os.path.exists(self.output_json):
            try:
                with open(self.output_json, 'r') as f:
                    self.all_crops = json.load(f)
            except:
                pass

    def _get_image_list(self, path):
        """
        Discovers images from the provided path.

        Args:
            path (str): File or directory path.

        Returns:
            list: Sorted list of discovered image paths.
        """
        if os.path.isfile(path): return [path]
        files = []
        for ext in IMG_FILE_EXTS:
            files.extend(glob.glob(os.path.join(path, ext)))
            files.extend(glob.glob(os.path.join(path, ext.upper())))
        return sorted(list(set(files)))

    def get_crop(self, cx, cy, w, h):
        """
        Calculates the stamp coordinates centered at (cx, cy) and clipped to image borders.

        Args:
            cx (float): Center X in original image coordinates.
            cy (float): Center Y in original image coordinates.
            w (int): Original image width.
            h (int): Original image height.

        Returns:
            tuple: (nx1, ny1, nw, nh) representing the clipped crop rectangle.
        """
        x1, y1 = int(cx - self.stamp_size // 2), int(cy - self.stamp_size // 2)
        nx1, ny1 = max(0, x1), max(0, y1)
        nx2, ny2 = min(w, x1 + self.stamp_size), min(h, y1 + self.stamp_size)
        return nx1, ny1, nx2 - nx1, ny2 - ny1

    def run(self):
        """
        Launch the interactive cropping interface.
        Handles the main event loop, rendering, and file operations.
        """
        if not self.image_list:
            print("No images found.")
            return

        for img_path in self.image_list:
            img = cv2.imread(img_path)
            if img is None: continue
            orig_h, orig_w = img.shape[:2]
            
            # Calculate initial scale to fit the window
            v_scale = min(INIT_W / orig_w, INIT_H / orig_h, 1.0)
            win_w, win_h = int(orig_w * v_scale) + BAR_T, int(orig_h * v_scale) + BAR_T
            
            crops = self.all_crops.get(img_path, [])
            win = f"Cropper - {os.path.basename(img_path)}"
            cv2.namedWindow(win, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win, win_w, win_h)
            
            # Interactive state
            state = {
                'mouse_win': [0, 0], 
                'trigger': False, 
                'zoom': v_scale, 
                'off_x': 0, 
                'off_y': 0, 
                'drag_x': False, 
                'drag_y': False
            }

            def cb(event, x, y, flags, param):
                """OpenCV Mouse Callback to handle navigation and interaction."""
                state['mouse_win'] = [x, y]
                rect = cv2.getWindowImageRect(win)
                vw, vh = rect[2] - BAR_T, rect[3] - BAR_T
                zoom = state['zoom']
                dw, dh = int(orig_w * zoom), int(orig_h * zoom)
                mox, moy = max(0, dw - vw), max(0, dh - vh)

                if event == cv2.EVENT_LBUTTONDOWN:
                    if x > vw: state['drag_y'] = True
                    elif y > vh: state['drag_x'] = True
                    else: state['trigger'] = True
                elif event == cv2.EVENT_LBUTTONUP:
                    state['drag_x'] = state['drag_y'] = False
                elif event == cv2.EVENT_MOUSEMOVE:
                    if state['drag_x'] and mox > 0: state['off_x'] = int((x / vw) * mox)
                    elif state['drag_y'] and moy > 0: state['off_y'] = int((y / vh) * moy)
                elif event == cv2.EVENT_MOUSEWHEEL:
                    if flags > 0: state['zoom'] *= 1.1
                    else: state['zoom'] /= 1.1
                    state['zoom'] = max(0.01, min(state['zoom'], 20.0))
            cv2.setMouseCallback(win, cb)
            
            while True:
                rect = cv2.getWindowImageRect(win)
                if rect is None or rect[2] <= BAR_T:
                    if cv2.waitKey(20) & 0xFF == ord('q'): break
                    continue
                ww, wh = rect[2], rect[3]
                vw, vh = ww - BAR_T, wh - BAR_T
                
                zoom = state['zoom']
                dw, dh = int(orig_w * zoom), int(orig_h * zoom)
                
                # Update scroll offsets based on current zoom and window size
                mox, moy = max(0, dw - vw), max(0, dh - vh)
                state['off_x'] = max(0, min(state['off_x'], mox))
                state['off_y'] = max(0, min(state['off_y'], moy))
                ox, oy = state['off_x'], state['off_y']

                # Create the display viewport
                interp = cv2.INTER_LINEAR if zoom > 1.0 else cv2.INTER_AREA
                fzoom = cv2.resize(img, (dw, dh), interpolation=interp)
                disp = np.zeros((wh, ww, 3), dtype=np.uint8)
                roi = fzoom[oy:min(dh, oy+vh), ox:min(dw, ox+vw)]
                disp[0:roi.shape[0], 0:roi.shape[1]] = roi

                # Draw Custom Scrollbars
                cv2.rectangle(disp, (0, vh), (vw, wh), (50, 50, 50), -1)
                if dw > vw:
                    bw = max(20, int((vw/dw)*vw))
                    bx = int((ox/mox)*(vw-bw)) if mox > 0 else 0
                    cv2.rectangle(disp, (bx, vh+2), (bx+bw, wh-2), (120, 120, 120), -1)
                cv2.rectangle(disp, (vw, 0), (ww, vh), (50, 50, 50), -1)
                if dh > vh:
                    bh = max(20, int((vh/dh)*vh))
                    by = int((oy/moy)*(vh-bh)) if moy > 0 else 0
                    cv2.rectangle(disp, (vw+2, by), (ww-2, by+bh), (120, 120, 120), -1)
                cv2.rectangle(disp, (vw, vh), (ww, wh), (30, 30, 30), -1)

                # Mouse interaction logic
                mx, my = state['mouse_win']
                over_image = False
                if mx < vw and my < vh:
                    # Visualize existing crops
                    for c in crops:
                        vx, vy = int(c['x']*zoom-ox), int(c['y']*zoom-oy)
                        vw_, vh_ = int(c['w']*zoom), int(c['h']*zoom)
                        cv2.rectangle(disp, (vx, vy), (vx+vw_, vy+vh_), (0, 255, 0), 1)
                        cv2.circle(disp, (vx+vw_//2, vy+vh_//2), 2, (0, 255, 0), -1)
                    
                    # Only process clicks/previews if mouse is over the image
                    if mx + ox < dw and my + oy < dh:
                        over_image = True
                        cxo, cyo = (mx+ox)/zoom, (my+oy)/zoom
                        xo, yo, cwo, cho = self.get_crop(cxo, cyo, orig_w, orig_h)
                        
                        # Visualize current stamp
                        vx, vy, vw_, vh_ = int(xo*zoom-ox), int(yo*zoom-oy), int(cwo*zoom), int(cho*zoom)
                        cv2.rectangle(disp, (vx, vy), (vx+vw_, vy+vh_), (0, 255, 0), 2)
                        cv2.line(disp, (mx-15, my), (mx+15, my), (0, 255, 0), 1)
                        cv2.line(disp, (mx, my-15), (mx, my+15), (0, 255, 0), 1)

                # UI Overlay
                txt = f"Zoom: {zoom:.2f}x | Click: Crop | Z: Undo | R: Reset | N: Next"
                cv2.putText(disp, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                cv2.imshow(win, disp)
                k = cv2.waitKey(20) & 0xFF
                
                if k == ord(' ') or state['trigger']:
                    if over_image: 
                        crops.append({'x': int(xo), 'y': int(yo), 'w': int(cwo), 'h': int(cho)})
                    state['trigger'] = False
                elif k == ord('z') and crops: crops.pop() # Undo last crop
                elif k == ord('r'): crops = [] # Reset crops for current image
                elif k == ord('n') or k == 13: # Save crops on move to next
                    base = os.path.splitext(os.path.basename(img_path))[0]
                    for i, c in enumerate(crops):
                        cid = f"{base}_{i:03d}"
                        c['id'] = cid
                        cv2.imwrite(os.path.join(self.output_dir, f"{cid}.png"), img[c['y']:c['y']+c['h'], c['x']:c['x']+c['w']])
                    self.all_crops[img_path] = crops
                    # write to json after each image to ensure progress is saved
                    with open(self.output_json, 'w') as f:
                        json.dump(self.all_crops, f, indent=4)
                    cv2.destroyWindow(win)
                    break
                elif k == 27 or k == ord('q'): # Save current state and exit
                    self.all_crops[img_path] = crops
                    with open(self.output_json, 'w') as f:
                        json.dump(self.all_crops, f, indent=4)
                    cv2.destroyAllWindows()
                    return

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Stamp-based Image Cropper")
    p.add_argument("-i", "--input", default="input", help="Path to image or folder")
    p.add_argument("-o", "--output", default="output_crops", help="Path to output directory")
    p.add_argument("--size", type=int, default=512, help="Fixed stamp size (default: 512x512)")
    args = p.parse_args()
    ImageCropper(args.input, args.size, args.output).run()
