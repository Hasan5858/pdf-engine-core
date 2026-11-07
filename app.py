import os
import sys
import json
import base64
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import tempfile
import cgi

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
        # Serve static assets
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
            content_type = self.headers.get('Content-Type')
            if not content_type or not content_type.startswith('multipart/form-data'):
                self._send_json({"error": "Expected multipart/form-data"}, status=400)
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type}
            )

            file_item = form['file']
            if file_item.file:
                tmp_dir = os.path.join(BASE_DIR, "tmp")
                os.makedirs(tmp_dir, exist_ok=True)
                target_path = os.path.join(tmp_dir, file_item.filename)
                with open(target_path, "wb") as f_out:
                    f_out.write(file_item.file.read())
                
                ACTIVE_PDF_PATH = target_path
                import fitz
                doc = fitz.open(ACTIVE_PDF_PATH)
                TOTAL_PAGES = len(doc)
                doc.close()

                self._send_json({
                    "success": True,
                    "filename": file_item.filename,
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
    print(f" PDF Cleaner Studio — Desktop Engine Running")
    print(f" URL: http://127.0.0.1:{PORT}")
    print(f"==================================================")
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time_wait = 1
    # Check if pywebview is available for desktop app shell
    try:
        import webview
        webview.create_window(
            "ClearMark Studio Desktop",
            f"http://127.0.0.1:{PORT}",
            width=1280,
            height=850,
            resizable=True
        )
        webview.start()
    except ImportError:
        # Fallback to standard browser window seamlessly!
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down studio engine.")
