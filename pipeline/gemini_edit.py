# The montage edited by a model that watches the footage (Gemini), with a second look at the finished cut.
#
#   1. every clip of the project goes to Gemini as video, with what motion.py measured (where the camera holds,
#      pans, swings or shakes) and the stretches that are usable
#   2. Gemini picks the shots: clip and exact start second for each 2-3 s shot, in the order of the work,
#      the clearest damage first and the finished repair last; it names the video for the title
#   3. code checks every shot against the measurements (inside a steady stretch, the camera keeps one way,
#      nothing shown twice, at most three shots a clip, clip order when the clips are numbered by the work),
#      moves a shot to the nearest steady second when it can, and sends what it cannot fix back once
#   4. the cut is rendered (montage.render: grade, stabilisation, phone bar, title, end card)
#   5. Gemini watches the finished cut and names the weak shots; those are replaced and the video rendered
#      again — the draft is removed, the _plan.txt says what changed and why
#
# Used by montage.py when GEMINI_API_KEY is set (--claude forces the older path).
import os, sys, re, json, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, picker, motion, gemini, montage, taste

STEP = 0.25


def num(n):
    m = re.search(r"(\d+)\.\w+$", n); return int(m.group(1)) if m else 0


_GOOD = {}


def good_ranges(f):
    """[(a, b)] of the clip that can be shown: not shaken/swung/smeared, not dull, not the first 0.3 s or the
    last 0.35 s (the window picker needs that much past the end of a shot)."""
    if f in _GOOD: return _GOOD[f]
    d, w = picker.windows(f)
    bad = montage.shaky(f) + [tuple(r) for r in picker.dull(f)]
    out, cur = [], None
    for (t, _, _) in w:
        ok = not picker.overlap(t, t + 1.0, bad)
        if ok: cur = [t, t + 1.0] if cur is None else [cur[0], t + 1.0]
        elif cur: out.append(tuple(cur)); cur = None
    if cur: out.append(tuple(cur))
    _GOOD[f] = [(max(a, 0.3), min(b, d - 0.35)) for a, b in out if min(b, d - 0.35) - max(a, 0.3) >= 1.0]
    return _GOOD[f]


def fits(f, t, d, used):
    """Can a shot of d seconds start at t in clip f?"""
    if any(a - 0.01 <= t and t + d <= b + 0.01 for a, b in good_ranges(f)) and \
            not picker.overlap(t, t + d + 0.3, used.get(f, [])):
        return montage.steady(f, t, d)
    return False


def nearest(f, t, d, used, reach=3.0):
    """The closest start to t (within `reach` s) where the shot fits, or None."""
    best = None
    for a, b in good_ranges(f):
        x = a
        while x + d <= b + 0.01:
            if abs(x - t) <= reach and (best is None or abs(x - t) < abs(best - t)) and fits(f, x, d, used):
                best = x
            x += STEP
    return best


_CANDS = {}
MIN_SHOT = 2.0  # montage shots are 2-3 s; a candidate needs 2 s steady, longer ones give longer shots
MAX_SHOT = 3.0


def candidates(f):
    """Ready-made shots of this clip: [(start, steady length)] — windows of at least 2 s that pass every check
    (steady stretch, one camera direction over the whole shot), each stretched up to 3 s while it stays steady,
    not overlapping. Gemini chooses among these by id instead of guessing a start second: guessed seconds
    missed the checks for half the slots. (Fixed 3-s candidates found almost nothing in handheld clips.)"""
    if f in _CANDS: return _CANDS[f]
    out, used = [], collections.defaultdict(list)
    for a, b in good_ranges(f):
        x = a
        while x + MIN_SHOT <= b + 0.01:
            if fits(f, x, MIN_SHOT, used) and not taste.disliked(f, x, x + MIN_SHOT):
                L = MIN_SHOT
                while L + STEP <= MAX_SHOT + 0.01 and fits(f, x, L + STEP, used): L += STEP
                out.append((round(x, 2), round(L, 2))); used[f].append((x, x + L + 0.3)); x += L + 0.3
            else:
                x += STEP
    _CANDS[f] = out
    return out


_TASTE = {}


def taste_of(f, x, L):
    """The owner-taste score of a candidate (0..1), or None while there are too few examples."""
    if not taste.ready(): return None
    k = (f, x, L)
    if k not in _TASTE:
        try: _TASTE[k] = taste.score(build.src(f), x, x + L)
        except Exception: _TASTE[k] = None
    return _TASTE[k]


