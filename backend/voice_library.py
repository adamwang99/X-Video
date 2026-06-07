#!/usr/bin/env python3
"""
X-Video Voice Library Server
=============================
Chạy trên Macmini M4 — port 8769
Quản lý thư viện giọng: clone, upload, preview, list, delete.
Tích hợp với VieNeu TTS và OmniVoice cho voice design.
"""

import io, os, json, re, time, hashlib, shutil, threading, subprocess, tempfile
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

# ===== CONFIG =====
BASE_DIR = Path(__file__).parent.parent.resolve()
VOICE_DIR = BASE_DIR / "voice-library"
CLONE_DIR = VOICE_DIR / "cloned-samples"
PREVIEW_DIR = VOICE_DIR / "previews"

for d in [VOICE_DIR, CLONE_DIR, PREVIEW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

VOICE_META_FILE = VOICE_DIR / "voice-metadata.json"
TTS_ENDPOINTS = {
    "vieneu": "http://localhost:6023/v1/audio/speech",
    "omnivoice": "http://localhost:6024/v1/audio/speech",
    "valtec": "http://localhost:6025/v1/audio/speech",
}
VOICE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="X-Video Voice Library", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== MODELS =====
class CloneRequest(BaseModel):
    name: str  # Name for the cloned voice
    audio_url: Optional[str] = None  # URL to audio file
    engine: str = "vieneu"  # TTS engine to use

class VoiceMeta(BaseModel):
    id: str
    name: str
    engine: str
    source: str  # "clone" | "builtin"
    language: str
    gender: str
    sample_path: str  # path to the cloned audio sample
    created_at: str
    size_bytes: int

# ===== VOICE METADATA STORE =====
def load_voices() -> dict:
    if VOICE_META_FILE.exists():
        raw = VOICE_META_FILE.read_text()
        if not raw.strip():
            print(f'[WARN] voice-metadata.json is empty - starting fresh')
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f'[CRITICAL] voice-metadata.json corrupted: {e}')
            backup = VOICE_META_FILE.with_suffix('.json.bak')
            if backup.exists():
                print(f'[RECOVERY] Loading from {backup}')
                return json.loads(backup.read_text())
            return {}
    return {}

def save_voices(voices: dict):
    """Atomic write: .tmp -> flush+fsync -> os.replace"""
    tmp_path = VOICE_META_FILE.with_suffix('.json.tmp')
    data = json.dumps(voices, indent=2, ensure_ascii=False)
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, VOICE_META_FILE)

