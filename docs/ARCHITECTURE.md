# X-Video Studio — Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    X-Video Studio                        │
│                    Tauri .app (macOS)                    │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Glass UI    │  │  FastAPI     │  │  Render      │  │
│  │  (WebView)   │→│  Backend     │→│  Engine      │  │
│  │  :8767       │  │  /api/*      │  │  HyperFrames │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                │                  │           │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌───────┴──────┐   │
│  │  Aurora     │  │  Content    │  │  Headless    │   │
│  │  Glass CSS  │  │  Engine     │  │  Chrome      │   │
│  └─────────────┘  │  WP API     │  │  + FFmpeg    │   │
│                   └─────────────┘  └──────────────┘   │
│                          │                              │
│                   ┌──────┴──────┐                       │
│                   │  Voice      │                       │
│                   │  Engine     │                       │
│                   │  VieNeu     │                       │
│                   │  :6023      │                       │
│                   └─────────────┘                       │
│                          │                              │
│                   ┌──────┴──────┐                       │
│                   │  Music      │                       │
│                   │  Engine     │                       │
│                   │  FFmpeg     │                       │
│                   └─────────────┘                       │
│                                                         │
│  Input: URL / Text           Output: MP4 + Playback     │
│  Render: M4 GPU              Codec: H.264 + AAC        │
└─────────────────────────────────────────────────────────┘
```

## Directory structure

```text
X-Video/
├── backend/
│   └── server.py          # FastAPI server
├── frontend/
│   ├── index.html         # Glass UI (standalone SPA)
│   └── static/
│       └── logo-xvideo.png # AI World logo
├── src/                   # Tauri splash page
│   └── index.html
├── src-tauri/
│   ├── src/
│   │   ├── lib.rs         # App entry — spawns backend, opens WebView
│   │   └── main.rs        # Rust main
│   ├── icons/             # App icons (32-512px)
│   ├── Cargo.toml          # Rust deps
│   └── tauri.conf.json     # Tauri config
├── docs/
│   ├── PRODUCT_SPEC.md
│   ├── ARCHITECTURE.md
│   ├── ui-design-prompt.md
│   ├── logo-xvideo.png
│   └── logo-xvideo.svg
├── scripts/
│   ├── package-macos.sh
│   ├── package-windows.bat
│   ├── package-linux.sh
│   ├── xvideo.service
│   └── build-tauri.sh
├── output/                # Video output
├── render-project/        # HyperFrames temp
├── requirements.txt
└── README.md
```

## Data flow

```text
POST /api/generate { url, voice, aspect, ... }
  │
  ├── 1. Content Ingestion
  │   ├── WordPress REST API (192.168.1.9:8080)
  │   └── HTML fallback parser
  │
  ├── 2. Voice Synthesis
  │   ├── VieNeu TTS (localhost:6023) — Vietnamese
  │   └── macOS say — English fallback
  │   └── Output: voice.mp3
  │
  ├── 3. Music Synthesis
  │   └── FFmpeg sine wave → bgm.mp3
  │
  ├── 4. HTML Composition
  │   ├── make_html() — responsive template
  │   ├── Brand: gradient + accent + logo + animation
  │   └── Audio: voice.mp3 (track 0) + bgm.mp3 (track 1)
  │
  ├── 5. HyperFrames Render
  │   ├── Headless Chrome: seek each frame
  │   ├── FFmpeg: encode to H.264 + AAC
  │   └── Output: .mp4 (deterministic)
  │
  └── 6. Serve
      ├── /output/<filename>.mp4
      ├── Embedded video player
      └── Download link
```

## Safety defaults

- Content preview before render — user confirms script.
- Voice preview before render — user hears sample.
- Max 5 videos/day — prevents runaway pipeline.
- Backend spawns only if port 8767 is free.
- App closes gracefully — kills backend process on exit.
- All filesystem paths relative to resource directory.

## Tech stack

| Layer | Technology |
|-------|-----------|
| App shell | Tauri 2 (Rust) |
| Backend | Python 3.12 + FastAPI |
| Frontend | Vanilla HTML/CSS/JS |
| Render | HyperFrames 0.6.70 |
| Animation | GSAP 3.14 |
| TTS | VieNeu (Python, port 6023) |
| TTS fallback | macOS say (native) |
| Audio | FFmpeg 7.1 (sine synthesis) |
| Video | FFmpeg + headless Chrome |
| Deployment | macOS .app / DMG / .bat / .sh |
