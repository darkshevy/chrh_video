# Build one video with the shots in an order YOU choose, instead of letting the picker match clips to words.
# Needed for a project story: the automatic editor has no idea that damage comes before the repair.
#
# Run from the project folder:
#   python pipeline\seq.py scripts\topics_1027.txt upperdeck 4 5 3 6 1 2 8 11 12 13 7 9
#
# After the script file and the key, list the clips in the order they should appear. A name can be partial
# ("4" matches trailerrepair4.mp4) as long as it matches exactly one clip. Fewer clips than cuts is fine —
# they are spread evenly across the video, so each clip holds for a shot or two before the next one.
# The cut points still come from the voice-over, so the picture still changes on the words.
import os, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()
sys.path.insert(0, HERE)
os.chdir(HERE)
import shutil
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

import autoplan, align, build, picker, plan

if len(sys.argv) < 4:
    sys.exit("usage: python pipeline\\seq.py SCRIPTS.txt KEY clip1 clip2 clip3 ...")

spath = sys.argv[1]
spath = spath if os.path.isabs(spath) else os.path.join(START, spath)
key = sys.argv[2].lower()
wanted = sys.argv[3:]

vids = [v for v in autoplan.parse_batch(open(spath, encoding="utf-8").read()) if v["key"] == key]
if not vids: sys.exit(f"'{key}' not found in {sys.argv[1]}")

autoplan.register(vids)
autoplan.load_all_batches()
L = autoplan.apply_lib()
autoplan.refresh_footage()

# resolve the names the operator typed into real files
C = L["clips"]
order = []
for name in wanted:
    hits = [n for n in C if n == name] or [n for n in C if name.lower() in n.lower()]
    hits = [n for n in hits if n in build.FILES]
    if len(hits) != 1:
        sys.exit(f"'{name}' matches {len(hits)} clips" + (f": {', '.join(hits[:5])}" if hits else ""))
    order.append(hits[0])
print("order:", " -> ".join(order))

build.A[key] = align.align_keys([key], log=print)[key]

# cut points come from the voice-over, exactly as in a normal build
ph = autoplan.phrases(key)
slots = [(None if i == 0 else a, [], None) for i, (a, b) in enumerate(ph)]
slots = picker.split_long(key, slots)
n = len(slots)
# The last cut carries the four-second end card, so it is much longer than the rest. If the clip that lands
# there is too short, the whole build fails — quietly move the longest clip that fits to the end instead.
dur = {}
for f in order:
    try: dur[f] = picker.windows(f)[0]
    except Exception: dur[f] = 0
last_w = slots[-1][0]
need_last = (build.PRE + build.voDur(key) + build.END) - (0 if last_w is None else build.A[key][last_w][1] + build.PRE - 0.06)
if dur.get(order[-1], 0) < need_last + 0.3:
    fits = [f for f in order if dur.get(f, 0) >= need_last + 0.3]
    if fits:
        pick = max(fits, key=lambda f: dur[f])
        order = [f for f in order if f != pick] + [pick]
        print(f"last cut needs {need_last:.1f}s: moved {pick} ({dur[pick]:.1f}s) to the end")
    else:
        print(f"warning: last cut needs {need_last:.1f}s and no clip is that long")

print(f"{n} cuts for {len(order)} clip(s)")

# spread the clips evenly over the cuts, in the given order
slots = [(w, [order[i * len(order) // n]], z) for i, (w, _, z) in enumerate(slots)]

P, rep = picker.plan_video(key, slots, {}, collections.defaultdict(list))
print("\n".join(rep))
miss = [r for r in rep if "NO CANDIDATE" in r]
if miss:
    sys.exit(f"\n{len(miss)} cut(s) found no usable window in the clip assigned to them.\n"
             f"Run `python pipeline\\tune.py free <prefix>` to drop the quality thresholds, or give a different order.")

plan.P[key] = P
path, d = autoplan.batch_of(key)
if d:
    d["videos"][key]["plan"] = [list(x) for x in P]
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

out = autoplan.render_key(key, log=print)
print("done:", out)
