import sys
import os
import time
import io
import fitz  # PyMuPDF
from PIL import Image

NAME = "Profile 1 — Interactive Dynamic Spectrum Engine"
DESCRIPTION = "Targeted watermark remover based on brightness, color match, tolerance, and adjustable margin boundaries."

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (220, 220, 220)

def apply_image_clean(img: Image.Image, opts: dict) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    pixels = img.load()

    mode = opts.get("mode", "brightness")
    min_br = opts.get("min_brightness", 185)
    max_br = opts.get("max_brightness", 245)
    target_hex = opts.get("target_color", "#d8d8d8")
    target_r, target_g, target_b = hex_to_rgb(target_hex)
    tol = opts.get("tolerance", 40)

    # Margins (0 to 100%)
    m_top = int(h * (opts.get("margin_top", 0) / 100.0))
    m_bottom = int(h * (1.0 - opts.get("margin_bottom", 0) / 100.0))
    m_left = int(w * (opts.get("margin_left", 0) / 100.0))
    m_right = int(w * (1.0 - opts.get("margin_right", 0) / 100.0))

    for y in range(m_top, m_bottom):
        for x in range(m_left, m_right):
            r, g, b = pixels[x, y]

            if mode == "color":
                dist = ((r - target_r)**2 + (g - target_g)**2 + (b - target_b)**2) ** 0.5
                if dist <= tol:
                    pixels[x, y] = (255, 255, 255)
            else:
                br = (r * 299 + g * 587 + b * 114) / 1000
                if min_br <= br <= max_br:
                    pixels[x, y] = (255, 255, 255)

    return img

def preview_page(input_path, page_num=0, options=None):
    if options is None:
        options = {}
    doc = fitz.open(input_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=150)
    orig_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    cleaned_img = apply_image_clean(orig_img.copy(), options)

    buf_orig = io.BytesIO()
    orig_img.save(buf_orig, format="JPEG", quality=85)
    buf_clean = io.BytesIO()
    cleaned_img.save(buf_clean, format="JPEG", quality=85)

    doc.close()
    return buf_orig.getvalue(), buf_clean.getvalue()

def process(input_path, output_path=None, options=None, progress_callback=None):
    if options is None:
        options = {}
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base} (Cleaned){ext}"

    t0 = time.time()
    doc = fitz.open(input_path)
    total_pages = len(doc)
    processed = 0

    for i in range(total_pages):
        if progress_callback:
            progress_callback(i + 1, total_pages, f"Cleaning page {i + 1}/{total_pages}")
            
        page = doc[i]
        image_list = page.get_images(full=True)
        if not image_list:
            continue

        for img_info in image_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            pil_img = Image.open(io.BytesIO(image_bytes))
            cleaned_img = apply_image_clean(pil_img, options)

            out_io = io.BytesIO()
            cleaned_img.save(out_io, format="JPEG", quality=90, optimize=True)
            doc.update_stream(xref, out_io.getvalue())
            processed += 1

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()

    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "total_pages": total_pages,
        "processed_images": processed,
        "output_path": output_path,
        "elapsed": f"{elapsed}s"
    }
