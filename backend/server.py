#!/usr/bin/env python3
"""
X-Video Backend — FastAPI Server
==================================
Chạy trên Macmini (192.168.1.12) — trung tâm tác vụ video AI World.
API endpoint cho mọi agent trong mạng LAN gọi remote.

Kiến trúc:
  POST /api/generate  — nhập link/content → ra video MP4
  
Flow:
  1. Crawl nội dung từ link WP hoặc nhận text trực tiếp
  2. Voiceover TTS bằng macOS say (Samantha/Voice Vietnamese)
  3. Background music sinh động
  4. HTML template khổ dọc/ngang/vuông → HyperFrames render
  5. Output MP4 + URL public xem online
"""

import subprocess, tempfile, json, os, re, shutil, time, hashlib, threading, asyncio
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
import urllib.request, urllib.parse

# ===== CONFIG =====
BASE_DIR = Path(__file__).parent.parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"
PROJECT_DIR = BASE_DIR / "render-project"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

FPS = 30

app = FastAPI(title="X-Video", description="AI World News → Video Pipeline", version="1.0.0")

# ===== HTML TEMPLATES =====
TEMPLATES = {
    "doc": {
        "name": "Khổ dọc 9:16",
        "width": 1080, "height": 1920,
        "desc": "TikTok / Reels / Shorts"
    },
    "ngang": {
        "name": "Khổ ngang 16:9",
        "width": 1920, "height": 1080,
        "desc": "YouTube / Website"
    },
    "vuong": {
        "name": "Khổ vuông 1:1",
        "width": 1080, "height": 1080,
        "desc": "Instagram / Facebook"
    }
}

