import os
import sys
def _find_root():
    """Project folder = the one that holds pipeline/. In the .exe build, search upward from the exe."""
    if getattr(sys, "frozen", False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        for _ in range(4):
            if os.path.isdir(os.path.join(d, "pipeline")): return d
            d = os.path.dirname(d)
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT=_find_root()
# bundled ffmpeg/ffprobe (exe build puts them in <exe folder>/bin) go first on PATH
_BIN=os.path.join(os.path.dirname(os.path.abspath(sys.executable)),"bin") if getattr(sys,"frozen",False) else ""
if _BIN and os.path.isdir(_BIN): os.environ["PATH"]=_BIN+os.pathsep+os.environ.get("PATH","")
FOOTAGE=os.path.join(ROOT,"footage")
MUSIC=os.path.join(ROOT,"music")
VOICE=os.path.join(ROOT,"voiceover")
PIPE=os.path.join(ROOT,"pipeline")
WORK=os.path.join(ROOT,"work")      # segments, .ass, .trf
OUT=os.path.join(ROOT,"output")     # finished videos
for d in (WORK,OUT): os.makedirs(d,exist_ok=True)
VIDEXT=(".mp4",".mov",".mkv")
def index_footage():
    """basename -> full path, searched recursively under footage/ (clips live in subfolders)."""
    idx={}
    for dp,_,fs in os.walk(FOOTAGE):
        if "_contact" in dp: continue
        for f in sorted(fs):
            if f.lower().endswith(VIDEXT): idx.setdefault(f,os.path.join(dp,f))
    return idx
