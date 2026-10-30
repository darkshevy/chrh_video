# Write the voice-over scripts from the footage itself.
#
# Every clip is described in plain English (describe.py), so the writer can see what was actually filmed instead
# of being told. For a project story that means the script follows the real job — the crack, the plate, the
# coating — and never promises a shot that does not exist.
#
# Length is aimed at 45 seconds and capped by the footage. A script needs roughly one cut every five words and
# about two seconds of distinct footage per cut, so twenty seconds of usable material cannot carry a hundred
# and twenty words without showing the same shots again. When the material is the shorter of the two, the
# script comes out shorter and says so — a dragged-out video is worse than a short one.
#
#   python pipeline\script.py --only trailerrepair
#         one script about that project, written from its clips
#   python pipeline\script.py --only trailerrepair --note "8-car hauler, upper deck reinforcement"
#         same, with a line of context only you know
#   python pipeline\script.py --count 10
#         the day's batch: nine topics plus the Cottrell one, from the facts and the whole library
#   --seconds 45                      how long the finished video should run (default 45)
#   --out scripts\topics_1028.txt     where to write (default: scripts\topics_MMDD.txt)
#   --track "Another Day"             force the music track
#
# Read the result before building. The facts come from AGENTS.md; anything not in there is not invented.
import os, sys, json, time, glob, datetime, re, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
START = os.getcwd()
sys.path.insert(0, HERE)
os.chdir(HERE)

import autoplan, build, picker

MODEL = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"

RULES = """Each script:
- one paragraph, natural spoken English, short sentences, no line breaks inside it.
- First sentence is a hook: the customer's problem, or a question.
- Around the middle, a second hook sentence (a question works best) with the marker [HOOK 2] right before it.
- Shape: problem -> what the shop did, in the order it happened -> result -> a short call to action.
- A different call to action in every script. The phone number is on screen: say "call the number on screen"
  or "bring it by the shop", never read digits.
- NO DIGITS ANYWHERE. Write numbers as words: "six-month", "seventeen and three sixteenths", "two thousand one".
- Never invent prices, measurements, causes, specs or promises. Use only the facts given below and what the
  footage descriptions actually show.

Output format, exactly this and nothing else, one block per script:

=== key | TITLE | SUBTITLE | Track
<the paragraph>

key: lowercase latin letters only, unique, not in the used list (it becomes the file name key.mp3).
TITLE: 2-4 words, max 22 characters, capitals. SUBTITLE: max 30 characters, capitals.
Track: one of Thunder, Hollywood waves, Kama Sutra, Fields of space, Another Day, Symphony one, Hyde and seek."""


