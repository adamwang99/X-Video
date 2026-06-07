"""
Storyboard manager for X-Video (v1.11.0)
Added by Tiep QSO 2026-06-06.

Two-phase pipeline:
  Phase 1 (plan): build_storyboard() -> scene list (text + image + duration), persisted to storyboard.json
  Phase 2 (manage): CRUD scenes via API (add/edit/delete/reorder/regenerate)
  Phase 3 (render): render_storyboard() -> per-scene animated HTML -> single video

Each scene: {id, order, text, image (local rel path or url), keyword, duration, layout}
Layouts give each scene a content-appropriate animated style.
"""
import json, os, re, time, html as _html

LAYOUTS = ["kenburns-zoom", "kenburns-pan", "split-reveal", "fade-up", "center-pop"]
VISUAL_TYPES = ["kinetic_quote", "data_card", "process_flow", "takeaway", "image_card"]


def _sid():
    return "s" + str(int(time.time() * 1000))[-9:] + str(int(time.time() * 1000000) % 1000)


def sb_path(jd):
    return os.path.join(str(jd), "storyboard.json")


def save(jd, sb):
    tmp = sb_path(jd) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sb, f, indent=2, ensure_ascii=False)
    os.replace(tmp, sb_path(jd))


def load(jd):
    try:
        with open(sb_path(jd)) as f:
            return json.load(f)
    except Exception:
        return None


