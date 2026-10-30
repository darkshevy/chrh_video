import numpy as np, onnxruntime as ort, subprocess, sys, time, json, os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from paths import MUSIC,PIPE
NFFT=7680; HOP=1024; DF=3072; DT=256; SR=44100
CH=HOP*(DT-1)
sess=ort.InferenceSession(os.path.join(PIPE,'voc.onnx'),providers=['CPUExecutionProvider'])
win=np.hanning(NFFT+1)[:-1].astype(np.float32)
def load(path,ss,dur):
    raw=subprocess.run(["ffmpeg","-v","error","-ss",str(ss),"-t",str(dur),"-i",path,"-ar",str(SR),"-ac","2","-f","f32le","-"],capture_output=True).stdout
    return np.frombuffer(raw,np.float32).reshape(-1,2).T
def stft(x):
    pad=NFFT//2
    x=np.pad(x,((0,0),(pad,pad)),mode='reflect')
    n=1+(x.shape[1]-NFFT)//HOP
    idx=np.arange(NFFT)[None,:]+HOP*np.arange(n)[:,None]
    fr=x[:,idx]*win  # (2,n,NFFT)
    return np.fft.rfft(fr,axis=2).transpose(0,2,1)  # (2,bins,n)
def vocal_frames(path,ss):
    x=load(path,ss,CH/SR)
    if x.shape[1]<CH: x=np.pad(x,((0,0),(0,CH-x.shape[1])))
    S=stft(x)[:,:DF,:DT]
    inp=np.stack([S[0].real,S[0].imag,S[1].real,S[1].imag])[None].astype(np.float32)
    out=sess.run(None,{'input':inp})[0][0]
    ein=(inp[0]**2).sum(axis=(0,1)); eout=(out**2).sum(axis=(0,1))
    # band-limited 200-4000Hz
    b0,b1=int(200*NFFT/SR),int(4000*NFFT/SR)
    ein_b=(inp[0][:,b0:b1]**2).sum(axis=(0,1)); eout_b=(out[:,b0:b1]**2).sum(axis=(0,1))
    return eout.sum()/ein.sum(), eout_b/(ein_b+1e-9)
if __name__=="__main__":
    U=MUSIC+os.sep
    tracks=sys.argv[1].split(",")
    res={}
    for t in tracks:
        p=U+t.replace("_"," ")+".mp3"
        d=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]))
        rs=[];fr=[]
        for x in (0.3,0.55,0.8):
            r,band=vocal_frames(p,d*x)
            rs.append(round(float(r),3)); fr.append(round(float((band>0.25).mean()),2))
        res[t]=dict(ratio=rs,vocal_frac=fr)
        print(t,rs,fr,flush=True)
    old=json.load(open(os.path.join(PIPE,'vd.json'))) if __import__('os').path.exists(os.path.join(PIPE,'vd.json')) else {}
    old.update(res); json.dump(old,open(os.path.join(PIPE,'vd.json'),'w'))
