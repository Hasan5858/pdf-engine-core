import sys
import os
import time
import io
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

NAME = "Profile 9 — ACS Deep 2nd-Pass Clean Engine"
DESCRIPTION = "Preserves 100% full-margin layout (0% crop) while erasing dark watermark stamps, Telegram pill badges, and purging promotional ad pages."

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

def erase_pill_watermarks_worker(arr):
    """
    Biometric Telegram Badge Pill Watermark Eraser:
    Matches native JS/WASM erasePillWatermarksWorker logic.
    Protects academic tables from false positives by requiring:
    1. Aspect ratio strictly 4.8 to 6.6
    2. Border outline thickness <= 5px (not solid headers)
    3. Isolated clear margin above & below
    4. Vertical separator bar inside left portion (12%-25% width) not leaking into surrounding rows
    5. Circular icon presence and rounded left border
    6. Right text presence (@AdmissionStuffs / handle)
    """
    h, w, _ = arr.shape
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)
    br = (r * 299 + g * 587 + b * 114) / 1000.0

    minLineLen = round(w * 0.08)
    maxLineLen = round(w * 0.28)
    minDy = round(h * 0.012)
    maxDy = round(h * 0.035)

    hLines = []
    for y in range(int(h * 0.03), int(h * 0.97)):
        run = 0
        startX = 0
        row = br[y, :]
        for x in range(10, w - 10):
            if row[x] < 195:
                if run == 0: startX = x
                run += 1
            else:
                if minLineLen <= run <= maxLineLen:
                    hLines.append({'y': y, 'startX': startX, 'endX': x, 'len': run})
                run = 0
        if minLineLen <= run <= maxLineLen:
            hLines.append({'y': y, 'startX': startX, 'endX': w - 10, 'len': run})

    mergedHLines = []
    for l in hLines:
        merged = False
        for m in mergedHLines:
            if abs(l['y'] - m['y']) <= 4 and abs(l['startX'] - m['startX']) < 30 and abs(l['len'] - m['len']) < 30:
                m['y'] = min(m['y'], l['y'])
                m['startX'] = min(m['startX'], l['startX'])
                m['endX'] = max(m['endX'], l['endX'])
                m['len'] = m['endX'] - m['startX']
                merged = True
                break
        if not merged:
            mergedHLines.append(dict(l))

    pills = []
    for i in range(len(mergedHLines)):
        topL = mergedHLines[i]
        for j in range(i + 1, len(mergedHLines)):
            btmL = mergedHLines[j]
            dy = btmL['y'] - topL['y']
            if dy < minDy or dy > maxDy: continue
            if abs(topL['startX'] - btmL['startX']) > 30: continue
            if abs(topL['len'] - btmL['len']) > 30: continue

            boxX1 = min(topL['startX'], btmL['startX'])
            boxX2 = max(topL['endX'], btmL['endX'])
            boxW = boxX2 - boxX1
            boxH = dy

            aspect = boxW / boxH
            if aspect < 4.8 or aspect > 6.6: continue

            # Outline thinness check
            sampleX = round(boxX1 + boxW * 0.5)
            topThick = 0
            for ty in range(topL['y'], topL['y'] + min(15, int(boxH * 0.4))):
                if br[ty, sampleX] < 150: topThick += 1
            if topThick > 5: continue

            # Isolation check above & below
            startX = round(boxX1 + boxW * 0.20)
            endX = round(boxX1 + boxW * 0.80)
            darkAbove = 0; totalAbove = 0
            for y in range(max(0, topL['y'] - 15), topL['y'] - 2, 2):
                for x in range(startX, endX + 1, 4):
                    totalAbove += 1
                    if br[y, x] < 160: darkAbove += 1
            darkBelow = 0; totalBelow = 0
            for y in range(btmL['y'] + 3, min(h - 1, btmL['y'] + 15), 2):
                for x in range(startX, endX + 1, 4):
                    totalBelow += 1
                    if br[y, x] < 160: darkBelow += 1
            if (darkAbove / (totalAbove or 1)) > 0.35 or (darkBelow / (totalBelow or 1)) > 0.35:
                continue

            # Vertical separator bar inside left section
            minBarX = boxX1 + int(boxW * 0.12)
            maxBarX = boxX1 + int(boxW * 0.25)
            foundBar = False
            barX = 0
            for sx in range(minBarX, maxBarX + 1):
                hits = 0
                for sy in range(topL['y'] + 3, btmL['y'] - 3):
                    if br[sy, sx] < 140: hits += 1
                if hits >= (boxH - 6) * 0.55:
                    barExt = 0
                    for ey in range(max(0, topL['y'] - 8), topL['y'] - 2):
                        if br[ey, sx] < 150: barExt += 1
                    for ey in range(btmL['y'] + 2, min(h, btmL['y'] + 8)):
                        if br[ey, sx] < 150: barExt += 1
                    if barExt <= 3:
                        foundBar = True
                        barX = sx
                        break
            if not foundBar: continue

            iconW = barX - boxX1
            if iconW < 12 or iconW > 35: continue
            circleDark = 0
            for y in range(topL['y'] + 2, btmL['y'] - 2):
                for x in range(boxX1 + 2, barX - 1):
                    if br[y, x] < 150: circleDark += 1
            minDarkIcon = max(25, round(boxH * boxH * 0.08))
            if circleDark < minDarkIcon: continue

            leftBorderHits = 0
            midY = round(topL['y'] + boxH * 0.5)
            for y in range(midY - 3, midY + 4):
                for x in range(boxX1 - 2, boxX1 + 5):
                    if br[y, x] < 160:
                        leftBorderHits += 1
                        break
            if leftBorderHits < 3: continue

            textDark = 0
            for ry in range(topL['y'] + 2, btmL['y'] - 2):
                for rx in range(barX + 3, boxX2 - 2):
                    if br[ry, rx] < 150: textDark += 1
            if textDark < max(30, round((boxX2 - barX) * 0.35)): continue

            pills.append({
                'eraseX1': max(0, boxX1 - 4),
                'eraseX2': min(w - 1, boxX2 + 4),
                'eraseY1': max(0, topL['y'] - 3),
                'eraseY2': min(h - 1, btmL['y'] + 3)
            })

    dedupedPills = []
    for p in pills:
        dup = False
        for dp in dedupedPills:
            if abs(p['eraseX1'] - dp['eraseX1']) < 25 and abs(p['eraseY1'] - dp['eraseY1']) < 25:
                dup = True
                break
        if not dup:
            dedupedPills.append(p)

    for p in dedupedPills:
        arr[p['eraseY1']:p['eraseY2'], p['eraseX1']:p['eraseX2']] = 255
    return len(dedupedPills)

