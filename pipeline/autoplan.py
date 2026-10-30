# Automatic editor for a batch of ready scripts + ready voice-overs (used by app.py, also usable from Python).
#   videos = parse_batch(text)          # scripts pasted in the "topics" format or the short "===" format
#   issues = check(videos)              # digits, unknown words, missing mp3, length, hook marker
#   register(videos, batch_name)        # into scripts/plan dicts + scripts/batches/<batch>.json
#   run(keys, log=print)                # align -> pick shots -> render -> contact sheets
import os, re, json, glob, shutil, subprocess, collections, datetime
import build, picker, contact, align, scripts, plan
from paths import PIPE, VOICE, OUT, WORK, FOOTAGE, ROOT, index_footage

LIB_PATH = os.path.join(PIPE, "library.json")
BATCHES = os.path.join(ROOT, "scripts", "batches")
os.makedirs(BATCHES, exist_ok=True)

def lib():
    return json.load(open(LIB_PATH, encoding="utf-8"))

def save_lib(L):
    json.dump(L, open(LIB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def apply_lib(L=None):
    """Push library settings into the modules that use them."""
    L = L or lib()
    clips = L.get("clips", {})
    picker.DULL.clear()
    for name, rec in clips.items():
        # a disabled clip is excluded entirely; an enabled one only loses its dull seconds
        picker.DULL[name] = [(0, 1e9)] if not rec.get("enabled") else [tuple(r) for r in rec.get("dull", [])]
    people = set(L.get("people", []))
    people |= {n for n, r in clips.items() if set(r.get("cats", [])) & {"weld", "work", "grind"}}
    build.PEOPLE = tuple(sorted(people))
    return L

def clips_for(L, cat):
    """Enabled clips tagged with this topic, strongest share first."""
    rows = [(n, r) for n, r in L.get("clips", {}).items() if r.get("enabled") and cat in r.get("cats", [])]
    rows.sort(key=lambda nr: (-nr[1].get("share", {}).get(cat, 1.0), nr[0]))
    return [n for n, _ in rows]

def rescan(log=print, progress=lambda i, n, m: None, force=False, names=None):
    """Find clips in footage/ and auto-tag the new ones (or `names`, or all non-manual with force)."""
    import autotag
    files = refresh_footage(); L = lib()
    todo = names if names is not None else files
    if names is not None:
        for n in names: L["clips"].pop(n, None)          # explicit re-tag: drop the old record, even a manual one
    n = autotag.scan(todo, build.src, L, log=log, progress=progress, force=force)
    for gone in [k for k in L["clips"] if k not in build.FILES]:
        log(f"{gone}: file no longer in footage, record kept")
    save_lib(L); apply_lib(L)
    return n

def refresh_footage():
    build.FILES = index_footage(); build.files = list(build.FILES)
    return build.files

# ---------------------------------------------------------------- parsing
HDR_TOPICS = re.compile(r'key:\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:[—–-]+\s*"([^"]*)"\s*(?:/\s*"([^"]*)")?)?'
                        r'(?:.*?music:\s*([^\n(]+))?', re.I)
HDR_SHORT = re.compile(r'^===\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:\|\s*([^|]*))?(?:\|\s*([^|]*))?(?:\|\s*([^|]*))?\s*$')

def parse_batch(text):
    """-> [dict(key,title,sub,track,text)] — accepts both formats, ignores '====' rules and 'Footage…' notes."""
    lines = text.replace("\r", "").split("\n")
    heads = []
    for i, ln in enumerate(lines):
        m = HDR_SHORT.match(ln.strip()) or (HDR_TOPICS.search(ln) if "key:" in ln.lower() else None)
        if m: heads.append((i, m))
    vids = []
    for n, (i, m) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        paras, cur = [], []
        for ln in lines[i + 1:end]:
            s = ln.strip()
            if not s or re.fullmatch(r"[=\-_*]{3,}", s):
                if cur: paras.append(" ".join(cur)); cur = []
                continue
            if s.startswith("(") and s.endswith(")"): continue
            cur.append(s)
        if cur: paras.append(" ".join(cur))
        body = next((p for p in paras if len(p.split()) >= 25 and not p.lower().startswith("footage")), "")
        key, title, sub, track = (g.strip() if g else "" for g in m.groups())
        vids.append(dict(key=key.lower(), title=title or key.upper(), sub=sub, track=track.strip(" .").strip(),
                         text=body))
    return vids

def clean_text(t):
    return re.sub(r"\s+", " ", t.replace("[HOOK 2]", " ")).strip()

def hook_index(t):
    if "[HOOK 2]" not in t: return None
    return len(scripts.norm(t.split("[HOOK 2]")[0]))

# ---------------------------------------------------------------- checks
def vo_path(key): return os.path.join(VOICE, f"{key}.mp3")

def dur(path):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", path]))
    except Exception:
        return None

def check(videos):
    """-> {key: [(level, message)]}; level 'err' blocks the build, 'warn' does not."""
    out = {}; seen = set(); tracks = set(lib()["tracks"])
    for v in videos:
        k, t = v["key"], v["text"]; iss = []
        if k in seen: iss.append(("err", "key used twice in this batch"))
        seen.add(k)
        if not t: iss.append(("err", "script text not found (needs a paragraph of 25+ words)"))
        n = len(clean_text(t).split())
        if t and not 90 <= n <= 150: iss.append(("warn", f"{n} words, usually 115–125 (~45 s video)"))
        if re.search(r"\d", clean_text(t)): iss.append(("err", "digits in the text: write numbers as words"))
        if t and "[HOOK 2]" not in t: iss.append(("warn", "no [HOOK 2] marker: there will be no mid-video hook"))
        unk = align.unknown_words(clean_text(t)) if t else []
        if unk: iss.append(("warn", "pronunciation will be guessed: " + ", ".join(unk)))
        d = dur(vo_path(k))
        if d is None: iss.append(("err", f"voice-over missing: voiceover\\{k}.mp3"))
        elif t and not 0.6 < n / d * 60 / 180 < 1.5:
            iss.append(("warn", f"voice-over is {d:.0f} s, does not fit this text ({n} words)"))
        if v["track"] and v["track"] not in tracks:
            iss.append(("warn", f"track \"{v['track']}\" is not an instrumental track: another one will be used"))
        if len(v["title"]) > 22: iss.append(("warn", "long title: keep it under 22 characters"))
        out[k] = iss
    return out

# ---------------------------------------------------------------- registration
def register(videos, batch_name=None):
    L = lib(); tr = L["tracks"]
    batch_name = batch_name or datetime.date.today().isoformat()
    path = os.path.join(BATCHES, f"{batch_name}.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"videos": {}}
    for i, v in enumerate(videos):
        k = v["key"]
        track = v["track"] if v["track"] in tr else tr[i % len(tr)]
        logo = "cottrell" if ("cottrell" in k or scripts.norm(v["text"]).count("cottrell") >= 2) else None
        rec = dict(title=v["title"], sub=v["sub"], track=track, text=clean_text(v["text"]),
                   hook=hook_index(v["text"]), logo=logo, plan=data["videos"].get(k, {}).get("plan"))
        data["videos"][k] = rec
        install(k, rec)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path

def install(k, rec):
    """Put one batch record into the runtime dicts used by build.py."""
    scripts.S[k] = rec["text"]; scripts.VO[k] = f"{k}.mp3"
    if rec.get("hook") is not None: scripts.HOOK[k] = rec["hook"]
    else: scripts.HOOK.pop(k, None)
    plan.TITLE[k] = rec["title"]; plan.SUB[k] = rec.get("sub", ""); plan.NEXT[k] = None
    plan.TRACK[k] = (f"{rec['track']}.mp3", f"{plan.DJ}  ·  {rec['track']}")
    if rec.get("logo"):
        lg = lib()["logos"][rec["logo"]]
        plan.LOGO[k] = (os.path.join(PIPE, lg["file"]), lg["word"], lg["width"])
    if rec.get("plan"): plan.P[k] = [(w, f, t, sp, tuple(z) if z else None) for w, f, t, sp, z in rec["plan"]]

def load_all_batches():
    for path in sorted(glob.glob(os.path.join(BATCHES, "*.json"))):
        for k, rec in json.load(open(path, encoding="utf-8"))["videos"].items():
            install(k, rec)

def batch_of(k):
    for path in sorted(glob.glob(os.path.join(BATCHES, "*.json")), reverse=True):
        d = json.load(open(path, encoding="utf-8"))
        if k in d["videos"]: return path, d
    return None, None

# ---------------------------------------------------------------- shot planning
def phrases(k):
    """Split the aligned script into phrases at punctuation (and at the hook). -> [(first_word, last_word)]"""
    toks = []
    for t in scripts.S[k].split():
        toks.append(t); n = len(scripts.norm(t))
        if n > 1: toks.extend([""] * (n - 1))
    words = build.A[k]; assert len(toks) == len(words)
    starts = [0]
    for i in range(1, len(words)):
        if re.search(r"[.,?!;:]$", toks[i - 1]) or i == scripts.HOOK.get(k): starts.append(i)
    t = lambda i: words[i][1]
    merged = [starts[0]]
    for s in starts[1:]:
        if t(s) - t(merged[-1]) < 1.3 and s != scripts.HOOK.get(k): continue   # too short — keep the shot going
        merged.append(s)
    return [(a, (merged[j + 1] - 1 if j + 1 < len(merged) else len(words) - 1)) for j, a in enumerate(merged)]

def pool_for(words, L, position, n):
    cats = L["categories"]; score = collections.Counter()
    for w in words:
        w = w.split("(")[0]
        for c, d in cats.items():
            if any(w == kw or (len(kw) > 3 and w.startswith(kw)) for kw in d["keywords"]): score[c] += 1
    order = [c for c, _ in score.most_common()]
    if position == n - 1: order = ["yard", "wide"] + order          # call to action: the shop from outside / inside
    elif position == 0 and not order: order = ["wide"]
    fallback = ["wide", "close"] if position % 2 == 0 else ["close", "wide"]
    pool = []
    for c in order + fallback:
        for clip in clips_for(L, c):
            if clip not in pool: pool.append(clip)
    return pool

def history_used(exclude):
    used = collections.defaultdict(list)
    for k in list(plan.P):
        if k in exclude: continue
        try: vo, total, segs = build.layout(k)
        except Exception: continue
        for s in segs: used[s["file"]].append((s["tin"], s["tin"] + s["n"] / 30 * s["sp"]))
    return used

def used_by(keys):
    """Seconds shown by these videos -> {file: [(a, b)]}."""
    used = collections.defaultdict(list)
    for k in keys:
        try: vo, total, segs = build.layout(k)
        except Exception: continue
        for s in segs: used[s["file"]].append((s["tin"], s["tin"] + s["n"] / 30 * s["sp"]))
    return used

def plan_keys(keys, log=print, hard_keys=()):
    """hard_keys: videos whose footage must not be repeated (e.g. yesterday's batch)."""
    L = apply_lib(); soft = history_used(set(keys)); hard = used_by(hard_keys)
    for k in keys:
        ph = phrases(k); words = build.A[k]
        slots = [(None if i == 0 else a, pool_for([w for w, _, _ in words[a:b + 1]], L, i, len(ph)), None)
                 for i, (a, b) in enumerate(ph)]
        P, rep = picker.plan_video(k, slots, hard, soft)
        rp = [r for r in rep if "REPEAT" in r]
        if rp: log(f"{k}: {len(rp)} shot(s) had to reuse yesterday's seconds")
        miss = [r for r in rep if "NO CANDIDATE" in r]
        if miss: raise RuntimeError(f"{k}: no usable shots for {len(miss)} phrase(s): add or enable clips in the library")
        plan.P[k] = P
        path, d = batch_of(k)
        if d:
            d["videos"][k]["plan"] = [list(x) for x in P]
            json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"{k}: {len(P)} shots picked")

# ---------------------------------------------------------------- render
def next_tag(k):
    n = 1
    while os.path.exists(os.path.join(OUT, build.outname(k, f"_v{n}"))): n += 1
    return f"_v{n}"

def render_key(k, log=print, tag=None):
    tag = tag or next_tag(k)
    for p in [os.path.join(WORK, f"part{k}.ass")]:
        if os.path.exists(p): os.remove(p)
    shutil.rmtree(os.path.join(WORK, f"s{k}{tag}"), ignore_errors=True)
    build.render(k, budget=10 ** 9, tag=tag)
    build.finish_music(k, target=30, src_tag=tag, out_tag=tag)
    out = os.path.join(OUT, build.outname(k, tag))
    contact.sheet(out, OUT, 6, 4)
    log(f"{k}: done -> {os.path.basename(out)}")
    return out

def blur_key(k, log=print):
    """Face blur for an approved video: reuses the last rendered cut, writes CHRH_<Key>_blur.mp4."""
    tags = sorted(glob.glob(os.path.join(WORK, f"s{k}_v*")), key=os.path.getmtime)
    if not tags: raise RuntimeError(f"{k}: build the video first")
    tag = os.path.basename(tags[-1])[len(f"s{k}"):]
    bl = os.path.join(WORK, f"s{k}{tag}", "cat_blur.mkv")
    if os.path.exists(bl): os.remove(bl)
    lg = os.path.join(WORK, f"s{k}{tag}", "cat_logo.mkv")
    if os.path.exists(lg): os.remove(lg)
    build.finish_music(k, target=30, src_tag=tag, out_tag="_blur", blur=True)
    log(f"{k}: faces blurred -> {build.outname(k, '_blur')}")

def run(keys, log=print, stop=lambda: False, progress=lambda i, n, msg: None):
    n = len(keys)
    progress(0, n * 3, "Aligning text to the voice-over")
    for i, k in enumerate(keys):
        if stop(): return
        build.A[k] = align.align_keys([k], log=log)[k]; progress(i + 1, n * 3, f"aligned: {k}")
    for i, k in enumerate(keys):
        if stop(): return
        plan_keys([k], log=log); progress(n + i + 1, n * 3, f"shots picked: {k}")
    outs = []
    for i, k in enumerate(keys):
        if stop(): return outs
        progress(2 * n + i, n * 3, f"rendering {i + 1} of {n}: {k}")
        outs.append(render_key(k, log=log))
    progress(3 * n, 3 * n, "Done")
    return outs