def ranked(f, latest_first=False):
    """The clip's candidates, best for the owner's taste first (or in time order while it knows nothing)."""
    c = list(candidates(f))
    if latest_first: c.reverse()
    if taste.ready(): c.sort(key=lambda xl: -(taste_of(f, *xl) or 0.5))
    return c


def cand_table(names):
    """{"c3.2": (clip, start, steady length)} for every candidate of every clip."""
    t = {}
    for f in names:
        for k, (x, L) in enumerate(candidates(f), 1): t[f"c{num(f)}.{k}"] = (f, x, L)
    return t


def place(f, t, d, used, L=None):
    """(start, length) for a shot of clip f wanted at t for d seconds: the length is cut to what stays steady
    (never under 2 s); at t if it fits, else the nearest steady second. None if nothing fits."""
    d0 = min(d, L) if L else d
    k = int(round(d0 / STEP))
    while k * STEP >= MIN_SHOT - 0.01:
        dd = round(k * STEP, 2)
        x = t if fits(f, t, dd, used) else nearest(f, t, dd, used)
        if x is not None: return x, dd
        k -= 1
    return None


def capacity(names, photos):
    """Shots the footage holds without repeating itself: per clip one per 2.5 s of steady footage, at most
    montage.MAX_PER_CLIP (a short steady stretch still gives one); a photo one."""
    return sum(min(cap(f), len(candidates(f))) for f in names) + len(photos)


RULES = """You are the editor of short vertical promo videos for a car hauler (car carrier trailer) repair shop.
You can watch the footage. There is no voice-over yet; a voice and captions are added later, so the pictures
alone have to tell the job — from the broken part to the finished repair — and look professional.

Pick a shot for every slot. The shots you can use are listed under each clip as ids like c3.2 (clip 3,
candidate 2) with their time in the clip; each one is already checked to be steady. Watch the clip at those
times and choose the ids that show the work best. Use an id at most once.

Rules, in order of importance:
1. Only listed ids. What the shot SHOWS matters most: the work itself — welding, cutting, fitting, fastening —
   beats a calm view of a wall or of someone standing. "(handheld)" ids move with the hand and are stabilised;
   use them freely when they show the work. Avoid any id that you see is blurred, dark, or the phone being
   raised or lowered.
2. Tell a story in three parts, in this order, as far as the footage allows (a part with no footage is
   skipped): BEGINNING — what came in: the damage, the old part, the bare frame (about 20% of the time);
   PROCESS — the work: cutting, grinding, fitting, welding, paint (about 50%); RESULT — the finished job,
   several shots from different angles and details (about 30%; a long clip of the finished work deserves
   three to five of its best moments, not one). Never show a finished part before the work that made it.
3. Start strong: the first shot is the clearest view of the beginning (the damage, or the job if there is
   none). End on the best-looking shot of the result.
4. "taste" next to an id (when shown) is how much that moment looks like shots the owner kept before and
   unlike the ones he threw out — 1 = very much his kind of shot. Between moments that tell the same step,
   take the higher taste; never let taste break the story order.
5. Action and detail win (even handheld): sparks, the welding arc, a cut, grinding, a hand fitting a part, a sharp close-up of
   the damage or of a fresh weld. Skip empty or repetitive moments, a wall, the floor, people standing.
6. Variety: at most three shots from one clip (five from a RESULT clip), never the same moment twice; when two shots come from one clip
   they must show clearly different moments.
7. Tell the whole job: every clip that has a usable stretch is a step of the work — use each of them at
   least once before using any clip a second time.
"""


def clip_parts(names, photos, log):
    parts, listing = [], []
    for f in sorted(names, key=lambda n: (num(n), n)):
        d, _ = picker.windows(f)
        c = candidates(f)
        if not c: continue                  # nothing steady: Gemini need not watch it (and pays no tokens)
        txt = (f"CLIP {num(f)} = {f} — {d:.1f} s. Shots you can use: " +
               ", ".join(f"c{num(f)}.{k} at {x:.1f}-{x + L:.1f}s"
                         + (" (handheld)" if motion.handheld(f, build.src(f), x, x + L) else "")
                         + (f" taste {t:.2f}" if (t := taste_of(f, x, L)) is not None else "")
                         for k, (x, L) in enumerate(c, 1)))
        listing.append(txt)
        parts.append({"text": txt})
        parts.append(gemini.video_part(gemini.video(f, build.src(f), log=log)))
    for n, p in sorted(photos.items(), key=lambda kv: (num(kv[0]), kv[0])):
        b = montage._photo_b64(p)
        if not b: continue
        parts.append({"text": f"PHOTO {n} — a still, shown about two seconds."})
        parts.append(gemini.image_part(b))
        listing.append(f"PHOTO {n}")
    return parts, listing