def ask(system, payload, key):
    body = json.dumps({"model": MODEL, "max_tokens": 4000, "system": system,
                       "messages": [{"role": "user", "content": payload}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            u = data.get("usage", {})
            print(f"(written by {data.get('model')}, {u.get('input_tokens')} in / {u.get('output_tokens')} out)")
            return "".join(p.get("text", "") for p in data.get("content", []))
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


def usable_seconds(f, rec):
    """Seconds of this clip that are sharp, steady and not empty — the same test the renderer applies."""
    d, w = picker.windows(f)
    th = picker.sharp_floor(f, 700)
    mlim = picker.motion_ceiling(f, 20 if picker.is_drone(f) else 35)
    bad = [tuple(r) for r in rec.get("dull", [])]
    return sum(0.5 for (t, m, sh) in w
               if picker.ok_window(m, sh, th, mlim) and not picker.overlap(t, t + 1.0, bad))


def used_keys():
    out = set()
    for p in glob.glob(os.path.join(ROOT, "scripts", "topics_*.txt")):
        try: txt = open(p, encoding="utf-8").read()
        except Exception: continue
        out |= set(re.findall(r"^===\s*([A-Za-z][A-Za-z0-9_]*)", txt, re.M))
    return sorted(out)


def facts():
    for name in ("AGENTS.md", "CLAUDE.md"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            txt = open(p, encoding="utf-8").read()
            a = txt.find("## Verified facts")
            if a < 0: continue
            b = txt.find("\n## ", a + 5)
            return txt[a:b if b > 0 else len(txt)]
    return ""


flags = [a for a in sys.argv[1:] if a.startswith("--")]


def opt(name, default=""):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"): return sys.argv[i + 1]
    return default


only = opt("--only").lower()
note = opt("--note")
track = opt("--track")
count = int(opt("--count", "1") or 1)
try: secs = float(opt("--seconds", "45") or 45)
except ValueError: sys.exit("--seconds wants a number, e.g. --seconds 45")
outp = opt("--out") or os.path.join(ROOT, "scripts", f"topics_{datetime.date.today():%m%d}.txt")
outp = outp if os.path.isabs(outp) else os.path.join(START, outp)

apikey = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not apikey: sys.exit('no API key. In PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."')

L = autoplan.apply_lib(); autoplan.refresh_footage()
C = L["clips"]
names = [n for n in sorted(C) if C[n].get("enabled") and n in build.FILES
         and (not only or n.lower().startswith(only)) and C[n].get("segments")]
if not names:
    sys.exit(("no described clips" + (f" starting with '{only}'" if only else "")) +
             " — run `python pipeline\\describe.py` first")

# Footage goes to the writer in the order of the work (by the stage judged when the project was described),
# not in file-name order: a writer reading "finished lock" first and "broken lock" fourth tells the story in
# that order, and then the planner has no right footage for the first sentences.
STAGES = {"damage": 0, "strip": 1, "fit": 2, "weld": 3, "finish": 4, "done": 5}
def _first_stage(n):
    st = [STAGES.get(s.get("stage"), 9) for s in C[n].get("segments", [])]
    return min(st) if st else 9
names.sort(key=lambda n: (_first_stage(n), n))
story = (L.get("stories") or {}).get(only, "") if only else ""

lines, total = [], 0.0
for n in names:
    rec = C[n]
    # not `secs`: that is the length asked for, and reusing the name here silently replaced it with the
    # last clip's usable seconds — a 45 s request came out as a 21 s script
    try: u = usable_seconds(n, rec)
    except Exception: u = 0.0
    total += u
    lines.append(f"  {n} ({u:.0f}s usable):")
    for s in rec["segments"]:
        lines.append(f"      {s['from']:.1f}-{s['to']:.1f}s [{s.get('stage','other')}] {s['shows']}")

# Two numbers decide the length, and the smaller one wins.
#   want: the length asked for, in words. 2.6 words a second is what this voice reads at on these videos.
#   cap:  what the material can carry without showing the same seconds twice — a cut every ~5 words and
#         ~2s of distinct footage per cut.
WPS = 2.6
want = int(secs * WPS)
cap = int(total * 2.2)
fit = int(max(55, min(want, cap)))

system = ("You write voice-over scripts for 45-second vertical promo videos of Car Hauler Repair Houston, "
          "a shop that works only on car carriers (car hauler trailers). You are shown what was actually "
          "filmed, described shot by shot, and the verified facts about the shop.\n\n" + RULES)

if count > 1:
    task = (f"Write {count} scripts: {count - 1} on different topics and one about the shop being a Cottrell "
            f"Authorized Warranty Repair Center (put it last, its key must contain 'cottrell'). "
            f"These are general videos about the service, not the story of one trailer, so write about what "
            f"the shop does and let the footage illustrate it. Aim for 115 to 125 words each.")
else:
    task = (f"Write ONE script telling the story of this single job, in the order the work actually happened, "
            f"using only what the footage shows. Write about {fit} words, which is roughly "
            f"{fit / WPS:.0f} seconds read aloud" +
            (f" — the length asked for." if fit >= want else
             f". That is shorter than the {secs:.0f} seconds asked for, because the material only holds "
             f"{total:.0f} seconds of usable footage and a longer script would have to repeat shots.") +
            " Do not pad it to reach the count: say the job and stop. Every sentence must earn its place.")
    if note: task += f"\n\nWhat the shop said about this job: {note}"
    if story: task += (f"\n\nHow the job went, judged from all the footage side by side: {story}\n"
                       "Follow this order. Every sentence about the work must be something a segment below "
                       "shows — if no segment shows it, leave it out.")

payload = (task + "\n\nVERIFIED FACTS (use nothing outside these):\n" + facts() +
           "\n\nKEYS ALREADY USED (do not reuse): " + ", ".join(used_keys()) +
           (f"\n\nUse this music track: {track}" if track else "") +
           "\n\nFOOTAGE AVAILABLE, clip by clip:\n" + "\n".join(lines))

# A clip with the quality gate lifted (tune.py free) passes every test, so "usable" would just be its length.
loose = [n for n in names if C[n].get("sharp") or C[n].get("motion")]
if loose:
    print(f"note: {len(loose)} clip(s) have the quality gate lifted, so the usable figure is their full length;"
          f" run `python pipeline\\tune.py gate {only or '<prefix>'}` for the real number")

if count == 1:
    why = "as asked" if fit >= want else f"the footage is the limit, not the {secs:.0f}s asked for"
    print(f"{len(names)} clip(s), {total:.0f}s usable footage -> {fit} words, about {fit / WPS:.0f}s ({why})")
else:
    print(f"{len(names)} clip(s), {total:.0f}s usable footage")


def blocks(t):
    """-> [(key, word count)] for every script in the reply."""
    out = []
    for m in re.finditer(r"^===\s*([A-Za-z][A-Za-z0-9_]*)[^\n]*\n(.+?)(?=\n===|\Z)", t, re.M | re.S):
        out.append((m.group(1), len(autoplan.clean_text(m.group(2)).split())))
    return out


def clean(t):
    a = t.find("===")
    if a < 0: return ""
    t = t[a:].strip()
    return "\n".join(l for l in t.split("\n") if not l.strip().startswith("```")).strip() + "\n"


lo, hi = (105, 130) if count > 1 else (int(fit * 0.90), int(fit * 1.08))
txt = clean(ask(system, payload, apikey))
if not txt: sys.exit("the reply had no script block")

# Length is not a detail here: words decide how many cuts there are, and cuts decide whether the footage has
# to repeat itself. So check it and send it back rather than accepting whatever came out.
for attempt in range(2):
    bad = [(k, n) for k, n in blocks(txt) if not lo <= n <= hi]
    if not bad: break
    print("length off: " + ", ".join(f"{k} {n} words" for k, n in bad) + f" (want {lo}-{hi})")
    fix = (payload + "\n\nYOUR PREVIOUS ANSWER WAS:\n" + txt +
           "\n\nThese scripts are the wrong length: " +
           "; ".join(f"{k} came out at {n} words" for k, n in bad) +
           f". Every script must be between {lo} and {hi} words. Rewrite ALL of them, same format, "
           f"keeping what works and cutting or adding sentences to land in range. Count as you write.")
    again = clean(ask(system, fix, apikey))
    if again: txt = again
bad = [(k, n) for k, n in blocks(txt) if not lo <= n <= hi]
if bad: print("still off after two tries: " + ", ".join(f"{k} {n}" for k, n in bad) + " — edit by hand")

os.makedirs(os.path.dirname(outp), exist_ok=True)
new_txt = txt
if os.path.exists(outp):
    old = open(outp, encoding="utf-8").read().rstrip()
    txt = old + "\n\n" + txt
    print(f"appending to the existing {os.path.basename(outp)}")
open(outp, "w", encoding="utf-8").write(txt)

# only what was just written: the file may already hold earlier scripts of the day
print("\n" + new_txt)
print(f"written to {outp}")
for k, n in blocks(new_txt):
    print(f"  {k}: {n} words, voice-over goes to voiceover\\{k}.mp3")
