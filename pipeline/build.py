import sys,os,json,subprocess,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from paths import FOOTAGE,MUSIC,VOICE,PIPE,WORK,OUT,index_footage
from plan import P,TITLE,NEXT,SUB,TRACK,BLUR,PEOPLE,LOGO
from scripts import S,VO,norm,HOOK
FILES=index_footage(); files=list(FILES)
def src(f): return FILES[f]
A=json.load(open(os.path.join(PIPE,'align.json')))
PRE=0.6; END=4.0; FPS=30
ADDRESS="6716 Long Drive, Houston, TX 77087"   # site spelling (FB page: "6716 Long. Drive")
PHONE="(832) 708-5492"
# pleasant grade (boss 09-24): lifted mids, vibrance, warm highlights / cool shadows, light clarity + vignette
GRADE=("eq=contrast=1.10:saturation=1.10:gamma=1.12:brightness=0.015,vibrance=intensity=0.35,"
       "colorbalance=rs=-0.03:bs=0.04:rh=0.05:bh=-0.05,curves=all='0/0.02 0.35/0.40 0.8/0.86 1/1',"
       "unsharp=5:5:0.35,vignette=angle=PI/7")
def ts(t):
    t=max(t,0); h=int(t//3600); m=int(t%3600//60); s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
def vof(k): return os.path.join(VOICE,VO.get(k,f"part{k}.mp3"))
def outname(k,tag): return f"RedHauler_Part{k}{tag}.mp4" if isinstance(k,int) else f"CHRH_{k.capitalize()}{tag}.mp4"
def voDur(k): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",vof(k)],stderr=subprocess.DEVNULL))
def layout(k):
    vo=voDur(k); total=PRE+vo+END
    cuts=[0 if w is None else A[str(k)][w][1]+PRE-0.06 for (w,*_) in P[k]]+[total]
    F=[round(t*FPS) for t in cuts]
    segs=[]
    for i,(w,pre,tin,sp,z) in enumerate(P[k]):
        f=[x for x in files if x.startswith(pre)][0]
        segs.append(dict(i=i,file=f,tin=tin,sp=sp,z=z,f0=F[i],n=F[i+1]-F[i]))
    return vo,F[-1]/FPS,segs
def make_ass(k,vo,total):
    words=A[str(k)]
    toks=[]
    for t in S[k].split():
        toks.append(t)
        n=len(norm(t))  # hyphens / spoken numbers expand to several aligned words
        if n>1: toks.extend([""]*(n-1))
    assert len(toks)==len(words),(k,len(toks),len(words))
    disp=[re.sub(r"[.,:;]","",t) for t in toks]
    # chunking (skip "Part N")
    chunks=[];cur=[]
    for i in range(2 if S[k].startswith("Part") else 0,len(words)):
        if cur:
            prev=cur[-1]
            gap=words[i][1]-words[prev][2]
            if len(cur)>=3 or re.search(r"[.,:;?]$",toks[prev]) or gap>0.25 or i==HOOK.get(k,-1):
                chunks.append(cur);cur=[]
        cur.append(i)
    if cur: chunks.append(cur)
    # hook sentence (boss 09-24: hook in the middle) — amber, bigger captions until the sentence ends
    hook=set()
    if k in HOOK:
        i=HOOK[k]
        while i<len(toks):
            hook.add(i)
            if re.search(r"[.?!]$",toks[i]): break
            i+=1
    ev=[]
    for ci,ch in enumerate(chunks):
        nxt=words[chunks[ci+1][0]][1] if ci+1<len(chunks) else None
        for j,wi in enumerate(ch):
            st=words[wi][1]
            if j+1<len(ch): en=words[ch[j+1]][1]
            else:
                en=words[wi][2]+0.35
                if nxt is not None and nxt-words[wi][2]<0.6: en=nxt
                if nxt is not None: en=min(en,nxt)
            parts=[]
            for jj,w2 in enumerate(ch):
                a="&H00&" if jj<=j else "&H9A&"
                if disp[w2]: parts.append("{\\alpha"+a+"}"+disp[w2])
            sty="CapHook" if ch[0] in hook else "Cap"
            ev.append(f"Dialogue: 1,{ts(st+PRE)},{ts(en+PRE)},{sty},,0,0,0,,"+" ".join(parts))
    e0=PRE+vo+0.15
    nx=NEXT[k]
    endev=[
     f"Dialogue: 0,{ts(e0)},{ts(total+0.1)},Box,,0,0,0,,{{\\fad(300,0)\\an7\\pos(0,0)\\p1}}m 0 0 l 1080 0 1080 1920 0 1920{{\\p0}}",
     f"Dialogue: 2,{ts(e0+0.1)},{ts(total+0.1)},EndBig,,0,0,0,,{{\\fad(350,0)\\pos(540,860)}}CAR HAULER\\NREPAIR HOUSTON",
     f"Dialogue: 2,{ts(e0+0.3)},{ts(total+0.1)},EndSub,,0,0,0,,{{\\fad(350,0)\\pos(540,1075)}}CALL {PHONE}",
     f"Dialogue: 2,{ts(e0+0.5)},{ts(total+0.1)},EndAddr,,0,0,0,,{{\\fad(350,0)\\pos(540,1160)}}{ADDRESS}",
    ]
    if nx: endev.append(f"Dialogue: 2,{ts(e0+0.6)},{ts(total+0.1)},EndNext,,0,0,0,,{{\\fad(350,0)\\pos(540,1250)}}{nx}")
    # phone number on top for the whole video (boss 09-24); hands over to the end card
    endev.append(f"Dialogue: 3,{ts(0.0)},{ts(e0+0.2)},Phone,,0,0,0,,{{\\fad(400,300)}}CALL {PHONE}")
    # mid-video hook (boss 09-24): quick white flash on the hook word
    if k in HOOK:
        th=words[HOOK[k]][1]+PRE
        endev.append(f"Dialogue: 4,{ts(th-0.04)},{ts(th+0.28)},Flash,,0,0,0,,"
                     f"{{\\an7\\pos(0,0)\\1a&H90&\\fad(0,240)\\p1}}m 0 0 l 1080 0 1080 1920 0 1920{{\\p0}}")
    # layout safe for Facebook 1:1 centre crop (y 420-1500) and 4:5 (y 285-1635)
    # Font: Arial (bold via the style flag). Every video approved so far was rendered in Arial — libass never
    # found the per-user Poppins install and fell back silently. Arial ships with every Windows, so the .exe matches.
    head="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,5,2.5,2,70,70,540,1
Style: TBrand,Arial,38,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,6,0,1,3,1.5,8,60,60,560,1
Style: TPart,Arial,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,3,0,1,5,2.5,8,60,60,610,1
Style: TName,Arial,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,740,1
Style: TPartS,Arial,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,620,1
Style: TNameS,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1.5,0,1,3,1.5,8,60,60,750,1
Style: Box,Arial,10,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: EndBig,Arial,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,5,60,60,0,1
Style: EndSub,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1.5,5,60,60,0,1
Style: EndNext,Arial,40,&H00DDDDDD,&H00DDDDDD,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,3,1.5,5,60,60,0,1
Style: Phone,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H64000000,-1,0,0,0,100,100,2,0,3,10,0,8,60,60,436,1
Style: CapHook,Arial,92,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,6,3,2,70,70,540,1
Style: EndAddr,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,3,1.5,5,60,60,0,1
Style: Flash,Arial,10,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Credit,Arial,34,&H40FFFFFF,&H40FFFFFF,&H60000000,&H80000000,0,0,0,0,100,100,1.5,0,1,1.5,1,2,60,60,440,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    big=f"PART {k}" if isinstance(k,int) else TITLE[k]
    small=TITLE[k] if isinstance(k,int) else SUB[k]
    bs="TPart" if len(big)<=13 else "TPartS"   # 104 px fits ~13 chars across 1080 px; longer titles clipped
    ss="TName" if len(small)<=22 else "TNameS"
    title=[f"Dialogue: 2,{ts(0.15)},{ts(3.3)},TBrand,,0,0,0,,{{\\fad(300,350)}}CAR HAULER REPAIR HOUSTON",
           f"Dialogue: 2,{ts(0.25)},{ts(3.3)},{bs},,0,0,0,,{{\\fad(300,350)}}"+big,
           f"Dialogue: 2,{ts(0.40)},{ts(3.3)},{ss},,0,0,0,,{{\\fad(300,350)}}"+small]
    # music credit (boss rule 5): small, bottom (above platform UI), ~5 s at the start, fade in/out
    if k in TRACK:
        title.append(f"Dialogue: 2,{ts(0.8)},{ts(5.8)},Credit,,0,0,0,,{{\\fad(500,700)}}{TRACK[k][1]}")
    # box style: black at ~55% alpha via override
    endev[0]=endev[0].replace("\\p1}","\\1c&H000000&\\1a&H70&\\bord0\\shad0\\p1}")
    open(os.path.join(WORK,f"part{k}.ass"),"w",encoding="utf-8").write(head+"\n".join(title+ev+endev)+"\n")
    return len(ev)
_DIMS={}
def dims(f):
    if f not in _DIMS:
        o=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height:stream_side_data=rotation",
                          "-of","default=nw=1",src(f)],capture_output=True,text=True).stdout
        d=dict(l.split("=",1) for l in o.split() if "=" in l)
        w,h=int(d.get("width",0)),int(d.get("height",0))
        if d.get("rotation","0").lstrip("-") in ("90","270"): w,h=h,w
        _DIMS[f]=(w,h)
    return _DIMS[f]
