"""
API key manager for X-Video (v1.10.0)
Added by Tiep QSO 2026-06-06.

Features:
- CRUD multiple keys per provider (pexels, openai, ...)
- Test a key (live validation)
- Auto-fallback: get_active_key() returns first healthy key;
  mark_failed() rotates to next when a key errors (403/429/quota).
- Persistent JSON store, thread-safe.
"""
import json, os, threading, time, urllib.request, urllib.parse, urllib.error

# Force IPv4 to avoid macOS IPv6 stall (urllib AAAA hang ~24s)
import socket as _socket
_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, _socket.AF_INET, type, proto, flags)
_socket.getaddrinfo = _ipv4_only


_lock = threading.RLock()
_STORE = None
_PATH = None


def init(store_path):
    global _STORE, _PATH
    _PATH = str(store_path)
    _load()


def _load():
    global _STORE
    try:
        with open(_PATH) as f:
            _STORE = json.load(f)
    except Exception:
        _STORE = {"providers": {}}
    # ensure structure
    _STORE.setdefault("providers", {})


def _save():
    tmp = _PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_STORE, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _PATH)


def _gen_id():
    return "k" + str(int(time.time() * 1000))[-9:]


# ---------- CRUD ----------
def list_keys(provider=None):
    with _lock:
        out = {}
        provs = _STORE["providers"]
        for pv, keys in provs.items():
            if provider and pv != provider:
                continue
            out[pv] = [{
                "id": k["id"], "label": k.get("label", ""),
                "masked": _mask(k["key"]), "status": k.get("status", "active"),
                "last_test": k.get("last_test", ""), "fail_count": k.get("fail_count", 0),
                "order": k.get("order", 0),
            } for k in keys]
        return out


def add_key(provider, key, label=""):
    with _lock:
        provs = _STORE["providers"].setdefault(provider, [])
        kid = _gen_id()
        order = max([k.get("order", 0) for k in provs], default=-1) + 1
        provs.append({"id": kid, "key": key.strip(), "label": label or f"{provider} key",
                      "status": "active", "fail_count": 0, "order": order, "last_test": ""})
        _save()
        return kid


def update_key(provider, kid, key=None, label=None, status=None):
    with _lock:
        for k in _STORE["providers"].get(provider, []):
            if k["id"] == kid:
                if key is not None: k["key"] = key.strip()
                if label is not None: k["label"] = label
                if status is not None: k["status"] = status
                if status == "active": k["fail_count"] = 0
                _save()
                return True
        return False


def delete_key(provider, kid):
    with _lock:
        provs = _STORE["providers"].get(provider, [])
        n = len(provs)
        _STORE["providers"][provider] = [k for k in provs if k["id"] != kid]
        _save()
        return len(_STORE["providers"][provider]) < n


def _mask(key):
    if not key or len(key) < 8:
        return "****"
    return key[:4] + "…" + key[-4:]


# ---------- rotation / fallback ----------
def get_active_key(provider):
    """Return raw key string of first healthy key (by order), or None."""
    with _lock:
        keys = sorted(_STORE["providers"].get(provider, []), key=lambda k: k.get("order", 0))
        for k in keys:
            if k.get("status", "active") == "active":
                return k["key"]
        return None


def get_all_active_keys(provider):
    """Return list of raw key strings, healthy first, for in-request fallback."""
    with _lock:
        keys = sorted(_STORE["providers"].get(provider, []), key=lambda k: k.get("order", 0))
        return [k["key"] for k in keys if k.get("status", "active") == "active"]


def mark_failed(provider, key, reason=""):
    """Increment fail count; disable after 3 strikes."""
    with _lock:
        for k in _STORE["providers"].get(provider, []):
            if k["key"] == key:
                k["fail_count"] = k.get("fail_count", 0) + 1
                k["last_error"] = reason[:120]
                if k["fail_count"] >= 3:
                    k["status"] = "failed"
                _save()
                return k["fail_count"]
        return 0


def mark_ok(provider, key):
    with _lock:
        for k in _STORE["providers"].get(provider, []):
            if k["key"] == key:
                k["fail_count"] = 0
                if k.get("status") == "failed":
                    k["status"] = "active"
                _save()
                return True
        return False


# ---------- live test ----------
def test_key(provider, key):
    """Validate a key against the provider. Returns (ok, detail)."""
    try:
        if provider == "pexels":
            url = "https://api.pexels.com/v1/search?query=ping%d&per_page=1" % int(time.time())
            req = urllib.request.Request(url, headers={
                "Authorization": key, "User-Agent": "Mozilla/5.0 XVideo"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = json.loads(r.read())
                remain = r.headers.get("X-Ratelimit-Remaining", "?")
                return True, f"OK · còn {remain} request"
        elif provider in ("openai", "deepseek", "9router", "openai_compatible"):
            bases = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "9router": os.environ.get("NINEROUTER_BASE_URL", "https://api.9router.com/v1"),
                "openai_compatible": os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://127.0.0.1:8000/v1"),
            }
            url = bases[provider].rstrip("/") + "/models"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=12) as r:
                json.loads(r.read())
                return True, "OK"
        elif provider == "gemini":
            url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + urllib.parse.quote(key)
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=12) as r:
                json.loads(r.read())
                return True, "OK"
        else:
            return False, f"Provider '{provider}' chưa hỗ trợ test"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:100]


def test_and_update(provider, kid):
    """Test a stored key by id, update status."""
    with _lock:
        target = None
        for k in _STORE["providers"].get(provider, []):
            if k["id"] == kid:
                target = k
                break
        if not target:
            return False, "Không tìm thấy key"
    ok, detail = test_key(provider, target["key"])
    with _lock:
        target["last_test"] = time.strftime("%Y-%m-%d %H:%M")
        target["status"] = "active" if ok else "failed"
        if ok:
            target["fail_count"] = 0
        _save()
    return ok, detail
