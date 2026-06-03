<div align="center">
  <h1>
    <span style="color:#8b5cf6">X</span><span style="color:#6366f1">-VIDEO</span>
  </h1>
  <p><strong>Write HTML. Render video. Built for agents.</strong></p>
  <p><em>URL → Video chất lượng cao có âm thanh — dành cho AI World News Pipeline</em></p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blueviolet" />
  <img src="https://img.shields.io/badge/macOS-26.2+-9cf" />
  <img src="https://img.shields.io/badge/Python-3.10+-blue" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-success" />
  <img src="https://img.shields.io/badge/HyperFrames-0.6.70+-orange" />
</p>

---

## 🎯 Tổng quan

**X-Video** là ứng dụng tự động hóa video tin tức, chạy trên Macmini M4 làm trung tâm tác vụ.  
Chỉ cần dán **URL bài viết** hoặc **nội dung text** → hệ thống tự động:

1. 📰 Crawl nội dung (WordPress AI World / bất kỳ web nào)
2. 🎤 TTS voiceover (macOS `say` — Samantha, Karen, Daniel...)
3. 🎵 Background music (ffmpeg sine wave ambient)
4. 🎬 HTML template → **HyperFrames render** (khổ dọc/ngang/vuông)
5. 📹 Output MP4 có âm thanh, sẵn sàng đăng tải

## 🏗 Kiến trúc

```
┌─────────────────┐     POST /api/generate     ┌──────────────────────┐
│  Mọi máy trong   │ ──────────────────────────→ │   Macmini M4         │
│  mạng LAN        │                             │   X-Video Server     │
│  Agent / Browser │ ←─── MP4 + URL online ──── │   :8767              │
└─────────────────┘                             └──────────────────────┘
                                                        │
                                          ┌─────────────┼─────────────┐
                                          ▼             ▼             ▼
                                     WordPress     macOS say     HyperFrames
                                     API fetch     TTS engine     GPU render
```

## ✨ Tính năng

| Tính năng | Chi tiết |
|-----------|----------|
| **URL → Video** | Dán link bài WordPress → tự động crawl → video |
| **Text → Video** | Nhập nội dung trực tiếp |
| **3 khổ video** | 📱 Dọc 9:16 (TikTok/Reels) · 🖥 Ngang 16:9 (YouTube) · 📐 Vuông 1:1 (Instagram) |
| **Giọng đọc** | macOS `say` — Samantha (en-US), Karen (en-AU), Daniel (en-GB) + mở rộng |
| **Nhạc nền** | Ambient tự sinh, không bản quyền |
| **Render GPU** | Macmini M4 Apple Silicon GPU — nhanh hơn software render 3-5x |
| **API đầy đủ** | REST API cho agent gọi từ xa |
| **Live preview** | Xem video online ngay từ browser |
| **Giới hạn** | Tối đa 5 video/ngày (có thể cấu hình) |
| **Template** | Brand AI World — gradient tím, accent bar, animation GSAP |

## 🚀 Quick Start

### Yêu cầu

- **macOS 26.2+** với **Apple Silicon** (M1/M2/M3/M4)
- **Python 3.10+**
- **Node.js 22+**
- **FFmpeg** (`brew install ffmpeg`)
- **HyperFrames CLI** (`npm install -g hyperframes`)

### Cài đặt

```bash
git clone https://github.com/aiworld/X-Video.git
cd X-Video

# Backend dependencies
pip install fastapi uvicorn

# Start server
python3 backend/server.py
```

Mở browser → `http://localhost:8767`

### Hoặc chạy bằng Docker (sắp có)

```bash
docker compose up -d
```

## 📡 API Reference

### `POST /api/generate` — Tạo video

```json
{
  "url": "http://192.168.1.9:8080/vi/ten-bai-viet/",
  "aspect": "doc",
  "language": "en",
  "voice": "Samantha"
}
```

### `GET /api/jobs/:id` — Kiểm tra trạng thái

```json
{
  "job_id": "abc123...",
  "status": "processing | done | error",
  "progress": 60,
  "video_url": "/output/xvideo_abc_20260603.mp4",
  "duration": 67,
  "size_kb": 3890
}
```

### `GET /api/templates` — Danh sách khổ video
### `GET /api/voices` — Danh sách giọng đọc
### `GET /output/:filename` — Serve video

## 🎬 Pipeline Resource Report (1 video)

| Bước | Thời gian | Máy |
|------|-----------|-----|
| Crawl WordPress | ~1s | Macmini |
| TTS (macOS say) | ~3s | Macmini (tích hợp) |
| BGM ambient | ~0.5s | Macmini |
| HTML generation | ~0.3s | Macmini |
| **HyperFrames render** | **~60-90s** | Macmini M4 GPU |
| **Tổng** | **~1-2 phút** | |

**So sánh:** Render trên máy thường (no GPU): ~3-5 phút → Macmini M4: **nhanh hơn 3-5x**

## 📁 Cấu trúc thư mục

```
X-Video/
├── backend/
│   ├── server.py           # FastAPI server (chạy trên Macmini)
│   └── templates/          # HTML templates (auto-generated)
├── frontend/
│   └── index.html          # Web UI (AI World brand)
├── output/                 # Video output directory
├── scripts/
│   └── setup.sh           # One-command setup
├── .gitignore
└── README.md
```

## 🔐 Security

- API không auth (mạng nội bộ) — có thể thêm API key layer
- Tất cả credential lưu trong EVO-CORE Dark Memory
- Video output chỉ truy cập được qua server

## 📜 License

Apache 2.0 — Mã nguồn mở cho cộng đồng AI World.

---

<p align="center"><em>Powered by Macmini M4 · HyperFrames · AI World</em></p>
