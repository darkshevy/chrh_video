# Temporarily restrict the library to one project, so a video is cut only from that trailer's footage.
# The automatic editor picks from topic pools across the WHOLE library, so a project story needs this.
#
#   python pipeline\only.py trailerrepair     disable every clip whose name lacks that prefix
#   python pipeline\only.py restore           put every clip back the way it was
#
# The previous enabled/disabled state is saved to work\only_backup.json, so `restore` is exact.
# Clips disabled for a real reason (outdoor painting, someone else's edit) stay disabled on restore.
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB = os.path.join(HERE, "library.json")
BAK = os.path.join(ROOT, "work", "only_backup.json")

if len(sys.argv) < 2:
    sys.exit(__doc__.strip() if __doc__ else "usage: only.py <prefix> | restore")

L = json.load(open(LIB, encoding="utf-8"))
C = L["clips"]
arg = sys.argv[1]

if arg == "restore":
    if not os.path.exists(BAK):
        sys.exit("nothing to restore: work\\only_backup.json not found")
    state = json.load(open(BAK, encoding="utf-8"))
    back = 0
    for n, rec in state.items():
        if n in C:
            C[n]["enabled"] = rec["enabled"]
            C[n]["reason"] = rec["reason"]
            back += 1
    json.dump(L, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.remove(BAK)
    print(f"restored {back} clip(s) | enabled now: {sum(1 for r in C.values() if r.get('enabled'))}")
    sys.exit(0)

if os.path.exists(BAK):
    sys.exit("a restriction is already active — run `python pipeline\\only.py restore` first")

prefix = arg.lower()
keep = [n for n in C if n.lower().startswith(prefix)]
if not keep:
    sys.exit(f"no clips start with '{prefix}'")

state, off = {}, 0
for n, rec in C.items():
    state[n] = {"enabled": rec.get("enabled", True), "reason": rec.get("reason", "")}
    if not n.lower().startswith(prefix) and rec.get("enabled"):
        rec["enabled"] = False
        rec["reason"] = "temporarily off: single-project build"
        off += 1

os.makedirs(os.path.dirname(BAK), exist_ok=True)
json.dump(state, open(BAK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(L, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

live = [n for n in keep if C[n].get("enabled")]
print(f"turned off {off} clip(s); {len(live)} left enabled:")
for n in sorted(live): print("   ", n)
print("\nbuild now, then run:  python pipeline\\only.py restore")
