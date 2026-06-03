#!/bin/bash
# X-Video Tauri Build — Macmini M4
set -ex

cd ~/X-Video-Repo

echo "=== Step 1: npm install ==="
npm install

echo "=== Step 2: Rust build ==="
cargo build --manifest-path src-tauri/Cargo.toml --release

echo "=== Step 3: Tauri bundle .app ==="
npx tauri build --target aarch64-apple-darwin

echo "=== CHECK OUTPUT ==="
find src-tauri/target -name "*.app" -type d 2>/dev/null
find src-tauri/target -name "*.dmg" -type f 2>/dev/null

echo "=== BUILD COMPLETE ==="
