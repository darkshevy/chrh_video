# The browser interface: http://localhost:8765 — montage, voice-over and the finished videos on one page.
#
#   python pipeline\server.py          (ui.bat in the project folder does this and opens the browser)
#
# Python's standard library only: nothing to install. It listens on this computer alone (127.0.0.1) and runs
# the same programs the console menu runs — montage.py, dub.py, chrh.py scan — one job at a time, showing
# their output live. The console menu (chrh.bat) stays for everything else.
import os, sys, re, json, glob, time, shutil, threading, subprocess, webbrowser, collections, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from paths import FOOTAGE, OUT, WORK

PORT = int(os.environ.get("CHRH_PORT", "8765"))
CURRENT = os.path.join(WORK, "current.json")
LIB = os.path.join(HERE, "library.json")
ORDER_LINE = "The clips are numbered in the order the work was done."
VIDEO_EXT = (".mp4", ".mov", ".mkv")
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


def jload(p, default):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default


def jsave(p, v):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(v, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def project_of(name):
    """springlock3.mp4 -> springlock (as in the menu: the shop names files by job, the prefix is the project)."""
    stem = os.path.splitext(name)[0]
    return stem.rstrip("0123456789") or stem


# ------------------------------------------------------------------ footage files: date, length, thumbnail
META = os.path.join(WORK, "footage_meta.json")
THUMBS = os.path.join(WORK, "thumbs")
_meta = None
_meta_lock = threading.Lock()


def footage_files():
    """name -> full path of every clip/photo in footage/ (names are unique there: the library keys on them)."""
    out = {}
    for dp, _, fs in os.walk(FOOTAGE):
        if "_contact" in dp: continue
        for f in fs:
            if f.lower().endswith(VIDEO_EXT + PHOTO_EXT): out.setdefault(f, os.path.join(dp, f))
    return out


def file_meta(path):
    """Shooting date, length and size of one file, cached by (size, mtime) in work/footage_meta.json.
    The date comes from the camera's creation_time tag when there is one: files saved from a messenger or
    copied to the PC get a fresh modified time, and the operator needs the day it was filmed."""
    global _meta
    st = os.stat(path); sig = f"{st.st_size}:{int(st.st_mtime)}"
    name = os.path.basename(path)
    with _meta_lock:
        if _meta is None: _meta = jload(META, {})
        m = _meta.get(name)
        if m and m.get("sig") == sig: return m
    m = {"sig": sig, "date": st.st_mtime, "dur": 0, "w": 0, "h": 0, "camera_date": False}
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        d = json.loads(p.stdout or "{}")
        fmt = d.get("format", {})
        vs = next((x for x in d.get("streams", []) if x.get("codec_type") == "video"), {})
        m["dur"] = round(float(fmt.get("duration") or 0), 1) if name.lower().endswith(VIDEO_EXT) else 0
        w, h = int(vs.get("width") or 0), int(vs.get("height") or 0)
        rot = (vs.get("tags") or {}).get("rotate") or next((str(x.get("rotation")) for x in vs.get("side_data_list", [])
                                                             if "rotation" in x), "0")
        if str(rot).lstrip("-") in ("90", "270"): w, h = h, w
        m["w"], m["h"] = w, h
        tags = {k.lower(): v for k, v in {**(fmt.get("tags") or {}), **(vs.get("tags") or {})}.items()}
        ct = tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time")
        if ct:
            import datetime
            t = datetime.datetime.fromisoformat(ct.replace("Z", "+00:00")).timestamp()
            if t > 946684800: m["date"], m["camera_date"] = t, True     # 1970/2000 placeholders are not dates
    except Exception:
        pass
    with _meta_lock:
        _meta[name] = m
        jsave(META, _meta)
    return m


def project_files(proj):
    """The project's clips and photos for the preview grid, in clip-number order."""
    out = []
    for name, path in footage_files().items():
        if project_of(name) != proj: continue
        m = file_meta(path)
        num = re.search(r"(\d+)$", os.path.splitext(name)[0])
        out.append({"name": name, "kind": "clip" if name.lower().endswith(VIDEO_EXT) else "photo",
                    "date": m["date"], "camera_date": m["camera_date"], "dur": m["dur"], "w": m["w"], "h": m["h"],
                    "folder": os.path.relpath(os.path.dirname(path), FOOTAGE).replace("\\", "/"),
                    "_n": int(num[1]) if num else 10 ** 6})
    out.sort(key=lambda f: (f["_n"], f["name"]))
    for f in out: del f["_n"]
    return out


def thumb(name):
    """A small jpg of one file (a frame ~1 s in for clips), made once into work/thumbs."""
    path = footage_files().get(os.path.basename(name))
    if not path: return None
    st = os.stat(path)
    out = os.path.join(THUMBS, f"{os.path.splitext(os.path.basename(path))[0]}_{st.st_size}_{int(st.st_mtime)}.jpg")
    if os.path.exists(out): return out
    os.makedirs(THUMBS, exist_ok=True)
    if path.lower().endswith(PHOTO_EXT):
        try:     # OpenCV turns phone photos upright by their EXIF orientation; ffmpeg would leave them sideways
            import cv2
            im = cv2.imread(path)
            if im is not None:
                k = 360 / max(im.shape[:2])
                cv2.imwrite(out, cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))
                return out
        except Exception:
            pass
    dur = file_meta(path)["dur"]
    for ss in ([min(1.0, dur / 2)] if dur else []) + [0]:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", path, "-frames:v", "1",
                        "-vf", "scale='if(gt(iw,ih),360,-2)':'if(gt(iw,ih),-2,360)'", "-q:v", "5", out],
                       capture_output=True, timeout=60)
        if os.path.exists(out): return out
    return None


