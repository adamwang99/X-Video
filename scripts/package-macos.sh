#!/bin/bash
# X-Video Studio — macOS .app Packager
# Usage: bash scripts/package-macos.sh
set -e

APP_NAME="X-Video Studio"
APP_DIR="dist/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
VERSION="1.2.0"

echo "📦 Packaging X-Video Studio for macOS..."
rm -rf "dist/$APP_NAME.app"

# Create bundle structure
mkdir -p "$MACOS" "$RESOURCES"

# Copy backend
cp -R backend "$RESOURCES/"
cp -R frontend "$RESOURCES/"
cp -R output "$RESOURCES/"
cp requirements.txt "$RESOURCES/"

# Create launcher script
cat > "$MACOS/xvideo" << 'SCRIPT'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$DIR"

# Check dependencies
command -v python3 >/dev/null 2>&1 || { osascript -e 'display dialog "❌ Python 3 not found. Install from python.org" buttons {"OK"}'; exit 1; }
command -v node >/dev/null 2>&1 || { osascript -e 'display dialog "❌ Node.js not found. Install from nodejs.org" buttons {"OK"}'; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { osascript -e 'display dialog "❌ FFmpeg not found. Run: brew install ffmpeg" buttons {"OK"}'; exit 1; }

# Install deps if needed
pip3 install -q fastapi uvicorn 2>/dev/null || true

# Start server
python3 backend/server.py &

# Wait and open browser
sleep 3
open http://localhost:8767

# Keep running
wait
SCRIPT

chmod +x "$MACOS/xvideo"

# Create Info.plist
cat > "$CONTENTS/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>xvideo</string>
    <key>CFBundleIdentifier</key>
    <string>com.aiworld.xvideo</string>
    <key>CFBundleName</key>
    <string>X-Video Studio</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
PLIST

# Copy icon (if exists)
if [ -f "docs/logo-xvideo.svg" ]; then
    cp "docs/logo-xvideo.svg" "$RESOURCES/"
fi

# Create DMG
echo "📀 Creating DMG..."
mkdir -p dist/dmg
cp -R "$APP_DIR" "dist/dmg/"
ln -s /Applications "dist/dmg/Applications"

hdiutil create -volname "X-Video Studio" \
    -srcfolder "dist/dmg" \
    -ov -format UDZO \
    "dist/X-Video-Studio-$VERSION.dmg" 2>/dev/null || {
    echo "✅ DMG optional, .app ready at dist/$APP_NAME.app"
}

rm -rf dist/dmg

echo ""
echo "✅ Done!"
echo "   .app: dist/$APP_NAME.app"
echo "   .dmg: dist/X-Video-Studio-$VERSION.dmg"
echo ""
echo "📎 To install:"
echo "   1. Open dist/$APP_NAME.app"
echo "   2. Allow in System Settings > Privacy & Security"
echo "   3. App will start server at http://localhost:8767"
