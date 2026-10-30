# Describe clips in plain English with Claude and store the description in library.json.
#
# Two levels are stored per clip:
#   desc      one sentence about the clip as a whole
#   segments  what is on screen during each stretch of it, with timecodes
#
# The second one is what makes the picture match the words. A ten-second clip is rarely one thing: the crack is
# in the first three seconds, the hand pointing at it in the next two, the wide view at the end. Describing the
# clip as a whole would let the planner put it under "a crack running through the support" and the renderer
# would then land on the wide view. With segments the planner picks the stretch, not just the file.
#
# Set the key once per terminal (or permanently via System Properties -> Environment Variables):
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."
#
#   python pipeline\describe.py                     describe every clip that has no description yet
#   python pipeline\describe.py rampwidth           only clips whose name starts with that
#   python pipeline\describe.py --force rampwidth   describe them again, overwriting
#   python pipeline\describe.py --show rampwidth    print what is stored, call nothing
#
# Usually you do not run this yourself: plan_ai.py describes whatever it needs. A clip is described once and
# cached by file size and date, so a re-shot clip under the same name is described again, an untouched one never.
import os, sys, json, time, base64, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autoplan, build

MODEL = "claude-haiku-5-5"
MAXFRAMES = 10             # a frame roughly every second or two, whichever gives fewer
MINSTEP = 1.2
MAXPX = 768
URL = "https://api.anthropic.com/v1/messages"

PROMPT = """You are cataloguing raw footage for a car hauler (car carrier trailer) repair shop in Houston.
The frames above all come from ONE clip, in order, each labelled with its time in seconds.

Reply with JSON only, no other text:
{"desc": "...", "kw": ["..."], "subject": "...", "stage": "...",
 "segments": [{"from": 0.0, "to": 3.5, "shows": "...", "stage": "..."}]}

desc:    one sentence covering the clip as a whole.
kw:      4 to 8 lowercase search keywords.
subject: two or three words naming the main object, e.g. "front extension ramp", "upper deck support".
stage:   the clip's overall stage, from the list below.

segments: split the clip where what is on screen actually changes — a new angle, a new part, a different
  activity. Use the frame times: a segment runs from one frame's time to the time where the picture changes.
  Cover the whole clip, in order, without gaps or overlaps. One segment is fine if nothing changes; do not
  invent changes you cannot see, and do not split into more than six.
  shows: one short phrase, what is visible in THAT stretch, concrete. Name the part, say close-up or wide,
         and say plainly if damage is visible (crack, rust, cracked coating) or if the part looks finished
         (fresh weld bead, new paint, clean steel). This phrase is what a shot gets matched against, so it
         matters more than anything else here.
  stage: damage, strip, weld, fit, finish, done or other — damage = the fault before work, strip =
         cutting/grinding/removal, weld = welding, fit = new steel being fitted, finish = paint or coating,
         done = the finished result, other = anything else (yard, walkaround, people)."""

_shown = False


