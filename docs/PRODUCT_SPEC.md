# X-Video Studio — Product Spec v1

## Status

**v1.3.3** — Production-ready trên Macmini M4. Đang phát triển clone voice & multi-agent orchestration.

## Product direction

X-Video Studio biến URL bài viết thành video MP4 có âm thanh — tự động, chất lượng cao, brand AI World.

```text
Current product:
  URL / Text
  → Content Analysis (preview + edit)
  → Voice Selection + Preview
  → Style Configuration + Music
  → HyperFrames Render (M4 GPU)
  → MP4 Output + Playback

Target product:
  URL / Text / RSS / AI Agent Output
  → Multi-modal Content Analysis (LLM)
  → Voice Library (clone, upload, save)
  → Template Library (design system)
  → Batch Render Queue
  → Multi-Platform Export (TikTok, YouTube, IG)
  → Analytics Dashboard
```

## Strategic objective

Build a self-service video automation platform that:

- Runs entirely on-premise (Macmini M4 — no cloud dependency)
- Supports Vietnamese natively (VieNeu TTS + 4 regional voices)
- Is API-first — any agent/employee in LAN can call
- Produces production-quality output (1080p-4K, audio sync, brand consistent)
- Stays bounded in cost (free — Apache 2.0, local render)

## Output levels

### Level 1 — Quick News (10-30s)

For breaking news / short-form social.

Outputs:
- Vertical 9:16 video
- Single-scene with headline + hook
- VieNeu voiceover
- Ambient background music

### Level 2 — Standard Broadcast (40-90s)

For daily content pipeline.

Outputs:
- Vertical/Horizontal/Square video
- Multi-scene: hook → content → CTA
- Voiceover + music sync
- AI World branding (gradient, accent bar, logo)
- Download MP4 + share link

### Level 3 — Premium Production (coming)

For flagship content.

Outputs:
- Multi-resolution (up to 4K)
- Advanced animation (Lottie, WebGL)
- Multi-voice narration
- Background video layer
- Subtitle overlay
- Custom brand kit

## Core principles

1. **Self-contained** — App spawns its own server, no browser dependency.
2. **Vietnamese-first** — VieNeu TTS prioritizes Vietnamese; English as fallback.
3. **Preview before commit** — User sees content preview + hears voice sample before render.
4. **Deterministic render** — Same HTML input → same MP4 output (HyperFrames guarantee).
5. **Glass UI standard** — Dark glassmorphism + aurora background + AI World brand colors.
6. **API for agents** — REST API enables automated pipeline from any machine.

## Functional architecture

### Layer A — Content Ingestion

Supported sources:
- WordPress REST API (AI World primary)
- Raw HTML parsing (fallback for any URL)
- Direct text input
- Future: RSS Feed, Google Doc, Notion

Responsibilities:
- Fetch content from URL
- Parse title, excerpt, category, date
- Present structured preview for user review
- Allow editing/re-generation before proceeding

### Layer B — Voice Engine

TTS providers:
- **VieNeu TTS** (port 6023, Macmini M4) — 4 Vietnamese voices
- **macOS say** (native) — 184 English voices
- Future: Voice cloning, custom voice upload

Responsibilities:
- List available voices by language/engine
- Generate voice sample on-demand (preview)
- Full voiceover synthesis for video
- Auto-adjust speed to fit target duration (40-90s)
- Fallback chain: VieNeu → macOS say

### Layer C — Music Engine

- ffmpeg sine wave synthesis
- 5 styles: Ambient, Corporate, Tech, Cinematic, Mute
- Auto-adjust duration to match voiceover
- Mix voice + music with volume balance

### Layer D — Render Engine

Tech stack:
- **HyperFrames v0.6.70** — Headless Chrome + ffmpeg → deterministic MP4
- **GSAP 3** — Professional animation library
- **HTML composition** — Responsive layout (CSS flexbox/grid)

Capabilities:
- 3 aspect ratios: 9:16, 16:9, 1:1
- 4 resolutions: HD 720p, Full HD 1080p, 2K 1440p, 4K 2160p
- 6 writing styles: News, Reportage, Analysis, Story, Hot, Tutorial
- Brand overlay: gradient background, accent bar, logo, animation

### Layer E — Output Layer

- MP4 file (H.264 + AAC)
- Online video player (embedded)
- Download link + share URL
- Post-render stats: duration, size, word count, speed

### Layer F — Application Layer

- **Tauri v2** — Native macOS app (Apple Silicon)
- **FastAPI + Uvicorn** — Backend server (:8767)
- **Vanilla HTML/CSS/JS** — Glass UI (no framework dependency)
- Auto-spawn server on app launch
- Self-contained .app bundle

## Required features

### Feature A — Content Analysis Engine ✅ (v1.0)

Goal: User pastes URL → sees structured preview before proceeding.

Status: ✅ Done
- WordPress API integration
- HTML fallback parser
- Preview card with title, excerpt, date, category
- Editable script (hook, content, CTA)

### Feature B — Voice Library ✅ (v1.3)

Goal: Select voice, hear sample, then render full video.

Status: ✅ Done
- 4 VieNeu Vietnamese voices
- 3 macOS English voices
- Preview API (/api/preview-voice) — instant MP3 sample
- Language auto-detection

### Feature C — Template System ✅ (v1.0)

Goal: Consistent AI World brand across all videos.

Status: ✅ Done
- 3 aspect ratios with responsive layout
- 6 writing styles with distinct CSS
- Brand elements: gradient, accent, logo, animation
- Glass UI design system

### Feature D — Voice Cloning 🔜 (v1.4)

Goal: User uploads voice sample → clone into TTS library.

Status: 🔜 Planned
- Single-file audio upload (.wav, .mp3, .m4a)
- Clone via VieNeu voice design API
- Saved to library for future use
- Preview + select in voice dropdown

### Feature E — Render Queue 🔜 (v1.5)

Goal: Queue multiple videos, render sequentially.

Status: 🔜 Planned
- Add jobs to queue
- Sequential processing
- Progress dashboard
- Max 5 videos/day (configurable)

### Feature F — Multi-Platform Packaging 🔜 (v2.0)

Goal: One-click export optimized for each platform.

Status: 🔜 Planned
- TikTok preset (9:16, 30-60s)
- YouTube preset (16:9, 60-90s)
- Instagram preset (1:1, 15-60s)
- Auto-format naming convention

## Release criteria

Before claiming a version is done:

- [ ] Web UI loads correctly (glass theme, logo, all controls)
- [ ] URL fetch returns preview content
- [ ] Voice preview generates audible sample
- [ ] Video render completes without error
- [ ] Output video has correct resolution and aspect ratio
- [ ] Audio is synced with video
- [ ] Tauri .app launches without crash
- [ ] DMG installer mounts and installs correctly
- [ ] All API endpoints return 200
- [ ] No hardcoded paths — all relative to resource dir
