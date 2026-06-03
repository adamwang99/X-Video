<div align="center">
  <img src="docs/logo-xvideo.svg" alt="X-Video Logo" width="200" />
  <h1>X-Video Studio</h1>
  <h3>URL → Video. Tích tắc.</h3>

  <p>
    <img src="https://img.shields.io/badge/version-1.2-blueviolet?style=flat-square" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Ubuntu-blue?style=flat-square" />
    <img src="https://img.shields.io/badge/license-Apache%202.0-success?style=flat-square" />
    <img src="https://img.shields.io/badge/GPU-Apple%20M4%20%7C%20CUDA-orange?style=flat-square" />
  </p>
</div>

---

## 📖 Mục lục
- [Tổng quan](#-tổng-quan)
- [Tính năng](#-tính-năng)
- [Cài đặt](#-cài-đặt)
  - [macOS](#macos)
  - [Windows](#windows)
  - [Ubuntu / Linux](#ubuntu--linux)
- [Sử dụng](#-sử-dụng)
- [API cho Agent](#-api-cho-agent)
- [Kiến trúc](#-kiến-trúc)
- [Logo & Nhận diện](#-logo--nhận-diện)
- [Phát triển](#-phát-triển)

---

## 🎯 Tổng quan

**X-Video Studio** là ứng dụng biến **URL bài viết → Video MP4** có âm thanh chất lượng cao trong vòng 1-2 phút. Thiết kế cho AI World, chạy trên Macmini M4, giao diện glassmorphism tím–cyan.

```mermaid
graph LR
    A[📰 URL bài viết] --> B[🤖 Crawl nội dung]
    B --> C[✍️ Phân tích kịch bản]
    C --> D[🎤 TTS Voiceover]
    D --> E[🎵 Nhạc nền]
    E --> F[🎬 Render video]
    F --> G[📹 MP4 Output]
    
    style A fill:#6366f1
    style G fill:#22c55e
```

### Luồng xử lý

| Bước | Mô tả | Thời gian |
|------|-------|-----------|
| **1. Crawl** | Lấy nội dung từ WP REST API / HTML | < 1s |
| **2. Script** | Phân tích cấu trúc kịch bản (hook + nội dung + CTA) | < 0.5s |
| **3. Voice** | TTS voiceover bằng macOS `say` / Coqui TTS | ~3s |
| **4. Nhạc** | Sinh nhạc nền ambient bằng ffmpeg | ~0.5s |
| **5. Render** | HyperFrames headless Chrome → MP4 | ~60-120s |
| **Tổng** | | **~1-2 phút** |

---

## ✨ Tính năng

### 🎬 Sản xuất video
- ✅ **URL → Video** — dán link, ra MP4
- ✅ **6 phong cách tường thuật** — Bản tin, Phóng sự, Phân tích, Kể chuyện, Tin nóng, Hướng dẫn
- ✅ **Hook mở đầu** — 3 giây giữ chân người xem với preset: 🔥 Tin nóng, 🤔 Bạn có biết, 🚀 Đột phá...
- ✅ **CTA cuối video** — Like & Follow, AI World, Comment, Đăng ký...
- ✅ **3 khổ video** — Dọc 9:16 / Ngang 16:9 / Vuông 1:1
- ✅ **4 độ phân giải** — HD / Full HD / 2K / 4K
- ✅ **5 phong cách nhạc nền** — Ambient, Corporate, Tech, Cinematic, Mute

### 🎤 Voiceover
- ✅ **184 giọng đọc** macOS `say` (🇺🇸🇬🇧🇦🇺🇮🇳🇮🇪🇿🇦...)
- ✅ **3 tốc độ** — Chậm / Bình thường / Nhanh
- ✅ **Tự động canh thời lượng** 40-90 giây

### 🎨 Giao diện
- ✅ **Dark glassmorphism** — backdrop-blur + card kính
- ✅ **Aurora tím–cyan** — 3 orb nền float animation
- ✅ **Responsive** — Desktop + Tablet
- ✅ **AI World brand** — indigo 400-600, violet 400-500, cyan 400

### 🔌 API
- ✅ **REST API** — Agent gọi `POST /api/generate`
- ✅ **Job queue + progress tracking**
- ✅ **Live video preview** — xem online ngay trên browser

---

## 📦 Cài đặt

### Yêu cầu chung
- **Python 3.10+**
- **Node.js 22+**
- **FFmpeg** (xử lý audio/video)
- **HyperFrames CLI** (render engine)
- **macOS `say`** (TTS — yêu cầu macOS)

> ⚠️ **Lưu ý:** TTS engine hiện dùng macOS `say` (tích hợp sẵn). Trên Windows/Ubuntu, cần cài thêm Coqui TTS hoặc Edge-TTS để thay thế.

---

### <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg" width="18" /> macOS

```bash
# 1. Cài dependencies
brew install python@3.12 node ffmpeg

# 2. Cài HyperFrames
npm install -g hyperframes

# 3. Cài X-Video
git clone https://github.com/adamwang99/X-Video.git
cd X-Video
pip install -r requirements.txt

# 4. Chạy
python3 backend/server.py
# → Mở http://localhost:8767

# Hoặc đóng gói thành .app
bash scripts/package-macos.sh
```

#### Đóng gói macOS (.app)
```bash
bash scripts/package-macos.sh
# Output: dist/X-Video Studio.app
```

---

### <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg" width="18" /> Windows

```powershell
# 1. Cài Python 3.12 từ python.org (tick "Add to PATH")
# 2. Cài Node.js 22+ từ nodejs.org
# 3. Cài FFmpeg: choco install ffmpeg (hoặc tải từ ffmpeg.org)

# 4. Cài TTS engine thay thế (Coqui TTS)
pip install TTS

# 5. Cài HyperFrames
npm install -g hyperframes

# 6. Cài X-Video
git clone https://github.com/adamwang99/X-Video.git
cd X-Video
pip install -r requirements.txt

# 7. Chạy
python backend\server.py
# → Mở http://localhost:8767

# Đóng gói thành .exe
scripts\package-windows.bat
```

---

### <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/ubuntu.svg" width="18" /> Ubuntu / Linux

```bash
# 1. Cài dependencies
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm ffmpeg git

# 2. Cài TTS engine thay thế (piper-tts)
pip install piper-tts

# 3. Cài HyperFrames
npm install -g hyperframes

# 4. Cài X-Video
git clone https://github.com/adamwang99/X-Video.git
cd X-Video
pip install -r requirements.txt

# 5. Chạy
python3 backend/server.py &
# → Mở http://localhost:8767

# Đóng gói AppImage
bash scripts/package-linux.sh
```

#### Systemd service (auto-start)
```bash
sudo cp scripts/xvideo.service /etc/systemd/system/
sudo systemctl enable --now xvideo
```

---

## 🖥 Sử dụng

### Giao diện Web

```
┌────────────────────────────────────────────────────────────┐
│  X-Video Studio   [v1.2]  [M4 GPU]    AI World · Engine    │
│────────────────────────────────────────────────────────────│
│                                                            │
│  📰 Nguồn nội dung                                         │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ [🌐 Link bài viết]  [✏️ Nhập nội dung]               │ │
│  │ https://192.168.1.9:8080/vi/slug/  [📥 Lấy nội dung] │ │
│  │ ──────────────────────────────────────────────────── │ │
│  │ ✅ Đã lấy: "GPT-5.5 Terminal-Bench..."               │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  🎨 Phong cách                                             │
│  [📺 Bản tin] [🎬 Phóng sự] [📊 Phân tích] [🔥 Tin nóng]  │
│                                                            │
│  ✍️ Kịch bản                                               │
│  Hook: [🔥 Tin nóng] [🤔 Bạn có biết] [🚀 Đột phá]        │
│  🎯 [Bạn có biết GPT-5.5 đạt 82.7%....________]          │
│  📝 [Nội dung chính từ bài viết...______________]         │
│  📢 [👍 Like & Follow để cập nhật tin mới!______]         │
│                                                            │
│  ⚙️ Cấu hình                                               │
│  Voice: 🇺🇸 Samantha  Speed: ▶   Music: 🎵                 │
│  Khổ: 📱 Dọc 9:16    Độ phân giải: Full HD                │
│                                                            │
│  [▶ 🎬 Tạo Video]                                          │
│────────────────────────────────────────────────────────────│
│  📹 Preview                    [55s] [3.2MB] [192 từ]     │
│  ┌──────────────────────┐     [📥 Tải MP4] [🔗 Copy link] │
│  │    VIDEO PLAYER      │                                  │
│  │    ▶ 00:00:55        │     📋 Lịch sử                   │
│  └──────────────────────┘     ✅ GPT-5.5 ...  ▶ Xem        │
│                                ✅ Microsoft ... ▶ Xem       │
└────────────────────────────────────────────────────────────┘

Nền: Aurora tím–cyan float || Glass cards blur(20px)
```

### Video đầu ra

```
┌─────────────────────┐
│     AI WORLD        │  ← Logo
│  📺 BẢN TIN         │  ← Style tag
│                     │
│  GPT-5.5: 82.7%    │  ← Headline (font-size responsive)
│  Terminal-Bench     │
│                     │
│  Mô hình mới của    │  ← Content excerpt
│  OpenAI đạt điểm... │
│                     │
│ 👍 Like & Follow    │  ← CTA (xuất hiện cuối video)
│                     │
│  AI World News      │  ← Meta
│  03/06/2026         │
└─────────────────────┘

Đặc điểm:
  • Gradient nền tím–xanh đen
  • Grid overlay mờ
  • Accent bar gradient tím–violet–fuchsia
  • 3 floating circles aurora
  • Animation GSAP (fade-in, float, transition)
  • Codec: H.264 30fps + AAC 192kbps
```

### Quy trình: 4 bước

| Step | Bạn làm | Hệ thống |
|------|---------|----------|
| **1** | Dán URL + bấm "📥 Lấy nội dung" | Crawl WordPress → trả về title, nội dung |
| **2** | Chọn phong cách, chỉnh hook/CTA | Tự generate script theo style |
| **3** | Chọn voice, khổ, nhạc, độ phân giải | Config render pipeline |
| **4** | Bấm "🎬 Tạo Video" | TTS → Nhạc nền → Render → MP4 |
| **✅** | Xem + Tải video | Playback ngay trên browser |

---

## 🔌 API cho Agent

### `POST /api/generate`
```json
{
  "url": "http://192.168.1.9:8080/vi/slug-bai-viet/",
  "hook": "🔥 Tin nóng:",
  "cta": "👍 Like & Follow!",
  "aspect": "doc",
  "voice": "Samantha",
  "speed": "normal",
  "style": "news",
  "music": "ambient",
  "resolution": "fhd"
}
```

### `GET /api/jobs/:id`
```json
{
  "job_id": "abc123...",
  "status": "done",
  "progress": 100,
  "video_path": "xvideo_abc_20260603.mp4",
  "duration": 67,
  "size_kb": 3890,
  "word_count": 192,
  "tts_rate": 172
}
```

### `GET /api/prefetch?url=...`
```json
{
  "title": "GPT-5.5 82.7% Terminal-Bench",
  "excerpt": "Mô hình mới đạt điểm cao nhất...",
  "content": "Ngày 23/4/2026, OpenAI ra mắt...",
  "source": "http://...",
  "date": "2026-05-18",
  "category": "CÔNG NGHỆ"
}
```

---

## 🏗 Kiến trúc

```
┌──────────────────────────────────────────────────────┐
│                    X-Video Studio                     │
│                                                      │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Frontend   │  │  FastAPI   │  │  Render      │  │
│  │  Glass UI   │→ │  Backend   │→ │  Engine      │  │
│  │  :8767      │  │  /api/*    │  │  HyperFrames │  │
│  └─────────────┘  └────────────┘  └──────────────┘  │
│                          │               │           │
│                    ┌─────┴─────┐   ┌─────┴──────┐   │
│                    │  Crawler  │   │  FFmpeg    │   │
│                    │  WP API   │   │  Encode    │   │
│                    └───────────┘   └────────────┘   │
│                          │                           │
│                    ┌─────┴─────┐                     │
│                    │  TTS       │                    │
│                    │  macOS say │                    │
│                    │  (184 voice)│                   │
│                    └───────────┘                     │
│                                                      │
│  Input: URL / Text           Output: MP4 + Playback  │
└──────────────────────────────────────────────────────┘
```

### Stack công nghệ
| Lớp | Công nghệ |
|-----|-----------|
| Frontend | Vanilla JS + CSS glassmorphism + GSAP |
| Backend | Python 3.12 + FastAPI + Uvicorn |
| Render | HyperFrames 0.6.70 + headless Chrome + FFmpeg |
| TTS | macOS `say` (native) / Coqui TTS (cross-platform fallback) |
| Audio | FFmpeg sine wave synthesis |
| Crawl | urllib + WordPress REST API |

---

## 🎨 Logo & Nhận diện

### Logo specs

```
┌─────────────────────────────────────────┐
│  Logo chính:                            │
│                                         │
│  X - VIDEO                              │
│  ─────────                              │
│  "X" = violet #8b5cf6, bold 900        │
│  "VIDEO" = indigo #6366f1, bold 900    │
│                                         │
│  Icon: Chữ "X" cách điệu trong khung   │
│  tròn gradient tím–cyan, có hiệu ứng   │
│  glow aurora phía sau.                  │
│                                         │
│  Style: Dark glass BG + aurora orb      │
│  nền tím–cyan mờ phía sau icon.         │
└─────────────────────────────────────────┘
```

### Yêu cầu logo cho GPT vẽ

> **Prompt cho AI vẽ logo:**
> 
> "Create a modern tech logo for 'X-Video Studio' — a video automation platform. 
> Style: dark glassmorphism with indigo (#6366f1) and violet (#8b5cf6) accents.
> The logo should feature a stylized letter 'X' inside a rounded square frame,
> with a subtle cyan (#06b6d4) to violet gradient glow behind it.
> The overall feel should be premium, AI-native, professional.
> Background: transparent or very dark (#030712).
> The 'X' should look like an intersection/convergence point — 
> symbolizing content meeting video. 
> Include a subtle aurora/light effect behind the mark.
> Suitable for: website header, app icon, GitHub social preview."

### Màu sắc thương hiệu

| Tên | Hex | Vai trò |
|-----|-----|---------|
| Deep BG | `#030712` | Nền chính |
| Surface | `rgba(15,23,42,0.75)` | Card kính |
| Indigo 500 | `#6366f1` | Primary CTA |
| Violet 400 | `#a78bfa` | Style tag |
| Violet 500 | `#8b5cf6` | Gradient accent |
| Cyan 400 | `#22d3ee` | Aurora orb |
| Cyan 500 | `#06b6d4` | Machine badge |
| Success | `#22c55e` | Done status |
| Error | `#ef4444` | Error alert |

### Typography

- **Font chính:** Inter (Google Fonts) — weights 300, 400, 500, 600, 700, 900
- **Fallback:** -apple-system, BlinkMacSystemFont, 'Segoe UI'

---

## 🛠 Phát triển

### Cấu trúc thư mục

```
X-Video/
├── backend/
│   ├── server.py          # FastAPI server
│   └── templates/         # [auto-generated]
├── frontend/
│   └── index.html         # Web UI (standalone)
├── output/                # Video output
├── render-project/        # HyperFrames temp
├── scripts/
│   ├── package-macos.sh   # macOS .app bundler
│   ├── package-windows.bat # Windows .exe bundler
│   ├── package-linux.sh   # Linux AppImage
│   └── xvideo.service     # Systemd unit
├── docs/
│   ├── logo-xvideo.svg    # Logo vector
│   └── screenshots/       # UI screenshots
├── requirements.txt       # Python deps
├── .gitignore
└── README.md
```

### Lệnh hữu ích

```bash
# Chạy development (auto-reload)
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8767

# Đóng gói macOS
bash scripts/package-macos.sh

# Đóng gói Windows
scripts\package-windows.bat

# Đóng gói Linux
bash scripts/package-linux.sh

# Test API
curl -X POST http://localhost:8767/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url":"http://192.168.1.9:8080/vi/ten-bai/","aspect":"doc"}'
```

### Roadmap

| Phase | Mục tiêu | Trạng thái |
|-------|----------|------------|
| **v1.0** | Core pipeline + Web UI | ✅ Done |
| **v1.1** | 6 styles + Hook/CTA + Voice config | ✅ Done |
| **v1.2** | AI World Studio glass UI | ✅ Done |
| **v1.3** | Cross-platform packaging (.app/.exe/.AppImage) | 🔜 In progress |
| **v1.4** | Vietnamese TTS (edge-tts / Coqui) | 🔜 |
| **v1.5** | Telegram Bot integration | 📝 Planned |
| **v2.0** | Native desktop app (Tauri) | 📝 Planned |

---

<div align="center">
  <p>Built with ❤️ on Macmini M4 for <strong>AI World</strong></p>
  <p>
    <a href="https://github.com/adamwang99/X-Video">GitHub</a> · 
    <a href="http://192.168.1.12:8767">Live Demo</a> · 
    <a href="https://aiworld.vn">AI World</a>
  </p>
  <p><small>Apache 2.0 © 2026 AI World</small></p>
</div>
