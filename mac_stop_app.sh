#!/bin/bash
echo "Stopping Attendance System on port 8500..."

# Find and kill the process listening on port 8500
lsof -ti:8500 | xargs kill -9 2>/dev/null

echo "Application stopped successfully."