def frames(path):
    """[(seconds, base64 jpeg)] — up to MAXFRAMES, evenly spaced, never closer than MINSTEP apart."""
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    dur = total / fps if total else 0
    if dur <= 0: cap.release(); return [], 0.0
    step = max(MINSTEP, dur / MAXFRAMES)
    out, t = [], min(0.3, dur / 20)
    while t < dur - 0.1 and len(out) < MAXFRAMES:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if ok:
            h, w = f.shape[:2]
            s = MAXPX / max(h, w)
            if s < 1: f = cv2.resize(f, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
            ok2, buf = cv2.imencode(".jpg", f, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok2: out.append((round(t, 1), base64.b64encode(buf.tobytes()).decode()))
        t += step
    cap.release()
    return out, dur


def ask(shots, dur, key, log=print, note=""):
    global _shown
    content = []
    for t, b in shots:
        content.append({"type": "text", "text": f"frame at {t}s"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b}})
    # One line from the shop about the job turns guesswork into naming: knowing the part is a spring lock is
    # the difference between "a rusty metal fitting" and "the broken spring lock, cut free of the rail".
    ctx = (f"\n\nWHAT THE SHOP SAYS THIS JOB IS: {note}\nUse it to name parts correctly and to judge which "
           f"stage a frame belongs to. Do not describe anything you cannot see in the frames.\n" if note else "")
    content.append({"type": "text", "text": f"The clip is {dur:.1f} seconds long.{ctx}\n\n{PROMPT}"})
    body = json.dumps({"model": MODEL, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            if not _shown:
                u = data.get("usage", {})
                log(f"   (described by {data.get('model')}, {u.get('input_tokens')} in / "
                    f"{u.get('output_tokens')} out tokens for this clip)")
                _shown = True
            txt = "".join(p.get("text", "") for p in data.get("content", []))
            a, b = txt.find("{"), txt.rfind("}")
            if a < 0 or b < 0:
                kinds = [p.get("type") for p in data.get("content", [])]
                raise ValueError(f"no JSON in reply (stop={data.get('stop_reason')}, "
                                 f"blocks={kinds}, text={txt[:300]!r})")
            return json.loads(txt[a:b + 1])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


def clean_segments(raw, dur):
    """Keep segments inside the clip, in order, each at least a second long."""
    out = []
    for s in raw if isinstance(raw, list) else []:
        try:
            a = max(0.0, float(s.get("from", 0))); b = min(dur, float(s.get("to", dur)))
        except Exception:
            continue
        if b - a < 1.0: continue
        shows = str(s.get("shows", "")).strip()[:200]
        if not shows: continue
        out.append({"from": round(a, 1), "to": round(b, 1), "shows": shows,
                    "stage": str(s.get("stage", "other")).lower()[:10]})
    out.sort(key=lambda s: s["from"])
    return out[:6]


def sig(path):
    st = os.stat(path); return f"{st.st_size}|{int(st.st_mtime)}"


def needs_description(rec, name, note=""):
    """True when this clip has no usable description for the file as it is on disk right now. A note that was
    not there last time also counts: the same frames described with the job in mind come back different."""
    try:
        return (rec.get("desc_sig") != sig(build.src(name)) or not rec.get("segments")
                or (note and rec.get("desc_note", "") != note))
    except Exception:
        return False


def describe(names, L, api_key, log=print, force=False, note=""):
    """Describe these clips into L['clips']; returns how many were described. Saves as it goes."""
    C = L["clips"]
    todo = [n for n in names if n in C and n in build.FILES and (force or needs_description(C[n], n, note))]
    if not todo: return 0
    log(f"describing {len(todo)} clip(s) with {MODEL}…")
    done = 0
    for i, n in enumerate(todo, 1):
        try:
            shots, dur = frames(build.src(n))
            if not shots:
                log(f"  {i}/{len(todo)} {n}: could not read frames"); continue
            r = ask(shots, dur, api_key, log=log, note=note)
            segs = clean_segments(r.get("segments"), dur)
            C[n]["desc"] = str(r.get("desc", ""))[:400]
            C[n]["kw"] = [str(k).lower() for k in r.get("kw", [])][:8]
            C[n]["stage"] = str(r.get("stage", "other")).lower()
            C[n]["subject"] = str(r.get("subject", ""))[:60]
            C[n]["segments"] = segs or [{"from": 0.0, "to": round(dur, 1),
                                         "shows": C[n]["desc"], "stage": C[n]["stage"]}]
            C[n]["desc_sig"] = sig(build.src(n))
            C[n]["desc_note"] = note
            done += 1
            log(f"  {i}/{len(todo)} {n}: {len(C[n]['segments'])} segment(s)")
            for s in C[n]["segments"]:
                log(f"      {s['from']:5.1f}-{s['to']:<5.1f} [{s['stage']}] {s['shows']}")
            if done % 10 == 0: autoplan.save_lib(L)      # checkpoint: a crash never loses the batch
        except Exception as e:
            log(f"  {i}/{len(todo)} {n}: FAILED {e}")
    autoplan.save_lib(L)
    return done


def main():
    os.chdir(HERE)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    prefix = (args[0] if args else "").lower()

    L = autoplan.lib(); autoplan.refresh_footage()
    C = L["clips"]
    names = [n for n in sorted(C) if n.lower().startswith(prefix) and n in build.FILES]
    if not names: sys.exit("no clips found" + (f" starting with '{prefix}'" if prefix else ""))

    if "--show" in flags:
        for n in names:
            r = C[n]
            print(f"\n{n}  [{r.get('stage','?')}] {r.get('subject','')}")
            if r.get("desc"): print(f"  {r['desc']}")
            for s in r.get("segments", []):
                print(f"      {s['from']:5.1f}-{s['to']:<5.1f} [{s['stage']}] {s['shows']}")
            if not r.get("desc"): print("  (no description)")
        return

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key: sys.exit('no API key. In PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."')
    note = ""
    if "--note" in sys.argv:
        i = sys.argv.index("--note")
        if i + 1 < len(sys.argv): note = sys.argv[i + 1]
    n = describe(names, L, key, force="--force" in flags, note=note)
    print(f"\ndescribed {n} clip(s); library.json saved")


if __name__ == "__main__":
    main()