def make_html(template_key: str, title: str, date_str: str, slug: str,
              category: str, duration: int, excerpt: str = "") -> str:
    t = TEMPLATES[template_key]
    w, h = t["width"], t["height"]
    
    safe_title = title.replace('<', '&lt;').replace('>', '&gt;')[:200]
    safe_excerpt = (excerpt or "Tin tức công nghệ AI mới nhất từ AI World").replace('<','&lt;').replace('>','&gt;')[:280]
    cat_name = category or "CÔNG NGHỆ"
    
    return f'''<!doctype html>
<html lang="vi">
<head><meta charset="UTF-8"/><meta name="viewport" content="width={w},height={h}"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#06061a}}
#root{{position:relative;width:{w}px;height:{h}px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
.bg{{position:absolute;inset:0}}
.bg-grad{{background:radial-gradient(ellipse at 50% 20%,#1a1a4e 0%,#0a0a1a 55%,#06061a 100%)}}
.bg-grid{{opacity:.04;background-image:linear-gradient(rgba(255,255,255,.1)1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.1)1px,transparent 1px);background-size:{int(w/24)}px {int(h/24)}px}}
.accent{{position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#6366f1,#8b5cf6,#d946ef)}}
.logo{{position:absolute;top:{int(h*0.04)}px;left:0;right:0;text-align:center;font-size:{int(h*0.017)}px;font-weight:900;color:#6366f1;letter-spacing:4px}}
.cat{{position:absolute;top:{int(h*0.09)}px;left:50%;transform:translateX(-50%);font-size:{int(h*0.011)}px;font-weight:700;color:#a78bfa;background:rgba(99,102,241,.12);padding:{int(h*0.005)}px {int(h*0.015)}px;border-radius:{int(h*0.01)}px;letter-spacing:2px;text-transform:uppercase}}
.title-w{{position:absolute;top:{int(h*0.18)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px}}
.title-w h1{{font-size:{int(h*0.03)}px;font-weight:900;color:#fff;line-height:1.12;letter-spacing:-1px}}
.divider{{position:absolute;left:{int(w*0.07)}px;right:{int(w*0.07)}px;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.3),rgba(168,85,247,.3),transparent)}}
.meta{{position:absolute;bottom:{int(h*0.12)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px;text-align:center;font-size:{int(h*0.013)}px;color:rgba(255,255,255,.45)}}
.brand{{position:absolute;bottom:{int(h*0.07)}px;left:{int(w*0.07)}px;right:{int(w*0.07)}px;text-align:center;font-size:{int(h*0.014)}px;font-weight:700;color:#6366f1;letter-spacing:2px}}
.circle{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(99,102,241,.08)0%,transparent 70%);pointer-events:none}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-width="{w}" data-height="{h}">
  <audio data-start="0" data-duration="{duration}" data-track-index="0" data-volume="1.0" src="voice.mp3"></audio>
  <audio data-start="0" data-duration="{duration}" data-track-index="1" data-volume="0.3" src="bgm.mp3"></audio>
  <div class="bg bg-grad"></div><div class="bg bg-grid"></div>
  <div class="circle" style="width:{int(w*0.28)}px;height:{int(w*0.28)}px;top:-{int(w*0.05)}px;right:-{int(w*0.05)}px" id="c1"></div>
  <div class="circle" style="width:{int(w*0.17)}px;height:{int(w*0.17)}px;top:{int(h*0.42)}px;left:-{int(w*0.04)}px" id="c2"></div>
  <div class="circle" style="width:{int(w*0.2)}px;height:{int(w*0.2)}px;bottom:{int(h*0.18)}px;right:-{int(w*0.06)}px" id="c3"></div>
  <div class="accent" id="accent"></div>
  <div class="logo" id="logo">AI WORLD</div>
  <div class="cat" id="cat">&#9679; {cat_name}</div>
  <div class="title-w" id="title"><h1>{safe_title}</h1></div>
  <div class="divider" style="top:{int(h*0.41)}px" id="div1"></div>
  <div class="meta" id="meta">AI World News &#183; {date_str}</div>
  <div class="brand" id="brand">AI WORLD</div>
</div>
<script>
  window.__timelines=window.__timelines||{{}};
  const tl=gsap.timeline({{paused:true}});
  tl.from("#accent",{{scaleX:0,transformOrigin:"left",duration:.5,ease:"power3.out",delay:.2}},0);
  tl.from("#c1",{{opacity:0,scale:.4,duration:1,ease:"power2.out"}},.2);
  tl.from("#c2",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.5);
  tl.from("#c3",{{opacity:0,scale:.4,duration:.8,ease:"power2.out"}},.6);
  tl.from("#logo",{{opacity:0,y:-15,duration:.5,ease:"power3.out"}},.3);
  tl.from("#cat",{{opacity:0,y:-10,scale:.9,duration:.4,ease:"back.out(1.3)"}},.5);
  tl.from("#title",{{opacity:0,y:30,duration:.7,ease:"power3.out"}},.8);
  tl.from("#div1",{{opacity:0,scaleX:0,transformOrigin:"center",duration:.5,ease:"power2.out"}},1.3);
  tl.from("#meta",{{opacity:0,duration:.5,ease:"power2.out"}},1.5);
  tl.from("#brand",{{opacity:0,y:10,duration:.5,ease:"power2.out"}},1.4);
  tl.to("#c1",{{y:-20,duration:4,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
  tl.to("#c2",{{y:20,duration:5,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
  tl.to("#c3",{{y:-15,duration:4.5,ease:"sine.inOut",yoyo:true,repeat:-1}},2);
  tl.to("#root>*",{{opacity:0,duration:1,ease:"power2.in"}},{duration-3});
  window.__timelines["main"]=tl;
</script></body></html>'''

# ===== MODELS =====
class GenerateRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    aspect: str = "doc"  # doc | ngang | vuong
    language: str = "en"  # en | vi
    voice: str = "Samantha"  # macOS voice name

class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | processing | done | error
    progress: int  # 0-100
    video_url: Optional[str] = None
    error: Optional[str] = None

# ===== JOB STORE =====
jobs = {}
jobs_lock = threading.Lock()

def clean_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def categorize(slug: str) -> str:
    if "phan-bien" in slug or "thuc-thi" in slug:
        return "TỔNG HỢP"
    if "evo-core" in slug:
        return "EVO-CORE"
    return "CÔNG NGHỆ"