def fit_mode(f):
    """Small landscape source (e.g. 848x464 from a messenger) -> letterbox, not a 9:16 crop (that would be a 4x upscale)."""
    w,h=dims(f); return w>h and h<720
def fit_filters():
    # whole frame across the width, over a blurred and darkened copy of itself (1.3x upscale for 848x464)
    return ["split=2[fitbg][fitfg];"
            "[fitbg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:2,"
            "eq=brightness=-0.10:saturation=0.9[fitb];"
            "[fitfg]scale=1080:-2:flags=lanczos[fitf];[fitb][fitf]overlay=(W-w)/2:(H-h)/2"]
def has_audio(f):
    return bool(subprocess.run(["ffprobe","-v","error","-select_streams","a","-show_entries","stream=index","-of","csv=p=0",src(f)],capture_output=True,text=True).stdout.strip())
def render(k,budget=160,tag="_v2"):
    import time
    t0=time.time()
    vo,total,segs=layout(k)
    os.makedirs(os.path.join(WORK,f"s{k}{tag}"),exist_ok=True)
    ass=f"part{k}.ass"  # relative: ffmpeg runs with cwd=WORK (Windows drive colon breaks filter args)
    if not os.path.exists(os.path.join(WORK,ass)): print("captions",make_ass(k,vo,total))
    last=len(segs)-1
    for s in segs:
        out=f"s{k}{tag}/{s['i']:02d}.mkv"
        if os.path.exists(os.path.join(WORK,out)): continue
        if time.time()-t0>budget: print("budget hit"); return False
        f=s['file']; lowres=min(dims(f))<720   # messenger-size sources get a stronger sharpen
        z,cx,cy=s['z'] if s['z'] else (1.0,0.5,0.5)
        W,H=int(1080*z)//2*2,int(1920*z)//2*2
        off=s['f0']/FPS; n=s['n']; d=n/FPS
        vf=[]
        if s['sp']!=1: vf.append(f"setpts={1/s['sp']}*PTS")
        trf=out+".trf"
        stab=not (f.startswith("DJI") or "DroneDirections" in src(f))  # boss rule 3: no stab on drone
        pre=",".join(vf+["vidstabdetect=shakiness=6:accuracy=15:stepsize=6:result="+trf])
        if stab: subprocess.run(["ffmpeg","-y","-v","error","-ss",str(s['tin']),"-t",f"{d*s['sp']+0.3:.3f}","-i",src(f),"-vf",pre,"-f","null","-"],check=True,cwd=WORK)
        # optzoom=1 zooms in until no border shows, with no ceiling: on a shaky handheld stretch that was 20-30%,
        # the "too close, cut off at the edge" shots. Capping the correction (4% of the width, ~3 degrees) caps
        # the zoom; a little shake left in beats the subject cropped out.
        if stab: vf.append(f"vidstabtransform=input={trf}:smoothing=14:optzoom=1:zoomspeed=0.2:interpol=bicubic"
                           f":maxshift={max(8, int(0.04 * min(dims(f))))}:maxangle=0.05")
        vf+=(fit_filters() if fit_mode(f) else
             [f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase",
              f"crop=1080:1920:'min(max(iw*{cx}-540,0),iw-1080)':'min(max(ih*{cy}-960,0),ih-1920)'"])
        vf+=[GRADE,
             "unsharp=5:5:0.5:5:5:0.2" if lowres else "null",
             "fps=30",f"setpts=PTS-STARTPTS+{off}/TB",f"ass={ass}"]
        if s['i']==0: vf.append("fade=t=in:st=0:d=0.5")
        if s['i']==last: vf.append(f"fade=t=out:st={total-0.6:.3f}:d=0.6")
        vf+=["setpts=PTS-STARTPTS","format=yuv420p"]
        src_d=d*s['sp']+0.3
        cmd=["ffmpeg","-y","-v","error","-ss",str(s['tin']),"-t",f"{src_d:.3f}","-i",src(f)]
        if has_audio(f):
            af=(f"atempo={s['sp']}," if s['sp']!=1 else "")+"aresample=48000,aformat=channel_layouts=stereo,apad"
            cmd+=["-map","0:v:0","-map","0:a:0","-af",af]
        else:
            cmd+=["-f","lavfi","-t",f"{d:.3f}","-i","anullsrc=r=48000:cl=stereo","-map","0:v:0","-map","1:a:0"]
        cmd+=["-vf",",".join(vf),"-frames:v",str(n),"-t",f"{d:.4f}",
              "-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-g","30",
              "-c:a","pcm_s16le","-ar","48000","-ac","2",out+".tmp.mkv"]
        subprocess.run(cmd,check=True,cwd=WORK); os.replace(os.path.join(WORK,out+".tmp.mkv"),os.path.join(WORK,out))
    print(f"part{k} segments done in {time.time()-t0:.0f}s"); return True