def build_storyboard(title, content, narration, local_imgs, duration, aspect, style,
                     resolution, keywords=None):
    """Build initial scene list. Returns storyboard dict."""
    # LLM-first scene segmentation (concise rewrite, keep meaning, no mid-text "...").
    # Falls back to rule-based split inside build_scenes_smart on any LLM failure.
    import xvideo_scenes
    raw = xvideo_scenes.build_scenes_smart(narration, local_imgs or [None], duration)
    scenes = []
    for i, sc in enumerate(raw):
        scene = {
            "id": _sid() + str(i),
            "order": i,
            "text": sc["text"],
            "image": sc.get("image"),
            "keyword": (keywords[i % len(keywords)] if keywords else None),
            "duration": sc["dur"],
            "start": sc["start"],
            "layout": LAYOUTS[i % len(LAYOUTS)],
        }
        # Prefer the LLM-provided headline when present.
        if sc.get("headline"):
            scene["headline"] = sc["headline"]
        try:
            import xvideo_scene_analyzer
            scene = xvideo_scene_analyzer.enrich_scene(scene, i)
        except Exception as e:
            print("[storyboard] enrich failed:", e, flush=True)
        scenes.append(scene)
    return {
        "title": title, "aspect": aspect, "style": style, "resolution": resolution,
        "total_duration": duration, "scenes": scenes,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _recompute_timing(sb):
    """Recompute start/duration proportional to word count, normalized to total_duration."""
    scenes = sorted(sb["scenes"], key=lambda s: s.get("order", 0))
    total_words = sum(max(1, len(s["text"].split())) for s in scenes) or 1
    total = sb.get("total_duration") or 30
    acc = 0.0
    for i, s in enumerate(scenes):
        wc = max(1, len(s["text"].split()))
        s["order"] = i
        s["duration"] = round(max(2.0, total * wc / total_words), 2)
    # normalize
    cur = sum(s["duration"] for s in scenes) or 1
    scale = total / cur
    acc = 0.0
    for s in scenes:
        s["duration"] = round(s["duration"] * scale, 2)
        s["start"] = round(acc, 2)
        acc += s["duration"]
    sb["scenes"] = scenes
    return sb


# ---- CRUD ----
def add_scene(sb, text="Phân cảnh mới", image=None, after_id=None):
    order = len(sb["scenes"])
    if after_id:
        for s in sb["scenes"]:
            if s["id"] == after_id:
                order = s["order"] + 1
                break
    new = {"id": _sid() + "n", "order": order, "text": text, "image": image,
           "keyword": None, "duration": 3.0, "start": 0, "layout": LAYOUTS[order % len(LAYOUTS)]}
    try:
        import xvideo_scene_analyzer
        new = xvideo_scene_analyzer.enrich_scene(new, order)
    except Exception as e:
        print("[storyboard] enrich add failed:", e, flush=True)
    # shift orders
    for s in sb["scenes"]:
        if s["order"] >= order:
            s["order"] += 1
    sb["scenes"].append(new)
    _recompute_timing(sb)
    return new["id"]


def update_scene(sb, sid, text=None, image=None, layout=None, duration=None,
                 visual_type=None, motion_preset=None, asset_policy=None, headline=None):
    for s in sb["scenes"]:
        if s["id"] == sid:
            changed_text = text is not None and text != s.get("text")
            if text is not None: s["text"] = text
            if image is not None: s["image"] = image
            if layout is not None: s["layout"] = layout
            if duration is not None: s["duration"] = float(duration)
            if visual_type is not None: s["visual_type"] = visual_type
            if motion_preset is not None: s["motion_preset"] = motion_preset
            if asset_policy is not None: s["asset_policy"] = asset_policy
            if headline is not None: s["headline"] = headline
            if changed_text:
                for k in ("keywords", "entities", "numbers"):
                    s.pop(k, None)
                if headline is None: s.pop("headline", None)
                if visual_type is None: s.pop("visual_type", None)
                if motion_preset is None: s.pop("motion_preset", None)
            try:
                import xvideo_scene_analyzer
                s = xvideo_scene_analyzer.enrich_scene(s, s.get("order", 0))
            except Exception as e:
                print("[storyboard] enrich update failed:", e, flush=True)
            _recompute_timing(sb)
            return True
    return False


def delete_scene(sb, sid):
    n = len(sb["scenes"])
    sb["scenes"] = [s for s in sb["scenes"] if s["id"] != sid]
    if len(sb["scenes"]) < n:
        _recompute_timing(sb)
        return True
    return False


def reorder_scenes(sb, ordered_ids):
    idmap = {s["id"]: s for s in sb["scenes"]}
    new = []
    for i, sid in enumerate(ordered_ids):
        if sid in idmap:
            idmap[sid]["order"] = i
            new.append(idmap[sid])
    if new:
        sb["scenes"] = new
        _recompute_timing(sb)
        return True
    return False


def regenerate_scene_image(sb, sid, jd):
    """Fetch a fresh stock image for a scene based on its keyword/text."""
    try:
        import xvideo_pexels, xvideo_scenes
    except Exception:
        return None
    sc = next((s for s in sb["scenes"] if s["id"] == sid), None)
    if not sc:
        return None
    kw = sc.get("keyword") or " ".join(sc["text"].split()[:4])
    kws = xvideo_pexels.derive_keywords(kw, sc["text"])
    orient = xvideo_pexels.orientation_for_aspect(sb.get("aspect", "doc"))
    urls = []
    for k in kws:
        urls += xvideo_pexels.search_photos(k, orient, per_page=5)
    if not urls:
        return None
    # pick a different one each regenerate using a rotating index stored on scene
    idx = (sc.get("_regen", 0)) % len(urls)
    sc["_regen"] = sc.get("_regen", 0) + 1
    # download with unique name to avoid clobbering other scenes' img_N files
    import urllib.request, os as _os, time as _t
    asset_dir = _os.path.join(str(jd), "assets")
    _os.makedirs(asset_dir, exist_ok=True)
    fn = "regen_%s_%d.jpg" % (sid[-6:], int(_t.time()))
    fp = _os.path.join(asset_dir, fn)
    try:
        req = urllib.request.Request(urls[idx], headers={"User-Agent": "Mozilla/5.0 XVideo"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(8 * 1024 * 1024)
        if len(data) < 2000:
            return None
        with open(fp, "wb") as wf:
            wf.write(data)
        sc["image"] = "assets/" + fn
        return sc["image"]
    except Exception as e:
        print("[storyboard] regen dl fail:", e, flush=True)
        return None


# ---- render single combined HTML from storyboard ----
def render_html(sb, voice_file, bgm_file, date_str, ASPECT_MAP, RES_MAP):
    """Convert storyboard scenes -> the format make_html_scenes expects, then build HTML."""
    import xvideo_scenes
    _recompute_timing(sb)
    scenes = []
    for s in sorted(sb["scenes"], key=lambda x: x["order"]):
        scenes.append({"text": s["text"], "image": s.get("image"),
                       "dur": s["duration"], "start": s["start"]})
    return xvideo_scenes.make_html_scenes(
        sb.get("aspect", "doc"), sb.get("title", ""), date_str,
        sb.get("total_duration", 30), voice_file, bgm_file,
        scenes, ASPECT_MAP, RES_MAP, sb.get("style", "news"), sb.get("resolution", "hd"))


def public_view(sb, base_url=""):
    """Return UI-friendly storyboard (image as servable URL)."""
    out = dict(sb)
    scenes = []
    for i, s in enumerate(sorted(sb["scenes"], key=lambda x: x["order"])):
        try:
            import xvideo_scene_analyzer
            s = xvideo_scene_analyzer.enrich_scene(s, i)
        except Exception:
            pass
        scenes.append({
            "id": s["id"], "order": s["order"], "text": s["text"],
            "image": s.get("image"), "duration": s["duration"],
            "start": s.get("start", 0), "layout": s.get("layout", ""),
            "keyword": s.get("keyword"),
            "headline": s.get("headline"),
            "keywords": s.get("keywords", []),
            "entities": s.get("entities", []),
            "numbers": s.get("numbers", []),
            "visual_type": s.get("visual_type", "kinetic_quote"),
            "motion_preset": s.get("motion_preset", "slide_up"),
            "asset_policy": s.get("asset_policy", "none"),
            # ROOT-CAUSE FIX: template_id was dropped here, so GET returned None and
            # the UI dropdown fell back to "Ngẫu nhiên" even though the saved file kept
            # the concrete template. Always surface template_id + assets.
            "template_id": s.get("template_id"),
            "assets": s.get("assets"),
            "preview": s.get("preview", {}),
        })
    out["scenes"] = scenes
    # Preserve style_lock so the UI can show the locked/synced source-of-truth.
    if sb.get("style_lock") is not None:
        out["style_lock"] = sb.get("style_lock")
    return out
