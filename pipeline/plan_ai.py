# Let Claude lay out the videos: which stretch of which clip goes under which words.
#
# This is the whole build in one command: it tags any new footage, describes whatever has no description yet,
# plans the cuts and renders. Everything is cached, so a second run on the same clips calls nothing extra.
#
# Face blur is OFF by default. The detector keeps firing on rust, bolt heads and hub holes, so an automatic pass
# smeared patches over every video while the clips themselves hold no faces. --blur turns it back on for a batch
# that does show people; the menu's manual blur item (finish.py) works on a finished render either way.
#
# The plan works on SEGMENTS, not whole clips (see describe.py): a ten-second clip may hold the crack, then a
# hand pointing at it, then a wide view. Assigning a whole file under "a crack running through the support"
# would let the renderer land on the wide view; assigning the 0-3s stretch cannot.
#
#   python pipeline\plan_ai.py scripts\topics_1027.txt                   every video in the file
#   python pipeline\plan_ai.py scripts\topics_1027.txt upperdeck         just this one
#   python pipeline\plan_ai.py scripts\topics_1027.txt brakes electrical  these two
#   --only PREFIX     use only clips whose name starts with this (a single project's story)
#   --dry             show the plans and the reasoning, render nothing
#   --no-scan / --no-describe   skip those steps if you have already done them by hand
#   --blur            also run the face blur after the render (writes output\CHRH_<Key>_blur.mp4)
#
# A video whose voice-over is missing, or that fails for any other reason, is reported and skipped; the rest of
# the batch still builds.
import os, sys, json, time, collections, re as _re, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()
sys.path.insert(0, HERE)
os.chdir(HERE)
import shutil
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

import autoplan, align, build, picker, plan, describe, finish

MODEL = "claude-sonnet-5-5"     # one call per video: worth the stronger model
URL = "https://api.anthropic.com/v1/messages"

SYSTEM = """You are the editor of short vertical promo videos for a car hauler repair shop.
You are given the voice-over split into consecutive cuts, and a list of footage segments with a description of
what each one shows. Assign one segment to every cut.

Rules, in order of importance:
1. The picture must match the words spoken at that moment. If the words name damage, show damage; if they name
   a weld, show the weld; if they name paint, show paint. This is the whole point.
2. Real work order. Damage comes before cutting, cutting before welding, welding before paint, paint before the
   finished result. Never show a finished part before the work that produced it.
3. Do not jump back and forth: once the video has moved past a stage, stay there, unless the words themselves
   go back to it.
4. Spread the material out. Do not leave good segments unused while repeating one, and avoid using the same
   segment for more than two cuts in a row.
5. Respect the numbers. "longest run" is the longest unbroken stretch inside that segment which is sharp,
   steady and not empty — a segment can only carry a cut if its longest run is at least that cut's length.
   "usable" is how much good footage the segment holds in total, so a 3s segment cannot carry three 2s cuts
   without showing the same seconds again.
6. The last cut carries the closing card and is the longest; give it a wide or finished shot long enough for it.

Reply with JSON only:
{"plan": [{"cut": 0, "seg": "s3"}, ...], "why": "one or two sentences about the shape you chose"}
Every cut must appear exactly once, and every id must come from the list."""