def ask_plan(parts, durs, note, ordered, extra=""):
    task = (RULES +
            (f"\nWHAT THE SHOP SAYS THIS JOB IS: {note}\n" if note else "") +
            ("\nThe clips are numbered in the order the work was done: list the shots in clip-number order "
             "(and by time inside a clip).\n" if ordered else "") +
            f"\n{len(durs)} slots, lengths in seconds: " + ", ".join(f"{i}: {d:.1f}" for i, d in enumerate(durs)) +
            "\nA photo fills a slot of any length (it is held about two seconds); use photos only where they show "
            "something the video does not, never two in a row.\n"
            'Mark up to three key shots with "key": true — the clearest damage, the most striking moment of the '
            'work, the finished result; they get a slow push-in, so pick shots where the camera holds still.\n'
            + extra +
            '\nReply with JSON only: {"shots": [{"slot": 0, "id": "c3.2", '
            '"why": "a few words", "key": false}], "title": "2-4 words, max 22 characters, capitals, the repair", '
            '"sub": "max 30 characters, capitals, the gist", "note": "one sentence about the cut", '
            '"stages": {"<clip number>": "begin|process|result"} for every clip you watched}')
    return gemini.ask_json(parts + [{"text": task}])


STAGES = {}          # clip file -> begin|process|result for this run (from Gemini, else from the clip numbers)
RESULT_MAX = 5       # shots from a clip of the finished job: the payoff the owner wants to see at length
RESULT_SHARE = 0.25  # at least this share of the video shows the result when there is footage of it


def set_stages(res, names, ordered, log):
    """Which clips are the beginning, the work and the result: Gemini's answer, else for numbered clips the
    first is the beginning and the last the result."""
    STAGES.clear()
    by_num = {num(f): f for f in names}
    for k, v in (res.get("stages") or {}).items():
        f = by_num.get(int(re.sub(r"\D", "", str(k)) or -1))
        if f and str(v).lower() in ("begin", "process", "result"): STAGES[f] = str(v).lower()
    usable = [f for f in sorted(names, key=lambda n: (num(n), n)) if candidates(f)]
    if ordered and usable:
        STAGES.setdefault(usable[0], "begin")
        if "result" not in STAGES.values(): STAGES[usable[-1]] = "result"
    if STAGES:
        log("   story: " + "  ".join(f"{st}: " + ",".join(str(num(f)) for f in sorted(STAGES, key=num)
                                                       if STAGES[f] == st) for st in ("begin", "process", "result")
                                     if st in STAGES.values()))


def cap(f):
    return RESULT_MAX if STAGES.get(f) == "result" else montage.MAX_PER_CLIP


def resolve(r, lower, table):
    """(file, start) of one picked shot: by candidate id, or by clip name + start as before."""
    cid = str(r.get("id", "")).strip().lower()
    if cid in table: return table[cid]
    f = lower.get(str(r.get("clip", "")).lower())
    try: t = float(r.get("start", 0))
    except Exception: t = 0.0
    return (f, t, None) if f else (None, 0.0, None)