def erase_logo_badges_worker(data, w, h):
    """
    Admission Stuffs Graduation Cap + Dome + Banner Logo Badge Eraser:
    Matches native JS/WASM eraseAdmissionStuffsLogoBadgesWorker logic.
    Requires letter stroke transitions and dome arch check.
    """
    minBW = round(w * 0.080)
    maxBW = round(w * 0.220)
    badges = []

    r = data[:, :, 0].astype(np.float32)
    g = data[:, :, 1].astype(np.float32)
    b = data[:, :, 2].astype(np.float32)
    br = (r * 299 + g * 587 + b * 114) / 1000.0

    for y in range(int(h * 0.05), int(h * 0.90), 2):
        run = 0
        startX = 0
        for x in range(10, w - 10):
            if br[y, x] < 80:
                if run == 0: startX = x
                run += 1
            else:
                if minBW <= run <= maxBW:
                    sideDark = 0
                    for sx in range(max(0, startX - 35), startX - 10, 4):
                        if br[y, sx] < 100: sideDark += 1
                    for sx in range(startX + run + 10, min(w - 1, startX + run + 35), 4):
                        if br[y, sx] < 100: sideDark += 1

                    if sideDark < 6:
                        minDy = round(run * 0.12)
                        maxDy = round(run * 0.24)
                        for dy in range(minDy, maxDy + 1):
                            btmY = y + dy
                            if btmY >= h: break
                            btmRun = 0
                            for bx in range(startX, startX + run, 4):
                                if br[btmY, bx] < 80: btmRun += 1
                            if btmRun > (run / 4) * 0.75:
                                midY = round(y + dy * 0.5)
                                transitions = 0
                                prevIsWhite = False
                                for x2 in range(startX + round(run * 0.05), startX + run - round(run * 0.05)):
                                    isWhite = br[midY, x2] > 160
                                    if isWhite != prevIsWhite:
                                        transitions += 1
                                        prevIsWhite = isWhite
                                if 18 <= transitions <= 34:
                                    domeH = round(run * 0.55)
                                    tlDark = 0; trDark = 0; cornerSamples = 0
                                    for dy2 in range(y - domeH, y - round(domeH * 0.6), 2):
                                        if dy2 >= 0:
                                            for dx2 in range(startX, startX + round(run * 0.2), 2):
                                                cornerSamples += 1
                                                if br[dy2, dx2] < 80: tlDark += 1
                                            for dx2 in range(startX + round(run * 0.8), startX + run, 2):
                                                if br[dy2, dx2] < 80: trDark += 1
                                    cornerRatio = (tlDark + trDark) / (2 * (cornerSamples or 1))

                                    centerDark = 0; centerSamples = 0
                                    for dy2 in range(y - round(domeH * 0.8), y - round(domeH * 0.2), 2):
                                        if dy2 >= 0:
                                            for dx2 in range(startX + round(run * 0.35), startX + round(run * 0.65), 2):
                                                centerSamples += 1
                                                if br[dy2, dx2] < 80: centerDark += 1
                                    centerRatio = centerDark / (centerSamples or 1)

                                    if centerRatio >= 0.35 and cornerRatio <= 0.05:
                                        badges.append({
                                            'eraseX1': max(0, startX - round(run * 0.1)),
                                            'eraseX2': min(w - 1, startX + run + round(run * 0.1)),
                                            'eraseY1': max(0, y - domeH - round(run * 0.08)),
                                            'eraseY2': min(h - 1, btmY + round(run * 0.25))
                                        })
                run = 0

    deduped = []
    for b in badges:
        dup = False
        for db in deduped:
            if abs(b['eraseX1'] - db['eraseX1']) < 30 and abs(b['eraseY1'] - db['eraseY1']) < 30:
                dup = True
                break
        if not dup:
            deduped.append(b)

    for b in deduped:
        data[b['eraseY1']:b['eraseY2'], b['eraseX1']:b['eraseX2']] = 255
    return len(deduped)

