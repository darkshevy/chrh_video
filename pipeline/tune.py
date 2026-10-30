# Set or clear a per-clip override in library.json.
#   "sharp"  = sharpness floor   (default 700; LOWER it to let a soft clip through)
#   "motion" = motion ceiling    (default 35 handheld / 20 drone; RAISE it for a sharp clip that pans)
#
# Run from the project folder:
#   python pipeline\tune.py motion trailerrepair11.mp4=80 trailerrepair12.mp4=85
#   python pipeline\tune.py motion trailerrepair11.mp4=          <- empty value removes the override
#   python pipeline\tune.py show                                 <- list every override currently set
#   python pipeline\tune.py on trailerrepair9                    <- switch a clip back on
#   python pipeline\tune.py off trailerrepair3                   <- switch a clip off
#   python pipeline\tune.py free trailerrepair                   <- use every clip of a project, no quality gate
#   python pipeline\tune.py gate trailerrepair                   <- undo `free`: normal thresholds again
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library.json")
L = json.load(open(LIB, encoding="utf-8"))
C = L.get("clips", {})

if len(sys.argv) < 2 or sys.argv[1] == "show":
    found = False
    for n, r in sorted(C.items()):
        ov = {k: r[k] for k in ("sharp", "motion") if r.get(k)}
        if ov:
            print(f"{n}: {ov}"); found = True
    if not found: print("no overrides set")
    sys.exit(0)

key = sys.argv[1]

if key in ("free", "gate"):
    # `free` turns off every quality check for one project: enable the clips and drop the sharpness and
    # motion thresholds to nothing. Soft or shaky footage then DOES reach the cut — that is the point, and
    # also the cost. `gate` puts the normal standards back.
    prefix = (sys.argv[2] if len(sys.argv) > 2 else "").lower()
    if not prefix: sys.exit("name the project prefix, e.g. `tune.py free trailerrepair`")
    hits = [n for n in C if n.lower().startswith(prefix)]
    if not hits: sys.exit(f"no clips start with '{prefix}'")
    for n in hits:
        if key == "free":
            C[n].update(enabled=True, reason="", manual=True, sharp=1, motion=9999)
        else:
            C[n].pop("sharp", None); C[n].pop("motion", None)
    json.dump(L, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    verb = "no quality gate" if key == "free" else "normal thresholds restored"
    print(f"{len(hits)} clip(s) starting with '{prefix}': {verb}")
    for n in sorted(hits): print("   ", n)
    sys.exit(0)

if key in ("on", "off"):
    want = key == "on"
    changed = 0
    for name in sys.argv[2:]:
        hits = [n for n in C if n == name] or [n for n in C if name.lower() in n.lower()]
        if len(hits) != 1:
            print(f"skipped: '{name}' matches {len(hits)} clips"); continue
        n = hits[0]
        C[n]["enabled"] = want
        C[n]["reason"] = "" if want else "switched off by hand"
        C[n]["manual"] = True          # a hand decision also teaches the auto-tagger
        print(f"{n}: {'enabled' if want else 'disabled'}"); changed += 1
    if changed:
        json.dump(L, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\nlibrary.json saved ({changed} change(s))")
    sys.exit(0)

if key not in ("sharp", "motion"):
    sys.exit("first argument must be 'sharp', 'motion', 'on', 'off' or 'show'")

changed = 0
for arg in sys.argv[2:]:
    if "=" not in arg:
        print(f"skipped (expected NAME=VALUE): {arg}"); continue
    name, val = arg.split("=", 1)
    # accept a partial name, as long as it matches exactly one clip
    hits = [n for n in C if n == name] or [n for n in C if name.lower() in n.lower()]
    if len(hits) != 1:
        print(f"skipped: '{name}' matches {len(hits)} clips" +
              (f" ({', '.join(hits[:4])}…)" if hits else " — run `chrh.py scan` first?")); continue
    n = hits[0]
    if val.strip() == "":
        if C[n].pop(key, None) is not None:
            print(f"{n}: {key} override removed"); changed += 1
        else:
            print(f"{n}: had no {key} override")
    else:
        C[n][key] = float(val) if "." in val else int(val)
        print(f"{n}: {key} = {C[n][key]}"); changed += 1

if changed:
    json.dump(L, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nlibrary.json saved ({changed} change(s))")
else:
    print("\nnothing changed")
