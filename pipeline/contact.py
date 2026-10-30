# Contact sheets: one JPG per clip, COLS x ROWS frames spread evenly over the clip, timestamp on each frame.
# usage: python contact.py <folder under footage/ or abs path> [cols] [rows]
import sys,os,subprocess,tempfile,shutil
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from paths import FOOTAGE,VIDEXT
FONT="C\\:/Windows/Fonts/arialbd.ttf"
TW=480  # thumb width
def probe(f):
    o=subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
        "stream=width,height:stream_side_data=rotation:format=duration","-of","default=nw=1",f],text=True)
    d=dict(l.split("=",1) for l in o.split() if "=" in l)
    w,h=int(d["width"]),int(d["height"])
    if d.get("rotation","0").lstrip("-") in ("90","270"): w,h=h,w
    return float(d["duration"]),w,h
def esc(s): return s.replace("\\","\\\\").replace(":","\\:").replace("'","\u2019").replace(",","\\,")
def sheet(f,outdir,cols=4,rows=5):
    dur,w,h=probe(f); n=cols*rows
    name=os.path.basename(f); out=os.path.join(outdir,os.path.splitext(name)[0]+".jpg")
    tmp=tempfile.mkdtemp()
    try:
        for i in range(n):
            t=dur*(i+0.5)/n
            lab=f"{int(t//60)}:{t%60:04.1f}"
            vf=(f"scale={TW}:-2,drawtext=fontfile='{FONT}':text='{esc(lab)}':x=8:y=h-th-8:fontsize=26:"
                "fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5,format=yuvj420p")
            subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-vf",vf,
                            "-q:v","3",os.path.join(tmp,f"{i:03d}.jpg")],check=True)
        title=esc(f"{name}   {w}x{h}   {int(dur//60)}:{dur%60:04.1f}")
        vf=(f"tile={cols}x{rows}:padding=4:margin=4,pad=iw:ih+60:0:60:color=0x202020,"
            f"drawtext=fontfile='{FONT}':text='{title}':x=12:y=16:fontsize=30:fontcolor=white")
        subprocess.run(["ffmpeg","-v","error","-y","-i",os.path.join(tmp,"%03d.jpg"),"-vf",vf,
                        "-frames:v","1","-q:v","3",out],check=True)
    finally: shutil.rmtree(tmp,ignore_errors=True)
    return out,dur,w,h
if __name__=="__main__":
    src=sys.argv[1]; src=src if os.path.isabs(src) else os.path.join(FOOTAGE,src)
    cols=int(sys.argv[2]) if len(sys.argv)>2 else 4; rows=int(sys.argv[3]) if len(sys.argv)>3 else 5
    outdir=os.path.join(FOOTAGE,"_contact",os.path.basename(src.rstrip("/\\"))); os.makedirs(outdir,exist_ok=True)
    for f in sorted(os.listdir(src)):
        if f.lower().endswith(VIDEXT):
            o,d,w,h=sheet(os.path.join(src,f),outdir,cols,rows)
            print(f"{f}\t{w}x{h}\t{d:.1f}s\t-> {o}",flush=True)
