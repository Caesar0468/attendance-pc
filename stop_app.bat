@echo off
title Stopping Attendance System
echo Stopping Attendance System...

:: Find and terminate the process running on port 8500
for /f "tokens=5" %%a in ('netstat -a -n -o ^| findstr :8500') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo Application stopped successfully.
timeout /t 2 >nul
