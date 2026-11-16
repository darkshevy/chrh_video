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
import os, sys, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, picker, motion, gemini, montage

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


def capacity(names, photos):
    """Shots the footage holds without repeating itself: per clip one per 2.5 s of steady footage, at most
    montage.MAX_PER_CLIP (a short steady stretch still gives one); a photo one."""
    n = 0
    for f in names:
        steady = sum(b - a for a, b in good_ranges(f))
        n += min(montage.MAX_PER_CLIP, int(steady // 2.5) or (1 if steady >= 1.0 else 0))
    return n + len(photos)


RULES = """You are the editor of short vertical promo videos for a car hauler (car carrier trailer) repair shop.
You can watch the footage. There is no voice-over yet; a voice and captions are added later, so the pictures
alone have to tell the job — from the broken part to the finished repair — and look professional.

Pick a shot for every slot. A shot is a clip and the second it starts at; its length is given per slot.

Rules, in order of importance:
1. Only steady footage. Use only the "usable" stretches listed for each clip; within them prefer moments where
   the camera holds still or moves smoothly ONE way. Never a camera that swings back and forth, shakes, or
   whips — it looks amateur. Never a blurred or dark moment, never the phone being raised or lowered.
2. The order of the work. Damage first, then removal / cutting / grinding, fitting, welding, paint, and the
   finished result last. Never show a finished part before the work that made it.
3. Start strong: the first shot is the clearest view of the damage (or of the job, if there is no damage).
   End on the best-looking finished result.
4. Action and detail win: sparks, the welding arc, a cut, grinding, a hand fitting a part, a sharp close-up of
   the damage or of a fresh weld. Skip empty or repetitive moments, a wall, the floor, people standing.
5. Variety: at most three shots from one clip, never the same moment twice; when two shots come from one clip
   they must show clearly different moments.
6. A shot must fit inside one usable stretch: start + length <= end of that stretch.
"""


def clip_parts(names, photos, log):
    parts, listing = [], []
    for f in sorted(names, key=lambda n: (num(n), n)):
        d, _ = picker.windows(f)
        g = good_ranges(f)
        strip = motion.strip(f, build.src(f))
        txt = (f"CLIP {f} — {d:.1f} s. Camera, one mark per half second from 0:00 "
               f"(· still, → smooth pan, » too fast, ↔ swings back and forth, ~ shakes): {strip}\n"
               f"Usable stretches (seconds): " + (", ".join(f"{a:.1f}-{b:.1f}" for a, b in g) or "none"))
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
            '\nReply with JSON only: {"shots": [{"slot": 0, "clip": "<file name>", "start": 12.5, '
            '"why": "a few words", "key": false}], "title": "2-4 words, max 22 characters, capitals, the repair", '
            '"sub": "max 30 characters, capitals, the gist", "note": "one sentence about the cut"}')
    return gemini.ask_json(parts + [{"text": task}])


def check(res, durs, names, photos, ordered):
    """-> (shots, problems). shots: [{file, tin, dur, photo?, path?, why}] with starts moved to the nearest
    steady second where needed; problems: [(slot, reason)]."""
    by = {}
    for r in res.get("shots", []):
        try: by[int(r.get("slot", r.get("shot")))] = r
        except Exception: continue
    used, per, shots, problems = collections.defaultdict(list), collections.Counter(), [], []
    lower = {n.lower(): n for n in list(names) + list(photos)}
    for i, d in enumerate(durs):
        r = by.get(i)
        f = lower.get(str((r or {}).get("clip", "")).lower()) if r else None
        if not f:
            problems.append((i, "no shot, or a clip name that does not exist")); continue
        if f in photos:
            if shots and shots[-1].get("photo"):
                problems.append((i, "two photos in a row")); continue
            shots.append(dict(file=f, path=photos[f], tin=0.0, dur=d, photo=True, why=r.get("why", ""),
                              push=bool(r.get("key")) and sum(1 for s in shots if s.get("push")) < 3,
                              seg={"stage": "photo", "shows": r.get("why", "")}))
            continue
        if per[f] >= montage.MAX_PER_CLIP:
            problems.append((i, f"a fourth shot from {f}")); continue
        try: t = float(r.get("start", 0))
        except Exception: t = 0.0
        x = t if fits(f, t, d, used) else nearest(f, t, d, used)
        if x is None:
            problems.append((i, f"{f} at {t:.1f}s is not steady (shake, swing or blur) or already shown, and "
                                f"there is no steady moment within 3 s")); continue
        used[f].append((x, x + d + 0.3)); per[f] += 1
        shots.append(dict(file=f, tin=round(x, 2), dur=d, why=r.get("why", ""), moved=abs(x - t) > 0.05,
                          push=bool(r.get("key")) and sum(1 for s in shots if s.get("push")) < 3,
                          seg={"stage": "", "shows": r.get("why", "")}))
    if ordered: shots.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return shots, problems


def run(prefix, names, photos, seconds, ordered, note, dry=False, log=print):
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
    parts, listing = clip_parts(names, photos, log)

    res = ask_plan(parts, durs, note, ordered)
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
        if problems: log(f"   {len(problems)} slot(s) dropped — the video is that much shorter")
    title = re.sub(r"\s+", " ", str(res.get("title") or prefix).upper()).strip()[:22]
    sub = re.sub(r"\s+", " ", str(res.get("sub") or "")).upper().strip()[:30]
    show(shots, title, sub, log)
    if dry or not shots: return None

    out, total = montage.render(prefix, shots, title, sub)
    notes = review(out, shots, log)
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
    return out, total


def replace(shots, bad, res, names, photos, ordered):
    """The cut with only the weak slots swapped for the model's new picks — each new pick checked like any
    shot against the slots that stay; a slot whose new pick does not hold up keeps its old shot."""
    by = {}
    for r in res.get("shots", []):
        try: by[int(r.get("slot", r.get("shot")))] = r
        except Exception: continue
    lower = {n.lower(): n for n in list(names) + list(photos)}
    out = list(shots)
    for i in bad:
        r, d = by.get(i), shots[i]["dur"]
        f = lower.get(str((r or {}).get("clip", "")).lower()) if r else None
        if not f: continue
        if f in photos:
            if (i and out[i - 1].get("photo")) or (i + 1 < len(out) and out[i + 1].get("photo")): continue
            out[i] = dict(file=f, path=photos[f], tin=0.0, dur=d, photo=True, why=r.get("why", ""),
                          seg={"stage": "photo", "shows": r.get("why", "")})
            continue
        used = collections.defaultdict(list)
        for j, s in enumerate(out):
            if j != i and not s.get("photo"): used[s["file"]].append((s["tin"], s["tin"] + s["dur"] + 0.3))
        if sum(1 for j, s in enumerate(out) if j != i and s["file"] == f) >= montage.MAX_PER_CLIP: continue
        try: t = float(r.get("start", 0))
        except Exception: continue
        x = t if fits(f, t, d, used) else nearest(f, t, d, used)
        if x is None: continue
        out[i] = dict(file=f, tin=round(x, 2), dur=d, why=r.get("why", ""), moved=abs(x - t) > 0.05,
                      seg={"stage": "", "shows": r.get("why", "")})
    changed = [i for i in bad if out[i] is not shots[i]]
    if ordered:
        out.sort(key=lambda s: (num(s["file"]), s["file"], s["tin"]))
    return out, changed


def review(out, shots, log):
    """Gemini watches the rendered cut: [{"shot", "issue", "replace"}]."""
    try:
        rec = gemini.video("review_" + os.path.basename(out), out, log=log)
        t, table = 0.0, []
        for i, s in enumerate(shots):
            table.append(f"shot {i}: {t:.1f}-{t + s['dur']:.1f}s ({'photo' if s.get('photo') else 'video'})")
            t += s["dur"]
        ask = ("You are reviewing a finished vertical promo cut for a car hauler repair shop before it goes to "
               "the owner. He rejects: shaky footage, a camera swinging back and forth, blurred or dark shots, "
               "the order of the work broken (finished parts before the work), dull shots (walls, floor, people "
               "standing), the same moment twice. The text overlays and the black card at the end are fine.\n"
               "Shots: " + "; ".join(table) + "\nList only real problems. Reply with JSON only: "
               '{"problems": [{"shot": 3, "issue": "what is wrong", "replace": true}], "verdict": "one sentence"}')
        d = gemini.ask_json([gemini.video_part(rec, fps=4), {"text": ask}], max_tokens=4000)
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