def finish(k,tag="_v2"):
    vo,total,segs=layout(k)
    d=os.path.join(WORK,f"s{k}{tag}").replace("\\","/")
    open(f"{d}/list.txt","w",encoding="utf-8").write("".join(f"file '{d}/{s['i']:02d}.mkv'\n" for s in segs))
    subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{d}/list.txt","-c","copy",f"{d}/cat.mkv"],check=True)
    out=os.path.join(OUT,outname(k,tag))
    fc=(f"[1:a]adelay=600|600,aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,acompressor=threshold=0.09:ratio=3:attack=10:release=220,equalizer=f=3200:t=q:w=1.4:g=2,volume=1.5,asplit=2[vo][vk];"
        f"[vk]apad=whole_dur={total+1}[key];[0:a]highpass=f=95,lowpass=f=11000,volume=0.16[nat];"
        f"[nat][key]sidechaincompress=threshold=0.05:ratio=9:attack=12:release=380[nd];"
        f"[nd][vo]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={total-0.7:.2f}:d=0.7,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg","-y","-v","error","-i",f"{d}/cat.mkv","-i",vof(k),"-filter_complex",fc,
        "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-ar","48000","-t",f"{total:.3f}","-movflags","+faststart",out],check=True)
    r=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration,size","-of","csv=p=0",out]).decode().strip()
    print("done",out,r)