# Initialize with built-in voices
def init_builtin_voices():
    voices = load_voices()
    builtin = {
        "female_south": {
            "id": "female_south", "name": "🇻🇳 Nữ Nam Bộ", "engine": "vieneu",
            "source": "builtin", "language": "vi", "gender": "female",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "female_north": {
            "id": "female_north", "name": "🇻🇳 Nữ Bắc Bộ", "engine": "vieneu",
            "source": "builtin", "language": "vi", "gender": "female",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "male_south": {
            "id": "male_south", "name": "🇻🇳 Nam Nam Bộ", "engine": "vieneu",
            "source": "builtin", "language": "vi", "gender": "male",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "male_north": {
            "id": "male_north", "name": "🇻🇳 Nam Bắc Bộ", "engine": "vieneu",
            "source": "builtin", "language": "vi", "gender": "male",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "Samantha": {
            "id": "Samantha", "name": "🇺🇸 Samantha", "engine": "macos",
            "source": "builtin", "language": "en", "gender": "female",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "Karen": {
            "id": "Karen", "name": "🇦🇺 Karen", "engine": "macos",
            "source": "builtin", "language": "en", "gender": "female",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
        "Daniel": {
            "id": "Daniel", "name": "🇬🇧 Daniel", "engine": "macos",
            "source": "builtin", "language": "en", "gender": "male",
            "sample_path": "", "created_at": "2026-01-01", "size_bytes": 0
        },
    }
    for k, v in builtin.items():
        if k not in voices:
            voices[k] = v
    save_voices(voices)

def extract_voice_features(audio_path: Path) -> dict:
    """Extract voice characteristics from audio file for cloning"""
    import librosa, numpy as np

    # Load audio
    y, sr = librosa.load(str(audio_path), sr=22050, duration=15)
    duration = len(y) / sr

    # Basic features
    features = {
        "duration_sec": round(duration, 1),
        "sample_rate": sr,
        "rms_energy": float(np.sqrt(np.mean(y**2))),
        "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y))),
    }

    # Pitch (fundamental frequency)
    try:
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        valid_pitches = pitches[pitches > 0]
        if len(valid_pitches) > 0:
            features["mean_pitch_hz"] = float(np.mean(valid_pitches))
            features["pitch_std_hz"] = float(np.std(valid_pitches))
    except:
        features["mean_pitch_hz"] = 0

    # Spectral features
    try:
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        features["spectral_centroid"] = float(spectral_centroid)
    except:
        pass

    # MFCC for voice fingerprint
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features["mfcc_mean"] = [float(x) for x in np.mean(mfcc, axis=1)[:5]]
    except:
        features["mfcc_mean"] = []

    return features

def clone_via_vieneu(audio_path: Path, voice_name: str, ref_text: str = "") -> dict:
    """REAL voice clone via VieNeu clone-speech (6023)."""
    import requests
    features = extract_voice_features(audio_path)

    if ref_text and ref_text.strip():
        try:
            # Generate a real clone preview via VieNeu clone-speech
            preview_text = f"Xin chào, tôi là {voice_name}. Đây là giọng nói nhân bản."
            payload = {
                "input": preview_text,
                "ref_audio_path": str(audio_path),
                "ref_text": ref_text,
                "response_format": "mp3"
            }
            resp = requests.post(
                "http://localhost:6023/v1/audio/clone-speech",
                json=payload, timeout=180
            )
            if resp.status_code == 200:
                print(f"[clone] VieNeu clone-speech OK for {voice_name}", flush=True)
                return {"success": True, "method": "vieneu_clone", "voice_name": voice_name,
                        "features": features, "preview_bytes": len(resp.content)}
            else:
                print(f"[clone] VieNeu returned {resp.status_code}: {resp.text[:80]}", flush=True)
        except Exception as e:
            print(f"[clone] VieNeu clone-speech failed: {e}", flush=True)

    return {"success": True, "method": "feature_extraction", "features": features,
            "note": "Voice stored. Provide ref_text for real clone."}


# ===== INIT =====
init_builtin_voices()

# ===== API ENDPOINTS =====

@app.get("/api/voices")
def list_voices():
    """List all voices in library (builtin + cloned)"""
    voices = load_voices()
    return {"voices": list(voices.values()), "count": len(voices),
            "cloned_count": sum(1 for v in voices.values() if v["source"] == "clone")}

@app.get("/api/voices/{voice_id}")
def get_voice(voice_id: str):
    """Get single voice metadata"""
    voices = load_voices()
    if voice_id not in voices:
        raise HTTPException(404, "Voice not found")
    return voices[voice_id]

@app.post("/api/voices/clone")
async def clone_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    engine: str = Form("vieneu"),
    language: str = Form("vi"),
    gender: str = Form("unknown"),
    ref_text: str = Form(""),
    region: str = Form(None),
):
    """Upload audio file to clone a new voice"""
    if not file.filename:
        raise HTTPException(400, "No file uploaded")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in ['.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac']:
        raise HTTPException(400, f"Unsupported format: {ext}. Use .wav, .mp3, .m4a")

    # Generate voice ID
    voice_id = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

    # Save uploaded file (atomic write via .partial)
    content = await file.read()
    partial_path = CLONE_DIR / f"{voice_id}.partial{ext}"
    clone_path = CLONE_DIR / f"{voice_id}{ext}"

    # Write to .partial first
    with open(partial_path, 'wb') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())

    # Verify file integrity before finalizing
    if len(content) == 0:
        partial_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file is empty")

    # Verify audio format with ffprobe
    try:
        probe = subprocess.run(
            ['/opt/homebrew/bin/ffprobe', '-v', 'quiet', '-show_entries', 'format=duration,format_name',
             '-of', 'csv=p=0', str(partial_path)],
            capture_output=True, text=True, timeout=15
        )
        if probe.returncode != 0:
            partial_path.unlink(missing_ok=True)
            raise HTTPException(400, "Uploaded file is not valid audio")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, Exception):
        partial_path.unlink(missing_ok=True)
        raise HTTPException(400, "Audio validation timed out")

    # Atomic finalize
    try:
        os.replace(partial_path, clone_path)
    finally:
        # Catch-all: remove .partial if atomic rename failed
        if partial_path.exists():
            partial_path.unlink(missing_ok=True)

    # Convert to WAV if needed (for consistent processing)
    wav_path = CLONE_DIR / f"{voice_id}_ref.wav"
    if ext != '.wav':
        subprocess.run([
            'ffmpeg', '-y', '-i', str(clone_path),
            '-ar', '22050', '-ac', '1', '-sample_fmt', 's16',
            str(wav_path)
        ], capture_output=True, timeout=30)
    else:
        shutil.copy(clone_path, wav_path)

    # Clone voice
    result = clone_via_vieneu(wav_path, name, ref_text)

    # Generate preview sample — use clone-speech if ref_text provided
    preview_path = PREVIEW_DIR / f"{voice_id}_preview.mp3"
    preview_text = f"Xin chào, tôi là {name}. Đây là giọng nói đã được tạo bởi X Video Studio của AI World."
    try:
        import requests
        if ref_text and ref_text.strip() and result.get("method") == "vieneu_clone":
            # Use clone-speech for a real preview
            resp = requests.post(
                "http://localhost:6023/v1/audio/clone-speech",
                json={"input": preview_text, "ref_audio_path": str(wav_path),
                      "ref_text": ref_text, "response_format": "mp3"},
                timeout=120
            )
            if resp.status_code == 200:
                preview_path.write_bytes(resp.content)
        else:
            # Fallback to regular TTS
            resp = requests.post(
                "http://localhost:6023/v1/audio/speech",
                json={"model": "vieneu", "input": preview_text, "voice": "female_south", "speed": 1.0},
                timeout=60
            )
            if resp.status_code == 200:
                preview_path.write_bytes(resp.content)
    except Exception as e:
        print(f"Preview generation failed: {e}")
        # Silent preview
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
            '-t', '2', str(preview_path)
        ], capture_output=True)

    # Save metadata
    voices = load_voices()
    voices[voice_id] = {
        "id": voice_id,
        "name": name,
        "engine": engine,
        "source": "clone",
        "language": language,
        "gender": gender,
        "sample_path": str(clone_path),
        "preview_path": str(preview_path),
        "created_at": datetime.now().isoformat(),
        "size_bytes": len(content),
        "clone_method": result.get("method", "unknown"),
        "features": result.get("features", {}),
        "ref_text": ref_text if ref_text else "",
        "ref_audio_path": str(wav_path),
    }
    save_voices(voices)

    return {"success": True, "voice": voices[voice_id]}

@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str):
    """Delete a cloned voice (builtin voices cannot be deleted)"""
    voices = load_voices()
    if voice_id not in voices:
        raise HTTPException(404, "Voice not found")
    if voices[voice_id]["source"] == "builtin":
        raise HTTPException(400, "Cannot delete built-in voices")

    # Remove files
    paths = [
        CLONE_DIR / f"{voice_id}.wav",
        CLONE_DIR / f"{voice_id}.mp3",
        CLONE_DIR / f"{voice_id}.m4a",
        CLONE_DIR / f"{voice_id}_ref.wav",
        PREVIEW_DIR / f"{voice_id}_preview.mp3",
    ]
    for p in paths:
        if p.exists():
            p.unlink()

    del voices[voice_id]
    save_voices(voices)
    return {"success": True, "deleted": voice_id}

