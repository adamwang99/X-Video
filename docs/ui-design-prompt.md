# UI Design Reference for X-Video Studio

Dùng file này để đưa cho GPT / AI vẽ mockup giao diện X-Video Studio.

---

## GPT Prompt — Vẽ Giao Diện X-Video Studio

```
Create a professional UI mockup for "X-Video Studio" — a URL-to-video web application.

OVERALL STYLE:
- Dark glassmorphism theme
- Deep background #030712 with aurora light effects
- Glass cards with backdrop-blur(20px) and thin indigo borders
- Color palette: Indigo (#6366f1), Violet (#8b5cf6), Cyan (#06b6d4)
- Modern, clean, B2B SaaS aesthetic

HEADER:
- Left: "X-Video Studio" logo text in violet, with "X" emphasized in larger font
- Version badge (v1.2) in indigo pill
- Machine badge (M4 GPU) in cyan pill
- Right: "AI World · URL → Video Engine" in muted text

MAIN LAYOUT — 2 columns:

LEFT COLUMN (60% width):

[Card 1 — Nguồn nội dung]
- Header: 📰 icon + "Nguồn nội dung"
- Tab bar: [🌐 Link bài viết] [✏️ Nhập nội dung] — active tab highlighted
- URL input field + "📥 Lấy nội dung" button
- Preview area below: fetched title in indigo, date, excerpt text

[Card 2 — Phong cách tường thuật]
- Header: 🎨 icon + "Phong cách tường thuật"
- 6 pill chips: 📺 Bản tin, 🎬 Phóng sự, 📊 Phân tích, 📖 Kể chuyện, 🔥 Tin nóng, 🎓 Hướng dẫn
- One chip selected (highlighted indigo border + glow)

[Card 3 — Kịch bản video]
- Header: ✍️ icon + "Kịch bản video" + [Chỉnh sửa tự do] badge
- "🎯 Hook mở đầu — 3 giây đầu" label + small chips: [🔥 Tin nóng] [🤔 Bạn có biết] [🚀 Đột phá] [⚠️ Cảnh báo] [⚡ Vừa ra mắt]
- Hook textarea with sample text "🔥 Tin nóng: GPT-5.5 vừa đạt 82.7%..."
- "📝 Nội dung chính" label + large textarea with article content
- "📢 Kêu gọi hành động (CTA) — cuối video" label + chips: [👍 Like&Follow] [📌 AI World] [💬 Comment] [🔔 Đăng ký]
- CTA textarea with "👍 Like & Follow để cập nhật tin công nghệ mỗi ngày!"

[Card 4 — Cấu hình video]
- Header: ⚙️ icon + "Cấu hình video"
- Row 1 (3 columns): Voice dropdown (🇺🇸 Samantha), Speed dropdown (▶ Bình thường), Music dropdown (🎵 Ambient)
- Row 2 (2 columns): Aspect dropdown (📱 Dọc 9:16), Resolution dropdown (Full HD 1080p)
- Labels in uppercase, subtle style

[CARD 5 — Button]
- Full-width gradient button indigo→violet: "▶ 🎬 Tạo Video" with subtle glow shadow

RIGHT COLUMN (40% width):

[Card — Preview & Export]
- Header: 📹 icon + "Preview & Export" + [MP4] badge
- Video player area (portrait 9:16 aspect ratio)
- Below player: 4 stat cards in 2x2 grid
  - [67s] Thời lượng | [3.8MB] Dung lượng | [192] Số từ | [172 wpm] Tốc độ
- Action buttons:
  - [📥 Tải MP4] — gradient button
  - [🔗 Sao chép link] — glass button
- Link preview: "http://192.168.1.12:8767/output/..."

[Card — Lịch sử]
- Header: 📋 icon + "Lịch sử"
- List items with: ✅ status badge, job title, "▶ Xem" link
- Minimal design, subtle borders

STEPS INDICATOR (above the 2 columns):
4-step progress bar: 1 Nội dung → 2 Kịch bản → 3 Cấu hình → 4 Hoàn tất
- Active step: indigo background
- Done step: green checkmark
- Pending: subtle gray

BACKGROUND:
- Deep dark (#030712) with 3 large blurred aurora orbs:
  - Top left: indigo, 600px, 8% opacity
  - Bottom right: violet, 400px, 6% opacity
  - Center: cyan, 300px, 5% opacity
  - Orbs have subtle floating animation

ADDITIONAL NOTES:
- Font: Inter (Google Fonts), weights 400-900
- All text in Vietnamese
- Professional quality suitable for a tech startup website
- Include subtle grid pattern overlay at 4% opacity
```

---

## Màu sắc

```
Nền chính:    #030712
Card kính:    rgba(30, 41, 59, 0.55) + blur(20px)
Primary:      #6366f1 (Indigo)
Accent:       #8b5cf6 (Violet)
Aurora:       #06b6d4 (Cyan)
Success:      #22c55e (Green)
Error:        #ef4444 (Red)
Text chính:   #e2e8f0
Text dim:     rgba(148, 163, 184, 0.45)
```

## Logo

Logo X-Video đã có sẵn tại `docs/logo-xvideo.svg` — có thể dùng làm icon trong giao diện.
