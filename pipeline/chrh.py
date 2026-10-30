# Command line for the whole pipeline — for coding agents (Codex, Claude Code) and people without the GUI.
# Run from the project folder:   python pipeline/chrh.py <command> ...
#   scan                         find new clips in footage/ and auto-tag them (topics, dull seconds, overlays)
#   check  SCRIPTS.txt           parse scripts, check text + voiceover files, print problems
#   build  SCRIPTS.txt [keys..]  align -> pick shots -> render; avoids the previous batch's footage by default
#          --allow-repeat        do not forbid the previous batch's seconds
#   sheet  VIDEO.mp4             contact sheet (24 frames with timecodes) next to the video
#   blur   KEY [KEY..]           face blur for approved videos -> output/CHRH_<Key>_blur.mp4
#   status                       what is where: clips, batches, last outputs
import os, sys, glob, json
HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()                       # file arguments are relative to where the command was typed
sys.path.insert(0, HERE)
os.chdir(HERE)
def _abs(p): return p if os.path.isabs(p) else os.path.join(START, p)
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import shutil
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

def _vids(path):
    import autoplan
    v = autoplan.parse_batch(open(_abs(path), encoding="utf-8").read())
    if not v: sys.exit(f"no scripts found in {path} (header line: === key | TITLE | SUB | Track)")
    return v

def cmd_scan(a):
    import autoplan
    n = autoplan.rescan(log=print); print(f"tagged {n} new clip(s)")

def cmd_check(a):
    import autoplan
    vids = _vids(a[0]); bad = 0
    for k, iss in autoplan.check(vids).items():
        errs = [m for l, m in iss if l == "err"]; bad += len(errs)
        print(f"{k:16s} {'ERROR: ' + '; '.join(errs) if errs else 'ok'}" +
              "".join(f"\n{'':16s} warn: {m}" for l, m in iss if l == "warn"))
    sys.exit(1 if bad else 0)

def previous_batch_keys(exclude):
    """Keys of the newest earlier batch in scripts/batches (so today's videos don't repeat its footage)."""
    import autoplan
    files = sorted(glob.glob(os.path.join(autoplan.BATCHES, "20*.json")))
    for p in reversed(files):
        keys = [k for k in json.load(open(p, encoding="utf-8"))["videos"] if k not in exclude]
        if keys: return os.path.basename(p), keys
    return None, []

def cmd_build(a):
    import autoplan, align, build
    allow = "--allow-repeat" in a; a = [x for x in a if not x.startswith("--")]
    vids = _vids(a[0]); want = set(a[1:]) or {v["key"] for v in vids}
    vids = [v for v in vids if v["key"] in want]
    errs = {k: [m for l, m in i if l == "err"] for k, i in autoplan.check(vids).items()}
    errs = {k: e for k, e in errs.items() if e}
    if errs: sys.exit("fix first:\n" + "\n".join(f"  {k}: {'; '.join(e)}" for k, e in errs.items()))
    keys = [v["key"] for v in vids]
    autoplan.register(vids); autoplan.load_all_batches(); autoplan.apply_lib()
    prev, hard = (None, []) if allow else previous_batch_keys(set(keys))
    if prev: print(f"footage of the previous batch {prev} ({len(hard)} videos) is forbidden")
    for k in keys:
        build.A[k] = align.align_keys([k], log=print)[k]
    autoplan.plan_keys(keys, log=print, hard_keys=hard)
    for k in keys: autoplan.render_key(k, log=print)
    print("done. videos + contact sheets in output/")

def cmd_sheet(a):
    import contact
    for v in map(_abs, a): print(contact.sheet(v, os.path.dirname(v), 6, 4)[0])

def cmd_blur(a):
    import autoplan
    autoplan.load_all_batches(); autoplan.apply_lib()
    for k in a: autoplan.blur_key(k, log=print)

def cmd_status(a):
    import autoplan, paths
    L = autoplan.lib(); files = autoplan.refresh_footage(); C = L.get("clips", {})
    print(f"clips in footage/: {len(files)} | enabled: {sum(1 for r in C.values() if r.get('enabled'))} | "
          f"not tagged yet: {sum(1 for f in files if f not in C)}")
    for p in sorted(glob.glob(os.path.join(autoplan.BATCHES, "20*.json")))[-3:]:
        print("batch", os.path.basename(p), list(json.load(open(p, encoding="utf-8"))["videos"]))
    outs = sorted(glob.glob(os.path.join(paths.OUT, "*.mp4")), key=os.path.getmtime)[-10:]
    print("latest outputs:", *[os.path.basename(o) for o in outs], sep="\n  ")

CMDS = {"scan": cmd_scan, "check": cmd_check, "build": cmd_build, "sheet": cmd_sheet, "blur": cmd_blur, "status": cmd_status}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS: sys.exit(__doc__ if __doc__ else open(__file__, encoding="utf-8").read().split("import os")[0])
    CMDS[sys.argv[1]](sys.argv[2:])