# ------------------------------------------------------------------ what is there
def projects():
    """Projects from the files actually in footage\\ — clips and photos — with what the library knows."""
    lib = jload(LIB, {}).get("clips", {})
    notes = jload(CURRENT, {}).get("notes", {})
    out = {}
    for dp, _, fs in os.walk(FOOTAGE):
        if "_contact" in dp: continue
        for f in fs:
            low = f.lower()
            kind = "clips" if low.endswith(VIDEO_EXT) else "photos" if low.endswith(PHOTO_EXT) else None
            if not kind: continue
            p = project_of(f)
            g = out.setdefault(p, {"name": p, "clips": 0, "photos": 0, "described": 0, "mtime": 0})
            g[kind] += 1
            g["mtime"] = max(g["mtime"], os.path.getmtime(os.path.join(dp, f)))
            # the filming date once the preview grid has read it; modified time until then
            m = (_meta or {}).get(f)
            t = m["date"] if m else os.path.getmtime(os.path.join(dp, f))
            g["first"] = min(g.get("first", t), t); g["last"] = max(g.get("last", 0), t)
            if kind == "clips" and lib.get(f, {}).get("segments"): g["described"] += 1
    for p, g in out.items():
        n = notes.get(p, "")
        g["ordered"] = ORDER_LINE in n
        g["note"] = n.replace(" " + ORDER_LINE, "").replace(ORDER_LINE, "").strip()
    # single loose files with long camera names are kept, but listed after the real projects
    return sorted(out.values(), key=lambda g: (g["clips"] + g["photos"] < 2, -g["mtime"]))


_dims = {}


def videos():
    """Finished and dropped-in videos in output\\, newest first."""
    out = []
    for f in glob.glob(os.path.join(OUT, "*")):
        if not f.lower().endswith(VIDEO_EXT): continue
        n = os.path.basename(f); st = os.stat(f)
        key = (n, st.st_mtime)
        if key not in _dims:
            try:
                import dub
                _dims[key] = dub.probe(f)[:2]
            except Exception:
                _dims[key] = (0, 0)
        w, h = _dims[key]
        stem = os.path.splitext(n)[0]
        out.append({"name": n, "size": st.st_size, "mtime": st.st_mtime, "w": w, "h": h,
                    "voiced": stem.endswith("_voiced"), "montage": "_montage_" in n.lower(),
                    "has_voiced": os.path.exists(os.path.join(OUT, stem + "_voiced.mp4")),
                    "sheet": n.rsplit(".", 1)[0] + ".jpg" if os.path.exists(os.path.join(OUT, stem + ".jpg")) else None,
                    "plan": stem + "_plan.txt" if os.path.exists(os.path.join(OUT, stem + "_plan.txt")) else None})
    return sorted(out, key=lambda v: -v["mtime"])


