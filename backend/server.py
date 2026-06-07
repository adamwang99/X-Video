#!/usr/bin/env python3
"""
X-Video Backend — FastAPI Server
Chạy trên Macmini M4 (192.168.1.12:8767)
"""

import subprocess, json, os, re, shutil, time, hashlib, threading, sqlite3, uuid
from pathlib import Path
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn, urllib.request; _ur = urllib.request
import subprocess as _sp, pathlib as _pl
import html as _html
try:
    import xvideo_scenes
    import xvideo_pexels
    import xvideo_apikeys
    import xvideo_storyboard
except Exception as _e:
    xvideo_scenes = None
    xvideo_pexels = None
    xvideo_apikeys = None
    xvideo_storyboard = None
    print('[scene] module load failed:', _e)
try:
    import xvideo_hv
except Exception as _e:
    xvideo_hv = None
    print('[hv] bridge load failed:', _e)

# CONFIG
OUTPUT_DIR = Path(__file__).parent.parent / "output"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
PROJECT_DIR = Path(__file__).parent.parent / "render-project"
BGM_DIR = Path(__file__).parent.parent / "bgm_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
# API key store init + seed Pexels key from existing config
try:
    if xvideo_apikeys:
        xvideo_apikeys.init(PROJECT_DIR / "api_keys.json")
        if not xvideo_apikeys.get_active_key("pexels") and xvideo_pexels and getattr(xvideo_pexels, "PEXELS_KEY", ""):
            xvideo_apikeys.add_key("pexels", xvideo_pexels.PEXELS_KEY, "Default Pexels key")
        if xvideo_pexels and hasattr(xvideo_pexels, "set_keymanager"):
            xvideo_pexels.set_keymanager(xvideo_apikeys)
except Exception as _ke:
    print(f"[apikeys] init failed: {_ke}")
# LLM provider adapter + lightweight settings store
try:
    import xvideo_llm
    if xvideo_apikeys and hasattr(xvideo_llm, "set_keymanager"):
        xvideo_llm.set_keymanager(xvideo_apikeys)
except Exception as _le:
    xvideo_llm = None
    print(f"[llm] init failed: {_le}")

SETTINGS_PATH = PROJECT_DIR / "app_settings.json"
def load_settings():
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {"llm_provider": "local_ollama", "llm_model": "", "llm_base_url": ""}
def save_settings(d):
    cur = load_settings(); cur.update({k: v for k, v in d.items() if v is not None})
    tmp = str(SETTINGS_PATH) + ".tmp"
    Path(tmp).write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    os.replace(tmp, str(SETTINGS_PATH)); return cur
BGM_DIR.mkdir(parents=True, exist_ok=True)

APP_VERSION = "1.28.3"

# Resolution -> height multiplier (portrait height)
RES_MAP = {"hd": 720, "fhd": 1080, "2k": 1440, "4k": 2160}
# Aspect -> (w, h) for portrait — base at 1080p
ASPECT_MAP = {"doc": (9, 16), "ngang": (16, 9), "vuong": (1, 1)}
# Music styles
BGM_MAP = {
    "ambient": [(220, 0.12), (330, 0.08), (440, 0.06)],
    "corporate": [(262, 0.10), (330, 0.10), (392, 0.08)],
    "tech": [(440, 0.14), (554, 0.10), (659, 0.06)],
    "cinematic": [(130, 0.15), (196, 0.10), (262, 0.08)],
}

# FIX-CORS: restrict to LAN origin instead of wildcard
ALLOWED_ORIGINS = [
    "http://192.168.1.12:8767",
    "http://localhost:8767",
    "http://127.0.0.1:8767",
    "tauri://localhost",
]

app = FastAPI(title="X-Video", version=APP_VERSION)

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    hook: Optional[str] = None
    cta: Optional[str] = None
    aspect: str = "doc"
    language: str = "vi"
    voice: str = "female_south"
    speed: str = "normal"
    style: str = "news"
    resolution: str = "fhd"
    music: str = "ambient"
    image_url: str = None  # source URL for images when text/script is edited
    use_stock: bool = None  # use Pexels stock photos to fill scenes (default True)
    review_storyboard: bool = True  # pause after storyboard built for user review
    target_length: int = 0  # seconds; 0 = auto by content length

class RewriteRequest(BaseModel):
    text: str
    title: Optional[str] = None
    style: str = "news"          # news|reportage|analysis|story|hot
    length: int = 60             # target video length in seconds
    tone: Optional[str] = None   # optional extra tone hint
    random: bool = False         # pick a random style/tone for variety (n8n use)
    llm_provider: Optional[str] = None  # override saved provider for this call
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None

jobs_lock = threading.Lock()
# ---- Job DB (SQLite WAL mode) ----
JOB_DB = PROJECT_DIR / "jobs.db"

def _job_db():
    _tls = getattr(_job_db, "_tls", None)
    if _tls is None:
        _job_db._tls = threading.local()
        _tls = _job_db._tls
    if not hasattr(_tls, "conn"):
        conn = sqlite3.connect(str(JOB_DB))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            request_json TEXT,
            voice_snapshot TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.commit()
        _tls.conn = conn
    return _tls.conn

def _job_create(jid, req_json, voice_snap="{}"):
    db = _job_db()
    db.execute("INSERT OR REPLACE INTO jobs(job_id, status, progress, request_json, voice_snapshot) VALUES(?, 'queued', 0, ?, ?)",
               (jid, req_json, voice_snap))
    db.commit()
    # FIX: invalidate list cache so new job is visible
    _jobs_cache.pop(jid, None)
    _jobs_cache["__dirty__"] = True

def _job_update(jid, **fields):
    db = _job_db()
    sets = [f"{k}=?" for k in fields]
    vals = list(fields.values()) + [jid]
    db.execute(f"UPDATE jobs SET {', '.join(sets)}, updated_at=datetime('now') WHERE job_id=?", vals)
    db.commit()
    # FIX: keep cache in sync
    if jid in _jobs_cache:
        _jobs_cache[jid].update(fields)

