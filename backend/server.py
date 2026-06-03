#!/usr/bin/env python3
"""
X-Video Backend — FastAPI Server
Chạy trên Macmini M4 (192.168.1.12:8767)
"""

import subprocess, json, os, re, shutil, time, hashlib, threading
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn, urllib.request

# CONFIG
OUTPUT_DIR = Path(__file__).parent.parent / "output"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
PROJECT_DIR = Path(__file__).parent.parent / "render-project"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

# Resolution map
RES_MAP = {"hd": (720, 1280), "fhd": (1080, 1920), "2k": (1440, 2560), "4k": (2160, 3840)}
# Aspect -> (w, h) for portrait
ASPECT_MAP = {"doc": (1080, 1920), "ngang": (1920, 1080), "vuong": (1080, 1080)}
# Music styles
BGM_MAP = {
    "ambient": [(220, 0.12), (330, 0.08), (440, 0.06)],
    "corporate": [(262, 0.10), (330, 0.10), (392, 0.08)],
    "tech": [(440, 0.14), (554, 0.10), (659, 0.06)],
    "cinematic": [(130, 0.15), (196, 0.10), (262, 0.08)],
}

app = FastAPI(title="X-Video", version="1.1.0")

class GenerateRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    hook: Optional[str] = None
    cta: Optional[str] = None
    aspect: str = "doc"
    language: str = "en"
    voice: str = "Samantha"
    speed: str = "normal"
    style: str = "news"
    resolution: str = "fhd"
    music: str = "ambient"

jobs = {}
jobs_lock = threading.Lock()

def clean_html(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'&[a-z]+;', ' ', h))).strip()
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
    # Fallback parse HTML
    with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
    m = re.search(r'<title>(.*?)</title>', html)
    title = clean_html(m.group(1)) if m else slug.replace('-',' ')
    return title, html, title, datetime.now().strftime('%Y-%m-%d'), "TIN TỨC"

def generate_voice(text, voice, output_path):
    wc = len(text.split())
    rate = min(210, max(140, int(wc / 50 * 60)))  # target ~50s
    script_path = output_path.parent / "script.txt"
    with open(script_path, "w") as f: f.write(text)
    aiff = output_path.parent / "temp.aiff"
    subprocess.run(['say','-v',voice,'-r',str(rate),'-f',str(script_path),'-o',str(aiff)], capture_output=True, timeout=60)
    subprocess.run(['ffmpeg','-y','-i',str(aiff),'-acodec','libmp3lame','-b:a','128k',str(output_path)], capture_output=True, timeout=60)
    if aiff.exists(): aiff.unlink()
    r = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',str(output_path)], capture_output=True, text=True, timeout=10)
    dur = float(r.stdout.strip() or 50)
    return int(dur), wc, rate

def generate_bgm(music_style, duration, output_path):
    if music_style == "none":
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t',str(duration),str(output_path)], capture_output=True, timeout=10)
        return
    tones = BGM_MAP.get(music_style, BGM_MAP["ambient"])
    inputs = ' '.join([f'-f lavfi -i "sine=frequency={f}:duration={duration}"' for f, _, in tones])
    weights = ':'.join([str(w) for _, w in tones])
    filter_cmd = f'[0:a][1:a][2:a]amix=inputs={len(tones)}:duration=first:weights={weights},afade=t=in:d=1,afade=t=out:st={duration-2}:d=2,volume=0.07'
    subprocess.run(f'ffmpeg -y {inputs} -filter_complex "{filter_cmd}" -acodec libmp3lame -b:a 64k {output_path}'.split(), capture_output=True, timeout=30)

