@echo off
title Construction Attendance System
echo Starting Attendance System...

:: Ensure required directories exist
if not exist "data" mkdir data
if not exist "photos" mkdir photos
if not exist "uploads" mkdir uploads
if not exist "reports" mkdir reports

:: Start FastAPI server
start /B python -m uvicorn app.main:app --host 0.0.0.0 --port 8500

:: Wait 2 seconds for the server to spin up, then open browser
timeout /t 2 /nobreak > nul
start http://localhost:8500

echo.
echo ========================================================
echo App is running! Keep this window open while using the app.
echo To stop the app, run stop_app.bat or close this window.
echo ========================================================
pause
