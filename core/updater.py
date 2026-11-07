import os
import urllib.request
import json
import logging

GITHUB_REPO = "Hasan5858/pdf-engine-core"
MANIFEST_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/manifest.json"
BASE_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/engines/"

def check_and_apply_updates():
    """
    Checks remote GitHub manifest for any new or updated engine modules.
    Downloads them directly into the local engines/ directory.
    Non-technical admin gets immediate updates without touching terminal or Git!
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    engines_dir = os.path.join(os.path.dirname(current_dir), "engines")
    
    try:
        req = urllib.request.Request(MANIFEST_URL, headers={'User-Agent': 'PDFEngine-Client/1.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                return {"status": "skipped", "message": "Manifest unavailable"}
            manifest = json.loads(resp.read().decode('utf-8'))

        updated_count = 0
        for item in manifest.get("engines", []):
            filename = item.get("filename")
            remote_url = BASE_RAW_URL + filename
            local_path = os.path.join(engines_dir, filename)

            # Check if file needs download or update
            req_file = urllib.request.Request(remote_url, headers={'User-Agent': 'PDFEngine-Client/1.0'})
            with urllib.request.urlopen(req_file, timeout=5) as file_resp:
                new_code = file_resp.read()

            current_code = b""
            if os.path.exists(local_path):
                with open(local_path, "rb") as cur:
                    current_code = cur.read()

            if current_code != new_code:
                with open(local_path, "wb") as f_out:
                    f_out.write(new_code)
                updated_count += 1

        return {"status": "ok", "updated_engines": updated_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}