@app.get("/api/preview/{voice_id}")
def preview_voice(voice_id: str):
    """Get/preview a voice sample"""
    voices = load_voices()
    if voice_id not in voices:
        raise HTTPException(404, "Voice not found")

    v = voices[voice_id]

    # If cloned voice has a preview, serve it
    preview = v.get("preview_path", "")
    if preview and Path(preview).exists():
        return FileResponse(preview, media_type="audio/mp3",
                          headers={"Content-Disposition": "inline"})

    # For builtin voices, generate live preview
    text = f"Xin chào, đây là giọng {v['name']}."
    if v["engine"] == "macos":
        voice = v["id"]
        lang = "en"
        text = f"Hello, this is {v['name']}."
    else:
        voice = v["id"]
        lang = "vi"

    # Generate via VieNeu TTS directly
    preview_cache = PREVIEW_DIR / f"{voice_id}_preview.mp3"
    if not preview_cache.exists() or preview_cache.stat().st_size < 1000:
        try:
            import requests
            if v["engine"] == "macos":
                import subprocess, shutil
                aiff = PREVIEW_DIR / f"{voice_id}_tmp.aiff"
                subprocess.run(["say", "-v", voice_id, text, "-o", str(aiff)], timeout=20)
                subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", str(aiff),
                    "-acodec", "libmp3lame", "-b:a", "128k", str(preview_cache)],
                    capture_output=True, timeout=20)
                if aiff.exists(): aiff.unlink()
            else:
                resp = requests.post(
                    "http://localhost:6023/v1/audio/speech",
                    json={"model": "vieneu", "input": text, "voice": voice_id, "speed": 1.0},
                    timeout=120
                )
                if resp.status_code == 200:
                    preview_cache.write_bytes(resp.content)
        except Exception as e:
            print(f"Preview generation failed for {voice_id}: {e}")
    if preview_cache.exists() and preview_cache.stat().st_size > 100:
        return FileResponse(str(preview_cache), media_type="audio/mp3",
                          headers={"Content-Disposition": "inline",
                                   "Cache-Control": "max-age=3600"})
    raise HTTPException(503, "Preview generation failed")

