# Gemini over plain REST: the model that WATCHES video. Claude gets stills; Gemini gets the clip itself, every
# second of it, so it sees the shake, the camera turning, the spark, the hand on the part.
#
#   key      GEMINI_API_KEY (or GOOGLE_API_KEY) — Google AI Studio, aistudio.google.com -> Get API key
#   model    the newest Pro the key can use, found by asking Google's model list (names change too often to
#            hard-code); GEMINI_MODEL overrides it, e.g. setx GEMINI_MODEL "gemini-3.1-pro"
#
# Clips are uploaded through the Files API as light 480p copies without sound (same timeline, so the seconds
# Gemini names are the seconds of the original), and remembered for the two days Google keeps them.
import os, sys, re, json, time, base64, subprocess, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import WORK

API = "https://generativelanguage.googleapis.com"
CACHE = os.path.join(WORK, "gemini_files.json")
_model = None


def key():
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def _req(url, data=None, headers=None, method=None, timeout=600, raw=False):
    h = {"x-goog-api-key": key()}
    h.update(headers or {})
    body = data if isinstance(data, (bytes, type(None))) else json.dumps(data).encode()
    if body is not None and "content-type" not in {k.lower() for k in h}: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r if raw else json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:600]
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f"Gemini HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 4: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"Gemini unreachable: {e}")


# ------------------------------------------------------------------ the model
SKIP = ("lite", "image", "tts", "audio", "live", "embed", "robot", "computer", "nano", "veo", "imagen", "aqa",
        "learnlm", "gemma", "vision", "thinking-exp", "native")


def model():
    """The strongest model this key can use for video: GEMINI_MODEL if set, else the newest Pro (a Flash only
    when no Pro is offered). Stable versions before previews of the same number."""
    global _model
    if _model: return _model
    forced = os.environ.get("GEMINI_MODEL", "").strip()
    if forced:
        _model = forced if forced.startswith("models/") else "models/" + forced
        return _model
    names, page = [], ""
    while True:
        d = _req(f"{API}/v1beta/models?pageSize=200" + (f"&pageToken={page}" if page else ""), timeout=60)
        for m in d.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []): names.append(m["name"])
        page = d.get("nextPageToken", "")
        if not page: break
    best = None
    for n in names:
        low = n.lower()
        m = re.match(r"models/gemini-(\d+(?:\.\d+)?)-(pro|flash)\b", low)
        if not m or any(s in low for s in SKIP): continue
        score = (m.group(2) == "pro", float(m.group(1)), "preview" not in low and "exp" not in low, -len(low))
        if best is None or score > best[0]: best = (score, n)
    if not best: raise RuntimeError("no Gemini Pro or Flash model is available to this key: " + ", ".join(names[:20]))
    _model = best[1]
    return _model


# ------------------------------------------------------------------ files
def _load():
    try: return json.load(open(CACHE, encoding="utf-8"))
    except Exception: return {}


def proxy(src, name):
    """A light copy for upload: shorter side 480 px, 10 fps, no sound — the seconds are unchanged."""
    d = os.path.join(WORK, "gemini"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.splitext(name)[0]) + "_480.mp4")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-an", "-r", "10",
                        "-vf", "scale='if(gt(iw,ih),-2,480)':'if(gt(iw,ih),480,-2)'",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", out], check=True)
    return out


def upload(path, display):
    """Files API resumable upload -> {"name", "uri", "mimeType", "expirationTime"} once it is ACTIVE."""
    size = os.path.getsize(path)
    r = _req(f"{API}/upload/v1beta/files", {"file": {"display_name": display[:120]}}, raw=True, timeout=120, headers={
        "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": "video/mp4"})
    url = r.headers.get("X-Goog-Upload-URL") or r.headers.get("x-goog-upload-url")
    if not url: raise RuntimeError("Gemini did not return an upload URL")
    f = _req(url, open(path, "rb").read(), timeout=600, headers={
        "Content-Length": str(size), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
        "Content-Type": "video/mp4"}).get("file", {})
    for _ in range(120):                               # a video is processed before it can be used
        if f.get("state") == "ACTIVE": return f
        if f.get("state") == "FAILED": raise RuntimeError(f"Gemini could not process {display}")
        time.sleep(2)
        f = _req(f"{API}/v1beta/{f['name']}", timeout=60)
    raise RuntimeError(f"Gemini is still processing {display} after 4 minutes")


def video(name, src, log=print):
    """A file reference for this clip: reused while Google still keeps it (48 h), uploaded otherwise."""
    c = _load()
    st = os.stat(src); sig = [st.st_size, int(st.st_mtime)]
    hit = c.get(name)
    if hit and hit.get("sig") == sig:
        try:
            exp = datetime.datetime.fromisoformat(hit["expirationTime"].replace("Z", "+00:00"))
            if exp - datetime.datetime.now(datetime.timezone.utc) > datetime.timedelta(hours=2): return hit
        except Exception:
            pass
    log(f"   uploading {name} to Gemini…")
    f = upload(proxy(src, name), name)
    rec = {"sig": sig, "name": f["name"], "uri": f["uri"], "mimeType": f.get("mimeType", "video/mp4"),
           "expirationTime": f.get("expirationTime", "")}
    c[name] = rec
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(c, open(CACHE, "w", encoding="utf-8"), indent=1)
    return rec


def video_part(rec, fps=2):
    """The clip as a request part, sampled `fps` times a second (Gemini's default is 1)."""
    return {"fileData": {"mimeType": rec["mimeType"], "fileUri": rec["uri"]}, "videoMetadata": {"fps": fps}}


def image_part(jpeg_b64):
    return {"inlineData": {"mimeType": "image/jpeg", "data": jpeg_b64}}


# ------------------------------------------------------------------ asking
def ask_json(parts, max_tokens=16000, temperature=0.4, log=print):
    """One request, the reply parsed as JSON. A request the API refuses because of the per-video fps setting
    is sent again without it."""
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens,
                                 "temperature": temperature}}
    m = model()
    try:
        d = _req(f"{API}/v1beta/{m}:generateContent", body, timeout=900)
    except RuntimeError as e:
        if "videoMetadata" in str(e) or "video_metadata" in str(e):
            for p in parts: p.pop("videoMetadata", None)
            d = _req(f"{API}/v1beta/{m}:generateContent", body, timeout=900)
        else:
            raise
    cand = (d.get("candidates") or [{}])[0]
    txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    u = d.get("usageMetadata", {})
    log(f"   ({m.split('/')[-1]}: {u.get('promptTokenCount')} in / {u.get('candidatesTokenCount')} out)")
    if cand.get("finishReason") == "MAX_TOKENS": raise RuntimeError("Gemini's reply was cut off")
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0: raise RuntimeError(f"Gemini replied without JSON: {txt[:300]!r} (finish: {cand.get('finishReason')})")
    return json.loads(txt[a:b + 1])


if __name__ == "__main__":
    if not key(): sys.exit('no key: setx GEMINI_API_KEY "..."  (Google AI Studio -> Get API key)')
    print("model:", model())
