# Gemini over plain REST: the model that WATCHES video. Claude gets stills; Gemini gets the clip itself, every
# second of it, so it sees the shake, the camera turning, the spark, the hand on the part.
#
#   key      GEMINI_API_KEY (or GOOGLE_API_KEY) — Google AI Studio, aistudio.google.com -> Get API key
#   model    the newest Flash the key can use, found by asking Google's model list (names change too often to
#            hard-code). Flash watches video well at a fraction of Pro's price; for Pro set it by hand:
#            setx GEMINI_MODEL "gemini-3.1-pro-preview"
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


def _req(url, data=None, headers=None, method=None, timeout=600, raw=False, tries=5):
    h = {"x-goog-api-key": key()}
    h.update(headers or {})
    body = data if isinstance(data, (bytes, type(None))) else json.dumps(data).encode()
    if body is not None and "content-type" not in {k.lower() for k in h}: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r if raw else json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:600]
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                print(f"   Gemini HTTP {e.code}, повторяю…", flush=True)
                time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f"Gemini HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < tries - 1:
                print(f"   Gemini не ответил ({e}), повторяю…", flush=True)
                time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"Gemini unreachable: {e}")


# ------------------------------------------------------------------ the model
SKIP = ("lite", "image", "tts", "audio", "live", "embed", "robot", "computer", "nano", "veo", "imagen", "aqa",
        "learnlm", "gemma", "vision", "thinking-exp", "native")


def model():
    """GEMINI_MODEL if set, else the newest Flash (Pro only when no Flash is offered) — Pro picked by default
    cost several times more per video for a montage that Flash edits well. Stable before preview."""
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
        score = (m.group(2) == "flash", float(m.group(1)), "preview" not in low and "exp" not in low, -len(low))
        if best is None or score > best[0]: best = (score, n)
    if not best: raise RuntimeError("no Gemini Flash or Pro model is available to this key: " + ", ".join(names[:20]))
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
# Why streaming: a plain generateContent over several videos sends nothing back until the whole answer is
# ready; on the shop PC that silent connection sat for 5 minutes and timed out (an idle link gets dropped by
# routers/antivirus on the way). The streamed reply sends the model's thought summaries as it works, so bytes
# keep flowing, a stall is noticed in STALL seconds, and the log shows real progress instead of a clock.
STALL = 120
# Gemini 3 thinks at "high" unless told otherwise — minutes per montage and the answer cut off; at "low" Flash
# did not think at all and half its shots missed the steady stretches. "medium" sits between;
# GEMINI_THINKING=low|high overrides.
THINKING = os.environ.get("GEMINI_THINKING", "medium").strip().lower()


def _stream(m, body, log):
    """POST streamGenerateContent?alt=sse -> (text, finishReason, usage). Raises RuntimeError on a stall."""
    req = urllib.request.Request(f"{API}/v1beta/{m}:streamGenerateContent?alt=sse",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": key(), "Content-Type": "application/json"})
    out, finish, usage, thought = [], None, {}, 0
    t0 = last = time.time()
    try:
        with urllib.request.urlopen(req, timeout=STALL) as r:     # timeout = longest silence between chunks
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"): continue
                d = json.loads(line[5:])
                usage = d.get("usageMetadata") or usage
                c = (d.get("candidates") or [{}])[0]
                finish = c.get("finishReason") or finish
                for p in c.get("content", {}).get("parts", []):
                    if p.get("thought"): thought += 1
                    elif p.get("text"): out.append(p["text"])
                if time.time() - last >= 20:
                    last = time.time()
                    log(f"   Gemini {'пишет ответ' if out else 'думает'}… {int(last - t0)} с")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini HTTP {e.code}: {e.read().decode(errors='replace')[:600]}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise RuntimeError(f"Gemini stalled: no data for {STALL} s ({e})")
    return "".join(out), finish, usage


def ask_json(parts, max_tokens=32000, log=print):
    """One streamed request, the reply parsed as JSON. Settings an older model refuses (per-video fps,
    thinking level) are dropped and the request sent again; a stall or a 5xx is retried once."""
    # thinking tokens count against maxOutputTokens: at "high" Flash spent ~15k of 16k thinking and the JSON
    # was cut off after 632 tokens, so the cap is the model's whole budget rather than the answer's size
    cfg = {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}
    # temperature stays at the default 1.0: Google warns that lower values make Gemini 3 loop or degrade
    if THINKING in ("minimal", "low", "medium", "high"):
        cfg["thinkingConfig"] = {"thinkingLevel": THINKING, "includeThoughts": True}
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": cfg}
    m = model()
    log(f"   Gemini смотрит клипы (думает: {THINKING})…")
    for attempt in range(4):
        try:
            txt, finish, u = _stream(m, body, log); break
        except RuntimeError as e:
            msg = str(e)
            if ("videoMetadata" in msg or "video_metadata" in msg) and any("videoMetadata" in p for p in parts):
                for p in parts: p.pop("videoMetadata", None)
                log("   модель не берёт fps для видео — без него"); continue
            if ("thinking" in msg.lower()) and "thinkingConfig" in cfg and "HTTP 400" in msg:
                cfg.pop("thinkingConfig"); log("   модель не берёт уровень обдумывания — без него"); continue
            if attempt < 3 and ("stalled" in msg or re.search(r"HTTP (429|500|502|503|504)", msg)):
                log(f"   {msg[:160]} — повторяю…"); time.sleep(5); continue
            raise
    log(f"   ({m.split('/')[-1]}: {u.get('promptTokenCount')} in / {u.get('candidatesTokenCount')} out"
        f" + {u.get('thoughtsTokenCount', 0)} thinking)")
    if finish == "MAX_TOKENS": raise RuntimeError("Gemini's reply was cut off")
    # the first JSON value only: Flash sometimes adds a second object or sends the shots as a bare list,
    # and slicing first "{" to last "}" then failed with "Extra data"
    a = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0], default=-1)
    if a < 0: raise RuntimeError(f"Gemini replied without JSON: {txt[:300]!r} (finish: {finish})")
    v, _ = json.JSONDecoder().raw_decode(txt[a:])
    return {"shots": v} if isinstance(v, list) else v


if __name__ == "__main__":
    if not key(): sys.exit('no key: setx GEMINI_API_KEY "..."  (Google AI Studio -> Get API key)')
    print("model:", model())
