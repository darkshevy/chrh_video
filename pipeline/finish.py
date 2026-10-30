# Blur the faces on a finished video and say which file is the one to publish.
#
# Rule 7: nothing goes out with a recognisable face in it. Blurring is a second pass over the finished video,
# not part of the render, so it has always been a separate command that was easy to forget. This file makes it
# part of the build: plan_ai.py calls run() after every successful render, and this is also how to do it for
# videos that were built earlier.
#
#   python pipeline\finish.py scripts\topics_1027.txt     every video in that file
#   python pipeline\finish.py upperdeck rampwidth         these keys
#   --force     blur again even when the blurred file is already there
#
# What comes out:
#   output\CHRH_<Key>_blur.mp4   faces blurred  -> this is the file you publish
#   output\CHRH_<Key>.mp4        the plain render -> publish this one only when the pass found nothing to blur
#
# The pass never stops a batch. If it fails on one video, that video is reported as not cleared and the rest
# carry on, because a silent miss here is the one mistake that cannot be fixed after posting.
import os, sys, inspect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import autoplan


def outdir(hint=None):
    """Where the finished files land. Taken from a known path when there is one, probed otherwise."""
    if hint:
        d = os.path.dirname(os.path.abspath(hint))
        if os.path.isdir(d): return d
    try:
        import paths
        for n in ("OUT", "OUTPUT", "OUTDIR", "FINAL", "RENDER"):
            v = getattr(paths, n, None)
            if isinstance(v, str) and os.path.isdir(v): return v
    except Exception:
        pass
    for v in (os.path.join(ROOT, "output"), os.path.join(HERE, "output"), os.path.join(ROOT, "out")):
        if os.path.isdir(v): return v
    return os.path.join(ROOT, "output")


def outputs(key, d):
    """(plain renders, blurred versions) for this key, newest first. The file names carry a version suffix
    (CHRH_Upperdeck_v8.mp4), so match on the prefix rather than guessing the whole name."""
    k = f"chrh_{key}".lower()
    plain, blurred = [], []
    try:
        names = os.listdir(d)
    except OSError:
        return [], []
    for n in names:
        if not n.lower().endswith((".mp4", ".mov")): continue
        stem = os.path.splitext(n)[0].lower()
        if stem != k and not stem.startswith(k + "_"): continue
        (blurred if "blur" in stem else plain).append(os.path.join(d, n))
    newest = lambda L: sorted(L, key=lambda p: os.path.getmtime(p), reverse=True)
    return newest(plain), newest(blurred)


def people_in(key):
    """Clips used by this video that the library marks as showing people, or None when that cannot be read.
    Used only as a check: when the blur pass writes no file, this says whether that is because there was
    nothing to blur or because the pass quietly did nothing."""
    try:
        import plan
        used = {row[1] for row in (plan.P.get(key) or [])}
    except Exception:
        return None
    if not used: return None
    flagged = None
    try:
        L = autoplan.apply_lib()
        for src in (L.get("people"), getattr(autoplan, "PEOPLE", None), getattr(__import__("build"), "PEOPLE", None)):
            if isinstance(src, (list, set, tuple)):
                flagged = {str(x) for x in src}; break
    except Exception:
        return None
    if flagged is None: return None
    return used & flagged


def _blur(key, log):
    """Run this installation's blur step, whichever way it is spelled here."""
    fn = getattr(autoplan, "blur_key", None)
    if callable(fn):
        try:
            params = list(inspect.signature(fn).parameters.values())
        except (TypeError, ValueError):
            params = []
        args = [key]
        # a second positional with no default can only be the library dict
        if [p for p in params[1:] if p.default is inspect.Parameter.empty
                and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]:
            args.append(autoplan.apply_lib())
        kw = {"log": log} if any(p.name == "log" for p in params) else {}
        return fn(*args, **kw)
    # nothing to import: fall back to the command the package ships with
    import subprocess
    p = subprocess.run([sys.executable, os.path.join(HERE, "chrh.py"), "blur", key],
                       cwd=HERE, text=True, capture_output=True)
    if p.stdout: log(p.stdout.rstrip())
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "chrh.py blur failed").strip()[:300])
    return None


def run(key, log=print, force=False, hint=None):
    """Blur this video's faces. Returns the path of the file that is cleared for publishing, or None when the
    pass could not run — in which case nothing about this video is cleared."""
    d = outdir(hint)
    plain, blurred = outputs(key, d)
    if not plain and not blurred:
        log(f"{key}: no finished video in {os.path.basename(d)}\\ — nothing to blur")
        return None
    if blurred and not force:
        fresh = not plain or os.path.getmtime(blurred[0]) >= os.path.getmtime(plain[0])
        if fresh:
            log(f"{key}: already blurred -> {os.path.basename(blurred[0])}")
            return blurred[0]

    before = {p: os.path.getmtime(p) for p in blurred}
    log(f"{key}: blurring faces…")
    ret = _blur(key, log)

    _, after = outputs(key, d)
    made = [p for p in after if p not in before or os.path.getmtime(p) > before[p]]
    if made:
        log(f"{key}: publish {os.path.basename(made[0])}")
        return made[0]
    if isinstance(ret, str) and os.path.exists(ret):
        log(f"{key}: publish {os.path.basename(ret)}")
        return ret
    # No new file. Normally that means none of the clips used show people, so the plain render is already
    # clean — but it would also be what a pass that quietly did nothing looks like, so check before clearing it.
    faces = people_in(key)
    if faces:
        log(f"{key}: the pass wrote nothing, yet this video uses footage marked as showing people "
            f"({', '.join(sorted(faces))}) — NOT cleared")
        return None
    log(f"{key}: nothing to blur — publish {os.path.basename(plain[0])}")
    return plain[0]


# ------------------------------------------------------------------ run on its own
if __name__ == "__main__":
    START = os.getcwd()
    os.chdir(HERE)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        sys.exit("usage: python pipeline\\finish.py SCRIPTS.txt | KEY [KEY ...]  [--force]")

    first = args[0] if os.path.isabs(args[0]) else os.path.join(START, args[0])
    if os.path.isfile(first):
        vids = autoplan.parse_batch(open(first, encoding="utf-8").read())
        keys = [v["key"] for v in vids]
        if len(args) > 1:
            want = [a.lower() for a in args[1:]]
            keys = [k for k in keys if k in want]
        autoplan.register(vids)
    else:
        keys = [a.lower() for a in args]
    if not keys: sys.exit("no keys to blur")

    autoplan.load_all_batches()
    autoplan.apply_lib(); autoplan.refresh_footage()

    ok, bad = [], []
    for k in keys:
        try:
            p = run(k, log=print, force=force)
            (ok if p else bad).append((k, os.path.basename(p) if p else "no output"))
        except Exception as e:
            print(f"{k}: the blur pass FAILED {e}")
            bad.append((k, str(e)[:120]))

    print(f"\n=== cleared for publishing: {len(ok)}" + (f", not cleared: {len(bad)}" if bad else "") + " ===")
    for k, f in ok: print(f"  {k}: {f}")
    for k, e in bad: print(f"  {k}: NOT CLEARED — {e}")
    sys.exit(1 if bad else 0)
