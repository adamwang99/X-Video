"""
Pexels stock video/image integration for X-Video (v1.9.0)
Added by Tiep QSO 2026-06-06.

Fetches HD stock footage/photos from Pexels to use as scene backgrounds
when article images are missing or to enrich visuals.
"""
import json, os, re, urllib.request, urllib.parse, urllib.error

# Force IPv4 to avoid macOS IPv6 stall (urllib AAAA hang ~24s)
import socket as _socket
_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, _socket.AF_INET, type, proto, flags)
_socket.getaddrinfo = _ipv4_only


# SECURITY: key is NOT hardcoded. Loaded from env PEXELS_KEY or the runtime
# key store (render-project/api_keys.json, gitignored). Empty default is safe.
PEXELS_KEY = os.environ.get("PEXELS_KEY", "")

# Optional key manager for multi-key fallback (set by server at init)
_keymgr = None
def set_keymanager(mgr):
    global _keymgr
    _keymgr = mgr

def _candidate_keys():
    """Return ordered list of keys to try: manager keys first, else hardcoded."""
    if _keymgr:
        keys = _keymgr.get_all_active_keys("pexels")
        if keys:
            return keys
    return [PEXELS_KEY]

# Vietnamese -> English keyword hints for better Pexels matching
_VI_EN = {
    "trí tuệ nhân tạo": "artificial intelligence", "công nghệ": "technology",
    "máy tính": "computer", "dữ liệu": "data", "mạng": "network",
    "robot": "robot", "lập trình": "programming", "khóa học": "online course",
    "doanh nghiệp": "business", "tài chính": "finance", "y tế": "healthcare",
    "giáo dục": "education", "ô tô": "car", "điện thoại": "smartphone",
    "an ninh mạng": "cybersecurity", "đám mây": "cloud computing",
    "khoa học": "science", "vũ trụ": "space", "năng lượng": "energy",
    "thành phố": "city", "tương lai": "futuristic", "tự động": "automation",
}

# Stopwords to drop when deriving keywords
_STOP = set("và là của có trong cho được một những các với khi từ này đó để theo về như đã sẽ tại trên dưới ra vào the a an of to in for and or is are with".split())


def _derive_keywords_rule(title, content, max_terms=3):
    """Derive English search keywords from VN/EN title+content."""
    text = f"{title} {content}".lower()
    # direct VI->EN hints first
    hits = []
    for vi, en in _VI_EN.items():
        if vi in text and en not in hits:
            hits.append(en)
    if hits:
        return hits[:max_terms]
    # fallback: longest non-stop words from title
    words = re.findall(r'[a-zA-ZÀ-ỹ]{4,}', title.lower())
    words = [w for w in words if w not in _STOP]
    # if title is mostly english, use as-is
    en_words = [w for w in words if re.match(r'^[a-z]+$', w)]
    if en_words:
        return en_words[:max_terms]
    return ["technology", "abstract"]


def derive_keywords(title, content, max_terms=3, llm_opts=None):
    """LLM-first English Pexels keywords from VN/EN article; rule-based fallback.

    Returns concrete, visual search terms (e.g. ["artificial intelligence",
    "data center", "robot"]) instead of generic "technology". Falls back to the
    static VI->EN map on any LLM failure.
    """
    lo = llm_opts or {}
    prov = lo.get("provider")
    if prov and prov not in ("local", "ollama", "local_ollama"):
        try:
            import xvideo_llm
            prompt = (
                "Tu tieu de + noi dung bai bao sau, hay tra ve "
                + str(max_terms) + " tu khoa TIENG ANH NGAN (1-3 tu) de tim "
                "ANH/VIDEO STOCK tren Pexels khop voi noi dung. Uu tien danh tu CU THE, "
                "TRUC QUAN (vd: data center, robot arm, stock market, electric car), "
                "TRANH tu chung chung nhu technology/abstract. "
                'Tra ve DUY NHAT JSON: {"keywords":["...","..."]} khong them gi.\n\n'
                "Tieu de: " + (title or "")[:200] + "\nNoi dung: " + (content or "")[:1500]
            )
            resp = xvideo_llm.complete(prompt, provider=prov, model=lo.get("model") or None,
                                       json_mode=True, temperature=0.3, max_tokens=200,
                                       timeout=60, base_url=lo.get("base_url"))
            import json as _j
            data = _j.loads(resp or "{}")
            kws = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()]
            # keep only ascii-ish english terms; drop generic ones
            _generic = {"technology", "abstract", "tech", "background", "concept"}
            kws = [k for k in kws if k.lower() not in _generic]
            if kws:
                return kws[:max_terms]
        except Exception as e:
            print(f"[pexels] llm keywords failed, fallback rule: {e}", flush=True)
    return _derive_keywords_rule(title, content, max_terms)


