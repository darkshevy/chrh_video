# Dynamic montage: one project's footage cut every 2-3 seconds, from the damage to the finished part.
# No voice-over, no captions, no sound at all — those are added later, by hand. On screen: the title at the
# start, the phone bar on top, and the end card with the address.
#
#   python pipeline\montage.py springlock                 ~30 s, title invented from the footage
#   python pipeline\montage.py springlock --seconds 40
#   python pipeline\montage.py springlock --dry           show the plan, render nothing
#
# Claude (Sonnet) chooses which described stretch goes where: the order of the work, the most watchable
# moments, no clip twice in a row. Code then checks what a prompt alone kept getting wrong — stage order and
# repeats — and fixes what is left, picks the exact seconds inside each stretch (the sharpest, not the smeared
# ones) and renders with the same look as the voiced videos (grade, stabilisation, phone bar, end card).
#
# The clips must be described first (menu step 1, or describe.py <prefix>): the plan is made from the
# descriptions, and it is only as good as they are. "The clips are numbered in the order the work was done"
# in the note makes the clip number decide the order.
import os, sys, json, time, random, shutil, subprocess, collections, re, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

import autoplan, build, picker, describe

MODEL = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"
FPS = build.FPS
END = 4.0                         # end card, over the last shots
SHOT_MIN, SHOT_MAX = 2.0, 3.0     # boss: something new on screen every 2-3 seconds
ORDER = {"damage": 0, "strip": 1, "fit": 2, "weld": 3, "finish": 4, "done": 5}
CURRENT = os.path.join(os.path.dirname(HERE), "work", "current.json")

SYSTEM = """You edit short vertical videos for a car hauler (car carrier trailer) repair shop. There is no
voice-over and no captions: the pictures alone have to tell the job, from the broken part to the finished
repair, and keep a viewer watching.

You get the footage of ONE job as described stretches ("segments"), each tagged with its stage, and the
number of shots to fill. Choose a segment for every shot.

Rules, in order of importance:
1. Work order. The stages go damage -> strip (cutting, grinding, removal) -> fit -> weld -> finish -> done.
   Never show a later stage before an earlier one. "other" segments (walkarounds, wide views) may sit
   anywhere, but not between two shots of the same later stage after the job has moved on.
2. Start strong: the first shot is the clearest view of the damage — the viewer must see the problem at once.
   End on the finished result: the last three shots are [done] (or the latest stage there is), the best
   looking ones; the end card with the address sits over them.
3. Prefer action and detail: sparks, welding, cutting, grinding, a hand fitting a part, a close-up of the
   damage or of the new weld. Skip empty, dull or repetitive stretches when there is better material.
4. Variety: never the same clip in two shots in a row; a segment at most twice in the whole video, and only
   when there is nothing else for that stage.
5. A segment can only carry a shot if its "longest run" is at least the shot's length.
6. Give the stages room in proportion to how much good footage each has — do not spend half the video on the
   damage if most of the footage is the work.

Also write the title shown at the start: "title" 2-4 words, max 22 characters, capitals, naming the repair
(e.g. "SPRING LOCK REPAIR"); "sub" max 30 characters, capitals, the gist (e.g. "BROKEN LOCK OUT, NEW ONE IN").
Only what the footage and the shop's note show — no invented parts or materials.

Reply with JSON only:
{"shots": [{"shot": 0, "seg": "s3"}, ...], "title": "...", "sub": "...", "why": "one sentence"}"""


# ------------------------------------------------------------------ footage
def usable(f, rec, a, b):
    """(good seconds, longest unbroken stretch) inside a..b, the dull seconds left out."""
    d, w = picker.windows(f)
    th = picker.sharp_floor(f, 700)
    mlim = picker.motion_ceiling(f, 20 if picker.is_drone(f) else 35)
    bad = [tuple(r) for r in rec.get("dull", [])]
    runs, cur = [], None
    for (t, m, sh) in w:
        ok = t >= a - 0.01 and t + 1.0 <= b + 0.01 and picker.ok_window(m, sh, th, mlim) \
             and not picker.overlap(t, t + 1.0, bad)
        if ok:
            cur = [t, t + 1.0] if cur is None else [cur[0], t + 1.0]
        elif cur:
            runs.append(tuple(cur)); cur = None
    if cur: runs.append(tuple(cur))
    return sum(y - x for x, y in runs), max((y - x for x, y in runs), default=0.0)


