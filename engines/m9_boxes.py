import sys
import os
import time
import io
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

NAME = "Profile 9 — ACS Deep 2nd-Pass Clean Engine"
DESCRIPTION = "Preserves 100% full-margin layout (0% crop) while erasing dark watermark stamps, grey logos, and enhancing readability."

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (236, 72, 153)

def parse_target_pages(input_str, total_pages):
    if not input_str or not input_str.strip():
        return None
    text = input_str.strip().lower()
    if text in ('all', '*'):
        return None

    pages = set()
    parts = text.split(',')
    for part in parts:
        p_str = part.strip()
        if '-' in p_str:
            bounds = p_str.split('-')
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                start, end = int(bounds[0]), int(bounds[1])
                for p in range(min(start, end), max(start, end) + 1):
                    if 1 <= p <= total_pages:
                        pages.add(p - 1)
        elif p_str.isdigit():
            p = int(p_str)
            if 1 <= p <= total_pages:
                pages.add(p - 1)
    return pages if pages else None

def apply_acs_clean(img: Image.Image, opts: dict) -> Image.Image:
    """
    Dedicated ACS Deep 2nd Pass Engine:
    Zero crop by default, targets pink, coral and stubborn dark grey watermarks (br 78-165).
    """
    img = img.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape

    bg_whiten = opts.get("bg_whiten", 165)
    text_darken = opts.get("text_darken", 80)
    tol = opts.get("tolerance", 0)
    target_hex = opts.get("target_color", "#ec4899")
    tr, tg, tb = hex_to_rgb(target_hex)

    clean_pink = opts.get("clean_pink", True)
    clean_yellow = opts.get("clean_yellow", False)
    clean_grey = opts.get("clean_grey", True)
    preserve_color = opts.get("preserve_color", True)

    # Margins (M9 defaults to 0% crop unless user adjusts sliders)
    m_top = int(h * (opts.get("margin_top", 0.0) / 100.0))
    m_bottom = int(h * (1.0 - (opts.get("margin_bottom", 0.0) / 100.0)))
    m_left = int(w * (opts.get("margin_left", 0.0) / 100.0))
    m_right = int(w * (1.0 - (opts.get("margin_right", 0.0) / 100.0)))

    if m_top > 0:
        arr[:m_top, :, :] = 255
    if m_bottom < h:
        arr[m_bottom:, :, :] = 255
    if m_left > 0:
        arr[:, :m_left, :] = 255
    if m_right < w:
        arr[:, m_right:, :] = 255

    region = arr[m_top:m_bottom, m_left:m_right].astype(np.float32)
    r = region[:, :, 0]
    g = region[:, :, 1]
    b = region[:, :, 2]

    br = (r * 299 + g * 587 + b * 114) / 1000.0
    max_chroma = np.maximum(np.abs(r - g), np.maximum(np.abs(g - b), np.abs(r - b)))
    is_colored = (max_chroma >= 18) if preserve_color else np.zeros_like(br, dtype=bool)

    # Protected text mask: br < 55
    is_dark_text = (br < 55)

    remove_mask = np.zeros_like(br, dtype=bool)

    if tol > 0:
        color_diff = np.maximum(np.abs(r - tr), np.maximum(np.abs(g - tg), np.abs(b - tb)))
        remove_mask |= ((color_diff <= tol) & (br > 65))

    if clean_pink:
        pink_cond1 = (r > 105) & ((r - g) >= 3) & ((r - b) >= 3) & (br > 65)
        pink_cond2 = (r > 130) & (br > 65)
        remove_mask |= (pink_cond1 | pink_cond2)

    if clean_yellow:
        yellow_cond = (r > 160) & (g > 155) & (b < 145) & (br > 70)
        remove_mask |= yellow_cond

    if clean_grey:
        # Stubborn darker grey watermarks on hard pages
        grey_cond = (br >= 78) & (max_chroma <= 28)
        remove_mask |= grey_cond

    if bg_whiten > 0:
        remove_mask |= (br >= bg_whiten)

    # Absolute text protection
    remove_mask &= (~is_dark_text)

    region[remove_mask] = 255

    # Text Darken Boost: br < text_darken
    darken_mask = (br < text_darken) & (~remove_mask)
    if text_darken > 0:
        crisp_text_mask = darken_mask & (~is_colored)
        region[crisp_text_mask] = np.minimum(region[crisp_text_mask], 10)

    arr[m_top:m_bottom, m_left:m_right] = np.clip(region, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def process(input_path, output_path=None, options=None, progress_callback=None):
    if options is None:
        options = {}
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base} (Cleaned){ext}"

    t0 = time.time()
    src_doc = fitz.open(input_path)
    total_pages = len(src_doc)
    out_doc = fitz.open()

    target_pages_set = parse_target_pages(options.get("target_pages", ""), total_pages)
    delete_promo = options.get("delete_promo", False)

    p0_sig = None
    if delete_promo and total_pages > 1:
        p0_pix = src_doc[0].get_pixmap(dpi=36)
        p0_sig = bytes(p0_pix.samples)

    promo_removed = []
    processed_count = 0

    for i in range(total_pages):
        if progress_callback:
            progress_callback(i + 1, total_pages, f"M9 Deep Cleaning page {i + 1}/{total_pages}...")

        src_page = src_doc[i]
        page_rect = src_page.rect

        if delete_promo and p0_sig:
            p_pix = src_page.get_pixmap(dpi=36)
            if bytes(p_pix.samples) == p0_sig:
                promo_removed.append(i + 1)
                continue

        if target_pages_set is not None and i not in target_pages_set:
            out_page = out_doc.new_page(width=page_rect.width, height=page_rect.height)
            out_page.show_pdf_page(out_page.rect, src_doc, i)
            continue

        pix = src_page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        cleaned_img = apply_acs_clean(img, options)

        buf = io.BytesIO()
        cleaned_img.save(buf, format="JPEG", quality=88, optimize=True)
        img_bytes = buf.getvalue()

        out_page = out_doc.new_page(width=page_rect.width, height=page_rect.height)
        out_page.insert_image(out_page.rect, stream=img_bytes)
        processed_count += 1

    out_doc.save(output_path, garbage=3, deflate=True)
    out_doc.close()
    src_doc.close()

    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "total_pages": total_pages,
        "processed_pages": processed_count,
        "promo_pages_removed": promo_removed,
        "output_path": output_path,
        "elapsed": f"{elapsed}s"
    }
