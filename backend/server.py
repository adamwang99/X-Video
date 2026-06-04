#!/usr/bin/env python3
"""
X-Video Backend — FastAPI Server
Chạy trên Macmini M4 (192.168.1.12:8767)
"""

import subprocess, json, os, re, shutil, time, hashlib, threading, sqlite3, uuid
from pathlib import Path
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn, urllib.request; _ur = urllib.request
import subprocess as _sp, pathlib as _pl

# CONFIG
OUTPUT_DIR = Path(__file__).parent.parent / "output"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
PROJECT_DIR = Path(__file__).parent.parent / "render-project"
BGM_DIR = Path(__file__).parent.parent / "bgm_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR.mkdir(parents=True, exist_ok=True)

APP_VERSION = "1.5.9"

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
    # FIX: strip script/style blocks trước, sau đó strip tags
    h = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', ' ', h, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'&[a-z]+;', ' ', h))).strip()

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

def generate_voice(text, voice, output_path, language="vi"):
    """TTS — Macmini VieNeu (Vietnamese) or macOS say (English)"""
    wc = len(text.split())
    actual_engine = "macOS_say"  # default, updated if VieNeu succeeds

    if language == "vi":
        import urllib.request as ureq
        import json as jsonmod
        voice_map = {"female_south": "female_south", "female_north": "female_north",
                     "male_south": "male_south", "male_north": "male_north"}
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

def process_job(jid: str, req: GenerateRequest):
    try:
        _job_update(jid, status="processing", progress=5)
        jd = PROJECT_DIR / jid; jd.mkdir(exist_ok=True)

        _job_update(jid, status="processing", progress=15)
        if req.url:
            title, content, excerpt, date_str, category = fetch_content(req.url)
        elif req.text:
            title = req.text[:150]; content = req.text; excerpt = title[:200]
            date_str = datetime.now().strftime('%Y-%m-%d'); category = "TIN TỨC"
        else:
            raise ValueError("Cần url hoặc text")

        hook = req.hook or f"Tin nóng: {title[:50]}..."
        cta = req.cta or "Theo dõi AI World để cập nhật tin tức công nghệ mới nhất!"

        _job_update(jid, status="processing", progress=30)
        voice_text = f"AI World News. {hook} {excerpt or title}. {cta} Visit a i world dot v n."
        duration, wc, actual_engine = generate_voice(voice_text, req.voice, jd/"voice.mp3", req.language)

        # FIX: voice_snapshot ghi lại engine thực sự dùng (kể cả fallback)
        voice_snap = json.dumps({"voice": req.voice, "language": req.language, "engine": actual_engine})
        _job_update(jid, voice_snapshot=voice_snap)

        _job_update(jid, status="processing", progress=45)
        generate_bgm(req.music, duration, jd/"bgm.mp3")

        _job_update(jid, status="processing", progress=55)
        html = make_html(req.aspect, title, date_str, duration, "voice.mp3", "bgm.mp3", req.style, req.resolution)
        with open(jd/"index.html","w") as f: f.write(html)
        with open(jd/"hyperframes.json","w") as f:
            json.dump({"$schema":"https://hyperframes.heygen.com/schema/hyperframes.json","paths":{"blocks":"compositions","components":"compositions/components","assets":"assets"}}, f)

        _job_update(jid, status="processing", progress=70)
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

        _job_update(jid, status="done", progress=100,
            result_json=json.dumps({"video_path": out_name, "duration": duration, "size_kb": size_kb,
                "word_count": wc, "tts_rate": actual_engine, "title": title[:80], "category": category,
                "style": req.style, "aspect": req.aspect}))
        # FIX: mark cache dirty after job done so list refreshes
        _jobs_cache["__dirty__"] = True
    except Exception as e:
        _job_update(jid, status="error", progress=0, error=str(e))
        _jobs_cache["__dirty__"] = True

# ---- API ----

@app.get("/api/prefetch")
def api_prefetch(url: str):
    try:
        t, c, e, d, cat = fetch_content(url)
        return {"title": t[:200], "excerpt": e[:500], "content": c[:2000], "source": url, "date": d, "category": cat}
    except Exception as ex:
        return {"error": str(ex)}

@app.get("/api/templates")
def get_templates(): return {"doc":"Dọc 9:16","ngang":"Ngang 16:9","vuong":"Vuông 1:1"}

@app.get("/api/voices")
def get_voices():
    """Danh sách giọng đọc: VieNeu (vi) + macOS say (en)"""
    voices = [
        {"id": "female_south", "name": "🇻🇳 Nữ Nam Bộ", "lang": "vi", "engine": "VieNeu"},
        {"id": "female_north", "name": "🇻🇳 Nữ Bắc Bộ", "lang": "vi", "engine": "VieNeu"},
        {"id": "male_south", "name": "🇻🇳 Nam Nam Bộ", "lang": "vi", "engine": "VieNeu"},
        {"id": "male_north", "name": "🇻🇳 Nam Bắc Bộ", "lang": "vi", "engine": "VieNeu"},
        {"id": "Samantha", "name": "🇺🇸 Samantha", "lang": "en", "engine": "macOS"},
        {"id": "Karen", "name": "🇦🇺 Karen", "lang": "en", "engine": "macOS"},
        {"id": "Daniel", "name": "🇬🇧 Daniel", "lang": "en", "engine": "macOS"},
    ]
    return {"voices": voices}

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

# FIX: thêm endpoint warmup-tts để frontend không bị 404
@app.get("/api/warmup-tts")
def warmup_tts():
    """Warm up TTS engine — ping VieNeu, trả về status"""
    try:
        req_obj = _ur.Request("http://localhost:6023/v1/audio/speech",
                              data=json.dumps({"model":"vieneu","input":"test","voice":"female_south","speed":1.0}).encode(),
                              method="POST")
        req_obj.add_header("Content-Type", "application/json")
        with _ur.urlopen(req_obj, timeout=5) as r:
            r.read(16)
        return {"status": "ready", "engine": "vieneu"}
    except Exception as e:
        return {"status": "unavailable", "engine": "vieneu", "detail": str(e)}

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
    print(f"🚀 X-Video Server v{APP_VERSION}")
    print(f"   http://0.0.0.0:8767")
    uvicorn.run(app, host="0.0.0.0", port=8767)
