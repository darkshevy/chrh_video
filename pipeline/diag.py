# Diagnostic: are these clips usable, and where do they sit in the pool?
# Run from the project folder:   python pipeline\diag.py <name prefix> [script words ...]
#   python pipeline\diag.py roofinstall
#   python pipeline\diag.py roofinstall roof panel seams weld sealed
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import autoplan, build, picker

PREFIX = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
WORDS = sys.argv[2:] or "crack weld welding steel plates gussets reinforce structural frame deck".split()

L = autoplan.apply_lib()
autoplan.refresh_footage()

print("picker module file:", picker.__file__)
print("has MAX_POOL (new picker):", hasattr(picker, "MAX_POOL"))
print("has USE_TIERS (new picker):", hasattr(picker, "USE_TIERS"))
print()

names = sorted(n for n in L["clips"] if n.lower().startswith(PREFIX)) if PREFIX else []
if PREFIX and not names:
    print(f"!! no records starting with '{PREFIX}' in library.json — did you run `chrh.py scan`?")
if not PREFIX:
    print("(no prefix given — showing pool order only; pass a prefix to inspect clips)")
print()

for n in names:
    rec = L["clips"][n]
    line = [n]
    line.append("enabled" if rec.get("enabled") else "DISABLED(" + rec.get("reason", "") + ")")
    line.append("cats=" + ",".join(rec.get("cats", [])) or "cats=-")
    line.append("manual" if rec.get("manual") else "auto")
    line.append("share" if "share" in rec else "no-share")

    if n not in build.FILES:
        line.append("!! FILE NOT FOUND IN footage/")
        print(" | ".join(line)); continue

    w, h = build.dims(n)
    line.append(f"{w}x{h}")
    line.append("letterboxed" if build.fit_mode(n) else "full-bleed")

    try:
        d, win = picker.windows(n)
    except Exception as e:
        line.append(f"!! liveness failed: {e}")
        print(" | ".join(line)); continue

    if not win:
        line.append("!! clip too short, no 1-s windows")
        print(" | ".join(line)); continue

    sharps = [s for (_, _, s) in win]
    motions = [m for (_, m, _) in win]
    drone = picker.is_drone(n)
    mlim = picker.motion_ceiling(n, 20 if drone else 35)
    th = picker.sharp_floor(n, 700)
    good = [picker.ok_window(m, s, th, mlim) for (_, m, s) in win]
    ok = sum(good)
    # The count alone hides the thing that actually decides a build: a cut needs one UNBROKEN stretch, so
    # twenty good seconds scattered in half-second islands carry no 3-second shot at all.
    run = best_run = 0
    for g in good:
        run = run + 0.5 if g else 0
        best_run = max(best_run, run)
    line.append(f"dur={d:.1f}s win={len(win)}")
    line.append(f"sharp min/med/max={min(sharps):.0f}/{sorted(sharps)[len(sharps)//2]:.0f}/{max(sharps):.0f}")
    line.append(f"motion max={max(motions):.0f} (base limit {mlim})")
    line.append(f"PASS={ok}/{len(win)} longest run={best_run:.1f}s")
    print(" | ".join(line))

print()
print("--- pool order for words:", " ".join(WORDS), "---")
pool = autoplan.pool_for(WORDS, L, 1, 10)
print("pool size:", len(pool))
for i, p in enumerate(pool[:20]):
    mark = "  <<<" if PREFIX and p.lower().startswith(PREFIX) else ""
    print(f"  {i:2d} {p}{mark}")
if PREFIX:
    fr = [i for i, p in enumerate(pool) if p.lower().startswith(PREFIX)]
    print(f"'{PREFIX}' positions in pool:", fr if fr else "NOT IN THIS POOL (wrong tags for these words?)")
print("MAX_POOL cutoff:", getattr(picker, "MAX_POOL", "n/a"))
