@echo off
title ClearMark Studio - PDF Watermark Remover
cls

echo ==================================================
echo   Starting ClearMark Studio for Windows...
echo ==================================================
echo.

:: Auto-update codebase from GitHub if Git is available
where git >nul 2>&1
if %errorlevel% equ 0 (
    if exist ".git" (
        echo [INFO] Checking for updates from GitHub...
        git pull origin main --quiet
        echo [OK] Codebase is up to date!
        echo.
    )
)
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3 (check "Add Python to PATH" during install).
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Check and auto-install requirements if missing
python -c "import fitz, PIL, pypdf" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First time setup: Installing required libraries...
    echo This may take a minute...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Check internet connection.
        pause
        exit /b 1
    )
)

:: Run the Studio app
echo [OK] Launching ClearMark Studio...
python app.py

if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