@app.post("/api/voices/warmup")
def warmup_all():
    """Warm up all TTS engines"""
    results = {}
    for engine, endpoint in TTS_ENDPOINTS.items():
        try:
            resp = subprocess.run(
                ['curl', '-s', '-X', 'POST', endpoint.replace('/v1/audio/speech', '/warmup'),
                 '-H', 'Content-Type: application/json'],
                capture_output=True, text=True, timeout=10
            )
            results[engine] = "ok" if resp.returncode == 0 else "failed"
        except:
            results[engine] = "error"
    return {"warmed_up": results}

@app.get("/api/stats")
def get_stats():
    """Library statistics"""
    voices = load_voices()
    builtin = [v for v in voices.values() if v["source"] == "builtin"]
    cloned = [v for v in voices.values() if v["source"] == "clone"]
    total_size = sum(
        Path(v.get("sample_path", "")).stat().st_size
        for v in cloned
        if v.get("sample_path") and Path(v["sample_path"]).exists()
    )
    return {
        "total_voices": len(voices),
        "builtin_voices": len(builtin),
        "cloned_voices": len(cloned),
        "total_clone_size_mb": round(total_size / 1024 / 1024, 2),
        "library_path": str(VOICE_DIR),
    }

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "voice-library", "machine": "Macmini M4"}

# ===== MAIN =====

# ===== CUSTOM FIELDS & METADATA MANAGEMENT =====

