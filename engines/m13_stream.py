import sys
import os
import io
import re
import time
import hashlib
import pypdf
import fitz
from PIL import Image

NAME = "Profile 13 — Dual Stream Red Watermark & Promo Purge"
DESCRIPTION = "Removes full-page promotional covers and cleans red Telegram/URL watermark streams losslessly."

def _get_stream_data(contents):
    """Safely extracts combined stream bytes whether contents is a single stream or an ArrayObject."""
    if not contents:
        return b""
    c_obj = contents.get_object() if hasattr(contents, "get_object") else contents
    if hasattr(c_obj, "get_data"):
        return c_obj.get_data()
    if isinstance(c_obj, (list, pypdf.generic.ArrayObject)):
        combined = []
        for item in c_obj:
            sub_obj = item.get_object() if hasattr(item, "get_object") else item
            if hasattr(sub_obj, "get_data"):
                combined.append(sub_obj.get_data())
        return b"\n".join(combined)
    return b""

def _is_promo_page(page, p0_data=None, shared_image_hashes=None):
    """Detects promotional cover/advertisement pages accurately."""
    res = page.get('/Resources')
    xo_map = {}
    if res:
        res_obj = res.get_object()
        if '/XObject' in res_obj:
            xo_map = res_obj['/XObject'].get_object()
            
    text = (page.extract_text() or '').strip()
    promo_kws = ['pdfnexus', 'telegram', 'academic to admission', 'মেটিরিয়াল', 'মেটিরিয়াল', 'সমাহার']
    has_promo_kw = any(kw in text.lower() for kw in promo_kws)
    
    # Check if contents match initial promo page
    if p0_data:
        contents = page.get('/Contents')
        if contents and _get_stream_data(contents) == p0_data:
            return True
            
    # Page with promo keywords but without main content scan
    if '/X1' not in xo_map and has_promo_kw:
        return True
        
    # Full-page graphic repeated across multiple pages (same image data
    # drawn as the page's only Do on 2+ pages) - distributor promo sheet.
    if shared_image_hashes:
        data = _get_stream_data(page.get('/Contents'))
        if data:
            drawn = _referenced_xnames(data)
            if len(drawn) == 1:
                for n in drawn:
                    xval = xo_map.get("/" + n)
                    if not xval:
                        continue
                    xobj = xval.get_object()
                    if xobj.get('/Subtype') != '/Image':
                        continue
                    h = hashlib.sha1(xobj.get_data()).hexdigest()
                    if h in shared_image_hashes:
                        return True
    return False

def _referenced_xnames(sub_data):
    """Exact names of all XObjects drawn in this stream (e.g. /Im1 Do -> 'Im1')."""
    return {n.decode("latin1") for n in re.findall(rb"/([A-Za-z][A-Za-z0-9_+\-.]*)\s+Do", sub_data)}

def _clean_stream_data(sub_data, watermark_forms):
    """
    Surgically removes watermark draw commands from a content stream,
    preserving all other content (main scans, text). Never blanks a whole
    stream that also draws main content."""
    sub_lower = sub_data.lower()
    has_kw = any(w in sub_lower for w in [b"telegram", b"pdfnexus", b"t.me", b"joining link"])
    hit_forms = _referenced_xnames(sub_data) & set(watermark_forms)

    if not (has_kw or hit_forms):
        return sub_data, False

    cleaned = sub_data
    if has_kw:
        cleaned = re.sub(
            rb"BT[\s\S]*?ET",
            lambda m: b"" if any(w in m.group(0).lower() for w in [b"telegram", b"pdfnexus", b"t.me", b"joining link"]) else m.group(0),
            cleaned
        )
    for fk in sorted(hit_forms):
        tok = re.escape(fk.encode("latin1"))
        # If the watermark Do has its own q...Q wrapper that draws nothing
        # else, remove the whole wrapper block; otherwise remove the Do token.
        cleaned, n_block = re.subn(rb"q(?:(?!q)[\s\S])*?/" + tok + rb"\s+Do\s*Q", b"", cleaned)
        if not n_block:
            cleaned, _ = re.subn(rb"/" + tok + rb"\s+Do", b"", cleaned)
    return cleaned, cleaned != sub_data

