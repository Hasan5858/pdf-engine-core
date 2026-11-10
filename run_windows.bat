@echo off
setlocal EnableDelayedExpansion
title ClearMark Studio - PDF Watermark Remover

:: Always run in script's directory (fixes UNC path / working directory issues on Windows 11)
cd /d "%~dp0"

echo ==================================================
echo   Starting ClearMark Studio for Windows...
echo ==================================================
echo.

:: 1. Auto-update codebase if Git is installed
where git >nul 2>&1
if !errorlevel! equ 0 (
    if exist ".git" (
        echo [INFO] Checking for updates from GitHub...
        git pull origin main --quiet
        echo [OK] Codebase is up to date!
        echo.
    )
)

:: 2. Find Python executable (python, py launcher, or winget/custom location)
set "PY_CMD="

:: Check standard python
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

:: Check py launcher
py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :PYTHON_FOUND
)

:: Check LocalAppData python installations (often installed without PATH)
for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%I\python.exe" (
        set "PY_CMD=%%I\python.exe"
        goto :PYTHON_FOUND
    )
)

:: Python is missing - Attempt Auto-Installation
echo [WARN] Python is not detected on your Windows system.
echo [INFO] Attempting to install Python 3 automatically...
echo.

:: Try Windows Package Manager (winget) - Built-in on Windows 10 & 11
where winget >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Installing Python via winget (please wait or approve UAC prompt if shown)...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    
    :: Re-check after winget
    for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%I\python.exe" (
            set "PY_CMD=%%I\python.exe"
            goto :PYTHON_FOUND
        )
    )
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=python"
        goto :PYTHON_FOUND
    )
)

:: Fallback: Download official installer using PowerShell and install silently
echo [INFO] Downloading official Python installer via PowerShell...
set "TEMP_PY_INSTALLER=%TEMP%\python_setup.exe"
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%TEMP_PY_INSTALLER%')"

if exist "%TEMP_PY_INSTALLER%" (
    echo [INFO] Installing Python 3.11 (Silent Mode, adding to PATH)...
    start /wait "" "%TEMP_PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
    del /f /q "%TEMP_PY_INSTALLER%" >nul 2>&1
    
    for /d %%I in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%I\python.exe" (
            set "PY_CMD=%%I\python.exe"
            goto :PYTHON_FOUND
        )
    )
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=python"
        goto :PYTHON_FOUND
    )
)

echo.
echo [ERROR] Automatic Python installation failed.
echo Please manually install Python from: https://www.python.org/downloads/
echo (Make sure to check "Add Python to PATH" during installation)
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [OK] Python detected: !PY_CMD!
echo.

:: 3. Check and install dependencies
echo [INFO] Checking required packages...
!PY_CMD! -c "import fitz, PIL, pypdf, webview" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] Installing / updating required libraries from requirements.txt...
    !PY_CMD! -m pip install --upgrade pip >nul 2>&1
    !PY_CMD! -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies. Please check your internet connection.
        echo.
        pause
        exit /b 1
    )
    echo [OK] All dependencies successfully installed!
    echo.
) else (
    echo [OK] Dependencies are already up to date.
    echo.
)

:: 4. Launch ClearMark Studio
echo [OK] Launching ClearMark Studio...
echo.
!PY_CMD! app.py

if !errorlevel! neq 0 (
    echo.
    echo ==================================================
    echo [ERROR] Application stopped or encountered an error.
    echo ==================================================
    pause
)
