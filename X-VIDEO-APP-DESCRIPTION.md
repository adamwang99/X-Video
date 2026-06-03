# X-Video — Mô Tả Ứng Dụng Cho Sếp

## 🖥 Tổng quan

**X-Video** là ứng dụng desktop chạy trên **Macmini M4**, biến URL bài viết thành video ngắn có âm thanh chất lượng cao. Sếp dùng giao diện trên macOS, hoặc mở browser từ bất kỳ máy nào trong mạng LAN.

---

## 📐 1. Giao diện Web (đã chạy ở http://192.168.1.12:8767)

### Màn hình chính

```
┌─────────────────────────────────────────────────┐
│  X-VIDEO                    by AI World         │
├─────────────────────────────────────────────────┤
│                                                 │
│  URL → Video trong tích tắc                     │
│                                                 │
│  Dán link bài viết → chọn khổ → chọn giọng      │
│  → video MP4 có âm thanh, sẵn sàng đăng tải     │
│                                                 │
├─────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────┐  │
│  │ URL bài viết (WordPress AI World)          │  │
│  │ ┌─────────────────────────────────────┐   │  │
│  │ │https://192.168.1.9:8080/vi/slug/   │   │  │
│  │ └─────────────────────────────────────┘   │  │
│  │           — hoặc —                        │  │
│  │ ┌─────────────────────────────────────┐   │  │
│  │ │ Nhập trực tiếp nội dung bài viết..  │   │  │
│  │ └─────────────────────────────────────┘   │  │
│  │                                           │  │
│  │ 📱 Dọc 9:16  │  Samantha (English)       │  │
│  │ 🖥 Ngang 16:9│  Karen (English-AU)      │  │
│  │ 📐 Vuông 1:1 │  Daniel (English-UK)     │  │
│  │                                           │  │
│  │ [▶ Tạo Video]                             │  │
│  └───────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│  Video hoàn tất ✅                              │
│  ┌──────────────────────────────────────────┐   │
│  │            VIDEO PLAYER                  │   │
│  │           ▶ 00:01:07                      │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ 67s    │ │ 3.8MB  │ │ 192 từ │ │202wpm  │   │
│  │ Thời   │ │ Dung   │ │ Từ     │ │ Tốc độ │   │
│  │ lượng  │ │ lượng  │ │        │ │        │   │
│  └────────┘ └────────┘ └────────┘ └────────┘   │
│                                                 │
│  [📥 Tải video]  🔗 Link: http://.../video.mp4 │
├─────────────────────────────────────────────────┤
│  Lịch sử                                        │
│  ┌───────────────────────────────────────────┐  │
│  │ ✅ Hoàn tất  | GPT-5.5 Terminal-Bench     │  │
│  │ ✅ Hoàn tất  | Microsoft AI Agents...     │  │
│  │ ❌ Lỗi       | Anthropic Cookbook         │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Luồng sử dụng

| Bước | Sếp làm gì | Hệ thống làm gì |
|---|---|---|
| 1 | Mở `http://192.168.1.12:8767` | |
| 2 | Copy link bài từ site tin tức AI World (hoặc paste nội dung) | |
| 3 | Chọn khổ: Dọc 📱 / Ngang 🖥 / Vuông 📐 | |
| 4 | Chọn giọng: Samantha / Karen / Daniel | |
| 5 | Nút ▶ **Tạo Video** | Crawl WP → TTS → Nhạc nền → Render |
| 6 | Đợi ~1-2 phút (xem progress bar) | Macmini M4 đang render |
| 7 | Bấm ▶ xem video online luôn trên web | |
| 8 | Bấm 📥 tải MP4 về máy | |

---

## 🎬 2. Kết quả đầu ra

| Thuộc tính | Giá trị |
|---|---|
| **Độ phân giải** | Dọc 1080×1920 / Ngang 1920×1080 / Vuông 1080×1080 |
| **FPS** | 30 |
| **Codec** | H.264 video + AAC 192kbps audio |
| **Thời lượng** | 40-90 giây (tự động theo nội dung) |
| **Dung lượng** | ~3-5 MB/video |
| **Âm thanh** | Voiceover + nhạc nền ambient |

### Brand AI World trên video
- Gradient nền xanh tím đặc trưng
- Accent bar gradient tím
- Logo AI WORLD
- Animation GSAP chuyên nghiệp (fade in, float, transition)

---

## 🔌 3. API cho Agent / Nhân viên khác

Bất kỳ agent nào trong mạng cũng gọi được API:

```bash
# Agent gọi trực tiếp
curl -X POST http://192.168.1.12:8767/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url":"http://192.168.1.9:8080/vi/slug/","aspect":"doc"}'

# Trả về job ID → poll cho đến khi done
```

---

## 🗂 4. Cấu trúc repo GitHub

| File | Mục đích |
|---|---|
| `backend/server.py` | Backend FastAPI — crawl, TTS, render, API |
| `frontend/index.html` | Giao diện web AI World brand |
| `output/` | Thư mục chứa video (serve public) |
| `scripts/setup.sh` | Script cài đặt 1 lệnh |

---

## 🚀 5. Cách sử dụng ngay

**Trên Macmini (192.168.1.12) — đã chạy sẵn rồi:**
- Browser: `http://192.168.1.12:8767`

**Từ máy anh Adam:**
- Mở Safari/Chrome → gõ `http://192.168.1.12:8767`
- Dán link → chọn khổ → Tạo → Xem

**Từ máy Phương / Linh / Long SRO:**
- Cùng URL: `http://192.168.1.12:8767`
- Hoặc dùng API qua terminal/script

---

## ⚡ 6. Kế hoạch phát triển

| Phase | Tính năng | Trạng thái |
|---|---|---|
| **v1.0** | Web UI + API + Render trên Macmini | ✅ **Đang chạy** |
| **v1.1** | Docker Compose (1 lệnh chạy) | 🔜 |
| **v1.2** | Thêm giọng tiếng Việt (edge-tts) | 🔜 |
| **v1.3** | Telegram bot — gửi link → nhận video | 🔜 |
| **v1.4** | Queue + Rate limit cho nhiều user | 🔜 |
| **v2.0** | Native macOS app (SwiftUI) | 📝 |

---

Sếp thấy ổn không? Em có thể:
1. **Cho sếp xem thử** — sếp vào `http://192.168.1.12:8767` dùng thử liền
2. **Tạo video demo** — em render 1 bài, gửi link để sếp xem
3. **Thêm tiếng Việt** — cài edge-tts vào Macmini

Anh muốn gì trước ạ?