def ask(payload, key):
    body = json.dumps({"model": MODEL, "max_tokens": 4000, "system": SYSTEM,
                       "messages": [{"role": "user", "content": payload}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            txt = "".join(p.get("text", "") for p in data.get("content", []))
            a, b = txt.find("{"), txt.rfind("}")
            if a < 0: raise ValueError(f"no JSON (stop={data.get('stop_reason')}): {txt[:300]!r}")
            u = data.get("usage", {})
            print(f"(planned by {data.get('model')}, {u.get('input_tokens')} in / {u.get('output_tokens')} out)")
            return json.loads(txt[a:b + 1])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


def usable(f, rec, a=0.0, b=1e9):
    """(good seconds, longest unbroken good stretch) inside a..b — the same tests the renderer applies, so the
    plan is made against what can actually be cut, not against the raw file length."""
    d, w = picker.windows(f)
    th = picker.sharp_floor(f, 700)
    mlim = picker.motion_ceiling(f, 20 if picker.is_drone(f) else 35)
    bad = [tuple(r) for r in rec.get("dull", [])]
    runs, cur = [], None
    for (t, m, sh) in w:
        inside = t >= a - 0.01 and t + 1.0 <= b + 0.01
        if inside and picker.ok_window(m, sh, th, mlim) and not picker.overlap(t, t + 1.0, bad):
            if cur is None: cur = [t, t + 1.0]
            else: cur[1] = t + 1.0
        elif cur:
            runs.append(tuple(cur)); cur = None
    if cur: runs.append(tuple(cur))
    return sum(y - x for x, y in runs), max((y - x for x, y in runs), default=0.0)


def segments_of(C, pool_names):
    """Every described stretch of every clip, as one flat list of candidates."""
    cands = []
    for n in pool_names:
        rec = C.get(n, {})
        segs = rec.get("segments") or ([{"from": 0.0, "to": 1e9, "shows": rec["desc"],
                                         "stage": rec.get("stage", "other")}] if rec.get("desc") else [])
        for s in segs:
            a, b = float(s["from"]), float(s["to"])
            try: tot, longest = usable(n, rec, a, b)
            except Exception: continue
            if longest < 1.0: continue       # nothing in this stretch is long enough to be a shot
            cands.append({"id": f"s{len(cands) + 1}", "clip": n, "a": a, "b": b,
                          "usable": round(tot, 1), "longest": round(longest, 1),
                          "shows": s["shows"], "stage": s.get("stage", "other")})
    return cands


def place(key, slots, cuts, order, cands):
    """Put a real window under every cut. The assigned segment wins; the rest is only a fallback."""
    own = collections.defaultdict(list)
    batch_used = collections.defaultdict(list)
    P, rep, problems = [], [], []
    for i, (w, _, z) in enumerate(slots):
        need = cuts[i + 1] - cuts[i]
        base = collections.defaultdict(list)
        for f, r in own.items(): base[f] += r
        oc = {f: len(r) for f, r in own.items()}
        c = order[i]
        got, how = None, ""

        if c:   # keep the search inside the assigned stretch by forbidding everything outside it
            forbid = collections.defaultdict(list)
            for f, r in base.items(): forbid[f] += r
            forbid[c["clip"]] += [(0.0, c["a"]), (c["b"], 1e9)]
            got = (picker.best([c["clip"]], need, forbid, batch_used, 700, own_count=oc)
                   or picker.best([c["clip"]], need, forbid, batch_used, 600, own_count=oc))
            if got is None:   # the stretch is too short for this cut: stay in the clip, leave the stretch
                got = (picker.best([c["clip"]], need, base, batch_used, 700, own_count=oc)
                       or picker.best([c["clip"]], need, base, batch_used, 600, own_count=oc))
                if got: how = "  (outside the segment)"
        if got is None:
            rest = [x["clip"] for x in cands if not c or x["clip"] != c["clip"]]
            if rest:
                got = (picker.best(rest, need, base, batch_used, 700, own_count=oc)
                       or picker.best(rest, need, base, batch_used, 600, own_count=oc))
                if got: how = "  (another clip)"
        if got is None and c:   # last resort: seconds of the assigned clip this video already used
            got = picker.best([c["clip"]], need, collections.defaultdict(list), batch_used, 600, own_count=oc)
            how = "  (repeats seconds)"
        if got is None:
            rep.append(f"  cut {i} ({need:.1f}s) NO CANDIDATE")
            problems.append((i, "no usable window anywhere")); continue
        if how: problems.append((i, how.strip(" ()")))
        f, t, sp, ms, reused = got
        own[f].append((t, t + need * sp + 0.3)); batch_used[f].append((t, t + need * sp + 0.3))
        zz = z if z is not None else ((1.0, 0.5, 0.5) if picker.is_drone(f) and "decking" not in f else None)
        if "decking" in f or "DJI" in f: zz = z or (1.0, 0.5, 0.5)
        P.append((w, f, t, sp, zz))
        rep.append(f"  {i:2d} {need:4.1f}s {f[:30]:30s} @{t:5.2f} x{sp} sharp {ms:5.0f}{how}")
    return P, rep, problems


def make(key, cands, byid, apikey, dry, only):
    """Plan and render one video. Returns the output path, or None when nothing was rendered."""
    build.A[key] = align.align_keys([key], log=print)[key]
    A = build.A[key]

    # the cuts, exactly as a normal build would place them
    ph = autoplan.phrases(key)
    slots = [(None if i == 0 else a, [], None) for i, (a, b) in enumerate(ph)]
    slots = picker.split_long(key, slots)
    idx = [0 if w is None else w for (w, _, _) in slots] + [len(A)]
    total = build.PRE + build.voDur(key) + build.END
    cuts = [0 if w is None else A[w][1] + build.PRE - 0.06 for (w, _, _) in slots] + [total]
    # the aligner numbers repeats of a word ("the(2)"); that is its bookkeeping, not something to read
    word = lambda j: _re.sub(r"\(\d+\)$", "", A[j][0])
    texts = [" ".join(word(j) for j in range(idx[i], idx[i + 1])) for i in range(len(slots))]

    payload = ("VOICE-OVER, split into cuts:\n" +
               "\n".join(f'  cut {i}: needs {cuts[i+1]-cuts[i]:.1f}s — "{texts[i]}"' for i in range(len(slots))) +
               "\n\nFOOTAGE SEGMENTS:\n" +
               "\n".join(f'  {c["id"]}  {c["clip"]} {c["a"]:.1f}-{c["b"]:.1f}s '
                         f'(usable {c["usable"]}s, longest run {c["longest"]}s) [{c["stage"]}]: {c["shows"]}'
                         for c in cands))
    print(f"{len(slots)} cuts, {len(cands)} segment(s) from {len(set(c['clip'] for c in cands))} clip(s)")

    def read_plan(res):
        got = {}
        for row in res.get("plan", []):
            try: got[int(row["cut"])] = str(row.get("seg") or row.get("clip") or "")
            except Exception: continue
        out = []
        for i in range(len(slots)):
            v = got.get(i, "")
            if v in byid: out.append(byid[v]); continue
            hit = [c for c in cands if v and v.lower() in c["clip"].lower()]   # tolerate a clip name
            out.append(hit[0] if hit else None)
        return out

    res = ask(payload, apikey)
    order = read_plan(res)
    print("\n" + (res.get("why", "") or ""))
    blank = [i for i, c in enumerate(order) if c is None]
    if blank: print(f"note: nothing named for cut(s) {blank}; they will be filled from the rest")

    print()
    for i, c in enumerate(order):
        tag = f'{c["clip"]} {c["a"]:.0f}-{c["b"]:.0f}s' if c else "(free choice)"
        print(f"  cut {i:2d} {cuts[i+1]-cuts[i]:4.1f}s  {tag:34s} {texts[i][:52]}")
        if c: print(f"{'':42s}   -> {c['shows'][:70]}")

    if dry: return None

    P, rep, problems = place(key, slots, cuts, order, cands)

    # A cut that could not take its assigned segment is a wrong picture under those words — the thing this
    # script exists to prevent. So instead of quietly substituting, hand the failures back and let the model
    # choose again knowing what went wrong. One cheap extra call, and only when something did not fit.
    if problems:
        print(f"\n{len(problems)} cut(s) did not take what was assigned; asking for a correction...")
        for i, why in problems: print(f"   cut {i}: {why}")
        spent = collections.Counter(f for (_, f, _, _, _) in P)
        detail = "\n".join(
            f'  cut {i} (needs {cuts[i+1]-cuts[i]:.1f}s, "{texts[i]}") was given '
            f'{order[i]["id"] if order[i] else "nothing"}: {why}' for i, why in problems)
        repair = (payload + "\n\nYOUR PREVIOUS PLAN DID NOT WORK FOR THESE CUTS:\n" + detail +
                  "\n\nSeconds already spent per clip in that plan: " +
                  ", ".join(f"{k} x{v}" for k, v in sorted(spent.items())) +
                  "\n\nGive the WHOLE plan again, every cut, choosing differently for the cuts listed above. "
                  "A segment whose longest run is shorter than a cut cannot take that cut.")
        try:
            res2 = ask(repair, apikey)
            order2 = read_plan(res2)
            order2 = [order2[i] or order[i] for i in range(len(slots))]
            P2, rep2, prob2 = place(key, slots, cuts, order2, cands)
            if len(prob2) < len(problems):
                print(f"corrected: {len(problems)} problem cut(s) -> {len(prob2)}")
                print("\n" + (res2.get("why", "") or ""))
                P, rep, problems, order = P2, rep2, prob2, order2
            else:
                print("the correction was no better; keeping the first plan")
        except Exception as e:
            print(f"could not get a correction ({e}); keeping the first plan")

    print("\n".join(rep))
    if [r for r in rep if "NO CANDIDATE" in r]:
        raise RuntimeError(f"some cuts found no usable window — try `python pipeline\\tune.py free "
                           f"{only or '<prefix>'}`")
    if problems:
        print(f"{len(problems)} cut(s) show a substitute - check those on the contact sheet.")

    plan.P[key] = P
    path, d = autoplan.batch_of(key)
    if d:
        d["videos"][key]["plan"] = [list(x) for x in P]
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return autoplan.render_key(key, log=print)


# ------------------------------------------------------------------ run
args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]
if not args:
    sys.exit("usage: python pipeline\\plan_ai.py SCRIPTS.txt [KEY ...] [--only PREFIX] [--dry]")
spath = args[0]; spath = spath if os.path.isabs(spath) else os.path.join(START, spath)
only = ""
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    if i + 1 < len(sys.argv): only = sys.argv[i + 1].lower()
wanted = [a.lower() for a in args[1:] if a.lower() != only]
dry = "--dry" in flags

apikey = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not apikey: sys.exit('no API key. In PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."')

allvids = autoplan.parse_batch(open(spath, encoding="utf-8").read())
if not allvids: sys.exit(f"no scripts found in {args[0]}")
vids = [v for v in allvids if not wanted or v["key"] in wanted]
if not vids: sys.exit(f"none of {wanted} found in {args[0]} (it has: "
                      + ", ".join(v["key"] for v in allvids) + ")")
missing_vo = [v["key"] for v in vids if not os.path.exists(autoplan.vo_path(v["key"]))]
if missing_vo:
    print(f"no voice-over yet for: {', '.join(missing_vo)} — skipping those")
    vids = [v for v in vids if v["key"] not in missing_vo]
if not vids: sys.exit("nothing to build")

autoplan.register(vids); autoplan.load_all_batches()
L = autoplan.apply_lib(); autoplan.refresh_footage()

# new footage dropped into footage\ is tagged first: topics, dull seconds, the outdoor-paint rule
if "--no-scan" not in flags:
    untagged = [f for f in build.files if f not in L.get("clips", {})]
    if untagged:
        print(f"{len(untagged)} new clip(s) in footage/, tagging…")
        autoplan.rescan(log=print)
        L = autoplan.apply_lib(); autoplan.refresh_footage()
C = L["clips"]

pool_names = [n for n in sorted(C) if C[n].get("enabled") and n in build.FILES
              and (not only or n.lower().startswith(only))]
if not pool_names: sys.exit("no enabled clips" + (f" starting with '{only}'" if only else ""))

# describe whatever has none yet; already described clips cost nothing
if "--no-describe" not in flags:
    missing = [n for n in pool_names if describe.needs_description(C[n], n)]
    if missing:
        describe.describe(missing, L, apikey, log=print)
        L = autoplan.apply_lib(); C = L["clips"]

cands = segments_of(C, pool_names)
if not cands: sys.exit("no usable footage described — check the API key and the log above")
byid = {c["id"]: c for c in cands}

keys = [v["key"] for v in vids]
blur = "--blur" in flags
print(f"\n=== {len(keys)} video(s) to build: {', '.join(keys)} ===")
done, failed, unblurred = [], [], []
for n, k in enumerate(keys, 1):
    print(f"\n----- {n}/{len(keys)}  {k} " + "-" * 40)
    try:
        out = make(k, cands, byid, apikey, dry, only)
        if not out: continue
        if not blur:
            done.append((k, os.path.basename(out))); continue
        # The blur runs here rather than in make(), so a failure costs the publishable file and not the render.
        try:
            pub = finish.run(k, log=print, hint=out)
        except Exception as e:
            print(f"{k}: the blur pass FAILED {e}")
            pub = None
        if pub: done.append((k, os.path.basename(pub)))
        else: unblurred.append((k, os.path.basename(out), "the blur pass did not finish"))
    except Exception as e:
        print(f"{k}: FAILED {e}")
        failed.append((k, str(e)))

if not dry:
    print(f"\n=== ready to publish {len(done)}" + (f", not cleared {len(unblurred)}" if unblurred else "")
          + (f", failed {len(failed)}" if failed else "") + " ===")
    for k, f in done: print(f"  {k}: {f}")
    for k, f, why in unblurred: print(f"  {k}: {f} — NOT CLEARED, faces still in it ({why})")
    for k, e in failed: print(f"  {k}: FAILED {e}")
    if unblurred and blur:
        print("\nfix those with:  python pipeline\\finish.py " + " ".join(k for k, _, _ in unblurred))