def segments(C, names):
    """Every described stretch of the project's clips, numbered in work order."""
    num = lambda n: int(m.group(1)) if (m := re.search(r"(\d+)\.\w+$", n)) else 0
    ordered = all("numbered in the order" in C[n].get("desc_note", "").lower() for n in names)
    out = []
    for n in sorted(names, key=lambda n: (num(n), n)):
        for s in C[n].get("segments", []):
            a, b = float(s["from"]), float(s["to"])
            try: tot, longest = usable(n, C[n], a, b)
            except Exception: continue
            if longest < SHOT_MIN: continue          # cannot carry even the shortest shot
            out.append({"id": f"s{len(out) + 1}", "clip": n, "num": num(n), "a": a, "b": b,
                        "stage": s.get("stage", "other"), "shows": s["shows"],
                        "usable": round(tot, 1), "longest": round(longest, 1)})
    return out, ordered


def durations(total, seed):
    """Shot lengths of 2-3 s that add up to `total`, in whole frames. Seeded by the project, so a re-run of the
    same project cuts at the same moments."""
    rnd = random.Random(seed)
    out, left = [], total
    while left > SHOT_MAX + SHOT_MIN:
        d = round(rnd.uniform(SHOT_MIN, SHOT_MAX) * FPS) / FPS
        out.append(d); left -= d
    if left > SHOT_MAX: out += [round(left / 2 * FPS) / FPS] * 2      # two even shots instead of one too long
    else: out.append(round(left * FPS) / FPS)
    return out