def check(res, durs, names, photos, ordered):
    """-> (shots, problems). shots: [{file, tin, dur, photo?, path?, why}] with starts moved to the nearest
    steady second where needed; problems: [(slot, reason)]."""
    by = {}
    for r in res.get("shots", []):
        try: by[int(r.get("slot", r.get("shot")))] = r
        except Exception: continue
    used, per, shots, problems = collections.defaultdict(list), collections.Counter(), [], []
    lower = {n.lower(): n for n in list(names) + list(photos)}
    lower.update({f"p{num(n)}": n for n in photos})
    table = cand_table(names)
    for i, d in enumerate(durs):
        r = by.get(i)
        f, t, L = resolve(r, lower, table) if r else (None, 0.0, None)
        if not f:
            problems.append((i, "no shot, or a clip name that does not exist")); continue
        if f in photos:
            if shots and shots[-1].get("photo"):
                problems.append((i, "two photos in a row")); continue
            shots.append(dict(file=f, path=photos[f], tin=0.0, dur=d, photo=True, why=r.get("why", ""),
                              push=bool(r.get("key")) and sum(1 for s in shots if s.get("push")) < 3,
                              seg={"stage": "photo", "shows": r.get("why", "")}))
            continue
        if per[f] >= cap(f):
            problems.append((i, f"a fourth shot from {f}")); continue
        got = place(f, t, d, used, L)
        if got is None:
            problems.append((i, f"{f} at {t:.1f}s is not steady (shake, swing or blur) or already shown, and "
                                f"there is no steady moment within 3 s")); continue
        x, d = got
        used[f].append((x, x + d + 0.3)); per[f] += 1
        shots.append(dict(file=f, tin=round(x, 2), dur=d, why=r.get("why", ""), moved=abs(x - t) > 0.05,
                          push=bool(r.get("key")) and sum(1 for s in shots if s.get("push")) < 3,
                          seg={"stage": "", "shows": r.get("why", "")}))
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return shots, problems


def balance(shots, names, ordered, log):
    """The result gets its time: a 25-s clip of the finished deck got one 2-s shot. While the result shows
    under RESULT_SHARE of the video, a doubled shot of the work is swapped for another moment of the result."""
    res_clips = [f for f in names if STAGES.get(f) == "result"]
    if not res_clips: return shots
    shots = list(shots)
    total = lambda: sum(s["dur"] for s in shots)
    rtime = lambda: sum(s["dur"] for s in shots if s["file"] in res_clips)
    n = 0
    while rtime() < RESULT_SHARE * total():
        per = collections.Counter(s["file"] for s in shots
                                  if not s.get("photo") and STAGES.get(s["file"], "process") == "process")
        donors = [f for f, c in per.most_common() if c >= 2]
        if not donors: break
        js = [i for i, s in enumerate(shots) if s["file"] == donors[0] and not s.get("pinned")]
        if not js: break
        j = max(js)
        d = shots[j]["dur"]
        used = collections.defaultdict(list)
        for i, s in enumerate(shots):
            if i != j and not s.get("photo"): used[s["file"]].append((s["tin"], s["tin"] + s["dur"] + 0.3))
        got = None
        for f in res_clips:
            if sum(1 for s in shots if s["file"] == f) >= cap(f): continue
            # later moments of the finished work first: the end of a result clip is usually the best look
            for x, L in ranked(f, latest_first=True):
                g = place(f, x, max(d, 2.5), used, L)
                if g: got = (f, g); break
            if got: break
        if not got: break
        f, (x, dd) = got
        shots[j] = dict(file=f, tin=round(x, 2), dur=dd, why="more of the result (added by code)",
                        seg={"stage": "result", "shows": ""})
        n += 1
    if n: log(f"   {n} more shot(s) of the result, in place of repeated work")
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return shots


def cover(shots, names, ordered, log):
    """Every clip with steady footage gets a shot: a cut of 4 clips out of 9 did not tell what the job was.
    An unused clip takes the slot of a clip that has the most shots (its later duplicate), at the unused
    clip's first steady moment that fits the slot's length."""
    shots = list(shots)
    for f in sorted(names, key=lambda n: (num(n), n)):
        if any(s["file"] == f for s in shots) or not good_ranges(f): continue
        per = collections.Counter(s["file"] for s in shots if not s.get("photo") and STAGES.get(s["file"]) != "result")
        if not per or per.most_common(1)[0][1] < 2: break       # nothing doubled left to give up
        donor = per.most_common(1)[0][0]
        js = [i for i, s in enumerate(shots) if s["file"] == donor and not s.get("pinned")]
        if not js: continue
        j = max(js)
        d = shots[j]["dur"]
        used = collections.defaultdict(list)
        for i, s in enumerate(shots):
            if i != j and not s.get("photo"): used[s["file"]].append((s["tin"], s["tin"] + s["dur"] + 0.3))
        got = next((g for x, L in ranked(f) if (g := place(f, x, d, used, L))), None)
        if got is None: continue
        x, d = got
        log(f"   {f} was left out — it takes the second shot of {donor}")
        shots[j] = dict(file=f, tin=round(x, 2), dur=d, why="covers this step of the work (added by code)",
                        seg={"stage": "", "shows": ""})
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return shots