def make_html(aspect, title, date_str, duration, voice_path, bgm_path, style="news"):
    w, h = ASPECT_MAP.get(aspect, (1080, 1920))
    pct = lambda p: int(h * p)

    style_desc = {"news":"📺 BẢN TIN","reportage":"🎬 PHÓNG SỰ","analysis":"📊 PHÂN TÍCH","story":"📖 CÂU CHUYỆN","tutorial":"🎓 HƯỚNG DẪN","hot":"🔥 TIN NÓNG"}

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
<div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-width="{w}" data-height="{h}">
  <audio data-start="0" data-duration="{duration}" data-track-index="0" data-volume="1.0" src="{voice_path}"></audio>
  <audio data-start="0" data-duration="{duration}" data-track-index="1" data-volume="0.3" src="{bgm_path}"></audio>
  <div class="bg-grad"></div><div class="bg-grid"></div>
  <div class="circle" style="width:{int(w*0.3)}px;height:{int(w*0.3)}px;top:-{int(h*0.04)}px;right:-{int(w*0.06)}px" id="c1"></div>
  <div class="circle" style="width:{int(w*0.18)}px;height:{int(w*0.18)}px;top:{int(h*0.4)}px;left:-{int(w*0.04)}px" id="c2"></div>
  <div class="circle" style="width:{int(w*0.22)}px;height:{int(w*0.22)}px;bottom:{int(h*0.2)}px;right:-{int(w*0.06)}px" id="c3"></div>
  <div class="accent" id="accent"></div>
  <div class="logo" id="logo">AI WORLD</div>
  <div class="styletag" id="tag">{style_desc.get(style,"📺 TIN TỨC")}</div>
  <div class="title" id="title">{title[:200]}</div>
  <div class="content" id="content">Tin tức AI mới nhất từ AI World. Giải pháp doanh nghiệp AI First.</div>
  <div class="cta" id="cta"></div>
  <div class="meta" id="meta">AI World News &#183; {date_str}</div>
