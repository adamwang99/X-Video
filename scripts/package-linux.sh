#!/bin/bash
# X-Video Studio — Ubuntu / Linux Packager (AppImage)
# Usage: bash scripts/package-linux.sh
set -e

APP="X-Video Studio"
VERSION="1.2.0"
APP_DIR="dist/$APP.AppDir"
echo "📦 Packaging X-Video Studio for Linux..."

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin" "$APP_DIR/usr/lib/xvideo" "$APP_DIR/usr/share/applications" "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy app
cp -R backend "$APP_DIR/usr/lib/xvideo/"
cp -R frontend "$APP_DIR/usr/lib/xvideo/"
cp -R output "$APP_DIR/usr/lib/xvideo/"
cp requirements.txt "$APP_DIR/usr/lib/xvideo/"

# Create launcher
cat > "$APP_DIR/usr/bin/xvideo" << 'LAUNCHER'
#!/bin/bash
DIR="/usr/lib/xvideo"
cd "$DIR"

# Check deps
for cmd in python3 node ffmpeg; do
    if ! command -v $cmd &>/dev/null; then
        echo "❌ $cmd not found. Install with: sudo apt install $cmd"
        exit 1
    fi
done

# Install Python deps
pip3 install -q fastapi uvicorn 2>/dev/null || true

# Start
python3 backend/server.py &
sleep 3
xdg-open http://localhost:8767 2>/dev/null || true
wait
LAUNCHER
chmod +x "$APP_DIR/usr/bin/xvideo"

# Desktop entry
cat > "$APP_DIR/usr/share/applications/xvideo.desktop" << DESKTOP
[Desktop Entry]
Name=X-Video Studio
Comment=URL → Video Pipeline — AI World
Exec=/usr/bin/xvideo
Icon=xvideo
Terminal=false
Type=Application
Categories=Utility;Video;AI;
StartupNotify=true
DESKTOP

# Service file
cat > "$APP_DIR/usr/lib/systemd/user/xvideo.service" << SERVICE
[Unit]
Description=X-Video Studio — URL to Video Pipeline
After=network.target

[Service]
ExecStart=/usr/bin/xvideo
WorkingDirectory=/usr/lib/xvideo
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

# Simple install script
cat > dist/install.sh << 'INSTALL'
#!/bin/bash
set -e
echo "📦 Installing X-Video Studio..."

# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm ffmpeg git
sudo npm install -g hyperframes

# Copy files
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
sudo mkdir -p /usr/lib/xvideo
sudo cp -R "$SCRIPT_DIR/X-Video Studio.AppDir/usr/lib/xvideo/"* /usr/lib/xvideo/
sudo cp "$SCRIPT_DIR/X-Video Studio.AppDir/usr/bin/xvideo" /usr/bin/
sudo cp "$SCRIPT_DIR/X-Video Studio.AppDir/usr/share/applications/xvideo.desktop" /usr/share/applications/

# Service
mkdir -p ~/.config/systemd/user/
sudo cp "$SCRIPT_DIR/X-Video Studio.AppDir/usr/lib/systemd/user/xvideo.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now xvideo

echo "✅ Installed! Open http://localhost:8767"
echo "   Or run: xvideo"
INSTALL
chmod +x dist/install.sh

echo ""
echo "✅ Done!"
echo "   Install: bash dist/install.sh"
echo "   Or run directly: python3 backend/server.py"
echo ""
echo "📎 Cross-platform usage:"
echo "   1. Run: python3 backend/server.py"
echo "   2. Open http://localhost:8767"
echo ""
echo "   For systemd auto-start:"
echo "   cp scripts/xvideo.service ~/.config/systemd/user/"
echo "   systemctl --user enable --now xvideo"
