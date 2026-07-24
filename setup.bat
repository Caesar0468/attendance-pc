@echo off
title Kshirsagar Group Attendance System - Initial Setup
echo ========================================================
echo Setting up Kshirsagar Group Attendance System...
echo ========================================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH!
    echo Please download and install Python 3.10+ from https://www.python.org/
    echo CRITICAL: Make sure to check the box "Add python.exe to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo.
echo [1/3] Creating local data and storage directories...
if not exist "data" mkdir data
if not exist "photos" mkdir photos
if not exist "uploads" mkdir uploads
if not exist "reports" mkdir reports
if not exist "static" mkdir static

echo.
echo [2/3] Upgrading Python package manager (pip)...
python -m pip install --upgrade pip

echo.
echo [3/3] Installing required system and AI packages...
if exist "requirements.txt" (
    python -m pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not found! Installing core packages directly...
    python -m pip install fastapi uvicorn insightface onnxruntime opencv-python numpy pillow openpyxl qrcode piexif pydantic requests websockets
)

echo.
echo ========================================================
echo Setup completed successfully!
echo You can now double-click 'start_app.bat' to launch the app.
echo ========================================================
pause
