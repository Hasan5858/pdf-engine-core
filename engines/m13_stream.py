import sys
import os
import time
import pypdf

NAME = "Profile 13 — Dual Stream Red Watermark & Promo Purge"
DESCRIPTION = "Removes full-page promotional covers and cleans red Telegram/URL watermark streams losslessly."

def process(input_path, output_path=None, options=None):
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base} (Cleaned){ext}"
        
    t0 = time.time()
    reader = pypdf.PdfReader(input_path)
    writer = pypdf.PdfWriter()
    
    total_pages = len(reader.pages)
    
    # Signature of promotional page from page 1 (index 0)
    p0_contents = reader.pages[0].get('/Contents')
    p0_data = p0_contents.get_object().get_data() if p0_contents else None
    
    clean_stream_data = (
        b"q\n"
        b"1 0 0 1 0 24.33334 cm\n"
        b"595 0 0 793.33331 0 0 cm\n"
        b"/X1 Do\n"
        b"Q\n"
    )
    
    promo_removed = []
    cleaned_count = 0
    
    for i in range(total_pages):
        page = reader.pages[i]
        contents = page.get('/Contents')
        if not contents:
            writer.add_page(page)
            continue
            
        c_obj = contents.get_object()
        data = c_obj.get_data()
        
        # 1. Check if it's the promotional duplicate page
        if i > 0 and p0_data and data == p0_data:
            promo_removed.append(i + 1)
            continue
            
        # 2. Check if page contains red watermark text stream
        if b"Telegram : @PDFNexus" in data or b"https://t.me/PDFNexus" in data or b"/F1 18 Tf" in data:
            c_obj.set_data(clean_stream_data)
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m13_stream.py <input.pdf> [output.pdf]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    res = process(inp, out)
    print(res)
