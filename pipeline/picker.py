# Automatic shot picking for the phrases of a voice-over.
# Every cut has a topic pool of clips (chosen from the words of the phrase). From the pool a window is taken where
#   * every 1-second sub-window is sharp (sharp25 >= TH) and not shaky (motion <= 20 drone / 35 handheld, raised
#     for sharp windows because a sharp move is a pan and vidstab fixes it — see motion_allowed),
#   * nothing overlaps forbidden ranges (yesterday's videos, seconds already used in this video, dull seconds),
#   * all else equal, clips that have been shown LEAST across all videos win, so new footage gets used.
import json, os, subprocess, collections
import build, liveness

CACHE = os.path.join(build.WORK, "live_cache.json")
_c = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

# How many clips of a pool are examined for every cut. The pool is ordered by topic fit, so the first ones fit
# best; scanning all of a 90-clip pool at 0.25 s steps costs minutes per video for no real gain.
MAX_POOL = 30

# "How often has this clip been shown before" is ranked ABOVE "how well it fits the topic", but only up to this
# many uses — clips seen 0, 1, 2 and 3-or-more times form four tiers, and inside a tier topic fit decides again.
# Set to 0 for the old behaviour (topic fit first, fresh footage effectively never reached).
USE_TIERS = 3


def _dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", build.src(f)]))

def _sig(f):
    """Identity of the file behind a name: size + mtime. The cache is keyed by NAME, so replacing a clip
    with a better copy under the same name must invalidate its old sharpness/motion numbers."""
    try:
        st = os.stat(build.src(f)); return [st.st_size, int(st.st_mtime)]
    except OSError:
        return None