@app.get("/api/voice-library/custom-fields")
def get_custom_fields():
    """Get available custom fields configuration"""
    return {
        "custom_fields": [
            {"id": "language", "name": "Ngôn ngữ", "type": "select", "options": [
                {"id": "vi", "name": "Tiếng Việt", "flag": "🇻🇳"},
                {"id": "en", "name": "English", "flag": "🇺🇸"},
                {"id": "zh-cn", "name": "中文", "flag": "🇨🇳"},
                {"id": "ko", "name": "한국어", "flag": "🇰🇷"},
                {"id": "ja", "name": "日本語", "flag": "🇯🇵"},
                {"id": "fr", "name": "Français", "flag": "🇫🇷"},
                {"id": "de", "name": "Deutsch", "flag": "🇩🇪"},
                {"id": "es", "name": "Español", "flag": "🇪🇸"},
                {"id": "it", "name": "Italiano", "flag": "🇮🇹"},
                {"id": "pt", "name": "Português", "flag": "🇵🇹"},
                {"id": "ru", "name": "Русский", "flag": "🇷🇺"},
                {"id": "ar", "name": "العربية", "flag": "🇸🇦"},
                {"id": "th", "name": "ไทย", "flag": "🇹🇭"},
                {"id": "hi", "name": "हिन्दी", "flag": "🇮🇳"},
                {"id": "nl", "name": "Nederlands", "flag": "🇳🇱"},
                {"id": "pl", "name": "Polski", "flag": "🇵🇱"},
            ]},
            {"id": "gender", "name": "Giới tính", "type": "select", "options": [
                {"id": "female", "name": "Nữ"}, {"id": "male", "name": "Nam"}, {"id": "neutral", "name": "Trung tính"}
            ]},
            {"id": "region", "name": "Vùng miền", "type": "select", "options": [
                {"id": "south", "name": "Miền Nam"}, {"id": "north", "name": "Miền Bắc"}, {"id": "central", "name": "Miền Trung"}
            ]},
            {"id": "pitch", "name": "Giọng", "type": "select", "options": [
                {"id": "high", "name": "Cao"}, {"id": "mid", "name": "Trung bình"}, {"id": "low", "name": "Trầm"}
            ]},
            {"id": "expression", "name": "Biểu cảm", "type": "select", "options": [
                {"id": "gentle", "name": "Hiền hòa"}, {"id": "lively", "name": "Sôi nổi"},
                {"id": "strong", "name": "Mạnh mẽ"}, {"id": "soft", "name": "Nhẹ nhàng"},
                {"id": "serious", "name": "Nghiêm túc"}, {"id": "happy", "name": "Vui vẻ"},
                {"id": "funny", "name": "Hài hước"}
            ]},
            {"id": "profession", "name": "Nghề nghiệp", "type": "select", "options": [
                {"id": "blogger", "name": "Blogger"}, {"id": "journalist", "name": "Báo chí"},
                {"id": "storyteller", "name": "Kể truyện"}, {"id": "news", "name": "Thời sự"},
                {"id": "teacher", "name": "Giáo viên"}, {"id": "mc", "name": "MC"},
                {"id": "actor", "name": "Diễn viên"}
            ]},
            {"id": "age", "name": "Độ tuổi", "type": "select", "options": [
                {"id": "young", "name": "Trẻ (18-30)"}, {"id": "adult", "name": "Trung niên (31-50)"},
                {"id": "elder", "name": "Cao tuổi (50+)"}
            ]},
            {"id": "style", "name": "Phong cách", "type": "select", "options": [
                {"id": "normal", "name": "Nghiêm túc"}, {"id": "funny", "name": "Hài hước"},
                {"id": "serious", "name": "Trang trọng"}
            ]},
        ]
    }


@app.put("/api/voices/{voice_id}")
def update_voice(voice_id: str, data: dict):
    """Update voice metadata including custom fields"""
    voices = load_voices()
    if voice_id not in voices:
        raise HTTPException(404, "Voice not found")

    v = voices[voice_id]
    allowed = ["name", "engine", "language", "gender", "region", "pitch",
               "expression", "profession", "age", "style", "tags", "is_favorite"]

    for key in allowed:
        if key in data:
            v[key] = data[key]

    # Handle custom_fields
    custom_fields = data.get("custom_fields", {})
    if custom_fields:
        if "custom_fields" not in v:
            v["custom_fields"] = {}
        for k, val in custom_fields.items():
            v["custom_fields"][k] = val
            # Also set top-level for compatibility
            if k in allowed:
                v[k] = val

    # Update timestamp
    v["updated_at"] = datetime.now().isoformat()

    voices[voice_id] = v
    save_voices(voices)
    return {"success": True, "voice": v}