# ------------------------------------------------------------------ the plan
def ask(payload, key):
    body = json.dumps({"model": MODEL, "max_tokens": 8000, "system": SYSTEM,
                       "messages": [{"role": "user", "content": payload}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            if data.get("stop_reason") == "max_tokens": raise RuntimeError("the reply was cut off")
            txt = "".join(p.get("text", "") for p in data.get("content", []))
            a, b = txt.find("{"), txt.rfind("}")
            if a < 0: raise ValueError(f"no JSON in the reply: {txt[:300]!r}")
            u = data.get("usage", {})
            print(f"(planned by {data.get('model')}, {u.get('input_tokens')} in / {u.get('output_tokens')} out)")
            return json.loads(txt[a:b + 1])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except RuntimeError:
            raise
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


def rank(c):
    """Place of a segment in the job. 'other' takes the clip's place among its neighbours."""
    return ORDER.get(c["stage"], None)


def check(order, durs):
    """[(shot, reason)] for what breaks the rules: stage order, repeats, too short a stretch."""
    out, reached, seen = [], -1, collections.Counter()
    for i, c in enumerate(order):
        if c is None:
            out.append((i, "no segment")); continue
        r = rank(c)
        if r is not None:
            if r < reached: out.append((i, f"goes back to [{c['stage']}] after the job reached a later stage"))
            reached = max(reached, r)
        seen[c["id"]] += 1
        if seen[c["id"]] > 2: out.append((i, f"{c['id']} used a third time"))
        if i and order[i - 1] and order[i - 1]["clip"] == c["clip"]:
            out.append((i, f"same clip as the shot before ({c['clip']})"))
        if c["longest"] < durs[i]: out.append((i, f"{c['id']} longest run {c['longest']}s < shot {durs[i]:.1f}s"))
    return out


def repair(order, durs, cands):
    """Fix what is still wrong, shot by shot, without asking: the least used segment that keeps the stage
    order (between the stages of the neighbouring shots), is long enough and is not the neighbours' clip."""
    for _ in range(len(order) * 2):
        bad = check(order, durs)
        if not bad: break
        i, why = bad[0]
        used = collections.Counter(c["id"] for c in order if c)
        prev_r = max([rank(c) for c in order[:i] if c and rank(c) is not None], default=-1)
        next_r = min([rank(c) for c in order[i + 1:] if c and rank(c) is not None], default=99)
        lo, hi = prev_r, max(prev_r, next_r)
        nb = {order[j]["clip"] for j in (i - 1, i + 1) if 0 <= j < len(order) and order[j]}
        pool = [x for x in cands if (rank(x) is None or lo <= rank(x) <= hi) and x["clip"] not in nb
                and x["longest"] >= durs[i] and used[x["id"]] < 2]
        if not pool:
            pool = [x for x in cands if x["clip"] not in nb and x["longest"] >= durs[i]] or cands
        dist = lambda x: abs((lo if rank(x) is None else rank(x)) - max(lo, 0))
        pool.sort(key=lambda x: (used[x["id"]], rank(x) is None, dist(x), -x["longest"]))
        new = pool[0]
        if order[i] is new: break
        print(f"   shot {i}: {why} -> {new['id']} {new['clip']} [{new['stage']}]")
        order[i] = new
    return order


def plan(prefix, cands, ordered, durs, note, key):
    sec = sum(durs)
    payload = (f"{len(durs)} shots, {sec:.0f} seconds in all. Shot lengths: " +
               ", ".join(f"{i}: {d:.1f}s" for i, d in enumerate(durs)) +
               f"\nThe last {END:.0f} seconds carry the end card." +
               (f"\n\nWhat the shop says this job is: {note}" if note else "") +
               ("\n\nThe clips are numbered in the order the work was done." if ordered else "") +
               "\n\nFOOTAGE SEGMENTS (in clip order):\n" +
               "\n".join(f'  {c["id"]}  {c["clip"]} {c["a"]:.1f}-{c["b"]:.1f}s (longest run {c["longest"]}s) '
                         f'[{c["stage"]}]: {c["shows"]}' for c in cands))
    byid = {c["id"]: c for c in cands}

    def read(res):
        got = {}
        for row in res.get("shots", []):
            try: got[int(row["shot"])] = byid.get(str(row.get("seg", "")))
            except Exception: continue
        return [got.get(i) for i in range(len(durs))]

    res = ask(payload, key)
    order = read(res)
    print(res.get("why", ""))
    bad = check(order, durs)
    if bad:
        print(f"{len(bad)} shot(s) break the rules; asking for a correction…")
        for i, why in bad: print(f"   shot {i}: {why}")
        try:
            res2 = ask(payload + "\n\nYOUR PREVIOUS PLAN:\n" +
                       ", ".join(f"{i}:{c['id'] if c else '-'}" for i, c in enumerate(order)) +
                       "\nIT BREAKS THESE RULES:\n" + "\n".join(f"  shot {i}: {w}" for i, w in bad) +
                       "\n\nGive the whole plan again, fixing exactly these. JSON only.", key)
            order2 = read(res2)
            if len(check(order2, durs)) < len(bad):
                order, res = order2, {**res, **{k: v for k, v in res2.items() if v}}
                print("corrected")
        except Exception as e:
            print(f"no correction ({e}); fixing in code")
    order = repair(order, durs, cands)
    title = re.sub(r"\s+", " ", str(res.get("title") or prefix).upper()).strip()[:22]
    sub = re.sub(r"\s+", " ", str(res.get("sub") or "")).upper().strip()[:30]
    return order, title, sub


# ------------------------------------------------------------------ exact seconds
def window(c, d, own):
    """Best unused window of length d inside segment c, widened by up to 2 s if it must be."""
    for grow in (0.0, 1.0, 2.0):
        forbid = collections.defaultdict(list)
        for f, r in own.items(): forbid[f] += r
        forbid[c["clip"]] += [(0.0, max(0.0, c["a"] - grow)), (c["b"] + grow, 1e9)]
        got = picker.best([c["clip"]], d, forbid, collections.defaultdict(list), 700, allow_slow=False)
        if got: return got
    return None


def place(order, durs, cands):
    """The exact window for every shot: inside its segment, never seconds already used in this video,
    sharpest available. When the segment's free seconds are used up: another segment of the same stage (not
    the neighbours' clip); only then a repeat — a repeat used to pull 'before' seconds into the finale."""
    own = collections.defaultdict(list)
    shots = []
    for i, (c, d) in enumerate(zip(order, durs)):
        got, seg = window(c, d, own), c
        if got is None:
            nb = {order[j]["clip"] for j in (i - 1, i + 1) if 0 <= j < len(order)}
            for x in sorted((x for x in cands if x["stage"] == c["stage"] and x is not c),
                            key=lambda x: (x["clip"] in nb, -x["longest"])):
                got = window(x, d, own)
                if got: seg = x; break
        if got is None:
            got = picker.best([c["clip"]], d, collections.defaultdict(list), collections.defaultdict(list), 700,
                              allow_slow=False)
        if got is None: raise RuntimeError(f"shot {i}: no window in {c['clip']}")
        f, t, sp, ms, _ = got
        own[f].append((t, t + d + 0.3))
        shots.append(dict(file=f, tin=t, dur=d, seg=seg))
    return shots


# ------------------------------------------------------------------ render
ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TBrand,Arial,38,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,6,0,1,3,1.5,8,60,60,560,1
Style: TPart,Arial,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,3,0,1,5,2.5,8,60,60,610,1
Style: TName,Arial,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,740,1
Style: TPartS,Arial,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,620,1
Style: TNameS,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1.5,0,1,3,1.5,8,60,60,750,1
Style: Box,Arial,10,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: EndBig,Arial,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,5,60,60,0,1
Style: EndSub,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1.5,5,60,60,0,1
Style: EndAddr,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,3,1.5,5,60,60,0,1
Style: Phone,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H64000000,-1,0,0,0,100,100,2,0,3,10,0,8,60,60,436,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def make_ass(path, total, title, sub):
    """Title, phone bar and end card — the same styles and positions as the voiced videos (build.make_ass),
    all inside the Facebook 1:1 safe zone, without the captions and the music credit."""
    ts, e0 = build.ts, total - END
    big_style = "TPart" if len(title) <= 13 else "TPartS"
    sub_style = "TName" if len(sub) <= 22 else "TNameS"
    ev = [f"Dialogue: 2,{ts(0.15)},{ts(3.3)},TBrand,,0,0,0,,{{\\fad(300,350)}}CAR HAULER REPAIR HOUSTON",
          f"Dialogue: 2,{ts(0.25)},{ts(3.3)},{big_style},,0,0,0,,{{\\fad(300,350)}}{title}"]
    if sub: ev.append(f"Dialogue: 2,{ts(0.40)},{ts(3.3)},{sub_style},,0,0,0,,{{\\fad(300,350)}}{sub}")
    ev += [f"Dialogue: 0,{ts(e0)},{ts(total + 0.1)},Box,,0,0,0,,{{\\fad(300,0)\\an7\\pos(0,0)"
           f"\\1c&H000000&\\1a&H70&\\bord0\\shad0\\p1}}m 0 0 l 1080 0 1080 1920 0 1920{{\\p0}}",
           f"Dialogue: 2,{ts(e0 + 0.1)},{ts(total + 0.1)},EndBig,,0,0,0,,{{\\fad(350,0)\\pos(540,860)}}CAR HAULER\\NREPAIR HOUSTON",
           f"Dialogue: 2,{ts(e0 + 0.3)},{ts(total + 0.1)},EndSub,,0,0,0,,{{\\fad(350,0)\\pos(540,1075)}}CALL {build.PHONE}",
           f"Dialogue: 2,{ts(e0 + 0.5)},{ts(total + 0.1)},EndAddr,,0,0,0,,{{\\fad(350,0)\\pos(540,1160)}}{build.ADDRESS}",
           f"Dialogue: 3,{ts(0.0)},{ts(e0 + 0.2)},Phone,,0,0,0,,{{\\fad(400,300)}}CALL {build.PHONE}"]
    open(path, "w", encoding="utf-8").write(ASS_HEAD + "\n".join(ev) + "\n")


def render_shot(s, out, trf):
    """One shot, 1080x1920, graded and stabilised like build.render, no audio."""
    f = s["file"]
    n = round(s["dur"] * FPS)
    vf = []
    stab = not (f.startswith("DJI") or "DroneDirections" in build.src(f))     # boss rule 3: drones as they are
    if stab:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(s["tin"]), "-t", f"{s['dur'] + 0.3:.3f}",
                        "-i", build.src(f), "-vf", f"vidstabdetect=shakiness=6:accuracy=15:stepsize=6:result={trf}",
                        "-f", "null", "-"], check=True, cwd=build.WORK)
        vf.append(f"vidstabtransform=input={trf}:smoothing=14:optzoom=1:zoomspeed=0.2:interpol=bicubic"
                  f":maxshift={max(8, int(0.04 * min(build.dims(f))))}:maxangle=0.05")
    if build.fit_mode(f):
        vf += build.fit_filters()
    else:
        z, cx, cy = (1.0, 0.5, 0.5)
        vf += [f"scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase",
               f"crop=1080:1920:'min(max(iw*{cx}-540,0),iw-1080)':'min(max(ih*{cy}-960,0),ih-1920)'"]
    vf += [build.GRADE, "unsharp=5:5:0.5:5:5:0.2" if min(build.dims(f)) < 720 else "null",
           "fps=30", "setpts=PTS-STARTPTS", "format=yuv420p"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(s["tin"]), "-t", f"{s['dur'] + 0.3:.3f}",
                    "-i", build.src(f), "-an", "-vf", ",".join(vf), "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-g", "30", out],
                   check=True, cwd=build.WORK)


