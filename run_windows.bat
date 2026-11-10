@echo off
title ClearMark Studio - PDF Watermark Remover

cd /d "%~dp0"

echo ==================================================
echo   Starting ClearMark Studio for Windows...
echo ==================================================
echo.

:: 1. Auto-update codebase if Git is installed
where git >nul 2>&1
if not errorlevel 1 (
    if exist ".git" (
        echo [INFO] Checking for updates from GitHub...
        git pull origin main --quiet
        echo [OK] Codebase is up to date!
        echo.
    )
)

:: 2. Find Python executable
set "PY_CMD="

:: Check standard python in PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto PYTHON_READY
)

:: Check py launcher
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto PYTHON_READY
)

:: Check common local appdata installation paths
for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%I\python.exe" (
        set "PY_CMD=%%I\python.exe"
        goto PYTHON_READY
    )
)

:: Python not found - Automatic installation
echo [WARN] Python is not installed or not in PATH!
echo [INFO] Attempting to install Python 3 automatically...
echo.

:: Try Windows Package Manager (winget)
where winget >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Installing Python via winget (Windows Package Manager)...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
        goto PYTHON_READY
    )
    for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%I\python.exe" (
            set "PY_CMD=%%I\python.exe"
            goto PYTHON_READY
        )
    )
)

:: Fallback: Download official installer using PowerShell
echo [INFO] Downloading official Python installer via PowerShell...
set "TEMP_PY_INSTALLER=%TEMP%\python_setup_311.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%TEMP%\python_setup_311.exe')"

if exist "%TEMP%\python_setup_311.exe" (
    echo [INFO] Installing Python 3.11 silently and setting PATH...
    start /wait "" "%TEMP%\python_setup_311.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
    del /f /q "%TEMP%\python_setup_311.exe" >nul 2>&1
    
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
        goto PYTHON_READY
    )
    for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%I\python.exe" (
            set "PY_CMD=%%I\python.exe"
            goto PYTHON_READY
        )
    )
)

echo.
echo ==================================================
echo [ERROR] Python could not be installed automatically.
echo Please download and install Python manually from:
echo   https://www.python.org/downloads/
echo (Important: Check mark 'Add Python to PATH' during install)
echo ==================================================
echo.
pause
exit /b 1

:PYTHON_READY
echo [OK] Using Python: %PY_CMD%
echo.

:: 3. Check and install dependencies
echo [INFO] Checking required packages...
%PY_CMD% -c "import fitz, PIL, pypdf, webview" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Required packages not found. Installing from requirements.txt...
    %PY_CMD% -m pip install --upgrade pip >nul 2>&1
    %PY_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ==================================================
        echo [ERROR] Failed to install packages via pip.
        echo Please ensure you have an active internet connection.
        echo ==================================================
        echo.
        pause
        exit /b 1
    )
    echo [OK] Packages installed successfully!
    echo.
) else (
    echo [OK] All dependencies are ready.
    echo.
)

:: 4. Run Application
echo [OK] Launching ClearMark Studio...
echo.
%PY_CMD% app.py

echo.
echo ==================================================
echo Program has finished.
echo ==================================================
pause