def status():
    env = lambda k: bool(os.environ.get(k, "").strip())
    return {"keys": {"gemini": env("GEMINI_API_KEY") or env("GOOGLE_API_KEY"), "claude": env("ANTHROPIC_API_KEY"),
                     "eleven": env("ELEVENLABS_API_KEY")},
            "ffmpeg": bool(shutil.which("ffmpeg")), "job": JOB.view()}


# ------------------------------------------------------------------ one job at a time
class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.kind = None; self.title = ""; self.lines = []; self.proc = None
        self.running = False; self.code = None; self.result = None; self.started = 0.0

    def view(self, since=0):
        return {"kind": self.kind, "title": self.title, "running": self.running, "code": self.code,
                "result": self.result, "lines": self.lines[since:], "n": len(self.lines),
                "elapsed": round(time.time() - self.started) if self.started else 0}

    def start(self, kind, title, steps):
        """steps: [[script, args...], ...] run one after another; a failing step stops the job."""
        with self.lock:
            if self.running: return False
            self.kind, self.title, self.lines, self.code, self.result = kind, title, [], None, None
            self.running, self.started = True, time.time()
        threading.Thread(target=self._run, args=(steps,), daemon=True).start()
        return True

    def say(self, line):
        self.lines.append(line)
        m = re.search(r"done: output\\\\?([^\s]+\.mp4)", line)
        if m: self.result = m.group(1)

    def _run(self, steps):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            for st in steps:
                if callable(st):
                    st(self); continue
                self.say("▸ " + " ".join(os.path.basename(str(x)) if i < 1 else str(x) for i, x in enumerate(st)))
                self.proc = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, st[0])] + [str(x) for x in st[1:]],
                                             cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             text=True, encoding="utf-8", errors="replace")
                for line in self.proc.stdout:
                    self.say(line.rstrip("\n"))
                self.code = self.proc.wait()
                if self.code != 0:
                    self.say(f"✗ остановилось (код {self.code})"); return
            self.code = 0
            self.say("✓ готово")
        except Exception as e:
            self.code = -1; self.say(f"✗ ошибка: {e}")
        finally:
            self.running = False; self.proc = None

    def cancel(self):
        if self.proc and self.running:
            self.proc.terminate(); self.say("✗ остановлено вручную")


JOB = Job()


def save_note(project, note, ordered):
    cur = jload(CURRENT, {})
    n = note.strip().rstrip(" .")
    if ordered: n = (n + ". " if n else "") + ORDER_LINE
    cur.setdefault("notes", {})[project] = n
    cur["prefix"] = project
    jsave(CURRENT, cur)
    return n


def backup(job):
    """Library and scripts to GitHub, code updates back — the console's [S]."""
    def g(*a):
        p = subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        for line in ((p.stdout or "") + (p.stderr or "")).strip().splitlines(): job.say("  " + line)
        return p.returncode
    br = subprocess.run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                        text=True).stdout.strip() or "main"
    g("add", "--", "pipeline/library.json", "scripts")
    if subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--quiet"]).returncode:
        g("commit", "-m", f"Backup: clip library and scripts, {time.strftime('%Y-%m-%d %H:%M')}")
        job.say("изменения записаны")
    before = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    job.say("забираю обновления…")
    if g("pull", "--rebase", "--autostash", "origin", br):
        g("rebase", "--abort"); raise RuntimeError("обновления не встали — ничего не отправлял")
    job.say("отправляю в GitHub…")
    if g("push", "origin", f"HEAD:{br}"): raise RuntimeError("отправить не удалось")
    changed = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", before, "HEAD", "--", "pipeline"],
                             capture_output=True, text=True).stdout.strip()
    if changed: job.say("! код обновился — закрой окно сервера и запусти ui.bat заново")


# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urlparse(self.path); p = unquote(u.path)
        if p in ("/", "/index.html"):
            return self.send(200, open(os.path.join(HERE, "ui", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/api/status": return self.send(200, status())
        if p == "/api/projects": return self.send(200, projects())
        if p == "/api/videos": return self.send(200, videos())
        if p == "/api/project":
            m = re.search(r"name=([^&]*)", u.query or "")
            return self.send(200, project_files(unquote(m[1]) if m else ""))
        if p.startswith("/thumb/"):
            t = thumb(p[len("/thumb/"):])
            if not t: return self.send(404, {"error": "no thumb"})
            b = open(t, "rb").read()
            self.send_response(200); self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "max-age=86400")
            self.end_headers(); return self.wfile.write(b)
        if p.startswith("/footage/"):
            f = footage_files().get(os.path.basename(p[len("/footage/"):]))
            return self.media(f, root=FOOTAGE) if f else self.send(404, {"error": "no file"})
        if p == "/api/job":
            since = int((re.search(r"since=(\d+)", u.query or "") or [0, 0])[1])
            return self.send(200, JOB.view(since))
        if p.startswith("/media/"): return self.media(p[len("/media/"):])
        self.send(404, {"error": "not found"})

    def media(self, name, root=OUT):
        """A file from output\\ (or footage\\ for the previews) only, with Range support so the player can seek."""
        f = os.path.realpath(name if root != OUT else os.path.join(OUT, os.path.basename(name)))
        if not f.startswith(os.path.realpath(root)) or not os.path.isfile(f): return self.send(404, {"error": "no file"})
        size = os.path.getsize(f)
        ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
        if f.lower().endswith(".mov"): ctype = "video/mp4"     # Chrome plays iPhone .mov as mp4, not as quicktime
        if ctype == "text/plain": ctype += "; charset=utf-8"
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        a, b = 0, size - 1
        if rng:
            if rng[1]: a = int(rng[1])
            if rng[2]: b = min(int(rng[2]), size - 1)
            if not rng[1] and rng[2]: a, b = size - int(rng[2]), size - 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        if rng: self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(a); left = b - a + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except ConnectionError:     # reset/aborted/broken pipe: the player seeks or closes mid-file — normal
                pass

    def do_POST(self):
        p = urlparse(self.path).path
        try: d = self.body()
        except Exception: return self.send(400, {"error": "bad json"})
        if p == "/api/montage":
            proj = re.sub(r"[^A-Za-z0-9_\-]", "", str(d.get("project", "")))
            if not proj: return self.send(400, {"error": "нет проекта"})
            note = save_note(proj, str(d.get("note", "")), bool(d.get("ordered")))
            secs = max(10, min(120, float(d.get("seconds") or 30)))
            steps = [["chrh.py", "scan"]]
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                steps.append(["describe.py", proj, "--note", note])
            steps.append(["montage.py", proj, "--seconds", f"{secs:g}", "--ordered" if d.get("ordered") else "--unordered"])
            ok = JOB.start("montage", f"Монтаж: {proj}", steps)
            return self.send(200 if ok else 409, {"ok": ok, "error": None if ok else "уже идёт другая задача"})
        if p == "/api/dub":
            name = os.path.basename(str(d.get("video", "")))
            src = os.path.join(OUT, name)
            text = str(d.get("text", "")).strip()
            if not os.path.isfile(src) or not text: return self.send(400, {"error": "нет ролика или текста"})
            tdir = os.path.join(WORK, "dub"); os.makedirs(tdir, exist_ok=True)
            tp = os.path.join(tdir, os.path.splitext(name)[0] + "_input.txt")
            open(tp, "w", encoding="utf-8").write(text + "\n")
            args = ["dub.py", src, tp] + (["--landscape"] if d.get("landscape") else [])
            ok = JOB.start("dub", f"Озвучка: {name}", [args])
            return self.send(200 if ok else 409, {"ok": ok, "error": None if ok else "уже идёт другая задача"})
        if p == "/api/scan":
            ok = JOB.start("scan", "Поиск новых клипов", [["chrh.py", "scan"]])
            return self.send(200 if ok else 409, {"ok": ok})
        if p == "/api/backup":
            ok = JOB.start("backup", "Сохранение в облако", [backup])
            return self.send(200 if ok else 409, {"ok": ok})
        if p == "/api/cancel":
            JOB.cancel(); return self.send(200, {"ok": True})
        if p == "/api/open":
            target = FOOTAGE if d.get("what") == "footage" else OUT
            try:
                if os.name == "nt": os.startfile(target)
                else: subprocess.Popen(["xdg-open", target])
            except Exception as e:
                return self.send(500, {"error": str(e)})
            return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # the browser drops video and thumbnail requests whenever the user scrolls or seeks (WinError 10053);
        # a traceback for each of those buried the real messages in the server window
        if isinstance(sys.exc_info()[1], ConnectionError): return
        super().handle_error(request, client_address)


def main():
    os.makedirs(OUT, exist_ok=True)
    srv = Server(("127.0.0.1", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"CHRH Video — {url}   (закрой это окно, чтобы остановить)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
