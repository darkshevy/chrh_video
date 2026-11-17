# The owner's taste: which moments he keeps (★ pins, montages he voices) and which he throws out ("плохой
# кадр"), remembered as CLIP picture fingerprints and used to score new candidate shots.
#
# Why this and not training a model: one shop gives tens of examples, not thousands — enough to say "a new
# moment looks like the welding close-ups he pinned, not like the people standing he rejected", which is what
# a nearest-neighbour score over CLIP embeddings does, locally and for free (the same CLIP model autotag uses).
# Gemini still decides what tells the story; the score is a hint next to each id, and the code's own fallback
# picks (fill / cover / balance) take the highest-scoring moment instead of the earliest.
#
#   pipeline/taste.json   {"likes": [...], "dislikes": [...]} — kept in git and saved by "Сохранить в облако"
import os, re, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STORE = os.path.join(HERE, "taste.json")
MIN_LIKES = 3          # under this the score says nothing; Gemini gets no taste column
TOP = 3                # a moment is compared with its 3 nearest examples, so one odd pin does not decide
_E = {}                # path -> (times, embeddings), per run
_store = None


def _load():
    global _store
    if _store is None:
        try: _store = json.load(open(STORE, encoding="utf-8"))
        except Exception: _store = {}
        _store.setdefault("likes", []); _store.setdefault("dislikes", [])
    return _store


def _save():
    json.dump(_load(), open(STORE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def revision():
    """Changes whenever an example is added: part of the plan signature, so new feedback means a new plan."""
    s = _load(); return f"{len(s['likes'])}/{len(s['dislikes'])}"


def available():
    try:
        import autotag
        return os.path.exists(autotag.VISION)
    except Exception:
        return False


def _embed(path):
    if path not in _E:
        import autotag
        _E[path] = autotag.embed(path)
    return _E[path]


def vector(path, t0, t1):
    """The mean fingerprint of a stretch of a clip (CLIP samples once a second), unit length; None if none."""
    import numpy as np
    ts, E = _embed(path)
    if not len(ts): return None
    m = (ts >= t0 - 0.5) & (ts <= t1 + 0.5)
    if not m.any(): m = np.abs(ts - (t0 + t1) / 2) == np.abs(ts - (t0 + t1) / 2).min()
    v = E[m].mean(axis=0)
    n = float(np.linalg.norm(v))
    return v / n if n else None


def add(kind, project, clip, path, t0, t1, src, weight=1.0, log=print):
    """Remember a liked / disliked moment. The same moment again replaces the old record (a like turned into
    a dislike counts once, as the newer)."""
    s = _load()
    if src == "voiced" and any(r["clip"] == clip and abs(r["t0"] - t0) < 1.0 for r in s["dislikes"]):
        return                                   # voicing a cut does not overrule a shot he threw out
    for k in ("likes", "dislikes"):
        s[k] = [r for r in s[k] if not (r["clip"] == clip and abs(r["t0"] - t0) < 1.0)]
    v = None
    if available():
        try: v = vector(path, t0, t1)
        except Exception as e: log(f"   (taste: no fingerprint for {clip}: {e})")
    s[kind].append({"project": project, "clip": clip, "t0": round(t0, 2), "t1": round(t1, 2), "src": src,
                    "w": weight, "when": time.strftime("%Y-%m-%d"),
                    "v": [round(float(x), 4) for x in v] if v is not None else None})
    _save()


def backfill(src_of, log=print):
    """Examples saved while the CLIP model was missing get their fingerprint once it is there."""
    if not available(): return 0
    n = 0
    for k in ("likes", "dislikes"):
        for r in _load()[k]:
            if r.get("v") is None and (p := src_of(r["clip"])):
                try:
                    v = vector(p, r["t0"], r["t1"])
                    if v is not None: r["v"] = [round(float(x), 4) for x in v]; n += 1
                except Exception as e:
                    log(f"   (taste: no fingerprint for {r['clip']}: {e})")
    if n: _save()
    return n


def disliked(clip, t0, t1):
    """Was this exact stretch thrown out by the owner? Such a moment is never offered again."""
    return any(r["clip"] == clip and r["t0"] < t1 and t0 < r["t1"] for r in _load()["dislikes"])


def ready():
    s = _load()
    return available() and sum(1 for r in s["likes"] if r.get("v")) >= MIN_LIKES


def score(path, t0, t1):
    """0..1: how much this moment looks like what the owner keeps and unlike what he throws out (0.5 = no
    opinion). Weighted mean of the TOP nearest likes minus the same for dislikes, squashed."""
    import numpy as np
    s = _load()
    v = vector(path, t0, t1)
    if v is None: return 0.5
    def near(rs):
        rs = [r for r in rs if r.get("v")]
        if not rs: return 0.0
        sims = sorted(((float(np.dot(v, np.array(r["v"], np.float32))), r.get("w", 1.0)) for r in rs), reverse=True)[:TOP]
        return sum(a * w for a, w in sims) / sum(w for _, w in sims)
    d = near(s["likes"]) - near(s["dislikes"]) if s["dislikes"] else near(s["likes"]) - 0.7
    return float(1 / (1 + np.exp(-d * 25)))     # CLIP cosines sit in a narrow band; 25 spreads it to 0..1


PLAN_LINE = re.compile(r"^\s*\d+\s+[\d.]+s\s+([\d.]+)s\s+(\S+)\s+@([\d.]+)")


def plan_shots(plan_path):
    """[(clip, tin, dur)] from a montage's _plan.txt."""
    out = []
    try:
        for line in open(plan_path, encoding="utf-8"):
            if line.startswith("review of"): break
            m = PLAN_LINE.match(line)
            if m: out.append((m.group(2), float(m.group(3)), float(m.group(1))))
    except OSError:
        pass
    return out


def from_plan(plan_path, project, src_of, kind="likes", weight=0.5, log=print):
    """Every shot of a montage as an example — a voiced montage is one the owner accepted (a weak like)."""
    n = 0
    for clip, tin, dur in plan_shots(plan_path):
        p = src_of(clip)
        if p: add(kind, project, clip, p, tin, tin + dur, "voiced", weight, log); n += 1
    return n