def search_videos(keyword, orientation="portrait", per_page=3):
    """Search Pexels videos with multi-key fallback. Returns HD download links."""
    q = urllib.parse.quote(keyword)
    url = f"https://api.pexels.com/videos/search?query={q}&per_page={per_page}&orientation={orientation}"
    for key in _candidate_keys():
        try:
            req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0 (Macintosh) XVideo/1.9"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if _keymgr: _keymgr.mark_ok("pexels", key)
            links = []
            for v in data.get("videos", []):
                files = v.get("video_files", [])
                hd = [f for f in files if f.get("quality") == "hd" and (f.get("height") or 0) <= 1920]
                pick = hd[0] if hd else (files[0] if files else None)
                if pick and pick.get("link"):
                    links.append(pick["link"])
            return links
        except urllib.error.HTTPError as e:
            print(f"[pexels] video '{keyword}' key …{key[-4:]} HTTP {e.code}", flush=True)
            if e.code in (401, 403, 429) and _keymgr:
                _keymgr.mark_failed("pexels", key, f"HTTP {e.code}")
                continue  # try next key
            return []
        except Exception as e:
            print(f"[pexels] video search fail '{keyword}': {e}", flush=True)
            return []
    return []


def search_photos(keyword, orientation="portrait", per_page=3):
    """Search Pexels photos with multi-key fallback. Returns image URLs."""
    q = urllib.parse.quote(keyword)
    url = f"https://api.pexels.com/v1/search?query={q}&per_page={per_page}&orientation={orientation}"
    for key in _candidate_keys():
        try:
            req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0 (Macintosh) XVideo/1.9"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if _keymgr: _keymgr.mark_ok("pexels", key)
            out = []
            for p in data.get("photos", []):
                src = p.get("src", {})
                link = src.get("large2x") or src.get("large") or src.get("original")
                if link:
                    out.append(link)
            return out
        except urllib.error.HTTPError as e:
            print(f"[pexels] photo '{keyword}' key …{key[-4:]} HTTP {e.code}", flush=True)
            if e.code in (401, 403, 429) and _keymgr:
                _keymgr.mark_failed("pexels", key, f"HTTP {e.code}")
                continue
            return []
        except Exception as e:
            print(f"[pexels] photo search fail '{keyword}': {e}", flush=True)
            return []
    return []


def fetch_stock_videos(title, content, n_scenes, orientation="portrait", jd=None):
    """
    Fetch n_scenes stock videos, download to jd/assets. Returns list of local rel paths.
    """
    if not jd:
        return []
    keywords = derive_keywords(title, content)
    print(f"[pexels] keywords: {keywords}", flush=True)
    links = []
    for kw in keywords:
        links += search_videos(kw, orientation, per_page=3)
        if len(links) >= n_scenes:
            break
    # de-dup preserve order
    seen, uniq = set(), []
    for l in links:
        if l not in seen:
            seen.add(l); uniq.append(l)
    asset_dir = os.path.join(str(jd), "assets")
    os.makedirs(asset_dir, exist_ok=True)
    local = []
    for idx, link in enumerate(uniq[:n_scenes]):
        try:
            fn = f"stock_{idx}.mp4"
            fp = os.path.join(asset_dir, fn)
            req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0 XVideo"})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read(40 * 1024 * 1024)  # cap 40MB per clip
            if len(data) < 10000:
                continue
            with open(fp, "wb") as f:
                f.write(data)
            local.append(f"assets/{fn}")
        except Exception as e:
            print(f"[pexels] dl fail {link[:60]}: {e}", flush=True)
    print(f"[pexels] downloaded {len(local)} stock videos", flush=True)
    return local


def orientation_for_aspect(aspect):
    return {"doc": "portrait", "ngang": "landscape", "vuong": "square"}.get(aspect, "portrait")
