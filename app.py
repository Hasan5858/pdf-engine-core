import os
import sys
import json
import base64
import threading
import webbrowser
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Add directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.registry import get_available_engines
from core.updater import check_and_apply_updates

PORT = 7860
ACTIVE_PDF_PATH = None
TOTAL_PAGES = 0

class AppRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean_path = urllib.parse.urlparse(path).path
        if clean_path.startswith("/static/"):
            return os.path.join(BASE_DIR, clean_path.lstrip("/"))
        return super().translate_path(path)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            template_path = os.path.join(BASE_DIR, "templates", "index.html")
            with open(template_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if url.path == "/api/status":
            engines = get_available_engines()
            res = {
                "engines": [
                    {"id": k, "name": v["name"], "description": v["description"]}
                    for k, v in engines.items()
                ],
                "active_pdf": os.path.basename(ACTIVE_PDF_PATH) if ACTIVE_PDF_PATH else None,
                "total_pages": TOTAL_PAGES
            }
            self._send_json(res)
            return

        if url.path == "/api/check_update":
            update_res = check_and_apply_updates()
            self._send_json(update_res)
            return

        return super().do_GET()

    def do_POST(self):
        global ACTIVE_PDF_PATH, TOTAL_PAGES
        url = urllib.parse.urlparse(self.path)

        if url.path == "/api/upload":
            content_type = self.headers.get('Content-Type', '')
            if 'boundary=' not in content_type:
                self._send_json({"error": "Missing multipart boundary"}, status=400)
                return

            boundary = content_type.split("boundary=")[1].strip()
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]
            boundary_bytes = ('--' + boundary).encode('latin-1')

            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)

            # Fast binary parsing of multipart form-data (Python 3.13/3.14 compatible)
            parts = body.split(boundary_bytes)
            uploaded_filename = "document.pdf"
            file_data = None

            for part in parts:
                if b'Content-Disposition:' in part and b'filename=' in part:
                    header_part, content = part.split(b'\r\n\r\n', 1)
                    content = content.rstrip(b'\r\n')
                    
                    # Extract filename
                    for line in header_part.split(b'\r\n'):
                        if b'filename=' in line:
                            fn_str = line.decode('utf-8', errors='ignore')
                            if 'filename="' in fn_str:
                                uploaded_filename = fn_str.split('filename="')[1].split('"')[0]
                            break
                    file_data = content
                    break

            if not file_data:
                self._send_json({"error": "No file content received"}, status=400)
                return

            tmp_dir = os.path.join(BASE_DIR, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            target_path = os.path.join(tmp_dir, os.path.basename(uploaded_filename))

            with open(target_path, "wb") as f_out:
                f_out.write(file_data)

            ACTIVE_PDF_PATH = target_path
            import fitz
            doc = fitz.open(ACTIVE_PDF_PATH)
            TOTAL_PAGES = len(doc)
            doc.close()

            self._send_json({
                "success": True,
                "filename": uploaded_filename,
                "pages": TOTAL_PAGES
            })
            return

        if url.path == "/api/preview":
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            page_num = data.get("page", 0)
            options = data.get("options", {})

            if not ACTIVE_PDF_PATH or not os.path.exists(ACTIVE_PDF_PATH):
                self._send_json({"error": "No PDF loaded"}, status=400)
                return

            from engines.m1_live import preview_page
            orig_bytes, clean_bytes = preview_page(ACTIVE_PDF_PATH, page_num, options)

            self._send_json({
                "orig": "data:image/jpeg;base64," + base64.b64encode(orig_bytes).decode('ascii'),
                "clean": "data:image/jpeg;base64," + base64.b64encode(clean_bytes).decode('ascii')
            })
            return

        if url.path == "/api/process":
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            engine_id = data.get("engine", "m1_live")
            options = data.get("options", {})

            if not ACTIVE_PDF_PATH or not os.path.exists(ACTIVE_PDF_PATH):
                self._send_json({"error": "No PDF loaded"}, status=400)
                return

            engines = get_available_engines()
            if engine_id not in engines:
                self._send_json({"error": f"Engine {engine_id} not found"}, status=400)
                return

            engine = engines[engine_id]["module"]
            base, ext = os.path.splitext(ACTIVE_PDF_PATH)
            out_path = f"{base}_cleaned{ext}"

            result = engine.process(ACTIVE_PDF_PATH, out_path, options)
            result["download_url"] = f"/api/download?path={urllib.parse.quote(out_path)}"
            self._send_json(result)
            return

        self.send_error(404)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

def run_server():
    server = HTTPServer(('127.0.0.1', PORT), AppRequestHandler)
    print(f"==================================================")
    print(f" PDF Cleaner Studio — Engine Running")
    print(f" Open in Browser: http://127.0.0.1:{PORT}")
    print(f"==================================================")
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1)
    
    # Auto-open browser
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down studio engine.")