def fetch_content(url: str):
    """Fetch from WordPress or any web page"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "X-Video/1.0")
    
    # Try WordPress API first
    api_url = url.replace('/vi/', '/vi/wp-json/wp/v2/').rstrip('/')
    slug = url.split('/')[-1].split('?')[0]
    
    # Try wp-json
    wp_url = f"http://192.168.1.9:8080/vi/wp-json/wp/v2/posts?slug={slug}"
    try:
        with urllib.request.urlopen(urllib.request.Request(wp_url), timeout=10) as r:
            posts = json.loads(r.read())
            if posts:
                p = posts[0]
                title = clean_html(p['title']['rendered'])
                content = clean_html(p.get('content', {}).get('rendered', ''))
                excerpt = clean_html(p.get('excerpt', {}).get('rendered', title))
                date_str = p.get('date', '')[:10]
                cat_slug = p.get('slug', slug)
                category = categorize(cat_slug)
                return title, content, excerpt, date_str, category
    except:
        pass
    
    # Fallback: parse HTML
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
    title_match = re.search(r'<title>(.*?)</title>', html)
    title = clean_html(title_match.group(1)) if title_match else slug.replace('-', ' ')
    date_str = datetime.now().strftime('%Y-%m-%d')
    category = "TIN TỨC"
    excerpt = title
    
    return title, html, excerpt, date_str, category

def generate_voice(text: str, language: str, voice: str, output_path: Path):
    """TTS using macOS say command"""
    word_count = len(text.split())
    target_dur = max(40, min(85, word_count // 3))  # ~50-90s
    rate = min(210, max(140, int(word_count / target_dur * 60)))
    
    # Write script
    script_path = output_path.parent / "script.txt"
    with open(script_path, "w") as f:
        f.write(text)
    
    # Generate audio
    aiff_path = output_path.parent / "temp.aiff"
    subprocess.run(['say', '-v', voice, '-r', str(rate), '-f', str(script_path), '-o', str(aiff_path)],
                   capture_output=True, timeout=60)
    
    # Convert to MP3
    subprocess.run(['ffmpeg', '-y', '-i', str(aiff_path), '-acodec', 'libmp3lame', '-b:a', '128k', str(output_path)],
                   capture_output=True, timeout=60)
    
    # Clean temp
    if aiff_path.exists():
        aiff_path.unlink()
    
    # Get duration
    result = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                             '-of', 'csv=p=0', str(output_path)],
                            capture_output=True, text=True, timeout=10)
    dur = float(result.stdout.strip() or target_dur)
    return int(dur), word_count, rate

def generate_bgm(duration: int, output_path: Path):
    """Generate ambient background music"""
    subprocess.run([
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'sine=frequency=220:duration={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency=330:duration={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
        '-filter_complex',
        f'[0:a][1:a][2:a]amix=inputs=3:duration=first:weights=0.15|0.1|0.08,'
        f'afade=t=in:d=1,afade=t=out:st={duration-2}:d=2,volume=0.07',
        '-acodec', 'libmp3lame', '-b:a', '64k',
        str(output_path)
    ], capture_output=True, timeout=30)

def render_video(job_dir: Path, duration: int) -> Path:
    """Run HyperFrames render on Macmini"""
    # Setup project files
    hf_json = job_dir / "hyperframes.json"
    if not hf_json.exists():
        with open(hf_json, "w") as f:
            json.dump({
                "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
                "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}
            }, f)

    # Run render
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/.local/bin") + ":" + env.get("PATH", "")
    
    proc = subprocess.run(
        ["npx", "hyperframes@latest", "render"],
        cwd=str(job_dir),
        capture_output=True, text=True, timeout=600, env=env
    )
    
    if proc.returncode != 0:
        raise Exception(f"Render failed: {proc.stderr[-500:]}")
    
    # Find output MP4
    renders_dir = job_dir / "renders"
    if renders_dir.exists():
        mp4s = sorted(renders_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if mp4s:
            return mp4s[0]
    
    raise Exception("No MP4 output found")

def process_job(job_id: str, req: GenerateRequest):
    """Background job processing"""
    try:
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 5}
        
        job_dir = PROJECT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Fetch content
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 10}
        
        if req.url:
            title, content, excerpt, date_str, category = fetch_content(req.url)
        elif req.text:
            title = req.text[:200]
            content = req.text
            excerpt = title
            date_str = datetime.now().strftime('%Y-%m-%d')
            category = "TIN TỨC"
        else:
            raise ValueError("Cần url hoặc text")
        
        # Build voiceover script
        voice_text = f"AI World News. {title}. {excerpt or 'Stay updated with the latest from AI World.'} For more, visit a i world dot v n."
        
        # Step 2: Generate voice
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 30}
        duration, word_count, rate = generate_voice(voice_text, req.language, req.voice, job_dir / "voice.mp3")
        
        # Step 3: Background music
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 40}
        generate_bgm(duration, job_dir / "bgm.mp3")
        
        # Step 4: Build HTML
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 50}
        html = make_html(req.aspect, title, date_str, job_id, category, duration, excerpt)
        with open(job_dir / "index.html", "w") as f:
            f.write(html)
        
        # Step 5: Render
        with jobs_lock:
            jobs[job_id] = {"status": "processing", "progress": 60}
        mp4_path = render_video(job_dir, duration)
        
        # Step 6: Copy to output
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_name = f"xvideo_{job_id[:8]}_{timestamp}.mp4"
        out_path = OUTPUT_DIR / out_name
        shutil.copy(str(mp4_path), str(out_path))
        
        size_kb = out_path.stat().st_size // 1024
        
        with jobs_lock:
            jobs[job_id] = {
                "status": "done",
                "progress": 100,
                "video_url": f"/output/{out_name}",
                "video_path": str(out_name),
                "duration": duration,
                "size_kb": size_kb,
                "word_count": word_count,
                "tts_rate": rate,
                "title": title,
                "category": category
            }
        
    except Exception as e:
        with jobs_lock:
            jobs[job_id] = {"status": "error", "progress": 0, "error": str(e)}

# ===== API ENDPOINTS =====

@app.get("/api/templates")
def get_templates():
    """Danh sách template khổ video"""
    return {"templates": TEMPLATES}

@app.get("/api/voices")
def get_voices():
    """Danh sách giọng đọc macOS có sẵn"""
    result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True, timeout=10)
    voices = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 2:
            voices.append({
                "name": parts[0],
                "locale": parts[1] if len(parts) > 1 else "",
                "sample": ' '.join(parts[2:]) if len(parts) > 2 else ""
            })
    return {"voices": voices}

@app.post("/api/generate", status_code=201)
def generate_video(req: GenerateRequest, bg: BackgroundTasks):
    """Tạo video từ URL hoặc text"""
    if not req.url and not req.text:
        raise HTTPException(400, "Cần cung cấp url hoặc text")
    if req.aspect not in TEMPLATES:
        raise HTTPException(400, f"Template không hợp lệ: {req.aspect}. Chọn: {list(TEMPLATES.keys())}")
    
    job_id = hashlib.md5(f"{datetime.now().isoformat()}{req.url or req.text}".encode()).hexdigest()
    
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "progress": 0}
    
    bg.add_task(process_job, job_id, req)
    
    return {"job_id": job_id, "status": "queued", "check_url": f"/api/jobs/{job_id}"}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Kiểm tra trạng thái job"""
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus(job_id=job_id, **{k: v for k, v in job.items()})

@app.get("/api/jobs")
def list_jobs():
    """Danh sách tất cả jobs"""
    with jobs_lock:
        return {"jobs": {k: JobStatus(job_id=k, **{kk: vv for kk, vv in v.items()})
                         for k, v in jobs.items()}}

@app.get("/output/{filename}")
def serve_video(filename: str):
    """Serve video file"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path), media_type="video/mp4",
                        headers={"Access-Control-Allow-Origin": "*"})

# ===== FRONTEND =====
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

@app.get("/")
def index():
    with open(FRONTEND_DIR / "index.html") as f:
        return HTMLResponse(f.read())

@app.get("/healthz")
def healthz():
    return {"status": "ok", "machine": "Macmini", "gpu": "Apple M4"}

# ===== MAIN =====
if __name__ == "__main__":
    print(f"🚀 X-Video Server")
    print(f"   Backend: FastAPI on port 8767")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Templates: {list(TEMPLATES.keys())}")
    uvicorn.run(app, host="0.0.0.0", port=8767)