def _job_get(jid):
    db = _job_db()
    row = db.execute("SELECT * FROM jobs WHERE job_id=?", (jid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    result = {"job_id": d["job_id"], "status": d["status"], "progress": d["progress"], "error": d.get("error")}
    if d.get("result_json"):
        try:
            r = json.loads(d["result_json"])
            for k, v in r.items():
                result[k] = v
        except Exception:
            pass
    return result

# FIX: cache với dirty flag thay vì check `if _jobs_cache` mãi mãi
_jobs_cache = {}
def _job_list():
    if not _jobs_cache.get("__dirty__", True) and len(_jobs_cache) > 1:
        return {k: v for k, v in _jobs_cache.items() if k != "__dirty__"}
    db = _job_db()
    fresh = {}
    for row in db.execute("SELECT * FROM jobs WHERE status NOT IN ('done','error') ORDER BY created_at DESC LIMIT 50"):
        d = dict(row)
        result = {"job_id": d["job_id"], "status": d["status"], "progress": d["progress"], "error": d.get("error")}
        if d.get("result_json"):
            try:
                r = json.loads(d["result_json"])
                for k, v in r.items():
                    result[k] = v
            except Exception:
                pass
        fresh[d["job_id"]] = result
    for row in db.execute("SELECT * FROM jobs WHERE status IN ('done','error') ORDER BY created_at DESC LIMIT 20"):
        d = dict(row)
        if d["job_id"] not in fresh:
            result = {"job_id": d["job_id"], "status": d["status"], "progress": d["progress"], "error": d.get("error")}
            if d.get("result_json"):
                try:
                    r = json.loads(d["result_json"])
                    for k, v in r.items():
                        result[k] = v
                except Exception:
                    pass
            fresh[d["job_id"]] = result
    _jobs_cache.clear()
    _jobs_cache.update(fresh)
    _jobs_cache["__dirty__"] = False
    return fresh

def clean_html(h):
    # FIX: strip script/style blocks trước, sau đó strip tags, rồi decode entities
    if not h:
        return ""
    # 1) remove script/style/noscript blocks entirely
    h = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', ' ', h, flags=re.DOTALL | re.IGNORECASE)
    # 2) drop all remaining tags
    h = re.sub(r'<[^>]+>', ' ', h)
    # 3) decode ALL HTML entities (named &amp; AND numeric &#8220; &#8221;)
    h = _html.unescape(h)
    # 4) normalize smart punctuation to plain ASCII for clean TTS + captions
    repl = {
        '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
        '\u2013': '-', '\u2014': '-', '\u2026': '...', '\u00a0': ' ',
    }
    for k, v in repl.items():
        h = h.replace(k, v)
    # 5) collapse whitespace
    return re.sub(r'\s+', ' ', h).strip()

def categorize(slug):
    if "phan-bien" in slug or "thuc-thi" in slug: return "TỔNG HỢP"
    if "evo-core" in slug: return "EVO-CORE"
    return "CÔNG NGHỆ"

def fetch_content(url):
    slug = url.rstrip('/').split('/')[-1].split('?')[0]
    wp = f"http://192.168.1.9:8080/vi/wp-json/wp/v2/posts?slug={slug}"
    try:
        with urllib.request.urlopen(urllib.request.Request(wp), timeout=10) as r:
            posts = json.loads(r.read())
            if posts:
                p = posts[0]
                return (clean_html(p['title']['rendered']),
                        clean_html(p.get('content',{}).get('rendered','')),
                        clean_html(p.get('excerpt',{}).get('rendered',p['title']['rendered'])),
                        p.get('date','')[:10], categorize(p.get('slug',slug)))
    except: pass
    # Fallback parse HTML — FIX: giới hạn 512KB để tránh OOM
    req_obj = urllib.request.Request(url)
    with urllib.request.urlopen(req_obj, timeout=10) as r:
        html = r.read(524288).decode('utf-8', errors='replace')
    m = re.search(r'<title>(.*?)</title>', html)
    title = clean_html(m.group(1)) if m else slug.replace('-',' ')
    return title, html, title, datetime.now().strftime('%Y-%m-%d'), "TIN TỨC"


def get_article_images(url):
    """Fetch article images (featured + content) via WP API with _embed."""
    try:
        slug = url.rstrip('/').split('/')[-1].split('?')[0]
        wp = f"http://192.168.1.9:8080/vi/wp-json/wp/v2/posts?slug={slug}&_embed=1"
        with urllib.request.urlopen(urllib.request.Request(wp), timeout=10) as r:
            posts = json.loads(r.read())
        if posts and xvideo_scenes:
            p = posts[0]
            content_html = p.get('content', {}).get('rendered', '')
            return xvideo_scenes.extract_images(url, content_html, p)
    except Exception as e:
        print(f"[scene] get_article_images fail: {e}", flush=True)
    return []

def generate_voice(text, voice, output_path, language="vi"):
    """TTS — Macmini VieNeu (Vietnamese) or macOS say (English)"""
    wc = len(text.split())
    actual_engine = "macOS_say"  # default, updated if VieNeu succeeds

    if language == "vi":
        import urllib.request as ureq
        import json as jsonmod
        voice_map = {"female_south": "female_south", "female_north": "female_north",
                     "male_south": "male_south", "male_north": "male_north"}

        # Check if voice is a clone (not in builtin map) — fetch ref from voice_library
        if voice not in voice_map and voice:
            vi_voice = "female_south"  # fallback
            try:
                vl_req = ureq.Request(f"http://127.0.0.1:8769/api/voices/{voice}")
                with ureq.urlopen(vl_req, timeout=5) as vlr:
                    vld = jsonmod.loads(vlr.read())
                ref_audio = vld.get("ref_audio_path") or vld.get("sample_path", "")
                ref_txt = vld.get("ref_text", "")
                if ref_audio and ref_txt:
                    # Call clone-speech with the script text
                    clone_payload = jsonmod.dumps({
                        "input": text, "ref_audio_path": ref_audio,
                        "ref_text": ref_txt, "response_format": "mp3"
                    }).encode()
                    clone_req = ureq.Request("http://localhost:6023/v1/audio/clone-speech",
                                            data=clone_payload, method="POST")
                    clone_req.add_header("Content-Type", "application/json")
                    with ureq.urlopen(clone_req, timeout=300) as cr:
                        with open(output_path, "wb") as cf:
                            cf.write(cr.read())
                    r_dur = subprocess.run(['/opt/homebrew/bin/ffprobe','-v','quiet',
                            '-show_entries','format=duration','-of','csv=p=0',str(output_path)],
                           capture_output=True, text=True, timeout=10)
                    dur = float(r_dur.stdout.strip() or 50)
                    return int(dur), wc, f"vieneu_clone_{voice}"
                else:
                    print(f"[clone] Voice {voice} has no ref_text, falling back")
            except Exception as e:
                print(f"[clone] Clone voice fetch failed: {e}, falling back")
        else:
            vi_voice = voice_map.get(voice, "female_south")
        payload = jsonmod.dumps({
            "model": "vieneu", "input": text,
            "voice": vi_voice, "speed": 1.0
        }).encode()
        req = ureq.Request("http://localhost:6023/v1/audio/speech",
                          data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with ureq.urlopen(req, timeout=120) as r:
                with open(output_path, "wb") as f:
                    f.write(r.read())
            r_dur = subprocess.run(['/opt/homebrew/bin/ffprobe','-v','quiet','-show_entries','format=duration',
                                    '-of','csv=p=0',str(output_path)],
                                   capture_output=True, text=True, timeout=10)
            dur = float(r_dur.stdout.strip() or 50)
            return int(dur), wc, "vieneu"
        except Exception as e:
            # FIX: log warning rõ ràng khi fallback
            print(f"[WARN] VieNeu TTS failed ({e}), falling back to macOS say — voice snapshot sẽ phản ánh thực tế")

    # Fallback: macOS say
    rate = min(210, max(140, int(wc / 50 * 60)))
    script_path = output_path.parent / "script.txt"
    with open(script_path, "w") as f: f.write(text)
    aiff = output_path.parent / "temp.aiff"
    # dùng voice mặc định macOS nếu voice id là VieNeu format
    mac_voice = voice if voice not in ("female_south","female_north","male_south","male_north") else "Samantha"
    subprocess.run(['say','-v', mac_voice,'-r',str(rate),'-f',str(script_path),'-o',str(aiff)], capture_output=True, timeout=60)
    subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-i',str(aiff),'-acodec','libmp3lame','-b:a','128k',str(output_path)], capture_output=True, timeout=60)
    if aiff.exists(): aiff.unlink()
    r = subprocess.run(['/opt/homebrew/bin/ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',str(output_path)], capture_output=True, text=True, timeout=10)
    dur = float(r.stdout.strip() or 50)
    return int(dur), wc, f"macOS_say_{mac_voice}"

def generate_bgm(music_style, duration, output_path):
    # Check custom BGM file trước
    for ext in ("mp3", "wav", "m4a"):
        custom = BGM_DIR / f"{music_style}.{ext}"
        if custom.exists():
            subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-i',str(custom),
                            '-t',str(duration),'-acodec','libmp3lame','-b:a','128k',str(output_path)],
                           capture_output=True, timeout=30)
            return
    if music_style == "none":
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t',str(duration),str(output_path)], capture_output=True, timeout=10)
        return
    tones = BGM_MAP.get(music_style, BGM_MAP["ambient"])
    # FIX: build ffmpeg args as list thay vì string.split() để tránh shell injection
    cmd = ['/opt/homebrew/bin/ffmpeg', '-y']
    for f, _ in tones:
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency={f}:duration={duration}']
    weights = ':'.join([str(w) for _, w in tones])
    filter_cmd = f'[0:a][1:a][2:a]amix=inputs={len(tones)}:duration=first:weights={weights},afade=t=in:d=1,afade=t=out:st={duration-2}:d=2,volume=0.07'
    cmd += ['-filter_complex', filter_cmd, '-acodec', 'libmp3lame', '-b:a', '64k', str(output_path)]
    subprocess.run(cmd, capture_output=True, timeout=30)

def make_html(aspect, title, date_str, duration, voice_path, bgm_path, style="news", resolution="fhd"):
    ar_w, ar_h = ASPECT_MAP.get(aspect, (9, 16))
    base_h = RES_MAP.get(resolution, 1080)
    h = base_h
    w = int(h * ar_w / ar_h / 2) * 2
    pct = lambda p: int(h * p)

    style_desc = {"news":"📺 BẢN TIN","reportage":"🎬 PHÓNG SỰ","analysis":"📊 PHÂN TÍCH","story":"📖 CÂU CHUYỆN","tutorial":"🎓 HƯỚNG DẪN","hot":"🔥 TIN NÓNG"}

    # FIX: escape title để tránh inject vào HTML
    import html as _html
    safe_title = _html.escape(title[:200])
    dur_int = int(duration)

    return f'''<!doctype html>
<html lang="vi"><head><meta charset="UTF-8"/><meta name="viewport" content="width={w},height={h}"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#06061a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
#root{{position:relative;width:{w}px;height:{h}px}}
.bg-grad{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 20%,#1a1a4e 0%,#0a0a1a 55%,#06061a 100%)}}
.bg-grid{{position:absolute;inset:0;opacity:.04;background-image:linear-gradient(rgba(255,255,255,.1)1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.1)1px,transparent 1px);background-size:40px 40px}}
.accent{{position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#6366f1,#8b5cf6,#d946ef)}}
.logo{{position:absolute;top:{pct(0.04)}px;left:0;right:0;text-align:center;font-size:{pct(0.018)}px;font-weight:900;color:#6366f1;letter-spacing:4px;opacity:0.8}}
.styletag{{position:absolute;top:{pct(0.10)}px;left:50%;transform:translateX(-50%);font-size:{pct(0.01)}px;font-weight:700;color:#a78bfa;background:rgba(99,102,241,.12);padding:{pct(0.005)}px {pct(0.015)}px;border-radius:{pct(0.008)}px;letter-spacing:2px}}
.title{{position:absolute;top:{pct(0.20)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px;font-size:{pct(0.03)}px;font-weight:900;color:#fff;line-height:1.12;letter-spacing:-.5px}}
.content{{position:absolute;top:{pct(0.45)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px;font-size:{pct(0.016)}px;font-weight:400;color:rgba(255,255,255,.75);line-height:1.45;max-height:{pct(0.20)}px;overflow:hidden}}
.cta{{position:absolute;bottom:{pct(0.18)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px;text-align:center;font-size:{pct(0.017)}px;font-weight:700;color:#c4b5fd;line-height:1.3}}
.meta{{position:absolute;bottom:{pct(0.10)}px;left:0;right:0;text-align:center;font-size:{pct(0.012)}px;color:rgba(255,255,255,.40)}}
.circle{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(99,102,241,.08)0%,transparent 70%);pointer-events:none}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur_int}" data-width="{w}" data-height="{h}">
  <audio id="voice-main" data-start="0" data-duration="{dur_int}" data-track-index="0" data-volume="1.0" src="{voice_path}"></audio>
  <div class="bg-grad"></div><div class="bg-grid"></div>
  <div class="circle" style="width:{int(w*0.3)}px;height:{int(w*0.3)}px;top:-{int(h*0.04)}px;right:-{int(w*0.06)}px" id="c1"></div>
  <div class="circle" style="width:{int(w*0.18)}px;height:{int(w*0.18)}px;top:{int(h*0.4)}px;left:-{int(w*0.04)}px" id="c2"></div>
  <div class="circle" style="width:{int(w*0.22)}px;height:{int(w*0.22)}px;bottom:{int(h*0.2)}px;right:-{int(w*0.06)}px" id="c3"></div>
  <div class="accent" id="accent"></div>
  <div class="logo" id="logo">AI WORLD</div>
  <div class="styletag" id="tag">{style_desc.get(style,"📺 TIN TỨC")}</div>
  <div class="title" id="title">{safe_title}</div>
  <div class="content" id="content">Tin tức AI mới nhất từ AI World. Giải pháp doanh nghiệp AI First.</div>
  <div class="cta" id="cta"></div>
  <div class="meta" id="meta">AI World News &#183; {date_str}</div>
</div>
<script>
window.__timelines=window.__timelines||{{}};
const tl=gsap.timeline({{paused:true}});
const DUR={dur_int};
tl.from("#accent",{{scaleX:0,transformOrigin:"left",duration:.5,ease:"power3.out",delay:.2}},0);
tl.from("#c1",{{opacity:0,scale:.4,duration:1,ease:"power2.out"}},.2);
tl.from("#c2",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.5);
tl.from("#c3",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.6);
tl.from("#logo",{{opacity:0,y:-15,duration:.5,ease:"power3.out"}},.3);
tl.from("#tag",{{opacity:0,y:-10,scale:.9,duration:.4,ease:"back.out(1.3)"}},.5);
tl.from("#title",{{opacity:0,y:30,duration:.7,ease:"power3.out"}},.8);
tl.from("#content",{{opacity:0,y:20,duration:.6,ease:"power2.out"}},1.5);
tl.from("#cta",{{opacity:0,y:15,duration:.5,ease:"power2.out"}},DUR-5);
tl.from("#meta",{{opacity:0,duration:.5,ease:"power2.out"}},1.8);
tl.to("#c1",{{y:-20,duration:4,ease:"sine.inOut",yoyo:true,repeat:Math.floor(DUR/4)-1}},2);
tl.to("#c2",{{y:20,duration:5,ease:"sine.inOut",yoyo:true,repeat:Math.floor(DUR/5)-1}},2);
tl.to("#c3",{{y:-15,duration:4.5,ease:"sine.inOut",yoyo:true,repeat:Math.floor(DUR/4.5)-1}},2);
tl.to("#root>*",{{opacity:0,duration:1.5,ease:"power2.in"}},DUR-4);
window.__timelines["main"]=tl;
</script></body></html>'''

def _job_render(jid: str):
    """Phase 2: render storyboard -> video. Storyboard must already exist."""
    try:
        from pathlib import Path
        jd = PROJECT_DIR / jid
        sb = xvideo_storyboard.load(jd) if xvideo_storyboard else None
        if not sb:
            raise Exception("Storyboard not found - cannot render")
        _job_update(jid, status="rendering", progress=70)
        # build HTML from storyboard
        html = xvideo_storyboard.render_html(sb, "voice.mp3", "bgm.mp3",
                                              datetime.now().strftime('%Y-%m-%d'),
                                              ASPECT_MAP, RES_MAP)
        with open(jd/"index.html","w") as f: f.write(html)
        with open(jd/"hyperframes.json","w") as f:
            json.dump({"$schema":"https://hyperframes.heygen.com/schema/hyperframes.json","paths":{"blocks":"compositions","components":"compositions/components","assets":"assets"}}, f)
        env = os.environ.copy(); env["PATH"] = os.path.expanduser("~/.local/bin")+":"+env.get("PATH","")
        proc = subprocess.run(["npx","hyperframes@latest","render"], cwd=str(jd), capture_output=True, text=True, timeout=600, env=env)
        if proc.returncode != 0:
            raise Exception(f"Render fail: {proc.stderr[-300:]}")
        mp4s = sorted((jd/"renders").glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if not mp4s: raise Exception("No MP4 output")
        _job_update(jid, status="processing", progress=90)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_name = f"xvideo_{jid[:8]}_{ts}.mp4"
        out_path = OUTPUT_DIR / out_name
        shutil.copy(str(mp4s[0]), str(out_path))
        size_kb = out_path.stat().st_size // 1024
        # restore meta from job (jobs persisted in sqlite)
        cur = _job_get(jid) or {}
        meta = cur.get("result") if isinstance(cur.get("result"), dict) else {}
        if not meta:
            try: meta = json.loads(cur.get("result_json") or "{}")
            except Exception: meta = {}
        meta.update({"video_path": out_name, "duration": sb.get("total_duration"),
                     "size_kb": size_kb, "title": sb.get("title","")[:80]})
        _job_update(jid, status="done", progress=100, result_json=json.dumps(meta))
        _jobs_cache["__dirty__"] = True
    except Exception as e:
        _job_update(jid, status="error", progress=0, error=str(e))
        _jobs_cache["__dirty__"] = True


def _estimate_target_length(text, requested=0):
    """Return target seconds. 0/None = auto by content length."""
    words = len((text or "").split())
    if requested and int(requested) > 0:
        return max(15, int(requested))
    return int(max(30, min(360, round(words / 2.5))))

def _fit_narration_length(text, target_seconds):
    """Fit narration to a target length WITHOUT corrupting the reading text.

    Hard rule (CEO 2026-06-06): never inject "..." into the middle of the script.
    That destroyed sentences when read aloud. If content exceeds target, we trim
    whole sentences from the END only, keeping a clean, readable narration. If it
    barely exceeds, we keep it as-is and let scene durations stretch.
    """
    if not text:
        return ""
    text = text.strip()
    target_words = int(max(40, target_seconds * 2.6))
    words = text.split()
    # Keep as-is unless it wildly exceeds the target.
    if len(words) <= target_words * 1.4:
        return text
    # Trim by full sentences from the end so the script stays coherent.
    import re as _re
    sents = [p.strip() for p in _re.split(r"(?<=[.!?;])\s+", text) if p.strip()]
    out, wc = [], 0
    for sent in sents:
        swc = len(sent.split())
        if out and wc + swc > target_words:
            break
        out.append(sent); wc += swc
    if not out:
        out = sents[:1] if sents else [text]
    return " ".join(out)

def process_job(jid: str, req: GenerateRequest):
    """Phase 1: build voice/bgm/storyboard. If review_storyboard=False, auto-render."""
    try:
        _job_update(jid, status="processing", progress=5)
        jd = PROJECT_DIR / jid; jd.mkdir(exist_ok=True)

        _job_update(jid, status="processing", progress=15)
        if req.text:
            # edited script mode: text is narration; optional image_url for visuals
            title = (req.text.split(chr(10))[0][:150]).strip() or req.text[:150]
            content = req.text; excerpt = req.text[:400]
            date_str = datetime.now().strftime('%Y-%m-%d'); category = "TIN TỨC"
        elif req.url:
            title, content, excerpt, date_str, category = fetch_content(req.url)
        else:
            raise ValueError("Cần url hoặc text")

        hook = req.hook or f"Tin nóng: {title[:50]}..."
        cta = req.cta or "Theo dõi AI World để cập nhật tin tức công nghệ mới nhất!"

        _job_update(jid, status="processing", progress=30)
        narration_src = content or excerpt or title
        target_seconds = _estimate_target_length(narration_src, getattr(req, "target_length", 0))
        narration = _fit_narration_length(narration_src, target_seconds)
        voice_text = narration
        duration, wc, actual_engine = generate_voice(voice_text, req.voice, jd/"voice.mp3", req.language)

        # FIX: voice_snapshot ghi lại engine thực sự dùng (kể cả fallback)
        voice_snap = json.dumps({"voice": req.voice, "language": req.language, "engine": actual_engine})
        _job_update(jid, voice_snapshot=voice_snap)

        _job_update(jid, status="processing", progress=45)
        generate_bgm(req.music, duration, jd/"bgm.mp3")

        _job_update(jid, status="processing", progress=50)
        # Build storyboard (scenes + images) - then pause for user review if requested
        if not xvideo_storyboard or not xvideo_scenes:
            raise Exception("storyboard module not available")
        img_src = req.url or req.image_url
        images = get_article_images(img_src) if img_src else []
        local_imgs = xvideo_scenes.download_images(images, jd) if images else []
        scene_duration = max(duration, target_seconds if 'target_seconds' in locals() else duration)
        _tmp = xvideo_scenes.build_scenes(narration, local_imgs or [None], scene_duration)
        need = len(_tmp)
        _st = load_settings()
        _llm_opts = {"provider": _st.get("llm_provider") or "local_ollama",
                     "model": _st.get("llm_model") or None,
                     "base_url": _st.get("llm_base_url") or None}
        kws_used = []
        if ('xvideo_pexels' in globals() and xvideo_pexels) and len(local_imgs) < need and (req.use_stock if req.use_stock is not None else True):
            try:
                orient = xvideo_pexels.orientation_for_aspect(req.aspect)
                kws_used = xvideo_pexels.derive_keywords(title, content, llm_opts=_llm_opts)
                stock_urls = []
                for kw in kws_used:
                    stock_urls += xvideo_pexels.search_photos(kw, orient, per_page=4)
                    if len(local_imgs) + len(stock_urls) >= need: break
                extra = xvideo_scenes.download_images(stock_urls, jd) if stock_urls else []
                local_imgs = local_imgs + extra
                print(f"[pexels] added {len(extra)} stock photos (kw={kws_used})", flush=True)
            except Exception as _pe:
                print(f"[pexels] enrich failed: {_pe}", flush=True)
        sb = xvideo_storyboard.build_storyboard(title, content, narration, local_imgs,
                                                duration, req.aspect, req.style, req.resolution,
                                                keywords=kws_used, llm_opts=_llm_opts)
        xvideo_storyboard.save(jd, sb)
        # save preliminary meta so result_json has snapshot for later merge
        _job_update(jid, result_json=json.dumps({
            "title": title[:80], "category": category, "duration": duration,
            "word_count": wc, "style": req.style, "aspect": req.aspect,
            "tts_rate": actual_engine, "scene_count": len(sb["scenes"]),
        }))
        if req.review_storyboard:
            _job_update(jid, status="storyboard_ready", progress=60)
            print(f"[storyboard] built {len(sb['scenes'])} scenes - waiting user review", flush=True)
            _jobs_cache["__dirty__"] = True
            return  # pause; user calls /api/storyboard/{jid}/render to continue
        # auto-render
        _job_render(jid)
        return
    except Exception as e:
        _job_update(jid, status="error", progress=0, error=str(e))
        _jobs_cache["__dirty__"] = True

# ---- API ----

OLLAMA_URL = os.environ.get("XVIDEO_OLLAMA", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("XVIDEO_OLLAMA_MODEL", "hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M")

STYLE_TONE = {
    "news":      "giọng bản tin trung lập, súc tích, khách quan, ngắn gọn rõ ràng",
    "reportage": "giọng phóng sự, kể có bối cảnh, dẫn dắt sinh động nhưng vẫn chính xác",
    "analysis":  "giọng phân tích, mạch lạc, nêu nguyên nhân - hệ quả, có chiều sâu",
    "story":     "giọng kể chuyện gần gũi, có cảm xúc, cuốn người nghe",
    "hot":       "giọng tin nóng, dồn dập, nhấn mạnh tính thời sự, gây chú ý ngay",
}
STYLE_LIST = list(STYLE_TONE.keys())

def _strip_llm_noise(t):
    if not t:
        return ""
    # remove harmony-style channel tokens that this GGUF leaks
    t = re.sub(r'<\|?channel\|?>', ' ', t)
    t = re.sub(r'<\|[^>]*\|>', ' ', t)
    t = re.sub(r'<\|[^>]*>', ' ', t)
    t = re.sub(r'<[^>]*\|>', ' ', t)
    # drop a leading "thought"/"analysis" label if present
    t = re.sub(r'^\s*(thought|analysis|final)\s*[:\-]?\s*', '', t, flags=re.IGNORECASE)
    # strip surrounding quotes/markdown fences
    t = t.replace('```', ' ').strip().strip('"').strip()
    # Drop editorial/meta prefaces. The UI needs narration only, not assistant explanation.
    t = re.sub(r'^\s*(đây là|dưới đây là|sau đây là)[^:]{0,220}:\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^\s*[-–—]{2,}\s*', '', t)
    t = re.sub(r'^\s*(lời đọc video|lời dẫn|narration|bản chuyển thể)[^\n)]*\)\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^\s*(lời đọc video|lời dẫn|narration|bản chuyển thể)[^\n:]*[:：]\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\(?\s*nhạc nền\s*:[^)\n]{0,260}\)?', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'\(?\s*ghi chú\s*:[^)\n]{0,260}\)?', ' ', t, flags=re.IGNORECASE)
    parts = re.split(r'\s*[-–—]{3,}\s*', t)
    if len(parts) > 1:
        t = parts[-1]
    return re.sub(r'\s+', ' ', t).strip()

def _words_for_length(seconds):
    # Vietnamese TTS ~ 2.6 words/sec; clamp to a sane band
    w = int(max(20, min(600, round(seconds * 2.6))))
    return w

def llm_rewrite(text, title, style, length, tone, provider=None, model=None, base_url=None):
    words = _words_for_length(length)
    style_tone = STYLE_TONE.get(style, STYLE_TONE["news"])
    extra = (" " + tone) if tone else ""
    prompt = (
        "Bạn là biên tập viên video tiếng Việt. Viết lại đoạn nội dung dưới đây thành "
        "lời đọc (narration) cho video.\\n"
        "YÊU CẦU:\\n"
        "- Phong cách: " + style_tone + extra + ".\\n"
        "- Độ dài khoảng " + str(words) + " từ (cho video ~" + str(length) + " giây).\\n"
        "- GIỮ NGUYÊN mọi số liệu, tên riêng, dữ kiện quan trọng; chỉ đổi cách diễn đạt và ngữ điệu.\\n"
        "- KHÔNG thêm lời giới thiệu kiểu: 'Đây là bản...', 'LỜI ĐỌC VIDEO', 'Nhạc nền', 'Dưới đây là'.\\n"
        "- KHÔNG markdown, không tiêu đề, không separator, không ghi chú sản xuất.\\n"
        "- KHÔNG tự đổi ngôi sang 'tôi', 'chúng tôi', 'các bạn' nếu nội dung gốc không yêu cầu; ưu tiên giọng trung tính của AI World.\\n"
        "- Chỉ trả về đúng lời đọc sẽ đưa vào video, câu đầu tiên phải là câu narration thật.\\n\\n"
        + ("Tiêu đề: " + title + "\\n\\n" if title else "")
        + "Nội dung gốc:\\n" + text[:4000] + "\\n\\nLời đọc viết lại:"
    )
    temp = 0.8 if tone or style else 0.7
    # Route through the configured provider; fall back to local Ollama on any error.
    if provider and provider not in ("local", "ollama", "local_ollama") and xvideo_llm:
        try:
            resp = xvideo_llm.complete(prompt, provider=provider, model=model or None,
                                       json_mode=False, temperature=temp,
                                       max_tokens=words * 3 + 200, timeout=180, base_url=base_url)
            cleaned = _strip_llm_noise(resp or "")
            if cleaned:
                return cleaned
            print("[rewrite] provider", provider, "empty, fallback local", flush=True)
        except Exception as _pe:
            print("[rewrite] provider", provider, "failed, fallback local:", _pe, flush=True)
    payload = json.dumps({
        "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": temp, "num_predict": words * 3 + 200},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read())
    return _strip_llm_noise(out.get("response", ""))

@app.post("/api/rewrite")
def api_rewrite(req: RewriteRequest):
    if not (req.text or "").strip():
        return {"error": "Nội dung trống"}
    import random as _rnd
    style = req.style
    tone = req.tone
    if req.random:
        style = _rnd.choice(STYLE_LIST)
        tone = _rnd.choice([
            "thêm một câu hook mạnh ở đầu",
            "nhịp nhanh, câu ngắn",
            "ấm áp, gần gũi người xem",
            "chuyên nghiệp, điềm tĩnh",
            "trẻ trung, năng lượng cao",
        ])
    try:
        length_seconds = _estimate_target_length(req.text, int(req.length or 0))
        _st = load_settings()
        _prov = req.llm_provider or _st.get("llm_provider") or "local_ollama"
        _mdl = req.llm_model if req.llm_model is not None else _st.get("llm_model")
        _burl = req.llm_base_url if req.llm_base_url is not None else _st.get("llm_base_url")
        # If caller overrides provider for this run, persist it so the whole workflow stays consistent.
        if req.llm_provider:
            save_settings({"llm_provider": _prov, "llm_model": _mdl, "llm_base_url": _burl})
        rewritten = llm_rewrite(req.text, req.title, style, length_seconds, tone,
                                provider=_prov, model=_mdl or None, base_url=_burl or None)
        if not rewritten:
            return {"error": "Model không trả về nội dung"}
        wc = len(rewritten.split())
        return {"success": True, "text": rewritten, "style": style, "tone": tone,
                "word_count": wc, "target_seconds": length_seconds}
    except Exception as e:
        return {"error": "Rewrite lỗi: " + str(e)}

def llm_extract_clean(raw_text, title, provider=None, model=None, base_url=None):
    """Use the configured LLM to turn messy fetched text into clean readable article body.
    Keeps all facts/numbers/names; removes nav/boilerplate/ads/duplicate menus. Returns text or '' on failure."""
    if not xvideo_llm or not raw_text.strip():
        return ""
    prompt = (
        "Bạn là biên tập viên. Dưới đây là nội dung thô lấy từ một trang web (có thể lẫn menu, quảng cáo, "
        "thẻ điều hướng, ký tự rác). Hãy trích ra ĐÚNG phần nội dung bài viết chính, làm sạch thành văn bản đọc được.\n"
        "YÊU CẦU:\n"
        "- GIỮ NGUYÊN mọi số liệu, tên riêng, dữ kiện, trích dẫn quan trọng.\n"
        "- BỎ menu, nút chia sẻ, quảng cáo, 'đọc thêm', chân trang, nội dung trùng lặp.\n"
        "- KHÔNG tóm tắt, KHÔNG rút gọn ý; chỉ làm sạch và giữ trọn nội dung bài.\n"
        "- KHÔNG markdown, KHÔNG thêm lời bình, chỉ trả về văn bản bài viết.\n\n"
        + ("Tiêu đề: " + title + "\n\n" if title else "")
        + "Nội dung thô:\n" + raw_text[:8000] + "\n\nNội dung bài viết đã làm sạch:"
    )
    try:
        out = xvideo_llm.complete(prompt, provider=provider, model=model or None, json_mode=False,
                                  temperature=0.2, max_tokens=3000, timeout=180, base_url=base_url)
        return _strip_llm_noise(out or "")
    except Exception as _e:
        print("[prefetch] llm extract failed:", _e, flush=True)
        return ""

class PrefetchReq(BaseModel):
    url: str
    extract_mode: Optional[str] = "local"   # local | llm
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None

@app.get("/api/prefetch")
def api_prefetch(url: str):
    try:
        t, c, e, d, cat = fetch_content(url)
        return {"title": t[:200], "excerpt": e[:1200], "content": c[:12000], "source": url, "date": d, "category": cat, "word_count": len(c.split())}
    except Exception as ex:
        return {"error": str(ex)}

@app.post("/api/prefetch")
def api_prefetch_post(req: PrefetchReq):
    try:
        t, c, e, d, cat = fetch_content(req.url)
        c = c[:12000]
        mode = req.extract_mode or "local"
        used = "local"
        if mode == "llm":
            _st = load_settings()
            prov = req.llm_provider or _st.get("llm_provider") or "local_ollama"
            mdl = req.llm_model if req.llm_model is not None else _st.get("llm_model")
            burl = req.llm_base_url if req.llm_base_url is not None else _st.get("llm_base_url")
            cleaned = llm_extract_clean(c, t, provider=prov, model=mdl or None, base_url=burl or None)
            if cleaned:
                c = cleaned
                used = "llm:" + prov
        return {"title": t[:200], "excerpt": e[:1200], "content": c, "source": req.url,
                "date": d, "category": cat, "word_count": len(c.split()), "extract_used": used}
    except Exception as ex:
        return {"error": str(ex)}

@app.get("/api/templates")
def get_templates(): return {"doc":"Dọc 9:16","ngang":"Ngang 16:9","vuong":"Vuông 1:1"}

@app.get("/api/voices")
def get_voices():
    """Return all voices, with user cloned/favorite voices indexed first."""
    fallback = [
        {"id": "female_south", "name": "🇻🇳 Nữ Nam Bộ", "lang": "vi", "engine": "VieNeu", "source":"builtin"},
        {"id": "female_north", "name": "🇻🇳 Nữ Bắc Bộ", "lang": "vi", "engine": "VieNeu", "source":"builtin"},
        {"id": "male_south", "name": "🇻🇳 Nam Nam Bộ", "lang": "vi", "engine": "VieNeu", "source":"builtin"},
        {"id": "male_north", "name": "🇻🇳 Nam Bắc Bộ", "lang": "vi", "engine": "VieNeu", "source":"builtin"},
        {"id": "Samantha", "name": "🇺🇸 Samantha", "lang": "en", "engine": "macOS", "source":"builtin"},
        {"id": "Karen", "name": "🇦🇺 Karen", "lang": "en", "engine": "macOS", "source":"builtin"},
        {"id": "Daniel", "name": "🇬🇧 Daniel", "lang": "en", "engine": "macOS", "source":"builtin"},
    ]
    try:
        with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8769/api/voices"), timeout=5) as r:
            data = json.loads(r.read())
        voices = data.get("voices", []) or []
        def norm(v):
            raw_src = (v.get("source") or "builtin").lower()
            src = "cloned" if raw_src in ("clone", "cloned", "custom", "user") else raw_src
            fav = bool(v.get("is_favorite"))
            name = v.get("name") or v.get("id") or "Voice"
            if src == "cloned" and not name.startswith("🧬"):
                name = "🧬 " + name
            if fav and not name.startswith("⭐"):
                name = "⭐ " + name
            return {"id": v.get("id"), "name": name,
                    "lang": v.get("language") or v.get("lang") or "vi",
                    "engine": v.get("engine") or "unknown", "source": src,
                    "is_favorite": fav}
        out = [norm(v) for v in voices if v.get("id")]
        out.sort(key=lambda v: (0 if v.get("is_favorite") else 1, 0 if v.get("source") == "cloned" else 1, v.get("name","")))
        return {"voices": out or fallback}
    except Exception as e:
        print(f"[voices] voice library unavailable: {e}", flush=True)
        return {"voices": fallback}

@app.get("/api/preview-voice")
def preview_voice(voice: str, text: str = "Xin chào, đây là giọng đọc của X Video Studio", language: str = "vi"):
    """Quick voice preview - generates MP3 from TTS without video pipeline"""
    tdir = PROJECT_DIR / "preview"
    tdir.mkdir(parents=True, exist_ok=True)
    out = tdir / f"preview_{hashlib.md5(f'{voice}{text}'.encode()).hexdigest()[:8]}.mp3"
    if not out.exists():
        generate_voice(text, voice, out, language)
    return FileResponse(str(out), media_type="audio/mp3",
                       headers={"Access-Control-Allow-Origin": "*",
                                "Content-Disposition": "inline"})

# TTS readiness state — background warmup thread cập nhật liên tục
_tts_state = {"status": "warming_up", "engine": "vieneu", "detail": "Đang khởi động model...", "checked_at": 0}
_tts_lock = threading.Lock()

def _warmup_worker():
    """Background thread: thử gọi VieNeu mỗi 5s cho đến khi ready"""
    import time as _time
    attempt = 0
    while True:
        attempt += 1
        try:
            req_obj = _ur.Request("http://localhost:6023/v1/audio/speech",
                                  data=json.dumps({"model":"vieneu","input":"khởi động","voice":"female_south","speed":1.0}).encode(),
                                  method="POST")
            req_obj.add_header("Content-Type", "application/json")
            with _ur.urlopen(req_obj, timeout=20) as r:
                r.read(16)
            with _tts_lock:
                _tts_state["status"] = "ready"
                _tts_state["detail"] = "TTS sẵn sàng"
                _tts_state["checked_at"] = _time.time()
            print("[TTS] VieNeu ready")
            return  # done
        except Exception as e:
            with _tts_lock:
                _tts_state["status"] = "warming_up"
                _tts_state["detail"] = f"Đang tải model... (lần {attempt})"
                _tts_state["checked_at"] = _time.time()
            _time.sleep(5)

@app.get("/api/warmup-tts")
def warmup_tts():
    """Trả về TTS readiness state hiện tại (non-blocking)"""
    with _tts_lock:
        return dict(_tts_state)

# FIX: thêm endpoint bgm-files để frontend load được danh sách nhạc custom
@app.get("/api/bgm-files")
def get_bgm_files():
    """Liệt kê file MP3/WAV/M4A trong bgm_audio/"""
    files = []
    for ext in ("mp3", "wav", "m4a"):
        for f in sorted(BGM_DIR.glob(f"*.{ext}")):
            files.append({"id": f.stem, "name": f.stem.replace("-", " ").replace("_", " ").title(), "file": f.name})
    # Thêm built-in styles
    builtins = [
        {"id": "ambient", "name": "Ambient", "file": None},
        {"id": "corporate", "name": "Corporate", "file": None},
        {"id": "tech", "name": "Tech", "file": None},
        {"id": "cinematic", "name": "Cinematic", "file": None},
        {"id": "none", "name": "Không nhạc", "file": None},
    ]
    return {"files": files, "builtins": builtins}

@app.post("/api/generate", status_code=201)
def generate(req: GenerateRequest, bg: BackgroundTasks):
    if not req.url and not req.text:
        raise HTTPException(400, "Cần url hoặc text")
    # FIX: dùng uuid4 thay vì md5(timestamp+url) để tránh collision
    jid = uuid.uuid4().hex
    _job_create(jid, req.model_dump_json())
    bg.add_task(process_job, jid, req)
    return {"job_id": jid, "status": "queued", "check_url": f"/api/jobs/{jid}"}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    j = _job_get(job_id)
    if not j: raise HTTPException(404, "Not found")
    return j

@app.get("/api/jobs")
def list_jobs():
    return {"jobs": {k: {"status":v.get("status"),"progress":v.get("progress"),
        "title":v.get("title"),"video_path":v.get("video_path")} for k,v in _job_list().items()}}

@app.get("/output/{filename}")
def serve(filename: str):
    # FIX: path traversal protection
    try:
        fp = (OUTPUT_DIR / filename).resolve()
        output_resolved = OUTPUT_DIR.resolve()
        if not str(fp).startswith(str(output_resolved) + os.sep) and fp != output_resolved:
            raise HTTPException(403, "Forbidden")
    except Exception:
        raise HTTPException(403, "Forbidden")
    if not fp.exists(): raise HTTPException(404)
    return FileResponse(str(fp), media_type="video/mp4", headers={"Access-Control-Allow-Origin":"*"})

@app.get("/healthz")
def healthz(): return {"status":"ok","machine":"Macmini","gpu":"Apple M4","version": APP_VERSION}

# ===== VOICE LIBRARY PROXY =====
@app.get("/api/voice-library/voices")
def _vlv():
    try:
        r = _ur.Request("http://127.0.0.1:8769/api/voices")
        with _ur.urlopen(r, timeout=5) as resp:
            return __import__("json").loads(resp.read())
    except: return {"voices": [], "count": 0}

@app.get("/api/voice-library/custom-fields")
def _vlf():
    try:
        r = _ur.Request("http://127.0.0.1:8769/api/voice-library/custom-fields")
        with _ur.urlopen(r, timeout=5) as resp:
            return __import__("json").loads(resp.read())
    except: return {"custom_fields": []}

@app.get("/api/voice-library/tts-status")
def _vlt():
    try:
        r = _ur.Request("http://127.0.0.1:8769/api/tts-status")
        with _ur.urlopen(r, timeout=3) as resp:
            return __import__("json").loads(resp.read())
    except: return {"overall": "partial", "services": {}}

@app.post("/api/voice-library/voices/{voice_id}/favorite")
def _vlfa(voice_id: str):
    try:
        r = _ur.Request(f"http://127.0.0.1:8769/api/voices/{voice_id}/favorite", method="POST")
        with _ur.urlopen(r, timeout=5) as resp:
            return __import__("json").loads(resp.read())
    except: return {"success": False}

@app.delete("/api/voice-library/voices/{voice_id}")
def _vld(voice_id: str):
    try:
        r = _ur.Request(f"http://127.0.0.1:8769/api/voices/{voice_id}", method="DELETE")
        with _ur.urlopen(r, timeout=5) as resp:
            return __import__("json").loads(resp.read())
    except: return {"success": False}

@app.post("/api/clone-voice")
async def _clone_voice_proxy(
    file: UploadFile = File(...),
    name: str = Form(...),
    engine: str = Form("vieneu"),
    language: str = Form("vi"),
    gender: str = Form("unknown"),
    region: str = Form(None),
    lang: str = Form(None),
    age: str = Form(None),
    style_tag: str = Form(None),
    ref_text: str = Form(""),
):
    # Proxy to the voice library's clone endpoint
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        # Prepare the form data
        files = {"file": (file.filename, await file.read(), file.content_type)}
        # UI (index.html) sends "lang" instead of "language" — normalize
        eff_language = lang or language or "vi"
        data = {"name": name, "engine": engine, "language": eff_language, "gender": gender, "ref_text": ref_text}
        try:
            resp = await client.post(
                "http://127.0.0.1:8769/api/voices/clone",
                files=files,
                data=data,
            )
            return resp.json()
        except Exception as e:
            raise HTTPException(500, f"Voice library clone failed: {str(e)}")

@app.post("/api/try-tts")
def _try_tts(data: dict):
    text = data.get("text", "Xin chào")
    engine = data.get("engine", "vieneu")
    eps = {"vieneu":"http://127.0.0.1:6023/v1/audio/speech","omnivoice":"http://127.0.0.1:6024/v1/audio/speech","valtec":"http://127.0.0.1:6025/v1/audio/speech"}
    ep = eps.get(engine, eps["vieneu"])
    body = __import__("json").dumps({"model":engine,"input":text,"voice":"female_south","speed":1.0}).encode()
    req = _ur.Request(ep, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with _ur.urlopen(req, timeout=120) as resp:
            data = resp.read()
        from fastapi.responses import Response
        return Response(content=data, media_type="audio/mp3")
    except Exception as e:
        raise __import__("fastapi").HTTPException(503, f"TTS engine '{engine}' failed: {str(e)}")

# ---- Storyboard Management ----
class SceneReq(BaseModel):
    job_id: str
    scene_id: str = ""
    text: str = None
    image: str = None
    layout: str = None
    duration: float = None
    visual_type: str = None
    motion_preset: str = None
    asset_policy: str = None
    headline: str = None
    template_id: str = None
    aspect: str = "9:16"
    voice: str = None
    after_id: str = ""
    ordered_ids: list = []

@app.get("/api/storyboard/{job_id}")
def storyboard_get(job_id: str):
    if not xvideo_storyboard:
        return {"error": "storyboard module unavailable"}
    jd = PROJECT_DIR / job_id
    sb = xvideo_storyboard.load(jd)
    if not sb:
        return {"error": "Storyboard chua san sang"}
    return xvideo_storyboard.public_view(sb)

@app.post("/api/storyboard/scene/add")
def storyboard_scene_add(req: SceneReq):
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    sid = xvideo_storyboard.add_scene(sb, text=req.text or "Phan canh moi", image=req.image, after_id=req.after_id)
    xvideo_storyboard.save(jd, sb)
    return {"success": True, "id": sid}

@app.post("/api/storyboard/scene/update")
def storyboard_scene_update(req: SceneReq):
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    ok = xvideo_storyboard.update_scene(sb, req.scene_id, text=req.text, image=req.image,
                                         layout=req.layout, duration=req.duration,
                                         visual_type=req.visual_type, motion_preset=req.motion_preset,
                                         asset_policy=req.asset_policy, headline=req.headline)
    if req.template_id is not None and ok:
        for _sc in sb.get("scenes", []):
            if _sc.get("id") == req.scene_id:
                _sc["template_id"] = req.template_id
                break
    xvideo_storyboard.save(jd, sb)
    return {"success": ok}


@app.post("/api/storyboard/scene/sync-settings")
def storyboard_scene_sync_settings(req: SceneReq):
    """Copy visual/render settings from one approved scene to all remaining scenes.
    Does not copy story content, headline, duration, or image.
    """
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    scenes = sb.get("scenes", [])
    src = next((s for s in scenes if s.get("id") == req.scene_id), None)
    if not src: return {"error": "source scene not found"}
    # Prefer values explicitly submitted from the current UI controls. This prevents
    # a sync click from reloading stale/default-normalized values from storyboard.
    keys = ["visual_type", "motion_preset", "asset_policy", "layout", "template_id"]
    req_vals = {"visual_type": req.visual_type, "motion_preset": req.motion_preset,
                "asset_policy": req.asset_policy, "layout": req.layout, "template_id": req.template_id}
    copied = {}
    for k in keys:
        rv = req_vals.get(k)
        sv = src.get(k)
        # UI payload can be stale/defaulted to "random" while the source scene already
        # has a concrete approved setting. Sync must never downgrade concrete choices
        # to random. This protection applies to template + visual/motion/asset/layout.
        if rv == "random" and sv and sv != "random":
            copied[k] = sv
        elif rv not in (None, ""):
            copied[k] = rv
        elif sv is not None:
            copied[k] = sv
    for k, v in copied.items():
        src[k] = v
    n = 0
    for sc in scenes:
        if sc.get("id") == req.scene_id:
            continue
        for k, v in copied.items():
            sc[k] = v
        # invalidate render preview because settings changed; keep article image/content untouched
        if sc.get("preview"):
            sc["preview"] = {"status": "pending_sync", "engine": sc.get("preview", {}).get("engine", "html-video")}
        n += 1
    sb.setdefault("style_lock", {})
    sb["style_lock"].update({"source_scene_id": req.scene_id, "settings": copied, "updated_at": datetime.now().isoformat()})
    xvideo_storyboard.save(jd, sb)
    return {"success": True, "synced": n, "settings": copied}

@app.post("/api/storyboard/scene/delete")
def storyboard_scene_delete(req: SceneReq):
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    ok = xvideo_storyboard.delete_scene(sb, req.scene_id)
    xvideo_storyboard.save(jd, sb)
    return {"success": ok}

@app.post("/api/storyboard/scene/reorder")
def storyboard_scene_reorder(req: SceneReq):
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    ok = xvideo_storyboard.reorder_scenes(sb, req.ordered_ids)
    xvideo_storyboard.save(jd, sb)
    return {"success": ok}

@app.post("/api/storyboard/scene/regenerate")
def storyboard_scene_regen(req: SceneReq):
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb: return {"error": "no storyboard"}
    new_img = xvideo_storyboard.regenerate_scene_image(sb, req.scene_id, jd)
    xvideo_storyboard.save(jd, sb)
    return {"success": bool(new_img), "image": new_img}

@app.post("/api/storyboard/scene/preview")
def storyboard_scene_preview(req: SceneReq):
    """Render one storyboard scene to a PNG preview so user can approve scene-by-scene."""
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd)
    if not sb:
        return {"error": "no storyboard"}
    scene = next((s for s in sb.get("scenes", []) if s.get("id") == req.scene_id), None)
    if not scene:
        return {"error": "scene not found"}
    try:
        import copy
        single = copy.deepcopy(sb)
        one = copy.deepcopy(scene)
        one["start"] = 0
        one["duration"] = max(4, float(one.get("duration") or 4))
        single["scenes"] = [one]
        single["total_duration"] = one["duration"]
        try:
            import xvideo_scene_analyzer, xvideo_scene_templates
            one = xvideo_scene_analyzer.enrich_scene(one, one.get("order", 0))
            html = xvideo_scene_templates.render_scene_html(
                one, aspect=single.get("aspect", "doc"), title=single.get("title", ""),
                aspect_map=ASPECT_MAP, res_map=RES_MAP,
                resolution=single.get("resolution", "hd"), idx=one.get("order", 0))
        except Exception as e:
            print("[storyboard] template preview fallback:", e, flush=True)
            html = xvideo_storyboard.render_html(single, "voice.mp3", "bgm.mp3",
                                                 datetime.now().strftime('%Y-%m-%d'),
                                                 ASPECT_MAP, RES_MAP)
        html_path = jd / f"preview_{req.scene_id}.html"
        html_path.write_text(html, encoding="utf-8")
        asset_dir = jd / "assets"; asset_dir.mkdir(exist_ok=True)
        out = asset_dir / f"preview_{req.scene_id}.png"
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        # viewport size roughly matches selected aspect; render fast static first frame
        ar = ASPECT_MAP.get(single.get("aspect", "doc"), (9,16))
        vh = 960; vw = int(vh * ar[0] / ar[1] / 2) * 2
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               f"--window-size={vw},{vh}", f"--screenshot={out}", html_path.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        if not out.exists():
            return {"error": "preview render failed: " + (r.stderr or r.stdout)[-300:]}
        scene["preview"] = {
            "png": f"assets/{out.name}",
            "mp4": (scene.get("preview") or {}).get("mp4"),
            "status": "ready",
            "html": html_path.name,
        }
        try:
            xvideo_storyboard.save(jd, sb)
        except Exception as e:
            print("[storyboard] preview save failed:", e, flush=True)
        return {"success": True, "preview": f"/api/storyboard/{req.job_id}/asset/{out.name}?t={int(time.time())}", "scene": xvideo_storyboard.public_view({**sb, "scenes": [scene]}).get("scenes", [scene])[0]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/storyboard/{job_id}/render")
def storyboard_render_now(job_id: str):
    jd = PROJECT_DIR / job_id
    sb = xvideo_storyboard.load(jd)
    if not sb:
        return {"error": "Storyboard chua san sang"}
    _job_update(job_id, status="rendering", progress=65)
    threading.Thread(target=_job_render, args=(job_id,), daemon=True).start()
    return {"success": True, "status": "rendering"}

@app.get("/api/hv/templates")
def hv_templates(aspect: str = None):
    if not xvideo_hv:
        return {"error": "html-video bridge unavailable"}
    return {"templates": xvideo_hv.list_templates(aspect=aspect)}

@app.post("/api/hv/scene/render")
def hv_scene_render(req: SceneReq):
    """Render one storyboard scene to MP4 via the html-video engine.
    template_id optional; if missing or 'random', a template is auto-picked."""
    if not xvideo_hv:
        return {"error": "html-video bridge unavailable"}
    jd = PROJECT_DIR / req.job_id
    sb = xvideo_storyboard.load(jd) if xvideo_storyboard else None
    if not sb:
        return {"error": "no storyboard"}
    scene = next((sc for sc in sb.get("scenes", []) if sc.get("id") == req.scene_id), None)
    if not scene:
        return {"error": "scene not found"}
    aspect = req.aspect or "9:16"
    tid = req.template_id or scene.get("template_id")
    if not tid or tid == "random":
        tid = xvideo_hv.random_template(aspect=aspect)
    res = xvideo_hv.render_scene(scene, tid, aspect=aspect)
    if not res.get("success"):
        return {"error": res.get("error", "render failed")}
    # copy/mux mp4 into job assets so the UI can stream it. If a voice is supplied,
    # generate per-scene TTS and mux it with the visual scene.
    import shutil
    asset_dir = jd / "assets"; asset_dir.mkdir(parents=True, exist_ok=True)
    fn = "scene_%s.mp4" % req.scene_id
    dst = asset_dir / fn
    voice_used = None
    try:
        if req.voice:
            voice_text = scene.get("body") or scene.get("script") or scene.get("text") or scene.get("summary") or scene.get("headline") or ""
            voice_mp3 = asset_dir / ("scene_%s_voice.mp3" % req.scene_id)
            try:
                generate_voice(voice_text, req.voice, voice_mp3, "vi")
                mux_tmp = asset_dir / ("scene_%s_mux.mp4" % req.scene_id)
                cmd = ['/opt/homebrew/bin/ffmpeg','-y','-i',res["mp4"],'-i',str(voice_mp3),'-c:v','copy','-c:a','aac','-shortest',str(mux_tmp)]
                mr = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                if mr.returncode == 0 and mux_tmp.exists():
                    shutil.move(str(mux_tmp), str(dst))
                    voice_used = req.voice
                else:
                    shutil.copyfile(res["mp4"], dst)
            except Exception as e:
                print("[hv] scene voice mux failed:", e, flush=True)
                shutil.copyfile(res["mp4"], dst)
        else:
            shutil.copyfile(res["mp4"], dst)
    except Exception as e:
        return {"error": "copy/mux mp4 failed: %s" % e}
    scene["template_id"] = tid
    scene["preview"] = {"png": (scene.get("preview") or {}).get("png"),
                         "mp4": "assets/" + fn, "status": "ready", "engine": "html-video"}
    try:
        xvideo_storyboard.save(jd, sb)
    except Exception as e:
        print("[hv] save failed:", e, flush=True)
    return {"success": True, "template_id": tid, "aspect": res.get("aspect", aspect),
            "mp4": "/api/storyboard/%s/asset/%s?t=%d" % (req.job_id, fn, int(time.time())), "voice": voice_used}

@app.get("/api/storyboard/{job_id}/asset/{filename}")
def storyboard_asset(job_id: str, filename: str):
    jd = PROJECT_DIR / job_id / "assets"
    p = jd / filename
    if not p.exists() or ".." in filename:
        return Response(status_code=404)
    fl = filename.lower()
    mt = "image/jpeg" if fl.endswith((".jpg",".jpeg")) else "image/png" if fl.endswith(".png") else "image/webp" if fl.endswith(".webp") else "video/mp4" if fl.endswith(".mp4") else "video/webm" if fl.endswith(".webm") else "application/octet-stream"
    return Response(content=p.read_bytes(), media_type=mt)


# ---- API Key Management ----
class ApiKeyReq(BaseModel):
    provider: str
    key: str = ""
    label: str = ""
    id: str = ""

@app.get("/api/keys")
def api_keys_list(provider: str = None):
    if not xvideo_apikeys:
        return {"error": "key manager unavailable"}
    return {"providers": xvideo_apikeys.list_keys(provider)}

@app.post("/api/keys/add")
def api_keys_add(req: ApiKeyReq):
    if not xvideo_apikeys:
        return {"error": "key manager unavailable"}
    if not req.key.strip():
        return {"error": "Key trống"}
    kid = xvideo_apikeys.add_key(req.provider, req.key, req.label)
    return {"success": True, "id": kid}

@app.post("/api/keys/update")
def api_keys_update(req: ApiKeyReq):
    if not xvideo_apikeys:
        return {"error": "key manager unavailable"}
    ok = xvideo_apikeys.update_key(req.provider, req.id, req.key or None, req.label or None)
    return {"success": ok}

@app.post("/api/keys/delete")
def api_keys_delete(req: ApiKeyReq):
    if not xvideo_apikeys:
        return {"error": "key manager unavailable"}
    ok = xvideo_apikeys.delete_key(req.provider, req.id)
    return {"success": ok}

class SettingsReq(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None

@app.get("/api/settings")
def api_settings_get():
    return load_settings()

@app.post("/api/settings")
def api_settings_set(req: SettingsReq):
    return save_settings({"llm_provider": req.llm_provider, "llm_model": req.llm_model, "llm_base_url": req.llm_base_url})

@app.get("/api/llm/providers")
def api_llm_providers():
    return {"providers": [
        {"id": "local_ollama", "label": "Local (Ollama)", "needs_key": False, "needs_base_url": False},
        {"id": "gemini", "label": "Google Gemini", "needs_key": True, "needs_base_url": False},
        {"id": "openai", "label": "OpenAI", "needs_key": True, "needs_base_url": False},
        {"id": "openai_compatible", "label": "OpenAI-compatible proxy", "needs_key": True, "needs_base_url": True},
        {"id": "deepseek", "label": "DeepSeek", "needs_key": True, "needs_base_url": False},
        {"id": "9router", "label": "9Router", "needs_key": True, "needs_base_url": True},
    ]}

@app.post("/api/llm/test")
def api_llm_test(req: SettingsReq):
    """Live test the currently-selected (or provided) provider with a tiny prompt."""
    st = load_settings()
    provider = req.llm_provider or st.get("llm_provider") or "local_ollama"
    model = req.llm_model if req.llm_model is not None else st.get("llm_model")
    base_url = req.llm_base_url if req.llm_base_url is not None else st.get("llm_base_url")
    if not xvideo_llm:
        return {"success": False, "detail": "LLM adapter unavailable"}
    try:
        out = xvideo_llm.complete('Tra loi JSON {"ok":true}', provider=provider, model=model or None,
                                  json_mode=True, max_tokens=60, timeout=60, base_url=base_url or None)
        ok = '"ok"' in (out or "") or "ok" in (out or "").lower()
        return {"success": bool(ok), "detail": (out or "")[:160]}
    except Exception as e:
        return {"success": False, "detail": str(e)[:160]}

@app.post("/api/keys/test")
def api_keys_test(req: ApiKeyReq):
    if not xvideo_apikeys:
        return {"error": "key manager unavailable"}
    if req.id:
        ok, detail = xvideo_apikeys.test_and_update(req.provider, req.id)
    elif req.key:
        ok, detail = xvideo_apikeys.test_key(req.provider, req.key)
    else:
        return {"error": "Cần id hoặc key"}
    return {"success": ok, "detail": detail}

@app.get("/", response_class=HTMLResponse)
def _index_nocache():
    p = FRONTEND_DIR / "index.html"
    html = p.read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"})

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

if __name__ == "__main__":
    # FIX: Recover stale jobs on startup
    try:
        db = _job_db()
        stale = db.execute("SELECT job_id FROM jobs WHERE status IN ('queued','processing')").fetchall()
        for row in stale:
            db.execute("UPDATE jobs SET status='error', error='Server restart - job lost', updated_at=datetime('now') WHERE job_id=?", (row[0],))
        if stale:
            db.commit()
            print(f"  Job recovery: {len(stale)} stale jobs -> marked as error")
    except Exception as ex:
        print(f"  Job recovery skipped: {ex}")
    _vlp = _pl.Path(__file__).parent / "voice_library.py"
    if _vlp.exists():
        _sp.Popen(["python3", str(_vlp)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        import time; time.sleep(5)
        print("Voice Library spawned on :8769")
    else:
        print("voice_library.py not found at", str(_vlp))
    # Khởi động background warmup thread cho VieNeu TTS
    threading.Thread(target=_warmup_worker, daemon=True).start()
    print(f"🚀 X-Video Server v{APP_VERSION}")
    print(f"   http://0.0.0.0:8767")
    uvicorn.run(app, host="0.0.0.0", port=8767)
