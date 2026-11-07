#!/bin/bash
# Mac One-Click Launch Runner for PDF Cleaner Studio

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo " Starting ClearMark Studio (Mac)..."
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3."
    osascript -e 'display alert "Python 3 Not Found" message "Please install Python 3 to run this application."'
    exit 1
fi

# Run the studio app
python3 app.py
