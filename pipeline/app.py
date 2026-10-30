# CHRH Video — operator window: paste the day's scripts, drop the voice-overs, press "Build all".
# Start: double-click "CHRH Video.bat" in the project folder (or: pythonw app.py from the pipeline folder).
import os, sys, shutil, threading, queue, traceback, subprocess, datetime, json
if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths   # finds the project folder (also from the .exe) and puts the bundled ffmpeg on PATH
HERE = paths.PIPE
START = os.getcwd()          # command-line file arguments are relative to where the command was typed
os.chdir(HERE)
def _arg_path(p):
    if os.path.isabs(p): return p
    for base in (START, paths.ROOT):          # also accept paths relative to the project folder
        q = os.path.join(base, p)
        if os.path.exists(q): return q
    return os.path.join(START, p)
if not shutil.which("ffmpeg"):   # winget puts ffmpeg here; a shortcut launch may not have it on PATH yet
    os.environ["PATH"] += os.pathsep + os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")

# no console (pythonw / .exe): send prints from the render code to work/app.log instead of losing them
_LOG = os.path.join(paths.WORK, "app.log")
if sys.stdout is None or not sys.stdout.isatty():
    sys.stdout = sys.stderr = open(_LOG, "a", encoding="utf-8", buffering=1)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

SAMPLE = """=== deckdown | DECK DOWN? | IF IT'S ON A CARRIER, WE FIX IT | Thunder
Deck won't move? Line just blew and there's fluid on the pavement? ... (the whole script as one paragraph, 115–125 words) ... [HOOK 2] Here's the part that saves your week: ... Call the number on screen.

=== cottrell | COTTRELL AUTHORIZED | KEEP YOUR FACTORY WARRANTY | Kama Sutra
Own a Cottrell? ... [HOOK 2] So how does it work? ...

Header line format:  === key | TITLE | SUBTITLE | Track
Key = voice-over file name: voiceover\\deckdown.mp3. The scripts\\topics_*.txt format ("key: …" lines) works too.
"""

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CHRH Video — batch builder")
        self.geometry("1100x760"); self.minsize(900, 600)
        self.q = queue.Queue(); self.busy = False; self.stop_flag = False
        self.videos = []
        style = ttk.Style(self)
        try: style.theme_use("vista")
        except tk.TclError: pass
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Treeview", rowheight=24)

        top = ttk.Frame(self, padding=(12, 10, 12, 0)); top.pack(fill="x")
        ttk.Label(top, text="Car Hauler Repair Houston — video builder", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.status = ttk.Label(top, text="Loading…", foreground="#666"); self.status.pack(side="right")

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=12, pady=10)
        self.tab_batch = ttk.Frame(nb, padding=10); nb.add(self.tab_batch, text="  Batch  ")
        self.tab_lib = ttk.Frame(nb, padding=10); nb.add(self.tab_lib, text="  Clip library  ")
        self.tab_log = ttk.Frame(nb, padding=10); nb.add(self.tab_log, text="  Log  ")
        self.build_batch_tab(); self.build_log_tab(); self.build_lib_tab()

        self.after(100, self.poll)
        self.run_bg(self.boot, "Loading the editing engine…")

    # ------------------------------------------------------------ background work
    def boot(self):
        global autoplan, build, contact, paths
        import autoplan, build, contact, paths
        autoplan.apply_lib(); autoplan.load_all_batches()
        self.q.put(("status", f"Ready · clips in footage: {len(build.files)}"))
        self.q.put(("call", self.fill_library))

    def run_bg(self, fn, msg):
        if self.busy:
            messagebox.showinfo("Please wait", "A job is already running. Wait for it to finish or press Stop."); return
        self.busy = True; self.stop_flag = False; self.set_busy(True, msg)
        def work():
            try: fn()
            except Exception as e:
                self.q.put(("log", traceback.format_exc())); self.q.put(("error", str(e)))
            finally: self.q.put(("done", None))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log": self.log_write(val)
                elif kind == "status": self.status.config(text=val)
                elif kind == "progress":
                    i, n, msg = val; self.pb.config(maximum=max(n, 1), value=i); self.prog_lbl.config(text=msg)
                elif kind == "error": messagebox.showerror("Error", val)
                elif kind == "call": val()
                elif kind == "done": self.busy = False; self.set_busy(False, "")
        except queue.Empty:
            pass
        self.after(150, self.poll)

    def log(self, s): self.q.put(("log", s))

    def set_busy(self, on, msg):
        for b in (self.btn_check, self.btn_build, self.btn_build_sel, self.btn_blur, self.btn_rescan, self.btn_retag_all, self.btn_retag):
            b.config(state="disabled" if on else "normal")
        self.btn_stop.config(state="normal" if on else "disabled")
        if msg: self.prog_lbl.config(text=msg)
        if on: self.pb.config(value=0)

    # ------------------------------------------------------------ tab 1: batch
    def build_batch_tab(self):
        f = self.tab_batch
        f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1); f.rowconfigure(4, weight=1)
        bar = ttk.Frame(f); bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="1. Paste the scripts (or open a file)   2. Put the voice-overs into voiceover\\   3. Check → Build",
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(bar, text="Format example", command=self.show_sample).pack(side="right")
        ttk.Button(bar, text="Open script file…", command=self.open_scripts).pack(side="right", padx=6)

        self.txt = tk.Text(f, wrap="word", font=("Consolas", 10), undo=True, height=12)
        self.txt.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        acts = ttk.Frame(f); acts.grid(row=2, column=0, sticky="ew")
        self.btn_check = ttk.Button(acts, text="Check", command=self.do_check); self.btn_check.pack(side="left")
        self.btn_build = ttk.Button(acts, text="Build all", style="Big.TButton", command=self.do_build_all)
        self.btn_build.pack(side="left", padx=8)
        self.btn_build_sel = ttk.Button(acts, text="Build selected", command=self.do_build_sel)
        self.btn_build_sel.pack(side="left")
        self.btn_stop = ttk.Button(acts, text="Stop", command=self.do_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_blur = ttk.Button(acts, text="Blur faces (selected, after approval)", command=self.do_blur)
        self.btn_blur.pack(side="right")
        ttk.Button(acts, text="Output folder", command=lambda: os.startfile(paths.OUT)).pack(side="right", padx=6)
        ttk.Button(acts, text="Voice-over folder", command=lambda: os.startfile(paths.VOICE)).pack(side="right")

        pr = ttk.Frame(f); pr.grid(row=3, column=0, sticky="ew", pady=(10, 4))
        self.pb = ttk.Progressbar(pr, mode="determinate"); self.pb.pack(side="left", fill="x", expand=True)
        self.prog_lbl = ttk.Label(pr, text="", width=46); self.prog_lbl.pack(side="left", padx=8)

        cols = ("title", "track", "words", "vo", "status")
        self.tree = ttk.Treeview(f, columns=cols, show="tree headings", selectmode="extended", height=10)
        self.tree.heading("#0", text="Key"); self.tree.column("#0", width=120, stretch=False)
        for c, t, w in [("title", "Title", 200), ("track", "Track", 120), ("words", "Words", 60),
                        ("vo", "Voice-over", 80), ("status", "Check / result", 460)]:
            self.tree.heading(c, text=t); self.tree.column(c, width=w, stretch=(c == "status"))
        self.tree.tag_configure("err", foreground="#b3261e"); self.tree.tag_configure("warn", foreground="#8a5a00")
        self.tree.tag_configure("ok", foreground="#1e6b3a")
        self.tree.grid(row=4, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self.open_result)
        ttk.Label(f, text="Double-click a finished video to play it. Right-click opens its contact sheet.",
                  foreground="#666").grid(row=5, column=0, sticky="w", pady=(4, 0))
        self.tree.bind("<Button-3>", self.open_sheet)

    def show_sample(self):
        if self.txt.get("1.0", "end").strip() and not messagebox.askyesno("Example", "Replace the text in the box with the example?"):
            return
        self.txt.delete("1.0", "end"); self.txt.insert("1.0", SAMPLE)

    def open_scripts(self):
        p = filedialog.askopenfilename(initialdir=os.path.join(paths.ROOT, "scripts"),
                                       filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if p:
            self.txt.delete("1.0", "end"); self.txt.insert("1.0", open(p, encoding="utf-8").read())

    def parse(self):
        self.videos = autoplan.parse_batch(self.txt.get("1.0", "end"))
        if not self.videos:
            messagebox.showwarning("No scripts", "No scripts found. Press \"Format example\" to see the format."); return False
        return True

    def do_check(self, then=None):
        if not self.parse(): return
        vids = self.videos
        def work():
            res = autoplan.check(vids)
            self.q.put(("call", lambda: self.show_check(vids, res, then)))
        self.run_bg(work, "Checking scripts and voice-overs…")

    def show_check(self, vids, res, then):
        self.tree.delete(*self.tree.get_children())
        nerr = 0
        for v in vids:
            iss = res[v["key"]]; errs = [m for l, m in iss if l == "err"]; nerr += len(errs)
            d = autoplan.dur(autoplan.vo_path(v["key"]))
            tag = "err" if errs else ("warn" if iss else "ok")
            msg = "; ".join(m for _, m in iss) or "OK"
            self.tree.insert("", "end", iid=v["key"], text=v["key"], tags=(tag,),
                             values=(v["title"], v["track"] or "auto", len(autoplan.clean_text(v["text"]).split()),
                                     f"{d:.0f} s" if d else "—", msg))
        self.status.config(text=f"Scripts: {len(vids)} · errors: {nerr}")
        if then and nerr == 0: then()
        elif then: messagebox.showwarning("Errors found", "Fix the rows marked red and press Build again.")

    def do_build_all(self): self.do_check(then=lambda: self.start_build([v["key"] for v in self.videos]))

    def do_build_sel(self):
        sel = list(self.tree.selection())
        if not sel: messagebox.showinfo("Selection", "Select videos in the table (Ctrl+click)."); return
        self.do_check(then=lambda: self.start_build([k for k in sel if k in {v['key'] for v in self.videos}]))

    def start_build(self, keys):
        vids = [v for v in self.videos if v["key"] in keys]
        def work():
            path = autoplan.register(vids)
            self.log(f"Batch saved: {path}")
            def prog(i, n, msg): self.q.put(("progress", (i, n, msg)))
            def lg(s):
                self.log(s)
                if "done ->" in s:
                    k = s.split(":")[0]; name = s.split("→")[1].strip()
                    self.q.put(("call", lambda: self.mark(k, "ok", f"done: {name}")))
            outs = autoplan.run(keys, log=lg, stop=lambda: self.stop_flag, progress=prog)
            self.q.put(("status", f"Videos built: {len(outs or [])} of {len(keys)}"))
        self.run_bg(work, "Building…")

    def mark(self, k, tag, msg):
        if self.tree.exists(k):
            self.tree.item(k, tags=(tag,)); self.tree.set(k, "status", msg)

    def do_stop(self):
        self.stop_flag = True; self.prog_lbl.config(text="Stopping after the current step…")

    def latest_output(self, k, ext=".mp4"):
        import glob
        fs = glob.glob(os.path.join(paths.OUT, build.outname(k, "_*")[:-4] + ext))
        return max(fs, key=os.path.getmtime) if fs else None

    def open_result(self, ev):
        k = self.tree.identify_row(ev.y)
        p = k and self.latest_output(k)
        if p: os.startfile(p)

    def open_sheet(self, ev):
        k = self.tree.identify_row(ev.y)
        p = k and self.latest_output(k, ".jpg")
        if p: os.startfile(p)

    def do_blur(self):
        sel = list(self.tree.selection())
        if not sel: messagebox.showinfo("Selection", "Select the videos the boss approved."); return
        def work():
            for k in sel:
                if self.stop_flag: break
                autoplan.blur_key(k, log=self.log)
                self.q.put(("call", lambda k=k: self.mark(k, "ok", f"faces blurred: {build.outname(k, '_blur')}")))
        self.run_bg(work, "Blurring faces…")

    # ------------------------------------------------------------ tab 2: clip library
    def build_lib_tab(self):
        f = self.tab_lib; f.columnconfigure(0, weight=1); f.rowconfigure(2, weight=1)
        top = ttk.Frame(f); top.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.btn_rescan = ttk.Button(top, text="Refresh: find new clips and auto-tag", style="Big.TButton",
                                     command=self.lib_rescan)
        self.btn_rescan.pack(side="left")
        self.btn_retag_all = ttk.Button(top, text="Re-tag all (except manual)", command=self.lib_retag_all)
        self.btn_retag_all.pack(side="left", padx=8)
        self.lib_filter = tk.StringVar(value="all")
        ttk.Label(top, text="Show:").pack(side="left", padx=(16, 4))
        cb = ttk.Combobox(top, textvariable=self.lib_filter, state="readonly", width=16,
                          values=["all", "in use", "disabled", "auto", "manual", "new"])
        cb.pack(side="left"); cb.bind("<<ComboboxSelected>>", lambda e: self.fill_library())
        ttk.Label(f, wraplength=1040, foreground="#555", text=(
            "Clips are sorted into topics automatically: every second is compared with the clips tagged by hand. "
            "Empty seconds (wall, stairs, tarp, sky) and outdoor painting are switched off automatically. If a topic is "
            "wrong, fix the check boxes and press \"Save as manual\": the clip becomes an example and the next "
            "clips are tagged better.")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        cols = ("use", "folder", "cats", "src", "note")
        self.ltree = ttk.Treeview(f, columns=cols, show="tree headings", selectmode="extended")
        self.ltree.heading("#0", text="Clip"); self.ltree.column("#0", width=280)
        for c, t, w in [("use", "In use", 80), ("folder", "Folder", 150), ("cats", "Topics", 300),
                        ("src", "Tagged", 80), ("note", "Note", 200)]:
            self.ltree.heading(c, text=t); self.ltree.column(c, width=w, stretch=(c in ("cats", "note")))
        self.ltree.tag_configure("off", foreground="#999"); self.ltree.tag_configure("new", foreground="#b3261e")
        self.ltree.grid(row=2, column=0, sticky="nsew", pady=8)
        self.ltree.bind("<<TreeviewSelect>>", self.lib_select)
        self.ltree.bind("<Double-1>", self.lib_sheet)
        side = ttk.Frame(f, padding=(10, 8, 0, 0)); side.grid(row=2, column=1, sticky="ns")
        self.use_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(side, text="Use in videos", variable=self.use_var).pack(anchor="w")
        ttk.Label(side, text="What is in the clip:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.cat_vars = {}
        self.cat_box = ttk.Frame(side); self.cat_box.pack(anchor="w", pady=4)
        ttk.Button(side, text="Save as manual", command=self.lib_save).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Enable selected", command=lambda: self.lib_set_use(True)).pack(fill="x", pady=2)
        ttk.Button(side, text="Disable selected", command=lambda: self.lib_set_use(False)).pack(fill="x", pady=2)
        self.btn_retag = ttk.Button(side, text="Re-tag selected", command=self.lib_retag_sel)
        self.btn_retag.pack(fill="x", pady=2)
        ttk.Button(side, text="Clip contact sheet", command=self.lib_sheet).pack(fill="x", pady=2)
        ttk.Label(side, text="Double-click: the clip's frames\nas a grid with timecodes.\n\nRed rows: new clips,\nnot tagged yet.",
                  foreground="#666").pack(anchor="w", pady=8)

    def fill_library(self):
        L = autoplan.lib(); files = autoplan.refresh_footage(); clips = L.get("clips", {})
        lab = {c: d["label"] for c, d in L["categories"].items()}
        if not self.cat_vars:
            for c, d in L["categories"].items():
                v = tk.BooleanVar(); self.cat_vars[c] = v
                ttk.Checkbutton(self.cat_box, text=d["label"], variable=v).pack(anchor="w")
        flt = self.lib_filter.get()
        self.ltree.delete(*self.ltree.get_children())
        n_new = n_on = 0
        for fn in sorted(files, key=lambda x: x.lower()):
            r = clips.get(fn)
            on = bool(r and r.get("enabled")); n_on += on; n_new += r is None
            if flt == "in use" and not on: continue
            if flt == "disabled" and (on or r is None): continue
            if flt == "auto" and not (r and not r.get("manual")): continue
            if flt == "manual" and not (r and r.get("manual")): continue
            if flt == "new" and r is not None: continue
            folder = os.path.relpath(os.path.dirname(build.src(fn)), paths.FOOTAGE)
            folder = "" if folder == "." else folder
            if r is None:
                vals = ("?", folder, "", "", "new: press Refresh"); tag = ("new",)
            else:
                dull = sum(b - a for a, b in r.get("dull", []))
                note = r.get("reason") or (f"empty seconds: {dull:.0f} s" if dull >= 1 else "")
                vals = ("yes" if on else "no", folder, ", ".join(lab.get(c, c) for c in r.get("cats", [])),
                        "manual" if r.get("manual") else "auto", note)
                tag = () if on else ("off",)
            self.ltree.insert("", "end", iid=fn, text=fn, values=vals, tags=tag)
        self.status.config(text=f"Clips in footage: {len(files)} · in use: {n_on} · new: {n_new}")

    def lib_select(self, ev=None):
        sel = self.ltree.selection()
        if len(sel) != 1: return
        r = autoplan.lib().get("clips", {}).get(sel[0], {})
        self.use_var.set(bool(r.get("enabled", True)))
        for c, v in self.cat_vars.items(): v.set(c in r.get("cats", []))

    def lib_save(self):
        sel = self.ltree.selection()
        if not sel: return
        L = autoplan.lib(); cats = [c for c, v in self.cat_vars.items() if v.get()]
        for fn in sel:
            old = L["clips"].get(fn, {})
            L["clips"][fn] = {"enabled": self.use_var.get() and bool(cats), "cats": cats, "dull": old.get("dull", []),
                              "manual": True, "reason": "" if cats else "no topics ticked"}
        autoplan.save_lib(L); autoplan.apply_lib(L); self.fill_library(); self.reselect(sel)
        self.log(f"Manual: {', '.join(sel)} -> {', '.join(cats) or 'no topics'}")

    def lib_set_use(self, on):
        sel = self.ltree.selection()
        if not sel: return
        L = autoplan.lib(); skipped = []
        for fn in sel:
            r = L["clips"].get(fn)
            if r is None or (on and not r.get("cats")): skipped.append(fn); continue
            r["enabled"] = on; r["manual"] = True
            if on: r["reason"] = ""
            elif not r.get("reason"): r["reason"] = "disabled by hand"
        autoplan.save_lib(L); autoplan.apply_lib(L); self.fill_library(); self.reselect(sel)
        if skipped:
            messagebox.showinfo("Not changed", "Tag the clip first or tick its topics:\n" + "\n".join(skipped[:10]))

    def reselect(self, sel):
        for fn in sel:
            if self.ltree.exists(fn): self.ltree.selection_add(fn)

    def lib_scan(self, **kw):
        def work():
            def prog(i, n, msg): self.q.put(("progress", (i, n, msg)))
            n = autoplan.rescan(log=self.log, progress=prog, **kw)
            self.q.put(("status", f"Clips tagged: {n}")); self.q.put(("call", self.fill_library))
        self.run_bg(work, "Tagging clips…")

    def lib_rescan(self): self.lib_scan()

    def lib_retag_all(self):
        if messagebox.askyesno("Re-tag",
                               "Re-tag every automatically tagged clip? Manual tags stay as they are."):
            self.lib_scan(force=True)

    def lib_retag_sel(self):
        sel = list(self.ltree.selection())
        if not sel: return
        if any(autoplan.lib()["clips"].get(fn, {}).get("manual") for fn in sel) and not messagebox.askyesno(
                "Manual tags", "Some selected clips were tagged by hand. Replace their tags with automatic ones?"):
            return
        self.lib_scan(names=sel)

    def lib_sheet(self, ev=None):
        sel = self.ltree.selection()
        if not sel: return
        fn = sel[0]
        out = os.path.join(paths.FOOTAGE, "_contact", "library")
        p = os.path.join(out, os.path.splitext(fn)[0] + ".jpg")
        if os.path.exists(p): os.startfile(p); return
        def work():
            os.makedirs(out, exist_ok=True); contact.sheet(build.src(fn), out, 4, 5)
            self.q.put(("call", lambda: os.startfile(p)))
        self.run_bg(work, "Making the contact sheet…")

    # ------------------------------------------------------------ tab 3: log
    def build_log_tab(self):
        f = self.tab_log; f.columnconfigure(0, weight=1); f.rowconfigure(0, weight=1)
        self.logbox = tk.Text(f, wrap="word", font=("Consolas", 9), state="disabled")
        self.logbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, command=self.logbox.yview); sb.grid(row=0, column=1, sticky="ns")
        self.logbox.config(yscrollcommand=sb.set)

    def log_write(self, s):
        self.logbox.config(state="normal")
        self.logbox.insert("end", f"[{datetime.datetime.now():%H:%M:%S}] {s}\n"); self.logbox.see("end")
        self.logbox.config(state="disabled")
        try:
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {s}\n")
        except OSError:
            pass

def selftest(argv):
    """No-window checks for the .exe build (results go to work/app.log):
       --selftest SCRIPTS.txt            parse + check, test the aligner and OpenCV
       --run KEY SCRIPTS.txt             full build of one video from that file (batch "_selftest")"""
    import autoplan, align, build
    print("=== selftest", argv, "ROOT", paths.ROOT, "ffmpeg", shutil.which("ffmpeg"))
    autoplan.apply_lib(); autoplan.load_all_batches()
    if argv[0] == "--selftest":
        vids = autoplan.parse_batch(open(_arg_path(argv[1]), encoding="utf-8").read())
        for k, iss in autoplan.check(vids).items(): print("check", k, iss)
        from pocketsphinx import Decoder; print("pocketsphinx ok", Decoder().lookup_word("trailer"))
        import cv2, faces; print("opencv ok", cv2.__version__, os.path.exists(faces.MODEL))
        import autotag; autotag._load(); print("clip model ok", os.path.exists(autotag.VISION))
        print("rescan new clips:", autoplan.rescan(log=print))
    elif argv[0] == "--run":
        key = argv[1]; vids = [v for v in autoplan.parse_batch(open(_arg_path(argv[2]), encoding="utf-8").read()) if v["key"] == key]
        autoplan.register(vids, "_selftest"); print("outputs", autoplan.run([key], log=print))
    print("=== selftest done")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--selftest", "--run"):
        try: selftest(sys.argv[1:])
        except Exception: traceback.print_exc(); print("=== selftest FAILED")
    else:
        App().mainloop()
