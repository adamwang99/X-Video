"""
X-Video scene-based visual pipeline (v1.8.0)
Added by Tiep QSO 2026-06-05.

Replaces single static slide with a multi-scene video:
- Article images (featured + content) as scene backgrounds with Ken Burns (zoom/pan)
- Subtitles synced to narration segments (proportional timing)
- Cross-fade transitions between scenes
- Gradient fallback scene when no image available
"""
import re, os, html as _html, urllib.request, hashlib


def extract_images(url, content_html, wp_post=None):
    """Collect candidate image URLs: featured media + content images. Returns list."""
    imgs = []
    if wp_post:
        emb = wp_post.get("_embedded", {})
        fm = emb.get("wp:featuredmedia", [])
        if fm and isinstance(fm, list):
            su = fm[0].get("source_url", "")
            if su:
                imgs.append(su)
    # images in content
    for m in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_html or ""):
        if m and m not in imgs and not m.endswith(".svg"):
            imgs.append(m)
    # de-dup, keep order, filter tiny tracking pixels by name
    out = []
    for i in imgs:
        if i not in out and "spacer" not in i.lower() and "pixel" not in i.lower():
            out.append(i)
    return out


def download_images(images, jd, limit=8):
    """Download images into job dir/assets. Returns list of relative paths that succeeded."""
    asset_dir = os.path.join(str(jd), "assets")
    os.makedirs(asset_dir, exist_ok=True)
    local = []
    for idx, url in enumerate(images[:limit]):
        try:
            ext = os.path.splitext(url.split("?")[0])[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            fn = f"img_{idx}{ext}"
            fp = os.path.join(asset_dir, fn)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 XVideo"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read(8 * 1024 * 1024)  # cap 8MB
            if len(data) < 2000:  # skip tiny/broken
                continue
            with open(fp, "wb") as f:
                f.write(data)
            local.append(f"assets/{fn}")
        except Exception as e:
            print(f"[scene] image dl fail {url[:60]}: {e}", flush=True)
    return local


def split_sentences(text):
    """Split Vietnamese/English text into sentences."""
    text = re.sub(r'\s+', ' ', (text or '').strip())
    # split on . ! ? ; followed by space + capital, keep delimiter
    parts = re.split(r'(?<=[.!?;])\s+', text)
    return [p.strip() for p in parts if p.strip()]


import json as _json, os as _os, urllib.request as _ur

_OLLAMA_URL = _os.environ.get("XVIDEO_OLLAMA", "http://localhost:11434")
_OLLAMA_MODEL = _os.environ.get("XVIDEO_OLLAMA_MODEL", "hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M")

def target_scene_count(total_duration, total_words, sec_per_scene=10.0):
    import math
    n = max(1, round((total_duration or 30) / sec_per_scene))
    content_cap = max(1, math.ceil(max(1, total_words) / 18))
    return max(1, min(n, content_cap))

def llm_segment_scenes(narration, n_scenes, timeout=240, provider=None, model=None, base_url=None):
    """Split narration into exactly n_scenes coherent scenes via the configured LLM.
    Each scene: rewritten to be concise but keep meaning + appeal, NO mid-text '...'.
    Returns list of {headline, text} or None on any failure (caller falls back to rules).
    """
    text = (narration or "").strip()
    if not text or n_scenes < 1:
        return None
    prompt = (
        "Bạn là biên tập viên video tiếng Việt. Chia nội dung sau thành đúng "
        + str(n_scenes) + " phân cảnh cho video.\n"
        "QUY TẮC:\n"
        "- Mỗi phân cảnh là lời đọc mạch lạc, rút gọn nhưng GIỮ trọn ý và sức hấp dẫn.\n"
        "- TUYỆT ĐỐI không dùng dấu ... để cắt câu; mỗi câu phải trọn vẹn.\n"
        "- Giữ nguyên mọi số liệu, tên riêng, dữ kiện quan trọng; không bịa thêm.\n"
        "- Phủ hết nội dung gốc, chia đều, không bỏ ý chính.\n"
        "- Mỗi phân cảnh có headline ngắn (<=8 từ) và text lời đọc.\n"
        "- Trả về DUY NHẤT JSON: {\"scenes\":[{\"headline\":\"...\",\"text\":\"...\"}]} không thêm gì khác.\n\n"
        "Nội dung:\n" + text[:6000]
    )
    try:
        resp = None
        if provider and provider not in ("local", "ollama", "local_ollama"):
            try:
                import xvideo_llm
                resp = xvideo_llm.complete(prompt, provider=provider, model=model or None,
                                           json_mode=True, temperature=0.4, max_tokens=2400,
                                           timeout=timeout, base_url=base_url)
            except Exception as _pe:
                print("[scene] provider", provider, "failed, fallback local:", _pe, flush=True)
                resp = None
        if not resp:
            payload = _json.dumps({
                "model": _OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json",
                "options": {"temperature": 0.4, "num_predict": 2400},
            }).encode("utf-8")
            req = _ur.Request(_OLLAMA_URL + "/api/generate", data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
            with _ur.urlopen(req, timeout=timeout) as r:
                out = _json.loads(r.read())
            resp = out.get("response", "")
        data = _json.loads(resp or "{}")
        scenes = data.get("scenes") or []
        clean = []
        for sc in scenes:
            t = (sc.get("text") or "").strip()
            if not t:
                continue
            # safety: never allow a literal mid-text ellipsis to survive
            t = t.replace("...", " ").replace("\u2026", " ")
            t = " ".join(t.split())
            h = (sc.get("headline") or "").strip()
            clean.append({"headline": h, "text": t})
        return clean or None
    except Exception as e:
        print("[scene] llm_segment failed:", e, flush=True)
        return None

def build_scenes_smart(narration, images, total_duration, min_scene=2.5, use_llm=True,
                       provider=None, model=None, base_url=None):
    """LLM-first scene segmentation with rule-based fallback. Returns same shape as
    build_scenes plus optional 'headline'. Durations are word-proportional."""
    total_words = len((narration or "").split()) or 1
    n_scenes = target_scene_count(total_duration, total_words)
    segs = llm_segment_scenes(narration, n_scenes, provider=provider, model=model, base_url=base_url) if use_llm else None
    if not segs:
        return build_scenes(narration, images, total_duration, min_scene)
    # assign images (one-use only) + word-proportional duration
    tw = sum(len(x["text"].split()) for x in segs) or 1
    scenes, acc = [], 0.0
    for i, sc in enumerate(segs):
        wc = len(sc["text"].split())
        dur = max(min_scene, total_duration * wc / tw)
        img = images[i] if (images and i < len(images)) else None
        scenes.append({"text": sc["text"], "headline": sc.get("headline") or None,
                       "image": img, "dur": round(dur, 2), "start": round(acc, 2)})
        acc += dur
    if scenes and acc > 0:
        scale = total_duration / acc; a2 = 0.0
        for sx in scenes:
            sx["dur"] = round(sx["dur"] * scale, 2); sx["start"] = round(a2, 2); a2 += sx["dur"]
    return scenes

def build_scenes(narration, images, total_duration, min_scene=2.5):
    """
    Split narration into scenes; assign images round-robin.
    Each scene duration ∝ word count. Returns list of dicts.
    """
    sents = split_sentences(narration)
    if not sents:
        sents = [narration or ""]
    # GOAL (CEO 2026-06-06): cut scene count to ~1/3 of the old behavior to save
    # render resources. Old behavior split every ~14 words (many tiny scenes).
    # We now make each scene a HIGHLIGHT carrying ~3x more voice text, and cap the
    # number of scenes hard. Voice still reads the full text inside each longer scene.
    total_wc_src = sum(len(x.split()) for x in sents) or len((narration or "").split()) or 1
    import math
    # CEO target (2026-06-06): ~10s per scene, i.e. a 60s video ~ 5-6 scenes.
    # Drive scene count from DURATION, not from a fixed cap.
    SEC_PER_SCENE = 10.0
    n_scenes = max(1, round((total_duration or 30) / SEC_PER_SCENE))
    # Bound by content so very short text never gets over-split.
    content_cap = max(1, math.ceil(total_wc_src / 18))
    n_scenes = max(1, min(n_scenes, content_cap))
    words_per = max(1, total_wc_src / n_scenes)
    chunks, cur, cur_wc = [], [], 0
    for s in sents:
        wc = len(s.split())
        cur.append(s); cur_wc += wc
        # close current group once it reaches its balanced share, but never create
        # more than n_scenes groups (the last group absorbs the remainder).
        if cur_wc >= words_per and len(chunks) < n_scenes - 1:
            chunks.append(" ".join(cur)); cur, cur_wc = [], 0
    if cur:
        chunks.append(" ".join(cur))
    if not chunks:
        chunks = [narration or ""]

    total_words = sum(len(c.split()) for c in chunks) or 1
    scenes = []
    acc = 0.0
    n = len(chunks)
    for i, c in enumerate(chunks):
        wc = len(c.split())
        dur = max(min_scene, total_duration * wc / total_words)
        img = images[i] if (images and i < len(images)) else None  # no repeat; HTML scene handles missing images
        scenes.append({"text": c, "image": img, "dur": round(dur, 2), "start": round(acc, 2)})
        acc += dur
    # normalize so sum == total_duration
    if scenes and acc > 0:
        scale = total_duration / acc
        acc2 = 0.0
        for s in scenes:
            s["dur"] = round(s["dur"] * scale, 2)
            s["start"] = round(acc2, 2)
            acc2 += s["dur"]
    return scenes


def _short_headline(title, max_words=10, max_chars=72):
    """Rut headline ngan cho .vtitle de khong tran frame (fix overlap)."""
    t = (title or "").strip()
    parts = re.split(r"(?<=[.!?])\s", t)
    if parts and parts[0].strip():
        t = parts[0].strip()
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words])
    if len(t) > max_chars:
        t = t[:max_chars].rsplit(" ", 1)[0]
    return t.rstrip(" ,;:.-")

