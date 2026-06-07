"""
X-Video <-> html-video (nexu-io) bridge.
Added by Tiep QSO 2026-06-06 (Phase A).

Lets X-Video drive the html-video studio engine:
- list templates (from prebuilt catalog json)
- pick a template per scene (manual or random)
- map scene content -> template input vars (per its schema)
- render a scene to MP4 via the html-video CLI

The html-video repo lives at HV_ROOT and is built (packages/cli/dist/bin.js).
"""
import json, os, subprocess, random, time, re

HV_ROOT = os.environ.get("HV_ROOT", "/Users/tuan/html-video")
HV_BIN = os.path.join(HV_ROOT, "packages/cli/dist/bin.js")
HV_NODE_PATH = "/Users/tuan/.hermes/node/bin:/Users/tuan/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "hv_templates_catalog.json")

_CATALOG = None
BAD_RANDOM_TEMPLATES = {"vfx-text-cursor"}


def _env():
    e = dict(os.environ)
    e["PATH"] = HV_NODE_PATH + ":" + e.get("PATH", "")
    return e


def load_catalog():
    global _CATALOG
    if _CATALOG is None:
        try:
            with open(CATALOG_PATH) as f:
                _CATALOG = json.load(f)
        except Exception:
            _CATALOG = []
    return _CATALOG


def list_templates(aspect=None):
    """Return UI-friendly template list. aspect like '9:16' filters supported only."""
    out = []
    for t in load_catalog():
        if aspect and t.get("aspects") and aspect not in t["aspects"]:
            continue
        out.append({
            "id": t["id"], "name": t["name"], "category": t.get("category", ""),
            "best_for": t.get("best_for", []), "tags": t.get("tags", []),
            "aspects": t.get("aspects", []),
            "dmin": t.get("dmin", 3), "dmax": t.get("dmax", 15),
        })
    return out


def get_template(tid):
    for t in load_catalog():
        if t["id"] == tid:
            return t
    return None


def random_template(aspect=None, category=None, exclude=None):
    pool = [t for t in load_catalog()
            if (not aspect or not t.get("aspects") or aspect in t["aspects"])
            and (not category or t.get("category") == category)
            and (t["id"] not in BAD_RANDOM_TEMPLATES)
            and (not exclude or t["id"] not in exclude)]
    if not pool:
        pool = load_catalog()
    premium = [t for t in pool if t.get("category") == "premium"]
    return random.choice(premium or pool)["id"] if pool else None


# ---- content -> template inputs mapping ----
# Map common scene fields to whatever the chosen template's schema exposes.
# We fill the most "title-like" required field with headline, and a
# "body-like" field with the scene text. Unknown templates still get title+subtitle.

_TITLE_KEYS = ["title", "headline", "hero", "brand_name", "display_lines",
               "quote_lines", "text", "label"]
_SUB_KEYS = ["subtitle", "subheadline", "standfirst", "desc", "caption",
             "tagline", "script", "section", "role", "kicker", "eyebrow"]


def _clamp(s, n):
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s[:n]


