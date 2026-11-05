# What the camera does, second by second: stands still, pans one way, swings back and forth, or shakes.
#
# liveness.py measures HOW MUCH the picture moves; it cannot tell a smooth pan from a camera waved back and forth,
# and that is exactly what the boss objects to ("стабильный кадр, движение в одну сторону, а не в разные —
# иначе любительское видео"). This measures the camera's own movement: the shift of the whole picture between
# frames (phase correlation, OpenCV, no GPU), ~10 times a second, and from it per window:
#   speed        how far the picture travels, in frame widths per second
#   consistency  |net shift| / total path: 1 = one direction all the way, 0 = back where it started
#   jitter       the small fast shake left after smoothing the path — a pan can be smooth or shaky
# and a label:  static · pan (with direction) · whip (too fast) · back-forth · shaky
#
#   python pipeline\motion.py springlock        a line per clip: one letter per half second
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SAMPLE_FPS = 10        # shifts measured ~10 times a second: enough for shake, cheap to decode
WIDTH = 320            # analysis width; shifts are reported as fractions of the frame width
WIN, STEP = 1.0, 0.5   # 1-second windows every half second, the same grid as liveness/picker

# Thresholds, in frame widths. First guesses checked on synthetic clips; tune them on real footage with the
# per-clip report (python pipeline\motion.py <project>, or menu [6]).
STATIC_SPEED = 0.04    # under this the camera is standing still
WHIP_SPEED = 0.9       # a whole frame width per second or more: a whip, smeared
BACK_FORTH = 0.45      # consistency under this, while moving, is a swing back and forth
MOVING_SPEED = 0.10    # "moving" for the back-and-forth test
SHAKE = 0.010          # jitter (RMS of the shift left after smoothing) over this is shake

CACHE = os.path.join(os.path.dirname(HERE), "work", "motion_cache.json")
_cache = None
LETTER = {"static": "·", "pan": "→", "whip": "»", "back-forth": "↔", "shaky": "~"}


def _sig(path):
    try:
        st = os.stat(path); return [st.st_size, int(st.st_mtime)]
    except OSError:
        return None


def _load():
    global _cache
    if _cache is None:
        try: _cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception: _cache = {}
    return _cache


