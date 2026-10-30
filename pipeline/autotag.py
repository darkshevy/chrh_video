# Automatic clip tagging with CLIP (ONNX, Xenova/clip-vit-base-patch32, quantized).
# Every second of a clip is centre-cropped exactly like the final 9:16 frame and embedded. Each second is then
# labelled by (a) its 15 nearest seconds among clips tagged BY HAND in library.json (class-balanced vote) and
# (b) short English descriptions of each topic — 50/50. Hand-tagged clips are the teacher: every manual fix in the
# app makes the next scan better. Leave-one-clip-out check on 48 hand-tagged clips (09-29): top topic right in 40/48,
# 81% of a clip's topics found.
# Result per clip: topics, dull seconds (wall/stairs/tarp/sky), outdoor-paint flag (boss rule: no outdoor painting).
# The text side is precomputed once (build_prompts(), needs `tokenizers`); the .exe only runs the image model.
import os, json, subprocess
import numpy as np
from paths import PIPE

MODELS = os.path.join(PIPE, "models")
VISION = os.path.join(MODELS, "clip_vision_q.onnx")
PROMPTS = os.path.join(MODELS, "clip_prompts.json")

# topic -> descriptions. "dull" and "outdoor_paint" are not topics: they switch seconds / clips off.
PROMPT_TEXT = {
    "wide":  ["a wide view of a large industrial workshop interior with a car hauler trailer",
              "a car carrier trailer with steel decks inside a garage",
              "drone view flying inside a metal warehouse workshop over a trailer"],
    "close": ["a close-up of a welded steel beam", "close-up of steel weld seams on a trailer frame",
              "close-up of a steel bracket and gusset plate"],
    "weld":  ["a welder welding steel with bright sparks", "a person welding under a trailer",
              "arc welding with a welding helmet"],
    "hyd":   ["hydraulic cylinders and hoses on a trailer", "close-up of a hydraulic ram on a car hauler",
              "black hydraulic cylinder with coiled hoses"],
    "alu":   ["a perforated aluminum ramp on a workbench", "shiny aluminum deck section with holes"],
    "hub":   ["a trailer wheel hub and axle", "trailer tires and wheels", "a wheel spindle and brake drum"],
    "rust":  ["rusted damaged steel on a trailer", "corroded metal panel with rust",
              "a damaged storage compartment on a white trailer"],
    "grind": ["an angle grinder cutting metal with sparks", "grinding rusty steel with a grinder"],
    "work":  ["a mechanic working on a trailer", "a worker repairing a truck trailer"],
    "yard":  ["an outdoor yard with trailers parked", "aerial drone view of a shop building and a dirt yard",
              "the outside of a metal industrial building"],
    "blast": ["sandblasted bare gray steel deck", "sandblasting a trailer with dust"],
    "dull":  ["a blank white wall", "a wooden staircase", "a blue tarp hanging on a wall",
              "the sky with clouds", "an empty concrete floor", "a warehouse ceiling", "a blurry out of focus image"],
    "outdoor_paint": ["a red painted trailer frame outdoors on grass", "spray painting a trailer outdoors in a field",
                      "a freshly painted red car hauler in a field", "a gray primed trailer frame outdoors on grass"],
}
TOPICS = [c for c in PROMPT_TEXT if c not in ("dull", "outdoor_paint")]
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)

def build_prompts():
    """One-time: text embeddings for PROMPT_TEXT -> clip_prompts.json (dev machine, needs `tokenizers`)."""
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(os.path.join(MODELS, "clip_tokenizer.json"))
    sess = ort.InferenceSession(os.path.join(MODELS, "clip_text_q.onnx"), providers=["CPUExecutionProvider"])
    out = {}
    for cat, texts in PROMPT_TEXT.items():
        embs = []
        for t in texts:
            ids = np.array([tok.encode(t).ids], np.int64)
            e = sess.run(None, {"input_ids": ids})[0][0]
            embs.append((e / np.linalg.norm(e)).tolist())
        out[cat] = embs
    for key, texts in OVERLAY_TEXT.items():
        embs = []
        for t in texts:
            e = sess.run(None, {"input_ids": np.array([tok.encode(t).ids], np.int64)})[0][0]
            embs.append((e / np.linalg.norm(e)).tolist())
        out[key] = embs
    json.dump(out, open(PROMPTS, "w"), separators=(",", ":"))
    return out

