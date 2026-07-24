#!/bin/bash
echo "Starting Attendance System on macOS..."

# 1. Free port 8500 if previously occupied
OLD_PID=$(lsof -t -i:8500)
if [ -n "$OLD_PID" ]; then
    echo "Clearing port 8500 (killing PID $OLD_PID)..."
    kill -9 $OLD_PID 2>/dev/null
fi

# 2. Ensure required directories exist
mkdir -p data photos uploads reports static

# 3. Start FastAPI server in background
echo "Starting backend server..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8500 &
SERVER_PID=$!

# 4. Wait for server to bind to port 8500 (up to 15 seconds)
echo "Waiting for server startup..."
for i in {1..15}; do
    if lsof -i :8500 > /dev/null 2>&1; then
        echo "Server is online!"
        break
    fi
    sleep 1
done

# 5. Open browser
open http://localhost:8500

echo ""
echo "========================================================"
echo "App is running! Keep this terminal open while in use."
echo "To stop the app, press Ctrl+C or run ./mac_stop_app.sh"
echo "========================================================"

wait $SERVER_PID