def windows(f):
    """[(t, motion, sharp)] for 1-s windows every 0.5 s — cached on disk, re-measured if the file changed."""
    sig = _sig(f)
    hit = _c.get(f)
    if hit is None or (sig is not None and hit.get("sig") != sig):
        d = _dur(f); out = []; t = 0.0
        while t + 1.0 <= d - 0.05:
            m, s = liveness.measure(build.src(f), t, t + 1.0); out.append((t, m, s)); t += 0.5
        _c[f] = {"d": d, "w": out, "sig": sig}
        json.dump(_c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return _c[f]["d"], _c[f]["w"]

def is_drone(f): return "DJI" in f or "decking" in f or "shop east" in f or "yard" in f

def resolve(pre):
    """Library key -> real file. Exact name first; substring only as a fallback for legacy prefixes,
    otherwise a key like '1.MOV' silently matches 'framerepair1.MOV'."""
    if pre in build.FILES: return pre
    fs = [x for x in build.files if pre in x]
    return fs[0] if fs else None

# Seconds never to use. Filled from library.json by autoplan.apply_lib() (clip name -> [(a, b), ...]);
# it is cleared on every apply_lib, so nothing may be hard-coded here — put dull ranges in library.json.
DULL = {}
def dull(f):
    return [r for k, rr in DULL.items() if k in f for r in rr]

# Per-clip overrides, read from library.json:
#   clips[<file>]["sharp"]  = 50   lower sharpness floor (default 700; soft < 450, good > 700)
#   clips[<file>]["motion"] = 80   higher motion ceiling  (default 35 handheld / 20 drone)
# The motion metric cannot tell a deliberate camera move from shake: a smooth pan along a trailer scores
# just as high as a wobble. So a clip that is SHARP but scores high on motion is usually a pan, and vidstab
# smooths it — raise its ceiling instead of losing the shot. Never raise it on soft footage: soft + moving
# is exactly the "amateur phone video" look. Overrides apply to that one clip only.
def _ov(key):
    import json as _json, os as _os
    cache = globals().setdefault("_OV", {})
    if key not in cache:
        try:
            _lib = _json.load(open(_os.path.join(build.PIPE, "library.json"), encoding="utf-8"))
            cache[key] = {n: r[key] for n, r in _lib.get("clips", {}).items() if r.get(key)}
        except Exception:
            cache[key] = {}
    return cache[key]

def sharp_floor(f, th):
    o = _ov("sharp"); return min(th, o[f]) if f in o else th

def motion_ceiling(f, mlim):
    o = _ov("motion"); return max(mlim, o[f]) if f in o else mlim


def motion_allowed(mlim, sharp, th):
    """The ceiling for ONE window, raised by how sharp that window is.

    A flat ceiling throws away good footage. The metric cannot tell a camera move from a wobble, but
    sharpness can: a pan along a trailer stays sharp while it moves, a wobble smears. vidstab evens out the
    first and cannot save the second. So a window twice the sharpness floor may move half again as much, and
    one at five times the floor up to two and a half times as much; at or below the floor nothing is given."""
    if sharp <= th: return mlim
    return mlim * min(2.5, 1.0 + (sharp / th - 1.0) * 0.5)


def ok_window(m, s, th, mlim):
    """Is this one-second window usable? The single rule — the picker and everything that reports 'usable
    seconds' both call it, so the numbers the planner is given match the shots it can actually get."""
    return s >= th and m <= motion_allowed(mlim, s, th)

def overlap(a, b, rngs, tol=0.1):
    return any(x < b - tol and y > a + tol for x, y in rngs)

def best(pool, need, forbid, soft_used, th=700, allow_slow=True, own_count=None):
    """-> (file, tin, speed, minsharp, reused) or None"""
    cands = []
    seen = set()
    # The pool is ordered by topic fit and cut at MAX_POOL for speed. Clips that no video has used yet sit
    # wherever their tags put them, which on a long pool can be past the cut — so they would never be seen.
    # Always scan them too, keeping their real pool rank so topic fit still decides between equals.
    head = list(enumerate(pool))[:MAX_POOL]
    tail = [(i, p) for i, p in enumerate(pool) if i >= MAX_POOL
            and not soft_used.get(resolve(p) or "", [])]
    for rank_in_pool, pre in head + tail:
        f = resolve(pre)
        if f is None or f in seen: continue      # the same file can sit in the pool under two library keys
        seen.add(f)
        d, w = windows(f)
        if not w: continue
        mlim = motion_ceiling(f, 20 if is_drone(f) else 35)   # vidstab evens out handheld shake up to ~35
        oc = (own_count or {}).get(f, 0)
        lb = build.fit_mode(f)   # letterboxed landscape: fine, but full-bleed vertical looks better
        uses = min(len(soft_used.get(f, [])), USE_TIERS) if USE_TIERS else 0
        th_f = sharp_floor(f, th)          # a clip may declare its own, lower, sharpness floor
        banned = forbid.get(f, []) + dull(f)
        for sp in ((1.0, 0.8, 0.7) if allow_slow else (1.0,)):
            src = need * sp + 0.3
            t = 0.0
            while t + src <= d - 0.05:
                i0 = max(0, int((t - 0.01) / 0.5))          # windows sit at 0.0, 0.5, 1.0 … — slice, don't rescan
                i1 = min(len(w), int((t + src + 0.01 - 1.0) / 0.5) + 2)
                inside = [(m, s) for (tt, m, s) in w[i0:i1] if tt >= t - 0.01 and tt + 1.0 <= t + src + 0.01]
                if inside and not overlap(t, t + src, banned):
                    ms = min(s for m, s in inside)
                    # per window, not worst-sharpness against worst-motion: those two rarely sit in the same
                    # second, and pairing them rejected stretches where neither was actually a problem
                    if all(ok_window(m, s, th_f, mlim) for m, s in inside):
                        # how many other videos already show these exact seconds
                        reused = sum(1 for x, y in soft_used.get(f, []) if x < t + src - 0.1 and y > t + 0.1)
                        # rank: variety inside this video > fresh seconds > full-bleed > real speed >
                        #       least-used clip overall > topic fit > fewest reuses > sharpest
                        cands.append(((oc, reused > 0, lb, sp != 1.0, uses, rank_in_pool, reused, -ms),
                                      f, round(t, 2), sp, ms))
                t += 0.25
    if not cands: return None
    cands.sort()
    rank, f, t, sp, ms = cands[0]
    return f, t, sp, ms, rank[6]

MAXSHOT = 3.5   # boss 09-24: "something happens every 3-4 s" -> no shot longer than this (end card excluded)

def split_long(k, slots):
    """Insert extra cuts on word boundaries so no shot runs past MAXSHOT; new cut reuses the slot's pool."""
    A = build.A[k]; vo = build.voDur(k); e0 = build.PRE + vo + 0.15
    t = lambda w: 0.0 if w is None else A[w][1] + build.PRE - 0.06
    out = list(slots); i = 0
    while i < len(out):
        a = t(out[i][0]); b = t(out[i + 1][0]) if i + 1 < len(out) else e0
        if b - a > MAXSHOT:
            cand = [j for j in range(len(A)) if a + 1.5 < t(j) < b - 1.2]
            if cand:
                j = min(cand, key=lambda j: abs(t(j) - (a + min(3.0, (b - a) / 2))))
                out.insert(i + 1, (j, out[i][1], out[i][2])); continue
        i += 1
    return out

def plan_video(k, slots, forbid_global, batch_used, th=700):
    """slots: [(cut_word_or_None, [pool prefixes], zoom)] -> list of P tuples + report"""
    slots = split_long(k, slots)
    A = build.A[k]; vo = build.voDur(k); total = build.PRE + vo + build.END
    cuts = [0 if w is None else A[w][1] + build.PRE - 0.06 for (w, _, _) in slots] + [total]
    own = collections.defaultdict(list)
    P, rep = [], []
    for i, (w, pool, z) in enumerate(slots):
        need = cuts[i + 1] - cuts[i]
        forbid = collections.defaultdict(list)
        for f, r in forbid_global.items(): forbid[f] += r
        for f, r in own.items(): forbid[f] += r
        oc = {f: len(r) for f, r in own.items()}
        r = best(pool, need, forbid, batch_used, th, own_count=oc) or best(pool, need, forbid, batch_used, 600, own_count=oc)
        repeat = False
        if r is None and forbid_global:   # nothing fresh left: allow seconds from the forbidden (yesterday's) set
            only_own = collections.defaultdict(list)
            for f, rr in own.items(): only_own[f] += rr
            r = best(pool, need, only_own, batch_used, 600, own_count=oc); repeat = r is not None
        reused_own = False
        if r is None:
            # Last resort: show seconds this video already used. Normally forbidden, but a single-project
            # cut has only a handful of clips, and a repeated second beats a failed build. own_count still
            # ranks least-used clips first, so repeats spread out instead of hammering one clip.
            r = best(pool, need, collections.defaultdict(list), batch_used, 600, own_count=oc)
            reused_own = r is not None
        if r is None:
            rep.append(f"  slot {i} ({need:.1f}s) NO CANDIDATE in {pool}"); continue
        f, t, sp, ms, reused = r
        own[f].append((t, t + need * sp + 0.3)); batch_used[f].append((t, t + need * sp + 0.3))
        zz = z if z is not None else ((1.0, 0.5, 0.5) if is_drone(f) and "decking" not in f else None)
        if "decking" in f or "DJI" in f: zz = z or (1.0, 0.5, 0.5)
        pre = f  # full name as prefix
        P.append((w, pre, t, sp, zz))
        rep.append(f"  {i:2d} {need:4.1f}s {f[:34]:34s} @{t:5.2f} x{sp} sharp {ms:5.0f}{'  (reused in batch)' if reused else ''}"
                   f"{'  REPEAT FROM YESTERDAY' if repeat else ''}{'  REPEAT WITHIN VIDEO' if reused_own else ''}")
    return P, rep
