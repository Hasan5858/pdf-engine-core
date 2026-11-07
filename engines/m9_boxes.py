import sys
import os
import time
import io
import fitz  # PyMuPDF
from PIL import Image

NAME = "Profile 9 — Deep Structural Element & Box Eliminator"
DESCRIPTION = "Removes thick bordered promotion stamp boxes, stubborn dark watermarks, and restores pure scan contents."

def _erase_promo_boxes_and_watermarks(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    pixels = img.load()

    # Step 1: Detect horizontal strokes of thick promo box borders
    h_lines = []
    for y in range(40, h - 40, 2):
        run = 0
        start_x = 0
        for x in range(10, w - 10):
            r, g, b = pixels[x, y]
            br = (r * 299 + g * 587 + b * 114) / 1000
            if br < 55:  # Very dark border stroke
                if run == 0:
                    start_x = x
                run += 1
            else:
                if run >= 250:
                    h_lines.append((y, start_x, x, run))
                run = 0

    # Step 2: Group nearby lines into vertical bounding boxes
    boxes = []
    if h_lines:
        min_y = h_lines[0][0]
        max_y = h_lines[0][0]
        min_x = h_lines[0][1]
        max_x = h_lines[0][2]
        
        for y, sx, ex, _ in h_lines[1:]:
            if y - max_y <= 60:
                max_y = y
                min_x = min(min_x, sx)
                max_x = max(max_x, ex)
            else:
                if (max_y - min_y) >= 40 and (max_x - min_x) >= 200:
                    boxes.append((min_x - 5, min_y - 5, max_x + 5, max_y + 5))
                min_y = y
                max_y = y
                min_x = sx
                max_x = ex
        if (max_y - min_y) >= 40 and (max_x - min_x) >= 200:
            boxes.append((min_x - 5, min_y - 5, max_x + 5, max_y + 5))

    # Erase promo box areas
    for bx0, by0, bx1, by1 in boxes:
        bx0 = max(0, bx0)
        by0 = max(0, by0)
        bx1 = min(w, bx1)
        by1 = min(h, by1)
        for y in range(by0, by1):
            for x in range(bx0, bx1):
                pixels[x, y] = (255, 255, 255)

    return img

def process(input_path, output_path=None, options=None, progress_callback=None):
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base} (Cleaned){ext}"

    t0 = time.time()
    doc = fitz.open(input_path)
    total_pages = len(doc)
    cleaned_pages = 0

    for page_idx in range(total_pages):
        if progress_callback:
            progress_callback(page_idx + 1, total_pages, f"Deep cleaning page {page_idx + 1}/{total_pages}")
            
        page = doc[page_idx]
        image_list = page.get_images(full=True)
        
        if not image_list:
            continue

        for img_info in image_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            pil_img = Image.open(io.BytesIO(image_bytes))
            cleaned_img = _erase_promo_boxes_and_watermarks(pil_img)

            out_io = io.BytesIO()
            cleaned_img.save(out_io, format="JPEG", quality=90, optimize=True)
            page.clean_contents()
            doc.update_stream(xref, out_io.getvalue())
            cleaned_pages += 1

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()

    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "total_pages": total_pages,
        "cleaned_pages": cleaned_pages,
        "output_path": output_path,
        "elapsed": f"{elapsed}s"
    }
