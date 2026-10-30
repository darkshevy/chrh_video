# Order a project's clips by STAGE OF WORK, automatically, and optionally build the video in that order.
#
# The normal picker knows eleven broad topics (weld, close, rust …). Inside one project almost every clip lands
# in the same one or two, so it has nothing left to choose by and the shots come out in an arbitrary order.
# This asks CLIP a different question — not "what is in the frame" but "how far along the repair is it" —
# and sorts the clips from damage to finished result.
#
#   python pipeline\stage.py trailerrepair
#         show the detected order and each clip's stage, change nothing
#
#   python pipeline\stage.py trailerrepair scripts\topics_1027.txt upperdeck
#         same, then build that video with the shots in that order
#
# The stage descriptions live in STAGES below — edit them for a different kind of job (paint, decking …).
import os, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()
sys.path.insert(0, HERE)
os.chdir(HERE)
import shutil
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

import numpy as np
import autoplan, autotag, build, picker, plan

# Stage order IS the order on screen: damage first, finished last.
STAGES = [
    ("damage", ["a cracked steel beam on a trailer",
                "rusted and damaged steel on a trailer frame",
                "a broken bracket and torn metal",
                "a crack running through a steel support"]),
    ("strip",  ["an angle grinder throwing sparks on steel",
                "cutting out a damaged section of steel",
                "grinding rust off a steel beam",
                "a wire brush cleaning bare metal"]),
    ("weld",   ["a welder welding steel with a bright arc",
                "arc welding a steel plate onto a beam",
                "molten weld bead being laid on steel",
                "a welding torch with sparks under a trailer"]),
    ("build",  ["a new steel crossmember bolted across a trailer deck",
                "a fresh reinforcing plate welded over a beam",
                "new steel parts fitted onto a trailer frame",
                "clean new weld seams on a reinforced joint"]),
    ("done",   ["a freshly painted steel beam on a trailer",
                "a finished repaired car hauler deck",
                "a clean complete trailer standing in a workshop",
                "a finished trailer ready to leave the shop"]),
]

CACHE = os.path.join(os.path.dirname(HERE), "work", "stage_prompts.json")


def stage_vectors():
    """Text embeddings for the stage descriptions, computed once and cached in work\\stage_prompts.json."""
    want = {name: texts for name, texts in STAGES}
    if os.path.exists(CACHE):
        got = json.load(open(CACHE, encoding="utf-8"))
        if got.get("_texts") == {k: v for k, v in want.items()}:
            return {k: np.array(v, np.float32) for k, v in got.items() if not k.startswith("_")}
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError:
        sys.exit("this needs the text half of CLIP once:  python -m pip install --user tokenizers")
    tpath = os.path.join(autotag.MODELS, "clip_text_q.onnx")
    kpath = os.path.join(autotag.MODELS, "clip_tokenizer.json")
    for p in (tpath, kpath):
        if not os.path.exists(p): sys.exit(f"missing model file: {p}")
    tok = Tokenizer.from_file(kpath)
    sess = ort.InferenceSession(tpath, providers=["CPUExecutionProvider"])
    out = {}
    for name, texts in STAGES:
        embs = []
        for t in texts:
            e = sess.run(None, {"input_ids": np.array([tok.encode(t).ids], np.int64)})[0][0]
            embs.append((e / np.linalg.norm(e)).tolist())
        out[name] = embs
    out["_texts"] = {k: v for k, v in want.items()}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w", encoding="utf-8"))
    print("stage descriptions embedded and cached")
    return {k: np.array(v, np.float32) for k, v in out.items() if not k.startswith("_")}


def stage_score(name, rec, P):
    """Average stage of a clip, 0 (damage) to 4 (done). Uses the CLIP embeddings autotag already cached."""
    t, E = autotag.embed(build.src(name))
    if len(E) == 0: return None, None
    keep = [i for i, ti in enumerate(t)
            if not any(a <= float(ti) < b for a, b in rec.get("dull", []))]
    if keep: E = E[keep]
    names = [n for n, _ in STAGES]
    s = np.stack([(E @ P[n].T).max(axis=1) for n in names], axis=1) * 100.0   # seconds x stages
    p = np.exp(s - s.max(axis=1, keepdims=True)); p /= p.sum(axis=1, keepdims=True)
    per_second = p.mean(axis=0)
    return float((per_second * np.arange(len(names))).sum()), names[int(per_second.argmax())]


prefix = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
if not prefix:
    sys.exit("usage: python pipeline\\stage.py PREFIX [SCRIPTS.txt KEY]")

L = autoplan.apply_lib()
autoplan.refresh_footage()
C = L["clips"]
names = [n for n in C if n.lower().startswith(prefix) and n in build.FILES and C[n].get("enabled")]
if not names: sys.exit(f"no enabled clips start with '{prefix}'")

P = stage_vectors()
scored = []
for n in sorted(names):
    sc, lab = stage_score(n, C[n], P)
    if sc is None:
        print(f"{n}: could not be read, skipped"); continue
    scored.append((sc, lab, n))
scored.sort()

print(f"\n{len(scored)} clip(s), damage first:")
for sc, lab, n in scored:
    print(f"  {sc:4.2f}  {lab:7s}  {n}")
order = [n for _, _, n in scored]

if len(sys.argv) < 4:
    print("\nto build with this order, add the script file and the key:")
    print(f"  python pipeline\\stage.py {prefix} scripts\\topics_MMDD.txt <key>")
    sys.exit(0)

# ------------------------------------------------------------------ build in that order
import align
spath = sys.argv[2]
spath = spath if os.path.isabs(spath) else os.path.join(START, spath)
key = sys.argv[3].lower()

vids = [v for v in autoplan.parse_batch(open(spath, encoding="utf-8").read()) if v["key"] == key]
if not vids: sys.exit(f"'{key}' not found in {sys.argv[2]}")
autoplan.register(vids); autoplan.load_all_batches(); autoplan.apply_lib()

build.A[key] = align.align_keys([key], log=print)[key]
ph = autoplan.phrases(key)
slots = [(None if i == 0 else a, [], None) for i, (a, b) in enumerate(ph)]
slots = picker.split_long(key, slots)
n = len(slots)

# the final cut carries the end card and is the longest — give it a clip long enough to cover it
dur = {}
for f in order:
    try: dur[f] = picker.windows(f)[0]
    except Exception: dur[f] = 0
need_last = (build.PRE + build.voDur(key) + build.END) - (0 if slots[-1][0] is None else build.A[key][slots[-1][0]][1] + build.PRE - 0.06)
if dur.get(order[-1], 0) < need_last + 0.3:
    long_enough = [f for f in order if dur.get(f, 0) >= need_last + 0.3]
    if long_enough:
        pick = max(long_enough, key=lambda f: dur[f])
        order = [f for f in order if f != pick] + [pick]
        print(f"last cut needs {need_last:.1f}s, moved {pick} ({dur[pick]:.1f}s) to the end")

print(f"{n} cuts for {len(order)} clip(s)")
slots = [(w, [order[i * len(order) // n]], z) for i, (w, _, z) in enumerate(slots)]
Pl, rep = picker.plan_video(key, slots, {}, collections.defaultdict(list))
print("\n".join(rep))
if [r for r in rep if "NO CANDIDATE" in r]:
    sys.exit("\nsome cuts found no usable window. Run `python pipeline\\tune.py free " + prefix + "` and retry.")

plan.P[key] = Pl
path, d = autoplan.batch_of(key)
if d:
    d["videos"][key]["plan"] = [list(x) for x in Pl]
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done:", autoplan.render_key(key, log=print))
