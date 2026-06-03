# X-Video Studio — Project Status

Current version: **v1.3.3** (2026-06-03)
Latest build: `ed08d65` — `Update logo + glass UI + voice preview + content preview`

## Build & verify gates

Source-of-truth is `X-Video/`. Before claiming a build done:

- `git push` — commit all changes to GitHub
- `scp` — upload latest source to Macmini (`~/X-Video-App/`)
- `cargo build --release && cp binary` — compile + deploy to /Applications
- `curl http://localhost:8767/healthz` — backend running
- `curl http://localhost:8767/api/voices` — voices available
- `open /Applications/X-Video\ Studio.app` — app launches without crash

## Current capabilities

**v1.3.3** (latest):

- ✅ Glass UI — Aurora background, glass cards, AI World brand
- ✅ VieNeu TTS — 4 Vietnamese voices (north/south male/female)
- ✅ macOS say — 3 English voices (Samantha, Karen, Daniel)
- ✅ Voice preview — Instant MP3 sample via `/api/preview-voice`
- ✅ Content preview — URL fetch → title/excerpt/meta preview + edit
- ✅ 6 writing styles — News, Reportage, Analysis, Story, Hot, Tutorial
- ✅ 3 aspect ratios — 9:16 (doc), 16:9 (ngang), 1:1 (vuong)
- ✅ 4 resolutions — HD 720p, FHD 1080p, 2K 1440p, 4K 2160p
- ✅ 5 music styles — Ambient, Corporate, Tech, Cinematic, Mute
- ✅ Hook + CTA presets — chips for quick selection
- ✅ Tauri .app — self-contained, spawns backend on launch
- ✅ DMG installer — 7.8MB downloadable
- ✅ CRUD API — generate, jobs, preview, voices
- ✅ WordPress fetch — WP REST API + HTML fallback

## Feature roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| v1.0 | Core pipeline + Web UI | ✅ |
| v1.1 | 6 styles + Hook/CTA + Voice config | ✅ |
| v1.2 | AI World Studio glass UI + ZTauri | ✅ |
| v1.3 | VieNeu TTS + preview + 4 resolutions | ✅ |
| v1.4 | Voice cloning + voice library | 🔜 |
| v1.5 | Batch queue + multi-platform | 🔜 |
| v2.0 | Native desktop app (Tauri) | 🚧 |

## Known issues

- **Macmini `npx tauri build`** — bundle_dmg may fail due to pipe buffer. Workaround: build binary separately → manually bundle with DMG.
- **VieNeu cold start** — first TTS request takes ~30s to load model. Subsequent requests are ~2-3s.
- **HyperFrames font lint** — `-apple-system` font fallback warning doesn't affect output.

## Build commands

```bash
# Local dev
python3 backend/server.py
# → http://localhost:8767

# Full build
bash scripts/package-macos.sh

# Tauri build (on Macmini)
cd src-tauri && cargo build --release

# One-click commit & deploy
git push && scp backend/server.py macmini:~/X-Video-App/backend/
```

## Environment

- **Host:** Macmini (192.168.1.12)
- **CPU:** Apple M4 (10-core)
- **RAM:** 16GB
- **OS:** macOS 26.2
- **Python:** 3.14
- **Rust:** 1.95.0
- **Node:** 22.22.3
- **Tauri CLI:** 2.11.2
- **HyperFrames:** 0.6.70