def make_html_scenes(aspect, title, date_str, duration, voice_path, bgm_path,
                     scenes, ASPECT_MAP, RES_MAP, style="news", resolution="fhd"):
    """Build multi-scene HTML with Ken Burns images + synced subtitles for Hyperframes."""
    ar_w, ar_h = ASPECT_MAP.get(aspect, (9, 16))
    base_h = RES_MAP.get(resolution, 1080)
    h = base_h
    w = int(h * ar_w / ar_h / 2) * 2
    pct = lambda p: int(h * p)
    dur_int = int(duration) + 1

    style_desc = {"news": "📺 BẢN TIN", "reportage": "🎬 PHÓNG SỰ", "analysis": "📊 PHÂN TÍCH",
                  "story": "📖 CÂU CHUYỆN", "tutorial": "🎓 HƯỚNG DẪN", "hot": "🔥 TIN NÓNG"}
    tag = style_desc.get(style, "📺 TIN TỨC")
    # Prefer first-scene LLM headline (complete, <=8 words) over crude title truncation.
    _vt = ""
    for _sc in (scenes or []):
        _h = (_sc.get("headline") or "").strip()
        if _h:
            _vt = _h
            break
    if not _vt:
        _vt = _short_headline(title)
    safe_title = _html.escape(_vt)

    # Build scene DOM + GSAP per scene
    scene_divs = []
    scene_tl = []
    for i, sc in enumerate(scenes):
        sid = f"sc{i}"
        st = sc["start"]
        sd = sc["dur"]
        txt = sc["text"]
        sub = _html.escape(txt[:360])
        words = [w.strip(".,:;!?()[]{}\"'") for w in txt.split() if len(w.strip(".,:;!?()[]{}\"'")) > 3]
        kw = _html.escape((words[0] if words else "AI World")[:28])
            # pick a clean number/percent (e.g. 40%, 2026) - skip alnum like GPT-5.5
        _m = re.search(r"\d+(?:[.,]\d+)*%?", txt)
        num = _html.escape(_m.group(0) if _m else str(i+1))
        hue = (i * 47) % 360
        if sc.get("image"):
            media = f'<div class="media-card" id="{sid}img" style="background-image:url(\'{sc["image"]}\')"></div>'
            bg = f'<div class="sc-bg" style="background:radial-gradient(circle at 20% 20%,hsl({hue},72%,28%),transparent 34%),linear-gradient(145deg,#071124,#120a24 60%,#050713)"></div>'
        else:
            media = f'<div class="media-card abstract" id="{sid}img"><span>{kw}</span></div>'
            bg = f'<div class="sc-bg" id="{sid}img" style="background:radial-gradient(circle at 18% 22%,hsl({hue},70%,32%),transparent 34%),radial-gradient(circle at 82% 18%,hsl({(hue+90)%360},68%,30%),transparent 28%),linear-gradient(145deg,#071124,#120a24 60%,#050713)"></div>'
        layout = i % 4
        if layout == 0:
            extra = f'<div class="data-badge"><b>{num}</b><span>điểm chính</span></div>'
        elif layout == 1:
            extra = f'<div class="quote-mark">“</div><div class="keyword-chip">{kw}</div>'
        elif layout == 2:
            extra = f'<div class="timeline"><i></i><i></i><i></i></div><div class="keyword-chip">{kw}</div>'
        else:
            extra = f'<div class="orb o1"></div><div class="orb o2"></div><div class="keyword-chip">{kw}</div>'
        scene_divs.append(f'''
  <div class="scene layout-{layout}" id="{sid}" data-start="{st}" data-duration="{sd}">
    {bg}
    <div class="mesh"></div>
    {media}
    {extra}
    <div class="copy-card" id="{sid}sub">{sub}</div>
  </div>''')
        # timeline: fade in, ken burns over scene, fade out
        kb_scale = 1.0 + (0.10 if i % 2 == 0 else 0.06)
        kb_x = 2 if i % 2 == 0 else -2
        scene_tl.append(f'''
  tl.set("#{sid}",{{opacity:0}},{st});
  tl.to("#{sid}",{{opacity:1,duration:.6,ease:"power2.out"}},{st});
  tl.fromTo("#{sid} .sc-bg",{{scale:1.0,xPercent:0}},{{scale:{kb_scale},xPercent:{kb_x},duration:{sd},ease:"none"}},{st});
  tl.fromTo("#{sid} .media-card",{{opacity:0,y:28,scale:.96}},{{opacity:1,y:0,scale:1,duration:.65,ease:"power3.out"}},{st}+.18);
  tl.fromTo("#{sid}sub",{{opacity:0,y:24}},{{opacity:1,y:0,duration:.5,ease:"power3.out"}},{st}+.25);
  tl.to("#{sid}",{{opacity:0,duration:.5,ease:"power2.in"}},{round(st + sd - 0.45, 2)});''')

    scenes_html = "".join(scene_divs)
    scenes_js = "".join(scene_tl)

    return f'''<!doctype html>
<html lang="vi"><head><meta charset="UTF-8"/><meta name="viewport" content="width={w},height={h}"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#06061a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
#root{{position:relative;width:{w}px;height:{h}px;background:#06061a}}
.scene{{position:absolute;inset:0;overflow:hidden;background:#06061a}}
.sc-bg{{position:absolute;inset:0;will-change:transform;filter:saturate(1.15)}}
.mesh{{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:{pct(0.055)}px {pct(0.055)}px;mask-image:radial-gradient(circle at 50% 45%,#000 0%,transparent 78%);opacity:.55}}
.media-card{{position:absolute;top:{pct(0.225)}px;right:{int(w*0.06)}px;width:{int(w*0.40)}px;height:{pct(0.40)}px;border-radius:{pct(0.028)}px;background-size:cover;background-position:center;box-shadow:0 {pct(0.018)}px {pct(0.05)}px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.22);overflow:hidden}}
.media-card.abstract{{display:grid;place-items:center;background:linear-gradient(135deg,rgba(159,140,255,.35),rgba(103,221,255,.18));font-size:{pct(0.022)}px;font-weight:900;color:#fff;text-align:center;padding:{pct(0.02)}px}}
.copy-card{{position:absolute;left:{int(w*0.06)}px;right:{int(w*0.06)}px;bottom:{pct(0.18)}px;min-height:{pct(0.18)}px;padding:{pct(0.026)}px {pct(0.028)}px;border-radius:{pct(0.032)}px;background:linear-gradient(135deg,rgba(255,255,255,.16),rgba(255,255,255,.07));border:1px solid rgba(255,255,255,.23);backdrop-filter:blur(14px);font-size:{pct(0.024)}px;font-weight:850;color:#fff;line-height:1.32;text-shadow:0 2px 16px rgba(0,0,0,.75);display:flex;align-items:center;justify-content:center;text-align:left}}
.layout-1 .copy-card{{text-align:center;font-size:{pct(0.026)}px}}
.layout-2 .copy-card{{left:{int(w*0.10)}px;right:{int(w*0.10)}px}}
.keyword-chip{{position:absolute;top:{pct(0.23)}px;left:{int(w*0.07)}px;padding:{pct(0.01)}px {pct(0.018)}px;border-radius:999px;background:rgba(103,221,255,.14);border:1px solid rgba(103,221,255,.38);color:#67ddff;font-size:{pct(0.014)}px;font-weight:900;text-transform:uppercase;letter-spacing:1.5px}}
.data-badge{{position:absolute;top:{pct(0.25)}px;left:{int(w*0.08)}px;width:{pct(0.14)}px;height:{pct(0.14)}px;border-radius:{pct(0.03)}px;background:linear-gradient(135deg,#67ddff,#9f8cff);display:flex;flex-direction:column;align-items:center;justify-content:center;color:#081020;box-shadow:0 18px 46px rgba(0,0,0,.35)}}
.data-badge b{{font-size:{pct(0.032)}px;line-height:1;max-width:90%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center}}.data-badge span{{font-size:{pct(0.01)}px;font-weight:900;text-transform:uppercase}}
.quote-mark{{position:absolute;top:{pct(0.18)}px;left:{int(w*0.08)}px;font-size:{pct(0.16)}px;font-weight:900;color:rgba(255,255,255,.18);line-height:.8}}
.timeline{{position:absolute;top:{pct(0.26)}px;left:{int(w*0.08)}px;right:{int(w*0.08)}px;height:{pct(0.05)}px;display:flex;gap:{pct(0.018)}px}}.timeline i{{flex:1;border-radius:999px;background:linear-gradient(90deg,#67ddff,#9f8cff);opacity:.75}}
.orb{{position:absolute;border-radius:50%;filter:blur(8px);opacity:.55}}.o1{{width:{pct(0.18)}px;height:{pct(0.18)}px;top:{pct(0.23)}px;left:{int(w*0.12)}px;background:#67ddff}}.o2{{width:{pct(0.13)}px;height:{pct(0.13)}px;top:{pct(0.32)}px;right:{int(w*0.12)}px;background:#ff8da1}}
.accent{{position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#9f8cff,#67ddff,#ff8da1);z-index:20}}
.logo{{position:absolute;top:{pct(0.035)}px;left:0;right:0;text-align:center;font-size:{pct(0.018)}px;font-weight:900;color:#67ddff;letter-spacing:4px;z-index:20;text-shadow:0 2px 12px rgba(0,0,0,.7)}}
.styletag{{position:absolute;top:{pct(0.085)}px;left:50%;transform:translateX(-50%);font-size:{pct(0.012)}px;font-weight:800;color:#0b1020;background:linear-gradient(135deg,#67ddff,#9f8cff);padding:{pct(0.006)}px {pct(0.018)}px;border-radius:{pct(0.02)}px;letter-spacing:2px;z-index:20}}
.vtitle{{position:absolute;top:{pct(0.13)}px;left:{int(w*0.06)}px;right:{int(w*0.06)}px;font-size:{pct(0.032)}px;font-weight:900;color:#fff;line-height:1.14;text-shadow:0 3px 22px rgba(0,0,0,.85);z-index:20;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.meta{{position:absolute;bottom:{pct(0.05)}px;left:0;right:0;text-align:center;font-size:{pct(0.013)}px;color:rgba(255,255,255,.7);z-index:20;text-shadow:0 1px 6px rgba(0,0,0,.8)}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur_int}" data-width="{w}" data-height="{h}">
  <audio id="voice-main" data-start="0" data-duration="{dur_int}" data-track-index="0" data-volume="1.0" src="{voice_path}"></audio>
  <audio id="bgm-main" data-start="0" data-duration="{dur_int}" data-track-index="1" data-volume="0.12" src="{bgm_path}"></audio>
{scenes_html}
  <div class="accent" id="accent"></div>
  <div class="logo" id="logo">AI WORLD</div>
  <div class="styletag" id="tag">{tag}</div>
  <div class="vtitle" id="vtitle">{safe_title}</div>
  <div class="meta" id="meta">AI World News &#183; {date_str}</div>
</div>
<script>
window.__timelines=window.__timelines||{{}};
const tl=gsap.timeline({{paused:true}});
const DUR={dur_int};
tl.from("#accent",{{scaleX:0,transformOrigin:"left",duration:.5,ease:"power3.out"}},0);
tl.from("#logo",{{opacity:0,y:-12,duration:.5}},.2);
tl.from("#tag",{{opacity:0,scale:.9,duration:.4,ease:"back.out(1.3)"}},.4);
tl.from("#vtitle",{{opacity:0,y:24,duration:.7,ease:"power3.out"}},.6);
tl.to("#vtitle",{{opacity:0,y:-16,duration:.5,ease:"power2.in"}},3.2);
{scenes_js}
tl.from("#meta",{{opacity:0,duration:.5}},1.0);
window.__timelines["main"]=tl;
tl.play(0);
function seekTo(t){{tl.seek(t);}}
window.seekTo=seekTo;
</script>
</body></html>'''
