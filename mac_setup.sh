#!/bin/bash
echo "========================================================"
echo "Setting up Kshirsagar Group Attendance System on macOS..."
echo "========================================================"

# Check Python 3 installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found!"
    echo "Please install Python 3 from https://www.python.org/ or via Homebrew (brew install python)"
    exit 1
fi

echo ""
echo "[1/3] Creating runtime directories..."
mkdir -p data photos uploads reports static

echo ""
echo "[2/3] Upgrading pip and build tools..."
python3 -m pip install --upgrade pip setuptools wheel

echo ""
echo "[3/3] Installing AI and web dependencies..."
if [ -f "requirements.txt" ]; then
    python3 -m pip install -r requirements.txt
else
    python3 -m pip install fastapi uvicorn insightface onnxruntime opencv-python "numpy<2.0.0" pillow openpyxl qrcode piexif pydantic requests websockets python-multipart
fi

echo ""
echo "========================================================"
echo "Setup completed successfully!"
echo "Run './start_app.sh' to launch the application."
echo "========================================================"