def render(prefix, shots, title, sub):
    tag = 1
    while os.path.exists(os.path.join(build.OUT, f"CHRH_{prefix.capitalize()}_montage_v{tag}.mp4")): tag += 1
    out = os.path.join(build.OUT, f"CHRH_{prefix.capitalize()}_montage_v{tag}.mp4")
    d = f"m_{prefix}"
    full = os.path.join(build.WORK, d)
    shutil.rmtree(full, ignore_errors=True); os.makedirs(full)
    names = []
    for i, s in enumerate(shots):
        print(f"  shot {i + 1}/{len(shots)}  {s['file']} @{s['tin']:.2f} {s['dur']:.1f}s")
        render_shot(s, f"{d}/{i:02d}.mp4", f"{d}/{i:02d}.trf")
        names.append(f"{d}/{i:02d}.mp4")
    open(os.path.join(full, "list.txt"), "w", encoding="utf-8").write("".join(f"file '{n.split('/')[-1]}'\n" for n in names))
    total = sum(round(s["dur"] * FPS) for s in shots) / FPS
    make_ass(os.path.join(full, "over.ass"), total, title, sub)
    # one pass over the joined shots: overlays + fades; relative paths, ffmpeg runs in work\ (a drive colon
    # breaks filter arguments on Windows)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{d}/list.txt",
                    "-vf", f"ass={d}/over.ass,fade=t=in:st=0:d=0.4,fade=t=out:st={total - 0.6:.3f}:d=0.6",
                    "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out], check=True, cwd=build.WORK)
    shutil.rmtree(full, ignore_errors=True)       # several hundred MB of pieces; the video is what counts
    try:
        import contact
        contact.sheet(out, build.OUT, 6, 4)
    except Exception as e:
        print(f"(no contact sheet: {e})")
    return out, total


