import sys
import os
import io
import time
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

def _is_promo_page(page, p0_data=None):
    """Detects promotional cover/advertisement pages accurately."""
    res = page.get('/Resources')
    xo_map = {}
    if res:
        res_obj = res.get_object()
        if '/XObject' in res_obj:
            xo_map = res_obj['/XObject'].get_object()
            
    text = (page.extract_text() or '').strip()
    promo_kws = ['pdfnexus', 'telegram', 'academic to admission', 'মেটিরিয়াল', 'মেটিরিয়াল', 'সমাহার']
    has_promo_kw = any(kw in text.lower() for kw in promo_kws)
    
    # Check if contents match initial promo page
    if p0_data:
        contents = page.get('/Contents')
        if contents and _get_stream_data(contents) == p0_data:
            return True
            
    # Page with promo keywords but without main content scan
    if '/X1' not in xo_map and has_promo_kw:
        return True
        
    return False

def preview_page(input_path, page_num=0, options=None):
    """Generates before & after image preview for Studio Web UI."""
    doc = fitz.open(input_path)
    page_orig = doc[page_num]
    pix_orig = page_orig.get_pixmap(dpi=120)
    orig_img = Image.frombytes("RGB", [pix_orig.width, pix_orig.height], pix_orig.samples)
    doc.close()
    
    reader = pypdf.PdfReader(input_path)
    page = reader.pages[page_num]
    
    # Find and blank watermark forms
    res = page.get('/Resources')
    watermark_forms = set()
    if res:
        res_obj = res.get_object()
        if '/XObject' in res_obj:
            xo_map = res_obj['/XObject'].get_object()
            for xname, xval in xo_map.items():
                xobj = xval.get_object()
                if xobj.get('/Subtype') == '/Form':
                    fdata = xobj.get_data() if hasattr(xobj, 'get_data') else b''
                    fdata_lower = fdata.lower()
                    if any(w in fdata_lower for w in [b'telegram', b'pdfnexus', b't.me', b'joining link']):
                        watermark_forms.add(xname)
                        watermark_forms.add(xname.lstrip('/'))
                        xobj.set_data(b'')
                        
    # Blank watermark references in /Contents stream
    contents = page.get('/Contents')
    if contents:
        c_obj = contents.get_object() if hasattr(contents, 'get_object') else contents
        if isinstance(c_obj, (list, pypdf.generic.ArrayObject)):
            for item in c_obj:
                sub_obj = item.get_object() if hasattr(item, 'get_object') else item
                if hasattr(sub_obj, 'get_data'):
                    sub_data = sub_obj.get_data()
                    sub_lower = sub_data.lower()
                    should_blank = any(w in sub_lower for w in [b'telegram', b'pdfnexus', b't.me'])
                    if not should_blank:
                        for fk in watermark_forms:
                            if f'/{fk}'.encode('latin1') in sub_data:
                                should_blank = True
                                break
                    if should_blank:
                        sub_obj.set_data(b'')
        elif hasattr(c_obj, 'set_data'):
            sub_data = c_obj.get_data()
            if any(w in sub_data.lower() for w in [b'telegram', b'pdfnexus', b't.me']):
                c_obj.set_data(b'')
                
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
    
    # First pass: collect all watermark Form XObject names across the document
    for page in reader.pages:
        res = page.get('/Resources')
        if not res:
            continue
        res_obj = res.get_object()
        if '/XObject' not in res_obj:
            continue
        xo_map = res_obj['/XObject'].get_object()
        for xname, xval in xo_map.items():
            xobj = xval.get_object()
            if xobj.get('/Subtype') == '/Form':
                fdata = xobj.get_data() if hasattr(xobj, 'get_data') else b''
                fdata_lower = fdata.lower()
                if any(w in fdata_lower for w in [b'telegram', b'pdfnexus', b't.me', b'joining link']):
                    watermark_forms.add(xname)
                    watermark_forms.add(xname.lstrip('/'))
                    xobj.set_data(b'')
                    
    # Second pass: process and filter pages
    for i in range(total_pages):
        page = reader.pages[i]
        contents = page.get('/Contents')
        
        if progress_callback:
            progress_callback(i + 1, total_pages, f"Purifying page {i + 1}/{total_pages}")
            
        # 1. Check if page is promotional
        if _is_promo_page(page, p0_data if p0_is_promo else None):
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
                    sub_lower = sub_data.lower()
                    should_blank = any(w in sub_lower for w in [b'telegram', b'pdfnexus', b't.me'])
                    if not should_blank:
                        for fk in watermark_forms:
                            if f'/{fk}'.encode('latin1') in sub_data:
                                should_blank = True
                                break
                    if should_blank:
                        sub_obj.set_data(b"")
                        page_cleaned = True
        elif hasattr(c_obj, "get_data"):
            sub_data = c_obj.get_data()
            sub_lower = sub_data.lower()
            if any(w in sub_lower for w in [b'telegram', b'pdfnexus', b't.me']):
                c_obj.set_data(b"")
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
