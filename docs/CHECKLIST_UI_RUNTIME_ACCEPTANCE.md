# X-Video Studio — UI + Runtime Acceptance Checklist

## A. UI Glass Wave Check

PASS if all true:
- [ ] Aurora nền tím-cyan hiển thị (3 orb float)
- [ ] Glass cards có `backdrop-filter: blur(20px)`
- [ ] Header logo hiển thị đúng (`logo-xvideo.png` từ Sếp)
- [ ] Version badge hiển thị `v1.3`
- [ ] GPU badge hiển thị `M4 GPU`
- [ ] Nút "📥 Lấy nội dung" fetch được từ URL
- [ ] Preview card hiển thị title + excerpt + meta sau fetch
- [ ] Dropdown giọng đọc hiển thị đủ 4 giọng VieNeu + 3 giọng macOS
- [ ] Nút "🔈 Nghe thử giọng đọc" hoạt động
- [ ] Resolution dropdown có đủ: HD, Full HD, 2K, 4K
- [ ] Music dropdown có đủ: Ambient, Corporate, Tech, Cinematic, Mute
- [ ] Hook chips ngắn gọn: 🔥 Tin nóng, 🤔 Bạn có biết, 🚀 Đột phá, ⚠️ Cảnh báo
- [ ] CTA chips: 👍 Like, 📌 AI World, 💬 Comment, 🔔 Đăng ký

## B. Content Pipeline Check

PASS if all true:
- [ ] `GET /api/prefetch?url=<WP_URL>` trả về title, excerpt, content, source, date, category
- [ ] Preview hiển thị đúng dữ liệu
- [ ] Có thể edit nội dung trước khi tạo
- [ ] Hook và CTA preset hoạt động

## C. Voice Check

PASS if all true:
- [ ] `GET /api/preview-voice?voice=female_south&text=Xin+chào` trả về MP3
- [ ] Nút "Nghe thử" tạo audio và play được
- [ ] Đổi voice → nghe thử → ra giọng khác
- [ ] Fallback English: chọn Samantha → nghe thử → ra tiếng Anh

## D. Render Check

PASS if all true:
- [ ] `POST /api/generate` với text đơn giản → job queued
- [ ] `GET /api/jobs/:id` trả về progress
- [ ] Khi done: video player embed hiển thị
- [ ] Video có kích thước đúng resolution đã chọn
- [ ] Có nút 📥 Tải MP4
- [ ] Có nút 🔗 Sao chép link

## E. App Launch Check (Tauri)

PASS if all true:
- [ ] Mở app từ Applications → không crash
- [ ] Backend tự động start (check `curl localhost:8767/healthz`)
- [ ] WebView mở giao diện glass
- [ ] Đóng app → process killed

## F. Fails Immediately If

- [ ] Aurora nền không hiển thị
- [ ] Logo không phải của Sếp
- [ ] VieNeu voices không có trong dropdown
- [ ] Nút "Nghe thử" không hoạt động
- [ ] App mở ra crash ngay lập tức
- [ ] Backend không start trong vòng 3 giây
- [ ] Resolution khác nhau nhưng video ra cùng kích thước
