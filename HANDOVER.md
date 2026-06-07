# X-Video Studio — HANDOVER (v1.28.3)

**Snapshot:** 2026-06-07 · **Owner cũ:** Tiệp QSO · **Owner mới:** TBD

---

## 1. Hạ tầng

| Mục | Giá trị |
|-----|---------|
| Host | Macmini `192.168.1.12` (SSH alias `macmini`, user `tuan`, key `~/.ssh/id_xvideo`) |
| Dark Memory alias SSH | `macmini_access` |
| Project | `/Users/tuan/X-Video-Fresh` |
| Repo | https://github.com/adamwang99/X-Video — branch `master` |
| App cài đặt | `/Applications/X-Video Studio.app` (v1.28.3) |

## 2. Services & ports

| Service | Port | Lệnh |
|---------|------|------|
| Backend FastAPI | 8767 | `python3 backend/server.py` (log `/tmp/xvideo-backend.log`) |
| Voice Library | 8769 | spawn cùng backend |
| DMG download | 8768 | `cd /Users/tuan/xvideo-dmg && python3 -m http.server 8768` |
| VieNeu TTS | 6023 | |
| Piper TTS | 6022 | |
| OmniVoice TTS | 6024 | |
| Valtec TTS | 6025 | |

## 3. Kiến trúc

**Engine render:** hyperframes (schema HeyGen) — `npx hyperframes@latest render`.

**Pipeline:**
```
URL/text → fetch_content → _fit_narration_length → generate_voice (TTS)
        → generate_bgm → build_storyboard (LLM segment scenes + headline)
        → Pexels stock photos (LLM keyword) → make_html_scenes (HTML+GSAP)
        → hyperframes render → mp4
```

**LLM:** provider `9router/Tiep` (claude-opus-4.8 #1, gemini-3.5-flash #2 fallback), `stream:false`, base `http://192.168.1.8:20128/v1`. Fallback local ollama `gemma-4-12b`.

## 4. Modules (`backend/`)

| File | Vai trò |
|------|---------|
| `server.py` | FastAPI app, `GenerateRequest`, `process_job`, `_job_render`, `APP_VERSION` |
| `xvideo_storyboard.py` | `build_storyboard`, `render_html`, CRUD scenes |
| `xvideo_scenes.py` | `make_html_scenes` (layer render HTML chính), `_short_headline`, `build_scenes_smart`, `llm_segment_scenes` |
| `xvideo_pexels.py` | `derive_keywords` (LLM-first), `search_photos/videos`, `PEXELS_KEY` từ env/store |
| `xvideo_llm.py` | adapter đa provider (ollama/gemini/openai/deepseek/9router) |
| `xvideo_apikeys.py` | key store thread-safe, init từ `render-project/api_keys.json` |
| `xvideo_scene_templates.py`, `xvideo_scene_analyzer.py` | visual types (kinetic_quote, data_card, process_flow, takeaway, image_card) |

## 5. Secrets (KHÔNG hardcode trong source)

Lưu trong Dark Memory (EVO-CORE), resolve qua `dm_inbox.py resolve <alias>`:
- `xvideo_pexels_key_1` — Pexels key #1 (default)
- `xvideo_pexels_key_2` — Pexels key #2 (fallback)
- `xvideo_9router_key` — 9router Tiep combo key

Runtime keys nằm ở `render-project/api_keys.json` (đã gitignored, KHÔNG lên repo).

## 6. Workflow deploy

```bash
ssh macmini
cd /Users/tuan/X-Video-Fresh
# 1. sửa code
# 2. restart backend
kill $(lsof -t -i :8767); nohup python3 backend/server.py > /tmp/xvideo-backend.log 2>&1 &
# 3. bump version 3 file: src-tauri/Cargo.toml, src-tauri/tauri.conf.json, backend/server.py (APP_VERSION)
# 4. build
npx tauri build --target aarch64-apple-darwin
# 5. deploy app
rm -rf "/Applications/X-Video Studio.app"
cp -R src-tauri/target/aarch64-apple-darwin/release/bundle/macos/"X-Video Studio.app" /Applications/
# 6. copy DMG
cp src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/"X-Video Studio_VER_aarch64.dmg" /Users/tuan/xvideo-dmg/X-Video-Studio-VER.dmg
```

## 7. Test

- Web UI: http://192.168.1.12:8767
- DMG tải: http://192.168.1.12:8768/X-Video-Studio-1.28.3.dmg

## 8. Method chấm chất lượng UI video

Render thật → `ffmpeg` trích frame → đọc ảnh trực tiếp. **Không đoán bằng đọc code.**

## 9. Lịch sử fix gần nhất (v1.28.3)

1. `_short_headline` + CSS line-clamp 3 dòng (chống title tràn frame)
2. Title dùng headline LLM scene đầu thay cắt thô câu
3. Badge số regex sạch + auto-fit font
4. `render_html` truyền `headline` xuống `make_html_scenes` (nối mắt xích bị đứt)
5. Pexels keyword LLM-first thay map tĩnh VI→EN
6. Layout: media-card lớn hơn + copy-card nâng, hết khoảng trống
7. Security: gỡ Pexels key hardcode → đọc env/store
8. Chore: gitignore `src-tauri/target` + backups, untrack build artifacts