# ------------------------------------------------------------------ run
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit("usage: python pipeline\\montage.py PREFIX [--seconds 30] [--dry]")
    prefix = args[0].lower()
    seconds = 30.0
    if "--seconds" in sys.argv:
        try: seconds = float(sys.argv[sys.argv.index("--seconds") + 1])
        except Exception: sys.exit("--seconds wants a number")
    dry = "--dry" in sys.argv
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key: sys.exit('no API key. In PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."')

    L = autoplan.apply_lib(); autoplan.refresh_footage()
    C = L["clips"]
    names = [n for n in sorted(C) if n.lower().startswith(prefix) and C[n].get("enabled") and n in build.FILES]
    if not names: sys.exit(f"no enabled clips starting with '{prefix}' — scan and describe them first (menu step 1)")
    note = ""
    try: note = json.load(open(CURRENT, encoding="utf-8")).get("notes", {}).get(prefix, "")
    except Exception: pass
    missing = [n for n in names if not C[n].get("segments")]
    if missing:
        print(f"{len(missing)} clip(s) not described yet, describing the project…")
        if describe.describe_project(names, L, key, note=note, prefix=prefix) is None:
            describe.describe(missing, L, key, note=note)
        L = autoplan.apply_lib(); C = L["clips"]

    cands, ordered = segments(C, names)
    if not cands: sys.exit("no usable stretches in these clips")
    durs = durations(seconds, prefix)
    print(f"{prefix}: {len(names)} clip(s), {len(cands)} usable stretch(es), {len(durs)} shots for {seconds:.0f} s"
          + (" — clip numbers give the order" if ordered else ""))

    order, title, sub = plan(prefix, cands, ordered, durs, note, key)
    print(f"\ntitle: {title}" + (f" / {sub}" if sub else ""))
    t = 0.0
    for i, (c, d) in enumerate(zip(order, durs)):
        print(f"  {i:2d} {t:5.1f}s {d:.1f}s  [{c['stage']:6s}] {c['clip'][:26]:26s} {c['a']:.0f}-{c['b']:.0f}s  "
              f"{c['shows'][:60]}")
        t += d
    if dry: return

    shots = place(order, durs, cands)
    out, total = render(prefix, shots, title, sub)
    rp = os.path.splitext(out)[0] + "_plan.txt"
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(f"{prefix}  {title} / {sub}\n\n")
        t = 0.0
        for i, s in enumerate(shots):
            c = s["seg"]
            fh.write(f"{i:2d} {t:5.1f}s {s['dur']:.1f}s [{c['stage']}] {s['file']} @{s['tin']:.2f}  {c['shows']}\n")
            t += s["dur"]
    print(f"\ndone: output\\{os.path.basename(out)}  ({total:.1f} s, no sound)")


if __name__ == "__main__":
    main()