def shift(a, b):
    """The camera's shift between two grey frames: phase correlation in a 3x3 grid of overlapping tiles and
    the median of the trustworthy ones. A worker walking through, a part being moved, sparks — they move some
    tiles; the background, which is most of them, still says what the camera did."""
    import cv2, numpy as np
    h, w = a.shape
    th, tw = h // 2, w // 2                       # tiles half the frame, three per side, overlapping
    xs, ys = [], []
    for ty in (0, h // 4, h - th):
        for tx in (0, w // 4, w - tw):
            pa = a[ty:ty + th, tx:tx + tw]; pb = b[ty:ty + th, tx:tx + tw]
            key = (th, tw)
            if key not in _HANN: _HANN[key] = cv2.createHanningWindow((tw, th), cv2.CV_32F)
            (dx, dy), resp = cv2.phaseCorrelate(pa, pb, _HANN[key])
            if resp >= 0.05: xs.append(dx); ys.append(dy)     # a featureless or smeared tile says nothing
    if len(xs) < 3: return 0.0, 0.0
    return float(np.median(xs)), float(np.median(ys))


_HANN = {}


def samples(path):
    """[(t, dx, dy)] — the picture's shift between samples, in frame widths, from t to the next sample."""
    import cv2, numpy as np
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    every = max(1, int(round(fps / SAMPLE_FPS)))
    out, prev, i = [], None, 0
    while True:
        ok = cap.grab()
        if not ok: break
        if i % every == 0:
            ok, fr = cap.retrieve()
            if not ok: break
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            h = int(g.shape[0] * WIDTH / g.shape[1]) // 2 * 2
            g = cv2.resize(g, (WIDTH, h), interpolation=cv2.INTER_AREA).astype(np.float32)
            if prev is not None:
                dx, dy = shift(prev, g)
                out.append((round((i - every) / fps, 3), dx / WIDTH, dy / WIDTH))
            prev = g
        i += 1
    cap.release()
    return out, i / fps


def classify(s):
    """Label one window from its samples [(t, dx, dy)]."""
    if len(s) < 3: return "static", {}
    dur = (s[-1][0] - s[0][0]) + 1.0 / SAMPLE_FPS
    path = sum(math.hypot(dx, dy) for _, dx, dy in s)
    nx, ny = sum(dx for _, dx, _ in s), sum(dy for _, _, dy in s)
    net = math.hypot(nx, ny)
    speed = path / dur
    cons = net / path if path > 1e-9 else 1.0
    # jitter: what is left of each step after a 3-sample moving average of the path
    res = []
    for k in range(len(s)):
        a, b = max(0, k - 1), min(len(s), k + 2)
        mx = sum(x for _, x, _ in s[a:b]) / (b - a); my = sum(y for _, _, y in s[a:b]) / (b - a)
        res.append(math.hypot(s[k][1] - mx, s[k][2] - my))
    jitter = math.sqrt(sum(r * r for r in res) / len(res))
    m = {"speed": round(speed, 4), "cons": round(cons, 3), "jitter": round(jitter, 4),
         "dir": round(math.degrees(math.atan2(ny, nx))) if net > 1e-9 else None}
    if jitter > SHAKE: return "shaky", m
    if speed >= WHIP_SPEED: return "whip", m
    if speed >= MOVING_SPEED and cons < BACK_FORTH: return "back-forth", m
    if speed < STATIC_SPEED: return "static", m
    return "pan", m


def windows(name, path):
    """[(t, label, metrics)] for 1-s windows every 0.5 s — cached, re-measured when the file changes."""
    c = _load()
    sig = _sig(path)
    hit = c.get(name)
    if hit and hit.get("sig") == sig and hit.get("v") == 2:
        return [tuple(x) for x in hit["w"]]
    s, dur = samples(path)
    out, t = [], 0.0
    while t + WIN <= dur - 0.05:
        part = [x for x in s if t - 1e-6 <= x[0] < t + WIN - 1e-6]
        lab, m = classify(part)
        out.append((round(t, 2), lab, m))
        t += STEP
    c[name] = {"sig": sig, "v": 2, "w": out, "samples": [list(x) for x in s]}
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(c, open(CACHE, "w", encoding="utf-8"))
    except Exception:
        pass
    return out


def bad_ranges(name, path):
    """[(t0, t1)] the montage never uses: back-and-forth, shake, whip pans."""
    return [(t, t + WIN) for t, lab, _ in windows(name, path) if lab in ("back-forth", "shaky", "whip")]


def span(name, path, t0, t1):
    """(label, metrics) for an arbitrary stretch — used to check that one SHOT keeps one direction even when
    each of its 1-s windows passed on its own (a pan right, then a pan left)."""
    windows(name, path)
    s = [tuple(x) for x in _load()[name]["samples"] if t0 - 1e-6 <= x[0] < t1 - 1e-6]
    return classify(s)


def strip(name, path):
    """One letter per half second: · static  → pan  » whip  ↔ back and forth  ~ shaky."""
    return "".join(LETTER[lab] for _, lab, _ in windows(name, path))


if __name__ == "__main__":
    os.chdir(HERE)
    import autoplan, build
    autoplan.refresh_footage()
    pre = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    names = sorted(n for n in build.FILES if n.lower().startswith(pre))
    if not names: sys.exit(f"no clips starting with '{pre}'")
    print("· static   → pan   » whip   ↔ back and forth   ~ shaky      (one mark per half second)\n")
    for n in names:
        w = windows(n, build.src(n))
        bad = sum(1 for _, lab, _ in w if lab in ("back-forth", "shaky", "whip"))
        print(f"{n[:34]:34s} {strip(n, build.src(n))}   {bad}/{len(w)} unusable")
