import re

VISUAL_TYPES = ["kinetic_quote","data_card","process_flow","takeaway","image_card"]
MOTION_BY_TYPE = {
    "kinetic_quote":"typewriter",
    "data_card":"count_up",
    "process_flow":"flow_lines",
    "takeaway":"slide_up",
    "image_card":"zoom_mesh",
}
STOP = set("và là của có cho với một những các được trong khi từ đến này kia đó như về vào ra không đã sẽ đang nếu thì để nhưng hoặc".split())

NUMBER_RE = re.compile(r"(?<!\w)(?:\d+[\d\.,]*\s*(?:%|giây|s|phút|h|giờ|ngày|bài|cảnh|lần|triệu|tỷ|USD|đồng|token)?)(?!\w)", re.I)
ENTITY_RE = re.compile(r"\b(?:[A-ZĐ][\wÀ-ỹ0-9\-]*(?:\s+[A-ZĐ][\wÀ-ỹ0-9\-]*){0,3}|[A-Z0-9]{2,}(?:-[A-Z0-9]+)*)\b")

def clean_words(text):
    return [w.lower().strip(".,:;!?()[]{}\"'“”‘’") for w in re.findall(r"[\wÀ-ỹ\-]{3,}", text or "")]

def extract_numbers(text):
    out=[]
    for m in NUMBER_RE.findall(text or ""):
        v=m.strip()
        if v and v not in out: out.append(v)
    return out[:6]

def extract_entities(text):
    bad={"Có","Nhưng","Nếu","Khi","Điều","Cần","Phải","Không","Một","Những","Các"}
    out=[]
    for m in ENTITY_RE.findall(text or ""):
        v=m.strip()
        if len(v) < 2 or v in bad: continue
        if v.lower() in STOP: continue
        if v not in out: out.append(v)
    return out[:8]

def extract_keywords(text):
    counts={}
    for w in clean_words(text):
        if w in STOP or w.isdigit(): continue
        counts[w]=counts.get(w,0)+1
    return [w for w,_ in sorted(counts.items(), key=lambda kv:(-kv[1], -len(kv[0]), kv[0]))[:6]]

def headline_for(text, keywords=None):
    t=re.sub(r"\s+"," ",(text or "").strip())
    parts=re.split(r"(?<=[.!?;])\s+", t)
    h=(parts[0] if parts else t)[:86].strip(" -–—")
    if len(h) < 18 and keywords:
        h=(" · ".join(keywords[:3])).title()
    return h or "Điểm chính"

def classify_visual_type(text, image=None, order=0):
    low=(text or "").lower()
    nums=extract_numbers(text)
    if image:
        return "image_card"
    if any(k in low for k in ["bài học", "kết luận", "chốt", "rút ra", "điểm mấu chốt"]):
        return "takeaway"
    if any(k in low for k in ["bước", "quy trình", "pipeline", "đầu tiên", "tiếp theo", "sau đó", "cuối cùng", "->", "→"]):
        return "process_flow"
    if nums:
        return "data_card"
    return "kinetic_quote"

def enrich_scene(scene, order=0):
    text=scene.get("text") or ""
    kws=extract_keywords(text)
    vtype=scene.get("visual_type") or classify_visual_type(text, scene.get("image"), order)
    scene.update({
        "headline": scene.get("headline") or headline_for(text, kws),
        "keywords": scene.get("keywords") or kws,
        "entities": scene.get("entities") or extract_entities(text),
        "numbers": scene.get("numbers") or extract_numbers(text),
        "visual_type": vtype,
        "motion_preset": scene.get("motion_preset") or MOTION_BY_TYPE.get(vtype,"slide_up"),
        "assets": scene.get("assets") or {"article_image": scene.get("image"), "stock_image": None, "icon": None},
        "asset_policy": scene.get("asset_policy") or ("article_only" if scene.get("image") else "none"),
        "preview": scene.get("preview") or {"png": None, "mp4": None, "status": "pending"},
    })
    return scene