@app.get("/api/voices/search")
def search_voices(
    q: str = "",
    sort: str = "added_timestamp",
    order: str = "desc",
    page: int = 1,
    per_page: int = 12,
    language: str = "",
    gender: str = "",
    region: str = "",
    pitch: str = "",
    expression: str = "",
    profession: str = "",
    age: str = "",
    style: str = "",
    source: str = "",
    is_favorite: bool = None
):
    """Search, filter, sort, paginate voices"""
    voices = list(load_voices().values())

    # Filter by q (search name/tags)
    if q:
        ql = q.lower()
        voices = [v for v in voices
                  if ql in v.get("name", "").lower() or
                     ql in " ".join(v.get("tags", [])).lower()]

    # Filter by custom fields
    filters = {"language": language, "gender": gender, "region": region,
               "pitch": pitch, "expression": expression, "profession": profession,
               "age": age, "style": style, "source": source}
    for fk, fv in filters.items():
        if fv and fv.strip():
            voices = [v for v in voices if v.get(fk, "") == fv]

    if is_favorite is not None:
        voices = [v for v in voices if v.get("is_favorite", False) == is_favorite]

    # Sort
    reverse = order.lower() == "desc"
    sort_options = {
        "name": lambda v: v.get("name", "").lower(),
        "added_timestamp": lambda v: v.get("created_at", ""),
        "quality_score": lambda v: v.get("quality_score", 0),
        "usage_count": lambda v: v.get("usage_count", 0),
    }
    sort_key = sort_options.get(sort, sort_options["added_timestamp"])
    voices.sort(key=sort_key, reverse=reverse)

    # Paginate
    total = len(voices)
    start = (page - 1) * per_page
    end = start + per_page
    page_voices = voices[start:end]

    return {
        "voices": page_voices,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page))  # ceil division
    }


@app.post("/api/voices/{voice_id}/favorite")
def toggle_favorite(voice_id: str):
    """Toggle favorite status"""
    voices = load_voices()
    if voice_id not in voices:
        raise HTTPException(404, "Voice not found")
    v = voices[voice_id]
    v["is_favorite"] = not v.get("is_favorite", False)
    save_voices(voices)
    return {"success": True, "is_favorite": v["is_favorite"]}

@app.get("/api/tts-status")
def check_tts_status():
    """Check all TTS backends"""
    import urllib.request as ureq
    endpoints = {
        "vieneu": ("http://127.0.0.1:6023", "VieNeu TTS"),
        "omnivoice": ("http://127.0.0.1:6024", "OmniVoice TTS"),
        "valtec": ("http://127.0.0.1:6025", "Valtec TTS"),
        "xvideo_main": ("http://127.0.0.1:8767", "X-Video Backend"),
    }
    results = {}
    all_ok = True
    for name, (url, label) in endpoints.items():
        try:
            req = ureq.Request(url + "/health" if name in ("vieneu","omnivoice","valtec") else url + "/healthz")
            with ureq.urlopen(req, timeout=3) as r:
                body = r.read().decode()
                results[name] = {"status": "connected", "label": label}
        except Exception as e:
            results[name] = {"status": "disconnected", "label": label, "error": str(e)}
            all_ok = False
    return {"overall": "all_connected" if all_ok else "partial", "services": results}

if __name__ == "__main__":
    print(f"🎤 X-Video Voice Library")
    print(f"   Library: {VOICE_DIR}")
    print(f"   API: http://0.0.0.0:8769")
    print(f"   Voices: {len(load_voices())} total")
    uvicorn.run(app, host="0.0.0.0", port=8769)

