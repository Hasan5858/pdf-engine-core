import sys
import os
import time
import io
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

NAME = "Profile 1 — Interactive Dynamic Spectrum Engine"
DESCRIPTION = "Targeted watermark remover based on brightness, color match, tolerance, and adjustable margin boundaries."

# In-memory page render cache for instantaneous preview response (< 50ms)
PAGE_CACHE = {}

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (236, 72, 153)

def apply_image_clean(img: Image.Image, opts: dict) -> Image.Image:
    """
    High-speed vectorized NumPy implementation matching original ClearMark Studio M1.
    Features:
      - Margins (top, bottom, left, right %)
      - Target color + Tolerance match (only if br > 65)
      - Clean Pink / Telegram watermarks
      - Clean Grey watermarks
      - Whiten Background (bgWhitenBr)
      - Text Darken Boost (textDarkenBr)
      - Preserve Colored Text/Diagrams
      - Dark text absolute protection (br < 55)
    """
    img = img.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape

    # Extract options
    bg_whiten = opts.get("bg_whiten", opts.get("max_brightness", 165))
    text_darken = opts.get("text_darken", opts.get("textDarkenBr", 82))
    tol = opts.get("tolerance", 28)
    target_hex = opts.get("target_color", "#ec4899")
    tr, tg, tb = hex_to_rgb(target_hex)

    clean_pink = opts.get("clean_pink", True)
    clean_grey = opts.get("clean_grey", True)
    preserve_color = opts.get("preserve_color", True)

    # Margins
    m_top = int(h * (opts.get("margin_top", 4.6) / 100.0))
    m_bottom = int(h * (1.0 - (opts.get("margin_bottom", 8.5) / 100.0)))
    m_left = int(w * (opts.get("margin_left", 3.8) / 100.0))
    m_right = int(w * (1.0 - (opts.get("margin_right", 3.8) / 100.0)))

    # Outer margins wipe out to pure white
    if m_top > 0:
        arr[:m_top, :, :] = 255
    if m_bottom < h:
        arr[m_bottom:, :, :] = 255
    if m_left > 0:
        arr[:, :m_left, :] = 255
    if m_right < w:
        arr[:, m_right:, :] = 255

    # Process inside margins
    region = arr[m_top:m_bottom, m_left:m_right].astype(np.float32)
    r = region[:, :, 0]
    g = region[:, :, 1]
    b = region[:, :, 2]

    # Luminance formula: (299*R + 587*G + 114*B) / 1000
    br = (r * 299 + g * 587 + b * 114) / 1000.0

    # Chroma difference
    max_chroma = np.maximum(np.abs(r - g), np.maximum(np.abs(g - b), np.abs(r - b)))
    is_colored = (max_chroma >= 18) if preserve_color else np.zeros_like(br, dtype=bool)

    # Protected text mask: br < 55
    is_dark_text = (br < 55)

    # Watermark removal mask (only candidate if br > 65)
    remove_mask = np.zeros_like(br, dtype=bool)

    if tol > 0:
        color_diff = np.maximum(np.abs(r - tr), np.maximum(np.abs(g - tg), np.abs(b - tb)))
        remove_mask |= ((color_diff <= tol) & (br > 65))

    if clean_pink:
        pink_cond1 = (r > 105) & ((r - g) >= 3) & ((r - b) >= 3) & (br > 65)
        pink_cond2 = (r > 130) & (br > 65)
        remove_mask |= (pink_cond1 | pink_cond2)

    if clean_grey:
        grey_cond = (br >= 78) & (max_chroma <= 28)
        remove_mask |= grey_cond

    if bg_whiten > 0:
        remove_mask |= (br >= bg_whiten)

    # Absolute dark text protection overrides removal
    remove_mask &= (~is_dark_text)

    # Apply removals: set to white (255)
    region[remove_mask] = 255

    # Text Darken Boost: br < text_darken
    darken_mask = (br < text_darken) & (~remove_mask)
    if text_darken > 0:
        # Crisp black for non-colored dark text
        crisp_text_mask = darken_mask & (~is_colored)
        region[crisp_text_mask] = np.minimum(region[crisp_text_mask], 12)

    arr[m_top:m_bottom, m_left:m_right] = np.clip(region, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def preview_page(input_path, page_num=0, options=None):
    """
    Renders preview with aggressive in-memory pixmap caching for ultra-fast slider response (< 40ms).
    """
    if options is None:
        options = {}

    cache_key = (input_path, page_num)
    if cache_key not in PAGE_CACHE:
        doc = fitz.open(input_path)
        page = doc[page_num]
        # Fast 120 DPI rendering for super snappy live preview
        pix = page.get_pixmap(dpi=120)
        PAGE_CACHE[cache_key] = (pix.samples, pix.width, pix.height)
        doc.close()

    samples, width, height = PAGE_CACHE[cache_key]
    orig_img = Image.frombytes("RGB", [width, height], samples)

    cleaned_img = apply_image_clean(orig_img.copy(), options)

    buf_orig = io.BytesIO()
    orig_img.save(buf_orig, format="JPEG", quality=75)

    buf_clean = io.BytesIO()
    cleaned_img.save(buf_clean, format="JPEG", quality=75)

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
        
        if image_list:
            # Document is scanned images
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
        else:
            # Document is vector/text: render page to high-res image and replace
            pix = page.get_pixmap(dpi=200)
            pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            cleaned_img = apply_image_clean(pil_img, options)

            out_io = io.BytesIO()
            cleaned_img.save(out_io, format="JPEG", quality=90, optimize=True)
            page.clean_contents()
            img_rect = page.rect
            page.insert_image(img_rect, stream=out_io.getvalue())
            processed += 1

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()

    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "total_pages": total_pages,
        "processed_pages": processed,
        "output_path": output_path,
        "elapsed": f"{elapsed}s"
    }