PLANS = os.path.join(os.path.dirname(HERE), "work", "gemini_plans.json")
# bump when the way shots are chosen changes: a plan made by older code must not be reused (a 4-shot plan
# from the 3-s candidates came back after the fix)
PLAN_VERSION = 5     # 3: handheld allowed; 4: begin-process-result story; 5: owner taste


def plan_sig(prefix, names, photos, seconds, ordered, note):
    """What the plan depends on: the files (size + modified time), the note, order, length and model. Same
    signature -> the same cut, so a rebuild needs no Gemini at all."""
    files = []
    for f in sorted(names): st = os.stat(build.src(f)); files.append([f, st.st_size, int(st.st_mtime)])
    for n, pth in sorted(photos.items()): st = os.stat(pth); files.append([n, st.st_size, int(st.st_mtime)])
    raw = json.dumps([PLAN_VERSION, prefix, files, round(seconds, 1), bool(ordered), note.strip(), gemini.model()])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def load_plans():
    try: return json.load(open(PLANS, encoding="utf-8"))
    except Exception: return {}


def save_plan(prefix, sig, shots, title, sub, res, notes):
    plans = load_plans()
    old = plans.get(prefix, {})
    seen = old.get("seen", []) if old.get("sig") == sig else []
    seen.append([f"{s['file']}@{s['tin']}" for s in shots])
    plans[prefix] = {"sig": sig, "shots": shots, "title": title, "sub": sub, "note": res.get("note", ""),
                     "notes": notes, "seen": seen[-5:]}
    os.makedirs(os.path.dirname(PLANS), exist_ok=True)
    json.dump(plans, open(PLANS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def apply_pins(shots, pins, names, ordered, log):
    """The owner's ★ moments go in whatever the model picked: a pinned moment already in the cut (same clip,
    within 1.5 s) is just marked; otherwise it replaces the nearest shot of its clip, else a repeated shot of
    the work. Pinned shots are kept through the review and are not re-checked for shake — the owner chose them."""
    shots = list(shots)
    for clip, t in pins:
        f = next((n for n in names if n.lower() == str(clip).lower()), None)
        if not f: log(f"   ★ {clip}: no such clip in the project"); continue
        dur = picker.windows(f)[0]
        hit = next((s for s in shots if s["file"] == f and abs(s["tin"] - (t - 0.5)) <= 1.5), None)
        if hit: hit["pinned"] = True; continue
        d = 2.5
        x = round(min(max(0.3, t - 0.5), max(0.3, dur - 0.35 - d)), 2)
        d = round(min(d, dur - 0.35 - x), 2)
        if d < 1.5: log(f"   ★ {f} @{t:.1f}: too close to the end of the clip"); continue
        same = [i for i, s in enumerate(shots) if s["file"] == f and not s.get("pinned")]
        clash = [i for i in same if shots[i]["tin"] < x + d + 0.3 and x < shots[i]["tin"] + shots[i]["dur"] + 0.3]
        if clash or same:
            j = min(clash or same, key=lambda i: abs(shots[i]["tin"] - x))
        else:
            per = collections.Counter(s["file"] for s in shots if not s.get("pinned") and not s.get("photo"))
            donors = [g for g, c in per.most_common() if c >= 2 and STAGES.get(g) != "result"] or \
                     [g for g, c in per.most_common() if c >= 2]
            j = (max(i for i, s in enumerate(shots) if s["file"] == donors[0] and not s.get("pinned"))
                 if donors else None)
        new = dict(file=f, tin=x, dur=d, why="your ★ moment", pinned=True, seg={"stage": "", "shows": ""})
        if j is None: shots.append(new)
        else: shots[j] = new
        # a second shot of the same clip may now overlap it
        shots = [s for s in shots if s is new or s["file"] != f or s.get("pinned")
                 or not (s["tin"] < x + d + 0.3 and x < s["tin"] + s["dur"] + 0.3)]
        log(f"   ★ {f} @{x:.1f} — your moment is in")
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return shots


def run(prefix, names, photos, seconds, ordered, note, dry=False, log=print, fresh=False, pins=()):
    log(f"editing with Gemini ({gemini.model().split('/')[-1]}) — it watches the clips")
    durs = montage.durations(seconds - montage.END, prefix)
    cap = capacity(names, photos)
    if cap < len(durs):
        durs = durs[:cap]
        log(f"! the steady footage holds about {sum(durs):.0f} s without repeats — making a "
            f"{sum(durs):.0f} s video instead of {seconds:.0f} s")
    if not durs: sys.exit("no steady footage in these clips")
    log(f"{prefix}: {len(names)} clip(s), {len(photos)} photo(s), {len(durs)} shots"
        + (" — clip numbers give the order" if ordered else ""))
    for f in sorted(names, key=lambda n: (num(n), n)):
        g = good_ranges(f)
        if not g: log(f"   {f}: shakes hard or blurred everywhere — cannot be used")

    pins = [tuple(p) for p in (pins or [])]
    for c, t in pins:     # a pinned moment is the clearest "this is good" there is
        f = next((n for n in names if n.lower() == str(c).lower()), None)
        if f and not any(r["clip"] == f and abs(r["t0"] - (t - 0.5)) < 1.0 for r in taste._load()["likes"]):
            taste.add("likes", prefix, f, build.src(f), max(0.0, t - 0.5), t + 2.0, "pin", 1.0, log)
    taste.backfill(lambda c: build.src(c) if c in build.FILES else None, log)
    if taste.ready(): log(f"   taste: {taste.revision()} examples (likes/dislikes) guide the choice")
    elif not taste.available(): log("   taste: CLIP model not found — the owner's examples are not used")
    sig = plan_sig(prefix, names, photos, seconds, ordered,
                   note + json.dumps(sorted(pins)) + taste.revision())
    prev = load_plans().get(prefix, {})
    same = prev.get("sig") == sig
    # a saved plan far shorter than asked is a failed one, not one to repeat
    full = sum(s["dur"] for s in prev.get("shots", [])) >= 0.8 * min(seconds - montage.END, sum(durs))
    if same and not fresh and prev.get("shots") and full:
        # nothing changed since the last cut: render that plan again — no upload, no request, no review
        log("клипы и описание не менялись — беру прошлый план, Gemini не спрашиваю "
            "(«Другой вариант» — новый план)")
        shots, title, sub = prev["shots"], prev["title"], prev.get("sub", "")
        show(shots, title, sub, log)
        if dry: return None
        out, total = montage.render(prefix, shots, title, sub)
        write_plan(out, shots, title, sub, {"note": prev.get("note", "") + " (the previous plan, reused)"},
                   prev.get("notes", []))
        return out, total
    other = ""
    if fresh and same and prev.get("seen"):
        # a new variant: show Gemini what was already used so it picks other moments, not the same cut again
        other = ("\nTHE OWNER WANTS A DIFFERENT VERSION. Earlier cuts used (clip@start): " +
                 " | ".join(", ".join(c) for c in prev["seen"]) +
                 "\nTell the same job, but choose other ids wherever an equally good one exists, and a different "
                 "opening shot.\n")
        log("другой вариант: прошу Gemini взять другие моменты")
    parts, listing = clip_parts(names, photos, log)

    if pins:
        other += ("\nTHE OWNER HAS CHOSEN THESE MOMENTS, they will be in the cut anyway (clip @ second): " +
                  ", ".join(f"{c} @{t:.1f}" for c, t in pins) + " — build the story around them and do not "
                  "pick another shot of the same moment.\n")
    res = ask_plan(parts, durs, note, ordered, other)
    set_stages(res, names, ordered, log)
    shots, problems = check(res, durs, names, photos, ordered)
    if problems:
        log(f"{len(problems)} shot(s) do not hold up; asking again for those…")
        for i, why in problems: log(f"   slot {i}: {why}")
        prev = ", ".join(f"{s['file']}@{s['tin']}" for s in shots)
        try:
            res2 = ask_plan(parts, durs, note, ordered,
                            "\nYOUR PREVIOUS PLAN: " + prev + "\nTHESE SLOTS DID NOT WORK:\n" +
                            "\n".join(f"  slot {i}: {w}" for i, w in problems) +
                            "\nGive the whole plan again, fixing exactly these.\n")
            s2, p2 = check(res2, durs, names, photos, ordered)
            if len(p2) < len(problems): res, shots, problems = res2, s2, p2; log("   corrected")
        except Exception as e:
            log(f"   no correction ({e})")
        if problems:
            shots, problems = fill(shots, problems, durs, names, ordered, log)
        if problems: log(f"   {len(problems)} slot(s) dropped — the video is that much shorter")
    shots = cover(shots, names, ordered, log)
    # shots cut to their steady length leave the video short of what was asked: top it up from unused
    # steady footage (it stays shorter only when there is none)
    short = (seconds - montage.END) - sum(s["dur"] for s in shots)
    if short >= MIN_SHOT + 0.5 and len(shots) < capacity(names, photos):
        extra = [2.5] * int(short // 2.5)
        shots, _ = fill(shots, [(len(durs) + k, "top-up") for k in range(len(extra))], durs + extra, names,
                        ordered, log)
    shots = balance(shots, names, ordered, log)
    if pins: shots = apply_pins(shots, pins, names, ordered, log)
    title = re.sub(r"\s+", " ", str(res.get("title") or prefix).upper()).strip()[:22]
    sub = re.sub(r"\s+", " ", str(res.get("sub") or "")).upper().strip()[:30]
    show(shots, title, sub, log)
    if dry or not shots: return None

    out, total = montage.render(prefix, shots, title, sub)
    notes = review(out, shots, log, ordered)
    bad = sorted({n["shot"] for n in notes if n.get("replace") and isinstance(n.get("shot"), int)
                  and 0 <= n["shot"] < len(shots)})
    if bad:
        log(f"the review found {len(bad)} weak shot(s): {', '.join(map(str, bad))}; replacing them…")
        keep = ", ".join(f"{i}: {s['file']}@{s['tin']}" for i, s in enumerate(shots))
        fix = "\n".join(f"  shot {n['shot']}: {n.get('issue', '')}" for n in notes if n.get("shot") in bad)
        try:
            res3 = ask_plan(parts, [s["dur"] for s in shots], note, ordered,
                            f"\nTHE CURRENT CUT (slot: clip@start): {keep}\nA REVIEW OF THE RENDERED VIDEO "
                            f"SAYS THESE SHOTS ARE WEAK:\n{fix}\nKeep every other slot exactly as it is and give "
                            "these slots different, better moments.\n")
            s3, changed = replace(shots, bad, res3, names, photos, ordered)
            if changed: s3 = cover(s3, names, ordered, log)     # a swap must not drop a step of the job
            if changed:
                log(f"   replaced shot(s) {', '.join(map(str, changed))}")
                draft = out
                out, total = montage.render(prefix, s3, title, sub)
                for ext in (".mp4", ".jpg"):
                    try: os.remove(os.path.splitext(draft)[0] + ext)
                    except OSError: pass
                shots = s3
            else:
                log("   no usable replacement; keeping the first cut")
        except Exception as e:
            log(f"   no replacement ({e}); keeping the first cut")
    write_plan(out, shots, title, sub, res, notes)
    try: save_plan(prefix, sig, shots, title, sub, res, notes)
    except Exception as e: log(f"(plan not saved for reuse: {e})")
    return out, total


def fill(shots, problems, durs, names, ordered, log):
    """Slots the model could not place twice are filled by code rather than dropped (a 30 s order came out
    16 s): each takes a steady, unused stretch from the clip with the fewest shots so far — the later clip
    on a tie when the clips are ordered, so the gap is not filled with the start of the job."""
    used, per = collections.defaultdict(list), collections.Counter()
    for s in shots:
        if not s.get("photo"): used[s["file"]].append((s["tin"], s["tin"] + s["dur"] + 0.3)); per[s["file"]] += 1
    left, n = [], 0
    for i, why in problems:
        d, got = durs[i], None
        for f in sorted(names, key=lambda f: (per[f], -num(f) if ordered else 0, f)):
            if per[f] >= cap(f): continue
            for x0, L in ranked(f):
                g = place(f, x0, d, used, L)
                if g: got = (f, g[0], g[1]); break
            if got: break
        if not got: left.append((i, why)); continue
        f, x, d = got
        used[f].append((x, x + d + 0.3)); per[f] += 1; n += 1
        shots.append(dict(file=f, tin=round(x, 2), dur=d, why="steady filler (picked by code)",
                          seg={"stage": "", "shows": ""}))
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    if n: log(f"   {n} slot(s) filled by code from steady footage")
    return shots, left


def replace(shots, bad, res, names, photos, ordered):
    """The cut with only the weak slots swapped for the model's new picks — each new pick checked like any
    shot against the slots that stay; a slot whose new pick does not hold up keeps its old shot."""
    by = {}
    for r in res.get("shots", []):
        try: by[int(r.get("slot", r.get("shot")))] = r
        except Exception: continue
    lower = {n.lower(): n for n in list(names) + list(photos)}
    lower.update({f"p{num(n)}": n for n in photos})
    table = cand_table(names)
    out = list(shots)
    for i in bad:
        if shots[i].get("pinned"): continue                  # the owner chose it
        r, d = by.get(i), shots[i]["dur"]
        f, t, L = resolve(r, lower, table) if r else (None, 0.0, None)
        if not f: continue
        if f in photos:
            if (i and out[i - 1].get("photo")) or (i + 1 < len(out) and out[i + 1].get("photo")): continue
            out[i] = dict(file=f, path=photos[f], tin=0.0, dur=d, photo=True, why=r.get("why", ""),
                          seg={"stage": "photo", "shows": r.get("why", "")})
            continue
        used = collections.defaultdict(list)
        for j, s in enumerate(out):
            if j != i and not s.get("photo"): used[s["file"]].append((s["tin"], s["tin"] + s["dur"] + 0.3))
        if sum(1 for j, s in enumerate(out) if j != i and s["file"] == f) >= cap(f): continue
        got = place(f, t, d, used, L)
        if got is None: continue
        x, d = got
        if (f, round(x, 2)) == (shots[i]["file"], shots[i]["tin"]): continue      # the same shot again
        out[i] = dict(file=f, tin=round(x, 2), dur=d, why=r.get("why", ""), moved=abs(x - t) > 0.05,
                      seg={"stage": "", "shows": r.get("why", "")})
    changed = [i for i in bad if out[i] is not shots[i]]
    if ordered:
        out.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return out, changed


def review(out, shots, log, ordered=False):
    """Gemini watches the rendered cut: [{"shot", "issue", "replace"}]."""
    try:
        rec = gemini.video("review_" + os.path.basename(out), out, log=log)
        t, table = 0.0, []
        for i, s in enumerate(shots):
            table.append(f"shot {i}: {t:.1f}-{t + s['dur']:.1f}s ({'photo' if s.get('photo') else 'video'})")
            t += s["dur"]
        ask = ("You are reviewing a finished vertical promo cut for a car hauler repair shop before it goes to "
               "the owner. He rejects: strong shaking or fast swinging (light handheld movement is fine when the shot "
               "shows the work), blurred or dark shots, "
               + ("the shots are already in the order the clips were filmed — do not judge the order; " if ordered else
                  "the order of the work broken (finished parts before the work), ") +
               "dull shots (walls, floor, people "
               "standing), the same moment twice. The text overlays and the black card at the end are fine.\n"
               "Shots: " + "; ".join(table) + "\nList only real problems. Reply with JSON only: "
               '{"problems": [{"shot": 3, "issue": "what is wrong", "replace": true}], "verdict": "one sentence"}')
        d = gemini.ask_json([gemini.video_part(rec, fps=4), {"text": ask}], max_tokens=16000)
        log(f"review: {d.get('verdict', '')}")
        for n in d.get("problems", []): log(f"   shot {n.get('shot')}: {n.get('issue')}")
        return d.get("problems", [])
    except Exception as e:
        log(f"(no review: {e})")
        return []


def show(shots, title, sub, log):
    log(f"\ntitle: {title}" + (f" / {sub}" if sub else ""))
    t = 0.0
    for i, s in enumerate(shots):
        log(f"  {i:2d} {t:5.1f}s {s['dur']:.1f}s  {s['file'][:30]:30s} @{s['tin']:5.2f}"
            f"{' (moved to a steady second)' if s.get('moved') else ''}  {s.get('why', '')[:50]}")
        t += s["dur"]


def write_plan(out, shots, title, sub, res, notes):
    rp = os.path.splitext(out)[0] + "_plan.txt"
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(f"{title} / {sub}\nedited by {gemini.model().split('/')[-1]}: {res.get('note', '')}\n\n")
        t = 0.0
        for i, s in enumerate(shots):
            fh.write(f"{i:2d} {t:5.1f}s {s['dur']:.1f}s {s['file']} @{s['tin']:.2f}  {s.get('why', '')}\n")
            t += s["dur"]
        if notes:
            fh.write("\nreview of the first cut:\n" + "".join(f"  shot {n.get('shot')}: {n.get('issue')}\n" for n in notes))