if __name__=="__main__":
    cmd=sys.argv[1]; k=int(sys.argv[2]) if sys.argv[2].isdigit() else sys.argv[2]
    if cmd=="render": render(k)
    elif cmd=="finish": finish(k)
    elif cmd=="ass":
        vo,total,segs=layout(k); print(make_ass(k,vo,total))

def finish_music(k,target,track=None,src_tag="_v2",out_tag="_v3",blur=False):
    import json
    track=track or TRACK.get(k,("Thunder.mp3",))[0]  # must match the on-screen credit
    vo,total,segs=layout(k)
    d=os.path.join(WORK,f"s{k}{src_tag}").replace("\\","/")
    if not os.path.exists(f"{d}/cat.mkv"):
        open(f"{d}/list.txt","w",encoding="utf-8").write("".join(f"file '{d}/{s['i']:02d}.mkv'\n" for s in segs))
        subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{d}/list.txt","-c","copy",f"{d}/cat.mkv"],check=True)
    if blur:  # boss rule 7: no recognizable faces
        import faces
        src=f"{d}/cat.mkv"; bl=f"{d}/cat_blur.mkv"
        if not os.path.exists(bl):
            win=[(s["f0"]/FPS-0.2,(s["f0"]+s["n"])/FPS+0.2) for s in segs
                 if any(p in s["file"] for p in PEOPLE)]  # only look where people can be
            n=faces.blur_faces(src,bl,manual=BLUR.get(k,()),windows=win or None)
            print("face-blur: masked frames",n)
        if os.path.exists(bl): cat=bl
        else: cat=f"{d}/cat.mkv"
    else: cat=f"{d}/cat.mkv"
    if k in LOGO:  # partner logo (Cottrell video): on each spoken brand word + on the end card
        lg=f"{d}/cat_logo.mkv"
        if not os.path.exists(lg):
            path,word,w_px=LOGO[k]
            wins=[]
            for (ww,st,en) in A[str(k)]:
                if ww.split("(")[0]==word and st+PRE>3.4:          # not over the opening title
                    a,b=st+PRE-0.1,st+PRE+2.0
                    if wins and a<=wins[-1][1]+0.3: wins[-1][1]=b
                    else: wins.append([a,b])
            e0=PRE+vo+0.15; wins=[x for x in wins if x[0]<e0-0.5]
            wins=[[a,min(b,e0-0.1)] for a,b in wins]+[[e0+0.1,total]]
            n=len(wins)
            fc=f"[1:v]scale={w_px}:-1,format=rgba,split={n}"+"".join(f"[l{i}]" for i in range(n))+";"
            last="0:v"
            for i,(a,b) in enumerate(wins):
                fc+=(f"[l{i}]fade=in:st={a:.2f}:d=0.25:alpha=1,fade=out:st={max(a,b-0.25):.2f}:d=0.25:alpha=1[f{i}];"
                     f"[{last}][f{i}]overlay=(W-w)/2:{520 if i<n-1 else 560}:enable='between(t,{a:.2f},{b:.2f})'[o{i}];")
                last=f"o{i}"
            subprocess.run(["ffmpeg","-y","-v","error","-i",cat,"-loop","1","-framerate",str(FPS),"-t",f"{total+0.5:.2f}","-i",path,
                            "-filter_complex",fc.rstrip(";"),"-map",f"[{last}]","-map","0:a","-c:a","copy",
                            "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",lg],check=True)
            print("logo windows",[(round(a,1),round(b,1)) for a,b in wins])
        cat=lg
    bt=json.load(open(os.path.join(PIPE,"beats",os.path.splitext(track)[0]+".json")))  # per-track beats (librosa)
    b=min((x for x in bt if x-PRE>=0), key=lambda x: abs(x-target))
    off=b-PRE
    out=os.path.join(OUT,outname(k,out_tag))
    fc=(f"[1:a]adelay=600|600,aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,acompressor=threshold=0.09:ratio=3:attack=10:release=220,equalizer=f=3200:t=q:w=1.4:g=2,volume=1.5,asplit=2[vo][vk];"
        f"[vk]apad=whole_dur={total+1}[key];"
        f"[0:a]highpass=f=95,lowpass=f=11000,volume=0.05[nat];"
        f"[2:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.225,afade=t=in:st=0:d=0.4,afade=t=out:st={total-1.6:.2f}:d=1.6[mus];"
        f"[mus][key]sidechaincompress=threshold=0.05:ratio=4:attack=25:release=400[md];"
        f"[nat][md][vo]amix=inputs=3:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg","-y","-v","error","-i",cat,"-i",vof(k),"-ss",f"{off:.3f}","-t",f"{total+0.5:.3f}","-i",os.path.join(MUSIC,track),
        "-filter_complex",fc,"-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-ar","48000","-t",f"{total:.3f}","-movflags","+faststart",out],check=True)
    print("done",out,f"music offset {off:.2f}s")