def map_scene_to_vars(scene, template):
    """Build the template variable dict from a storyboard scene."""
    props = template.get("schema", {}) or {}
    req = template.get("required", []) or []
    headline = scene.get("headline") or scene.get("title") or scene.get("text") or scene.get("summary") or ""
    body = scene.get("body") or scene.get("script") or scene.get("text") or scene.get("summary") or headline
    dur = float(scene.get("duration") or 5)
    dmin, dmax = template.get("dmin", 3), template.get("dmax", 15)
    dur = max(dmin, min(dmax, dur))
    vars = {}

    def maxlen(key, default=120):
        p = props.get(key, {})
        return int(p.get("maxLength", default)) if isinstance(p, dict) else default

    # title-like
    title_filled = False
    for k in _TITLE_KEYS:
        if k in props:
            val = _clamp(headline, maxlen(k, 80))
            # array-typed props (display_lines/quote_lines) want a list
            ptype = (props.get(k, {}) or {}).get("type")
            if ptype == "array":
                vars[k] = [s for s in re.split(r"[.;\n]", headline) if s.strip()][:3] or [headline[:60]]
            else:
                vars[k] = val
            title_filled = True
            break
    # body-like
    for k in _SUB_KEYS:
        if k in props:
            vars[k] = _clamp(body, maxlen(k, 160))
            break
    # data-viz templates need 'data'
    if "data" in props:
        nums = scene.get("numbers") or []
        pts = []
        for i, n in enumerate(nums[:5]):
            pts.append({"label": (scene.get("keywords") or ["P%d" % (i+1)])[i] if i < len(scene.get("keywords") or []) else "P%d" % (i+1),
                        "value": _num(n, i)})
        if not pts:
            pts = [{"label": k, "value": (j + 1) * 10} for j, k in enumerate((scene.get("keywords") or ["A", "B", "C"])[:3])]
        vars["data"] = pts
    if "duration_sec" in props:
        vars["duration_sec"] = round(dur, 1)
    # ensure required fields exist
    for k in req:
        if k not in vars:
            ptype = (props.get(k, {}) or {}).get("type")
            if ptype == "array":
                vars[k] = [headline[:60]] if headline else ["AI World"]
            elif k == "data":
                vars["data"] = [{"label": "A", "value": 10}, {"label": "B", "value": 20}]
            else:
                vars[k] = _clamp(headline or body or "AI World", maxlen(k, 80))
    return vars


def _num(s, fallback=0):
    m = re.search(r"[\d.,]+", str(s))
    if not m:
        return (fallback + 1) * 10
    try:
        return float(m.group(0).replace(",", ""))
    except Exception:
        return (fallback + 1) * 10


def _run(args, timeout=240):
    r = subprocess.run(["node", HV_BIN] + args, capture_output=True, text=True,
                       timeout=timeout, env=_env(), cwd=HV_ROOT)
    return r


def render_scene(scene, template_id, aspect="9:16"):
    """Create an html-video project, set template+vars, render MP4.
    Returns dict {success, mp4, project_id, error}."""
    tpl = get_template(template_id)
    if not tpl:
        return {"success": False, "error": "unknown template " + str(template_id)}
    if tpl.get("aspects") and aspect not in tpl["aspects"]:
        aspect = tpl["aspects"][0]
    try:
        r = _run(["project-create", "--name", "xvscene_" + str(int(time.time() * 1000)), "--aspect", aspect], timeout=60)
        pid = json.loads(r.stdout.strip().splitlines()[-1]).get("project_id")
        if not pid:
            return {"success": False, "error": "create failed: " + (r.stderr or r.stdout)[-300:]}
        res_map = {"9:16": {"width": 1080, "height": 1920}, "16:9": {"width": 1920, "height": 1080}, "1:1": {"width": 1080, "height": 1080}}
        pj = os.path.join(HV_ROOT, ".html-video", "projects", pid, "project.json")
        try:
            with open(pj, "r") as f:
                pdata = json.load(f)
            prefs = pdata.setdefault("preferences", {})
            prefs["aspect"] = aspect
            prefs["resolution"] = res_map.get(aspect, res_map["16:9"])
            with open(pj, "w") as f:
                json.dump(pdata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        _run(["project-set-template", pid, "--template", template_id], timeout=60)
        vars = map_scene_to_vars(scene, tpl)
        # write vars JSON file and set all at once
        vpath = os.path.join("/tmp", "xvvars_%s.json" % pid)
        with open(vpath, "w") as f:
            json.dump(vars, f, ensure_ascii=False)
        rv = _run(["project-set-vars", pid, "--vars-file", vpath], timeout=60)
        rr = _run(["project-render", pid], timeout=300)
        try:
            out = json.loads(rr.stdout.strip().splitlines()[-1])
        except Exception:
            return {"success": False, "error": "render parse fail: " + (rr.stderr or rr.stdout)[-400:], "project_id": pid}
        mp4 = out.get("output_path")
        if not mp4 or not os.path.exists(mp4):
            return {"success": False, "error": "no output: " + (rr.stderr or rr.stdout)[-400:], "project_id": pid}
        return {"success": True, "mp4": mp4, "project_id": pid, "template_id": template_id, "vars": vars, "aspect": aspect}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "render timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}