def preview_page(input_path, page_num=0, options=None):
    """Generates before & after image preview for Studio Web UI."""
    doc = fitz.open(input_path)
    page_orig = doc[page_num]
    pix_orig = page_orig.get_pixmap(dpi=120)
    orig_img = Image.frombytes("RGB", [pix_orig.width, pix_orig.height], pix_orig.samples)
    doc.close()
    
    reader = pypdf.PdfReader(input_path)
    page = reader.pages[page_num]
    
    # Find and blank watermark forms / watermark images
    res = page.get('/Resources')
    watermark_forms = set()
    if res:
        res_obj = res.get_object()
        if '/XObject' in res_obj:
            xo_map = res_obj['/XObject'].get_object()
            for xname, xval in xo_map.items():
                xobj = xval.get_object()
                subtype = xobj.get('/Subtype')
                if subtype == '/Form':
                    fdata = xobj.get_data() if hasattr(xobj, 'get_data') else b''
                    fdata_lower = fdata.lower()
                    if any(w in fdata_lower for w in [b'telegram', b'pdfnexus', b't.me', b'joining link']):
                        watermark_forms.add(xname.lstrip('/'))
                        xobj.set_data(b'')
                elif subtype == '/Image':
                    if (xobj.get('/Width') == 720 and xobj.get('/Height') == 720) or (xname.startswith('/Xi') and xname != '/X1'):
                        watermark_forms.add(xname.lstrip('/'))
                        
    # Blank/Clean watermark references in /Contents stream
    contents = page.get('/Contents')
    if contents:
        c_obj = contents.get_object() if hasattr(contents, 'get_object') else contents
        if isinstance(c_obj, (list, pypdf.generic.ArrayObject)):
            for item in c_obj:
                sub_obj = item.get_object() if hasattr(item, 'get_object') else item
                if hasattr(sub_obj, 'get_data'):
                    sub_data = sub_obj.get_data()
                    cleaned_data, changed = _clean_stream_data(sub_data, watermark_forms)
                    if changed:
                        sub_obj.set_data(cleaned_data)
        elif hasattr(c_obj, 'get_data'):
            sub_data = c_obj.get_data()
            cleaned_data, changed = _clean_stream_data(sub_data, watermark_forms)
            if changed:
                c_obj.set_data(cleaned_data)
                
    writer = pypdf.PdfWriter()
    writer.add_page(page)
    bio = io.BytesIO()
    writer.write(bio)
    bio.seek(0)
    
    doc_c = fitz.open(stream=bio.getvalue(), filetype='pdf')
    pix_c = doc_c[0].get_pixmap(dpi=120)
    clean_img = Image.frombytes("RGB", [pix_c.width, pix_c.height], pix_c.samples)
    doc_c.close()
    
    buf_orig = io.BytesIO()
    orig_img.save(buf_orig, format="JPEG", quality=75)
    buf_clean = io.BytesIO()
    clean_img.save(buf_clean, format="JPEG", quality=75)
    return buf_orig.getvalue(), buf_clean.getvalue()

def process(input_path, output_path=None, options=None, progress_callback=None):
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base} [cleaned]{ext}"
        
    t0 = time.time()
    reader = pypdf.PdfReader(input_path)
    writer = pypdf.PdfWriter()
    
    total_pages = len(reader.pages)
    
    # Signature of promotional page from page 1 (index 0) if promo
    p0_contents = reader.pages[0].get('/Contents')
    p0_data = _get_stream_data(p0_contents)
    p0_is_promo = _is_promo_page(reader.pages[0])
    
    promo_removed = []
    cleaned_count = 0
    watermark_forms = set()
    
    # First pass: collect all watermark Form XObject & Image names across the document
    image_hash_users = {}
    for i, page in enumerate(reader.pages):
        res = page.get('/Resources')
        if not res:
            continue
        res_obj = res.get_object()
        if '/XObject' not in res_obj:
            continue
        xo_map = res_obj['/XObject'].get_object()
        for xname, xval in xo_map.items():
            xobj = xval.get_object()
            subtype = xobj.get('/Subtype')
            if subtype == '/Form':
                fdata = xobj.get_data() if hasattr(xobj, 'get_data') else b''
                fdata_lower = fdata.lower()
                if any(w in fdata_lower for w in [b'telegram', b'pdfnexus', b't.me', b'joining link']):
                    watermark_forms.add(xname.lstrip('/'))
                    xobj.set_data(b'')
            elif subtype == '/Image':
                if (xobj.get('/Width') == 720 and xobj.get('/Height') == 720) or (xname.startswith('/Xi') and xname != '/X1'):
                    watermark_forms.add(xname.lstrip('/'))
                idata = xobj.get_data() if hasattr(xobj, 'get_data') else b''
                h = hashlib.sha1(idata).hexdigest()
                image_hash_users.setdefault(h, set()).add(i)
                
    # Image data drawn on 2+ pages = repeated graphic (promo sheet / shared strip)
    shared_image_hashes = {h for h, pgs in image_hash_users.items() if len(pgs) >= 2}
    
    # Second pass: process and filter pages
    for i in range(total_pages):
        page = reader.pages[i]
        contents = page.get('/Contents')
        
        if progress_callback:
            progress_callback(i + 1, total_pages, f"Purifying page {i + 1}/{total_pages}")
            
        # 1. Check if page is promotional
        if _is_promo_page(page, p0_data if p0_is_promo else None, shared_image_hashes):
            promo_removed.append(i + 1)
            continue
            
        if not contents:
            writer.add_page(page)
            continue
            
        # 2. Check and clean /Contents stream
        page_cleaned = False
        c_obj = contents.get_object() if hasattr(contents, "get_object") else contents
        
        if isinstance(c_obj, (list, pypdf.generic.ArrayObject)):
            for item in c_obj:
                sub_obj = item.get_object() if hasattr(item, "get_object") else item
                if hasattr(sub_obj, "get_data"):
                    sub_data = sub_obj.get_data()
                    cleaned_data, changed = _clean_stream_data(sub_data, watermark_forms)
                    if changed:
                        sub_obj.set_data(cleaned_data)
                        page_cleaned = True
        elif hasattr(c_obj, "get_data"):
            sub_data = c_obj.get_data()
            cleaned_data, changed = _clean_stream_data(sub_data, watermark_forms)
            if changed:
                c_obj.set_data(cleaned_data)
                page_cleaned = True
                
        if page_cleaned:
            cleaned_count += 1
            
        writer.add_page(page)
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
        
    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "total_pages": total_pages,
        "cleaned_pages": cleaned_count,
        "promo_pages_removed": promo_removed,
        "output_path": output_path,
        "elapsed": f"{elapsed}s"
    }
