#!/bin/bash
# X-Video Setup Script — Chạy trên Macmini
set -e

echo "🚀 X-Video Setup"
echo "================"

echo "1. Kiểm tra dependencies..."
which python3 || { echo "❌ Need Python 3"; exit 1; }
which node || { echo "❌ Need Node.js"; exit 1; }
which ffmpeg || { echo "❌ Need ffmpeg. Run: brew install ffmpeg"; exit 1; }
which hyperframes || npm install -g hyperframes

echo "2. Cài Python dependencies..."
pip3 install fastapi uvicorn 2>/dev/null || pip install fastapi uvicorn

echo "3. Tạo thư mục output..."
mkdir -p output render-project

echo "4. Kiểm tra macOS say..."
say -v Samantha "Hello, this is X Video" 2>/dev/null && echo "✅ TTS OK"

echo ""
echo "✅ X-Video ready! Khởi động server:"
echo "   python3 backend/server.py"
echo "   → http://localhost:8767"
