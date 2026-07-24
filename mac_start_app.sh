#!/bin/bash
echo "Starting Attendance System..."

# Ensure required directories exist
mkdir -p data photos uploads reports static

# Start FastAPI server in background
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8500 &
SERVER_PID=$!

# Wait 2 seconds for server startup, then open default browser
sleep 2
open http://localhost:8500

echo ""
echo "========================================================"
echo "App is running! Keep this terminal open while in use."
echo "To stop the app, press Ctrl+C or run ./stop_app.sh"
echo "========================================================"

wait $SERVER_PID