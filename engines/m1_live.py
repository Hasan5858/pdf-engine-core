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

def apply_image_clean(img: Image.Image, opts: dict) -> Image.Image:
    """
    High-speed vectorized NumPy implementation matching ClearMark Studio M1.
    """
    img = img.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape

    bg_whiten = opts.get("bg_whiten", 165)
    text_darken = opts.get("text_darken", 82)
    tol = opts.get("tolerance", 28)
    target_hex = opts.get("target_color", "#ec4899")
    tr, tg, tb = hex_to_rgb(target_hex)

    clean_pink = opts.get("clean_pink", True)
    clean_yellow = opts.get("clean_yellow", True)
    clean_grey = opts.get("clean_grey", True)
    preserve_color = opts.get("preserve_color", True)

    # Margins
    m_top = int(h * (opts.get("margin_top", 4.6) / 100.0))
    raw_btm = opts.get("margin_bottom", 91.5)
    if raw_btm < 50.0:
        raw_btm = 100.0 - raw_btm
    m_bottom = int(h * (raw_btm / 100.0))
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

    if clean_yellow:
        yellow_cond = (r > 160) & (g > 155) & (b < 145) & (br > 70)
        remove_mask |= yellow_cond

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
        crisp_text_mask = darken_mask & (~is_colored)
        region[crisp_text_mask] = np.minimum(region[crisp_text_mask], 10)

    arr[m_top:m_bottom, m_left:m_right] = np.clip(region, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def preview_page(input_path, page_num=0, options=None):
    if options is None:
        options = {}

    cache_key = (input_path, page_num)
    if cache_key not in PAGE_CACHE:
        doc = fitz.open(input_path)
        page = doc[page_num]
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

def is_promotional_page(page, p0_sig=None, pno=0):
    if pno == 0:
        return False

    # Check 1: Matching Page 1 cover signature
    if p0_sig:
        p_pix = page.get_pixmap(dpi=36)
        if bytes(p_pix.samples) == p0_sig:
            return True

    # Check 2: Two large promo links covering the page (e.g. t.me/admission_stuffs + t.me/HSCStuffs)
    links = page.get_links()
    if len(links) >= 2:
        large_promo_links = 0
        for l in links:
            uri = l.get('uri', '').lower()
            rect = l.get('from')
            if ('t.me' in uri or 'facebook' in uri or 'admission' in uri or 'hsc' in uri) and rect and rect.height > 120:
                large_promo_links += 1
        if large_promo_links >= 2:
            return True

    return False

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

    # 1. Fingerprint first page (promotional cover) at low resolution for lightning-fast matching
    p0_sig = None
    if delete_promo and total_pages > 1:
        p0_pix = src_doc[0].get_pixmap(dpi=36)
        p0_sig = bytes(p0_pix.samples)

    promo_removed = []
    processed_count = 0

    for i in range(total_pages):
        if progress_callback:
            progress_callback(i + 1, total_pages, f"Checking & cleaning page {i + 1}/{total_pages}...")

        src_page = src_doc[i]
        page_rect = src_page.rect

        # Check if page is an identical promotional ad duplicate or multi-link promo poster
        if delete_promo and is_promotional_page(src_page, p0_sig, i):
            promo_removed.append(i + 1)
            continue

        # Skip if page scope is set and page is not included
        if target_pages_set is not None and i not in target_pages_set:
            out_page = out_doc.new_page(width=page_rect.width, height=page_rect.height)
            out_page.show_pdf_page(out_page.rect, src_doc, i)
            continue

        # Render source page at high print quality (150 DPI)
        pix = src_page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        cleaned_img = apply_image_clean(img, options)

        # Compress to high-quality JPEG
        buf = io.BytesIO()
        cleaned_img.save(buf, format="JPEG", quality=88, optimize=True)
        img_bytes = buf.getvalue()

        # Create output page and insert pristine cleaned scan
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
