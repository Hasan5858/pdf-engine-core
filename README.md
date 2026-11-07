# PDF Engine Core & Studio

High-performance modular PDF document processor and spectrum cleaner built with Python & PyMuPDF.

## Features
- **Dynamic Spectrum Profile (M1):** Interactive color match, luminance thresholds, and percentage-based margins with real-time feedback.
- **Deep Structural Box Purge (M9):** Automatic recognition of boxed advertisement stamps and thick border outlines.
- **Dual-Stream Lossless Cleaner (M13):** Signature-based promotional page detector and red text watermark stream purifier.
- **Zero-Friction Engine Loader:** Add new engines into `engines/` and they are auto-detected instantly.
- **Cross-Platform Auto-Sync:** Built-in engine updater that keeps client engines aligned with remote updates without code re-compiles.

## Quickstart

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Launch Studio
```bash
python app.py
```
Open your browser at `http://127.0.0.1:7860`.