def apply_acs_clean(img: Image.Image, opts: dict) -> Image.Image:
    """
    Dedicated ACS Deep 2nd Pass Engine:
    Zero crop by default, targets pills, stamps, pink, coral, yellow, and grey watermarks.
    """
    img = img.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape

    # 1. Structural biometric badges & pill watermarks
    erase_pill_watermarks_worker(arr)
    erase_logo_badges_worker(arr, w, h)

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
    raw_btm = opts.get("margin_bottom", 100.0)
    if raw_btm < 50.0:
        raw_btm = 100.0 - raw_btm
    m_bottom = int(h * (raw_btm / 100.0))
    m_left = int(w * (opts.get("margin_sides", 0.0) / 100.0))
    m_right = int(w * (1.0 - (opts.get("margin_sides", 0.0) / 100.0)))

    # Zero-out margins outside crop bounds
    if m_top > 0: arr[:m_top, :] = 255
    if m_bottom < h: arr[m_bottom:, :] = 255
    if m_left > 0: arr[:, :m_left] = 255
    if m_right < w: arr[:, m_right:] = 255

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
        pink_cond2 = (r > 120) & ((r - np.minimum(g, b)) >= 3) & (br > 70)
        pink_cond3 = (r > 130) & (r * 100 > g * 102) & (r * 100 > b * 102) & (br > 65)
        remove_mask |= (pink_cond1 | pink_cond2 | pink_cond3)

    if clean_yellow:
        yellow_cond = (br >= 135) & (r >= g) & (g >= b) & ((r - b) >= 4) & (max_chroma <= 40)
        remove_mask |= yellow_cond

    if clean_grey:
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

def is_promotional_page(page, p0_sig=None, pno=0):
    """
    Robust multi-feature promotional ad page detector matching original project:
    1. Duplicate cover match against Page 1
    2. Structural link check: 2 giant full-page clickable promo links
    """
    if pno == 0:
        return False

    # Check 1: Matching Page 1 cover signature
    if p0_sig:
        p_pix = page.get_pixmap(dpi=36)
        if bytes(p_pix.samples) == p0_sig:
            return True

    # Check 2: Two large promo links covering the page (t.me/admission_stuffs + t.me/HSCStuffs)
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

    cleaned_img = apply_acs_clean(orig_img.copy(), options)

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
    src_doc = fitz.open(input_path)
    total_pages = len(src_doc)
    out_doc = fitz.open()

    target_pages_set = parse_target_pages(options.get("target_pages", ""), total_pages)
    delete_promo = options.get("delete_promo", False)

    # Fingerprint page 1 for promo matching
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

        # Promo page check
        if delete_promo and is_promotional_page(src_page, p0_sig, i):
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
