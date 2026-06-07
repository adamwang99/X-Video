#!/bin/bash
# build-macos.sh — Build X-Video Studio .app + .dmg tren macOS (Apple Silicon)
# Chay tren chinh may Mac. Khong cross-compile tu Linux duoc.
set -euo pipefail

REPO="/Users/tuan/X-Video-Fresh"
TARGET="aarch64-apple-darwin"
APP_NAME="X-Video Studio"
cd "$REPO"

echo "==> [1/5] Kiem tra toolchain"
if ! command -v cargo >/dev/null 2>&1; then
  echo "    Cai Rust..."
  curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
fi
source "$HOME/.cargo/env" 2>/dev/null || true
rustup target add "$TARGET" 2>/dev/null || true
if [ ! -f "$HOME/.cargo/bin/cargo-tauri" ]; then
  echo "    Cai tauri-cli..."
  cargo install tauri-cli
fi

echo "==> [2/5] Go ban X-Video cu trong /Applications (neu co)"
if [ -d "/Applications/$APP_NAME.app" ]; then
  rm -rf "/Applications/$APP_NAME.app"
  echo "    Da go ban cu."
fi

echo "==> [3/5] Build (.app + .dmg) — target $TARGET"
cd "$REPO/src-tauri"
npx tauri build --target "$TARGET"

BUNDLE="$REPO/src-tauri/target/$TARGET/release/bundle"
echo "==> [4/5] Cai .app moi vao /Applications"
APP_SRC="$BUNDLE/macos/$APP_NAME.app"
if [ -d "$APP_SRC" ]; then
  cp -R "$APP_SRC" /Applications/
  echo "    Da cai: /Applications/$APP_NAME.app"
else
  echo "    !! Khong thay $APP_SRC — kiem tra log build."
  exit 1
fi

echo "==> [5/5] Copy .dmg ra thu muc phan phoi"
mkdir -p /Users/tuan/xvideo-dmg
DMG=$(ls -t "$BUNDLE/dmg/"*.dmg 2>/dev/null | head -1 || true)
if [ -n "$DMG" ]; then
  VER=$(grep -E "\"version\"" "$REPO/src-tauri/tauri.conf.json" | head -1 | sed -E "s/.*\"version\": *\"([^\"]+)\".*/\\1/")
  cp "$DMG" "/Users/tuan/xvideo-dmg/X-Video-Studio-${VER}.dmg"
  echo "    DMG: /Users/tuan/xvideo-dmg/X-Video-Studio-${VER}.dmg"
fi
echo ""
echo "✅ XONG. Mo app tu Launchpad hoac /Applications/$APP_NAME.app"