</div>
<script>
window.__timelines=window.__timelines||{{}};
const tl=gsap.timeline({{paused:true}});
tl.from("#accent",{{scaleX:0,transformOrigin:"left",duration:.5,ease:"power3.out",delay:.2}},0);
tl.from("#c1",{{opacity:0,scale:.4,duration:1,ease:"power2.out"}},.2);
tl.from("#c2",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.5);
tl.from("#c3",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.6);
tl.from("#logo",{{opacity:0,y:-15,duration:.5,ease:"power3.out"}},.3);
tl.from("#tag",{{opacity:0,y:-10,scale:.9,duration:.4,ease:"back.out(1.3)"}},.5);
tl.from("#title",{{opacity:0,y:30,duration:.7,ease:"power3.out"}},.8);
tl.from("#content",{{opacity:0,y:20,duration:.6,ease:"power2.out"}},1.5);
tl.from("#cta",{{opacity:0,y:15,duration:.5,ease:"power2.out"}},{duration-5});
tl.from("#meta",{{opacity:0,duration:.5,ease:"power2.out"}},1.8);
tl.to("#c1",{{y:-20,duration:4,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
tl.to("#c2",{{y:20,duration:5,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
tl.to("#c3",{{y:-15,duration:4.5,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
tl.to("#root>*",{{opacity:0,duration:1.5,ease:"power2.in"}},{duration-4});
window.__timelines["main"]=tl;
</script></body></html>'''

def process_job(jid: str, req: GenerateRequest):
    global jobs
    try:
        with jobs_lock: jobs[jid] = {"status":"processing","progress":5}
        jd = PROJECT_DIR / jid; jd.mkdir(exist_ok=True)

        with jobs_lock: jobs[jid] = {"status":"processing","progress":15}
        if req.url:
            title, content, excerpt, date_str, category = fetch_content(req.url)
        elif req.text:
            title = req.text[:150]; content = req.text; excerpt = title[:200]
            date_str = datetime.now().strftime('%Y-%m-%d'); category = "TIN TỨC"
        else:
            raise ValueError("Cần url hoặc text")

        hook = req.hook or f"Tin nóng: {title[:50]}..."
        cta = req.cta or "Theo dõi AI World để cập nhật tin tức công nghệ mới nhất!"

        with jobs_lock: jobs[jid] = {"status":"processing","progress":30}
        voice_text = f"AI World News. {hook} {excerpt or title}. {cta} Visit a i world dot v n."
        duration, wc, rate = generate_voice(voice_text, req.voice, jd/"voice.mp3")

        with jobs_lock: jobs[jid] = {"status":"processing","progress":45}
        generate_bgm(req.music, duration, jd/"bgm.mp3")

        with jobs_lock: jobs[jid] = {"status":"processing","progress":55}
        html = make_html(req.aspect, title, date_str, duration, "voice.mp3", "bgm.mp3", req.style)
        with open(jd/"index.html","w") as f: f.write(html)
        with open(jd/"hyperframes.json","w") as f:
            json.dump({"$schema":"https://hyperframes.heygen.com/schema/hyperframes.json","paths":{"blocks":"compositions","components":"compositions/components","assets":"assets"}}, f)

        with jobs_lock: jobs[jid] = {"status":"processing","progress":70}
        env = os.environ.copy(); env["PATH"] = os.path.expanduser("~/.local/bin")+":"+env.get("PATH","")
        proc = subprocess.run(["npx","hyperframes@latest","render"], cwd=str(jd), capture_output=True, text=True, timeout=600, env=env)
        if proc.returncode != 0:
            raise Exception(f"Render fail: {proc.stderr[-300:]}")

        mp4s = sorted((jd/"renders").glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if not mp4s: raise Exception("No MP4 output")

        with jobs_lock: jobs[jid] = {"status":"processing","progress":90}
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_name = f"xvideo_{jid[:8]}_{ts}.mp4"
        out_path = OUTPUT_DIR / out_name
        shutil.copy(str(mp4s[0]), str(out_path))
        size_kb = out_path.stat().st_size // 1024

        with jobs_lock:
            jobs[jid] = {"status":"done","progress":100,
                "video_path": out_name, "duration": duration, "size_kb": size_kb,
                "word_count": wc, "tts_rate": rate, "title": title[:80], "category": category,
                "style": req.style, "aspect": req.aspect}
    except Exception as e:
        with jobs_lock: jobs[jid] = {"status":"error","progress":0,"error":str(e)}

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
    r = subprocess.run(['say','-v','?'], capture_output=True, text=True, timeout=10)
    return {"voices": [l.split()[0] for l in r.stdout.strip().split('\n') if l.strip()]}

@app.post("/api/generate", status_code=201)
def generate(req: GenerateRequest, bg: BackgroundTasks):
    if not req.url and not req.text:
        raise HTTPException(400, "Cần url hoặc text")
    jid = hashlib.md5(f"{time.time()}{req.url or req.text}".encode()).hexdigest()
    with jobs_lock: jobs[jid] = {"status":"queued","progress":0}
    bg.add_task(process_job, jid, req)
    return {"job_id": jid, "status": "queued", "check_url": f"/api/jobs/{jid}"}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        j = jobs.get(job_id)
    if not j: raise HTTPException(404, "Not found")
    return {"job_id": job_id, **{"status":j.get("status","?"), "progress":j.get("progress",0),
        "error":j.get("error"), "video_path":j.get("video_path"), "duration":j.get("duration"),
        "size_kb":j.get("size_kb"), "word_count":j.get("word_count"), "tts_rate":j.get("tts_rate"),
        "title":j.get("title"), "category":j.get("category")}}

@app.get("/api/jobs")
def list_jobs():
    with jobs_lock: return {"jobs": {k: {"status":v.get("status"),"progress":v.get("progress"),
        "title":v.get("title"),"video_path":v.get("video_path")} for k,v in jobs.items()}}

@app.get("/output/{filename}")
def serve(filename: str):
    fp = OUTPUT_DIR / filename
    if not fp.exists(): raise HTTPException(404)
    return FileResponse(str(fp), media_type="video/mp4", headers={"Access-Control-Allow-Origin":"*"})

@app.get("/healthz")
def healthz(): return {"status":"ok","machine":"Macmini","gpu":"Apple M4"}

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

if __name__ == "__main__":
    print(f"🚀 X-Video Server v1.1")
    print(f"   http://0.0.0.0:8767")
    uvicorn.run(app, host="0.0.0.0", port=8767)