# someone else's finished edit (big cartoon captions, like-buttons, phone cards) must not end up in our videos
OVERLAY_TEXT = {
    "_ov_pos": ["a video frame with a large bold cartoon text caption overlay", "big red and yellow title text on top of a video",
                "a youtube thumbnail with bold words", "video with animated text sticker and like button"],
    "_ov_neg": ["a photo of a metal workshop", "a trailer frame being welded", "a car hauler trailer",
                "steel beams close-up", "a person working with tools"],
}

def overlay_hits(path):
    """(hits, samples): seconds whose FULL frame looks like a burned-in title (captions sit anywhere, so no 9:16 crop).
    Checked 09-29 on 56 new clips: edited clips 9CC7 / 727A / A9F4 = 21 / 18 / 7 hits, raw footage <= 5 (threshold 6)."""
    import cv2, hashlib
    _, P = _load()
    if "_ov_pos" not in P: return 0, 0
    st = os.stat(path); key = hashlib.md5(f"ov|{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, key + ".json")
    if os.path.exists(cp): return tuple(json.load(open(cp)))
    sess, _ = _load(); cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30; dur = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps
    xs = []; t = 0.25
    while t < dur - 0.1:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        if not ok: break
        im = cv2.cvtColor(cv2.resize(fr, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        xs.append(((im - MEAN) / STD).transpose(2, 0, 1)); t += 1.0
    cap.release()
    if not xs: return 0, 0
    x = np.stack(xs); E = np.concatenate([sess.run(None, {"pixel_values": x[i:i + 16]})[0] for i in range(0, len(x), 16)])
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    d = (E @ P["_ov_pos"].T).max(1) - (E @ P["_ov_neg"].T).max(1)
    res = (int((d > 0).sum()), len(d)); json.dump(res, open(cp, "w")); return res

_sess = None; _P = None
def _load():
    global _sess, _P
    if _sess is None:
        import onnxruntime as ort
        _sess = ort.InferenceSession(VISION, providers=["CPUExecutionProvider"])
        raw = json.load(open(PROMPTS))
        _P = {c: np.array(v, np.float32) for c, v in raw.items()}
        TOPIC_P = {c: v for c, v in _P.items() if not c.startswith("_")}
        _P["__topics__"] = list(TOPIC_P)
    return _sess, _P

def _frames(path, step=1.0):
    """RGB frames every `step` s, cropped to the 9:16 window the editor uses, 224x224 for CLIP."""
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = n / fps if n else 0
    t = 0.3; out = []
    while t < dur - 0.2:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
        if not ok: break
        h, w = f.shape[:2]
        if w / h > 9 / 16:                       # landscape (drone): centre 9:16 slice, as in the final video
            cw = int(h * 9 / 16); x = (w - cw) // 2; f = f[:, x:x + cw]
        h, w = f.shape[:2]; s = 224 / min(h, w)
        f = cv2.resize(f, (max(224, round(w * s)), max(224, round(h * s))), interpolation=cv2.INTER_CUBIC)
        h, w = f.shape[:2]; y, x = (h - 224) // 2, (w - 224) // 2
        f = cv2.cvtColor(f[y:y + 224, x:x + 224], cv2.COLOR_BGR2RGB)
        out.append((t, f)); t += step
    cap.release()
    return out, dur

CACHE = os.path.join(os.path.dirname(PIPE), "work", "clip_cache")

def embed(path):
    """-> (times, L2-normalised 512-d embeddings), cached per file (name+size+mtime)."""
    import hashlib
    st = os.stat(path); key = hashlib.md5(f"{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")).hexdigest()
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, key + ".npz")
    if os.path.exists(cp):
        z = np.load(cp); return z["t"], z["e"]
    sess, _ = _load()
    fr, dur = _frames(path)
    if not fr: return np.zeros(0), np.zeros((0, 512), np.float32)
    x = np.stack([((f.astype(np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1) for _, f in fr])
    E = np.concatenate([sess.run(None, {"pixel_values": x[i:i + 16]})[0] for i in range(0, len(x), 16)])
    E /= np.linalg.norm(E, axis=1, keepdims=True); t = np.array([a for a, _ in fr], np.float32)
    np.savez(cp, t=t, e=E.astype(np.float32))
    return t, E

K, ALPHA, TEMP, BALANCE = 15, 0.5, 40.0, 0.5     # tuned on the leave-one-clip-out check above

def _text_prob(E):
    _, P = _load(); C = P["__topics__"]
    s = np.stack([(E @ P[c].T).max(axis=1) for c in C], axis=1) * 100.0
    p = np.exp(s - s.max(axis=1, keepdims=True)); return C, p / p.sum(axis=1, keepdims=True)

def labels_of(rec):
    """Training labels of a hand-tagged clip."""
    if rec.get("reason") == "outdoor painting": return {"outdoor_paint"}
    return set(rec.get("cats", []))

def training(clips, src):
    """Frames of hand-tagged clips -> (X, Y, G). Seconds inside a clip's dull ranges are labelled 'dull'."""
    X, Y, G = [], [], []
    for name, rec in clips.items():
        if not rec.get("manual"): continue
        labs = labels_of(rec)
        if not labs: continue
        try: t, E = embed(src(name))
        except Exception: continue
        for ti, e in zip(t, E):
            dull = any(a <= ti < b for a, b in rec.get("dull", []))
            X.append(e); Y.append(("dull",) if dull else tuple(sorted(labs))); G.append(name)
    return (np.array(X, np.float32) if X else np.zeros((0, 512), np.float32)), Y, np.array(G)

def classify(name, path, train):
    X, Y, G = train
    t, E = embed(path)
    if len(E) == 0: return t, []
    C, TP = _text_prob(E)
    m = G != name; Xo = X[m]; Yo = [y for y, mm in zip(Y, m) if mm]
    freq = {}
    for y in Yo:
        for c in y: freq[c] = freq.get(c, 0) + 1
    S = E @ Xo.T if len(Xo) else np.zeros((len(E), 0))
    out = []
    for i in range(len(E)):
        vote = {}
        for j in np.argsort(-S[i])[:K]:
            for c in Yo[j]:
                vote[c] = vote.get(c, 0) + np.exp(TEMP * S[i, j]) / len(Yo[j]) / (freq[c] ** BALANCE)
        tot = sum(vote.values()) or 1.0
        comb = {c: ALPHA * vote.get(c, 0) / tot + (1 - ALPHA) * TP[i][C.index(c)] for c in C}
        out.append(max(comb, key=comb.get))
    return t, out

def summarize(t, labels, dur):
    """Per-second labels -> clip record."""
    if not labels:
        return {"cats": [], "dull": [], "enabled": False, "reason": "could not be read", "manual": False}
    n = len(labels)
    live = [l for l in labels if l not in ("dull", "outdoor_paint")]
    share = {c: live.count(c) / max(len(live), 1) for c in TOPICS}
    cats = [c for c in sorted(TOPICS, key=lambda c: -share[c]) if share[c] >= 0.2][:3]
    dull = []
    for ti, l in zip(t, labels):
        if l != "dull": continue
        a, b = float(ti) - 0.5, float(ti) + 0.5
        if dull and a <= dull[-1][1] + 0.01: dull[-1][1] = b
        else: dull.append([max(0.0, a), b])
    enabled, reason = True, ""
    if labels.count("outdoor_paint") / n >= 0.3: enabled, reason = False, "outdoor painting"
    elif len(live) < 2 or not cats: enabled, reason = False, "mostly empty frames"
    elif dur < 2.0: enabled, reason = False, "clip shorter than 2 s"
    return {"cats": cats, "dull": [[round(a, 1), round(b, 1)] for a, b in dull], "enabled": enabled,
            "reason": reason, "manual": False, "share": {c: round(share[c], 2) for c in cats}}

def tag_clip(name, path, train):
    t, labels = classify(name, path, train)
    dur = float(t[-1]) + 0.7 if len(t) else 0.0
    rec = summarize(t, labels, dur)
    hits, n = overlay_hits(path)
    if hits >= 6 or (n and hits / n >= 0.3):
        rec["enabled"], rec["reason"] = False, "someone else's edit with captions"
    return rec

def scan(names, src, lib, log=print, progress=lambda i, n, m: None, force=False):
    """Tag clips without a record (force=True: re-tag every clip not tagged by hand). Returns number tagged."""
    clips = lib.setdefault("clips", {})
    todo = [n for n in names if (n not in clips) or (force and not clips[n].get("manual"))]
    if not todo:
        progress(1, 1, "no new clips"); return 0
    progress(0, len(todo) + 1, "preparing examples from hand-tagged clips…")
    train = training(clips, src)
    for i, name in enumerate(todo):
        progress(i + 1, len(todo) + 1, f"tagging {i + 1} of {len(todo)}: {name}")
        try:
            rec = tag_clip(name, src(name), train)
        except Exception as e:
            rec = {"cats": [], "dull": [], "enabled": False, "reason": f"error: {e}", "manual": False}
        clips[name] = rec
        log(f"{name}: {', '.join(rec['cats']) or '—'}" + ("" if rec["enabled"] else f"  [disabled: {rec['reason']}]"))
    progress(len(todo) + 1, len(todo) + 1, f"clips tagged: {len(todo)}")
    return len(todo)
