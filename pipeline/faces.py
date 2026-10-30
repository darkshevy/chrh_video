# Boss rule 7 (09-23): people in frame must not be recognizable — light blur over faces.
# Two-pass: detect faces on the already-rendered cut, build a soft mask video, blur only inside the mask.
# Manual boxes (plan.BLUR) are merged in, for shots where the detector finds nothing (caps, hoods, profiles).
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
from paths import WORK

PAD = 0.28        # box padding (fraction of face size) — covers cap/chin/ear, stays off the rest of the shot
HOLD = 14         # frames a box stays alive after the last detection (~0.5 s) — bridges gaps when a
                  # face turns away or a cap hides it; low score + hold beats a missed face
MINFRAC = 0.018   # ignore detections smaller than this fraction of frame height (noise)
MAXFRAC = 0.22    # ignore absurdly large boxes (false positives on texture/shadow)
CAPTION = (1240, 1440)  # never blur the caption band

from paths import PIPE as _PIPE
MODEL = os.path.join(_PIPE,
                     "models", "face_detection_yunet_2023mar.onnx")  # opencv_zoo YuNet

def _skinish(frame, x, y, w, h):
    """Round steel (hubs, hinge holes, bolt heads) reads as a face for the detector.
    A real face has skin pixels: hue near red/orange with MODERATE saturation.
    Painted red steel is the same hue but almost fully saturated, so it fails this test."""
    H, W = frame.shape[:2]
    x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + w, W), min(y + h, H)
    if x1 - x0 < 4 or y1 - y0 < 4: return False
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    skin = (((hh <= 25) | (hh >= 165)) & (ss >= 30) & (ss <= 170) & (vv >= 60))
    return skin.mean() >= 0.15

def detect(video, step=2, score=0.35, windows=None, fps=30):  # profile faces under caps score ~0.4-0.55;
    # the low threshold is safe because `windows` already limits the search to shots that contain people
    """-> ({frame_index: [(x,y,w,h), ...]}, frame_count) on the video's own pixel grid.
    `windows` limits the search to [(t0,t1)] seconds — shots whose source clip has people in it.
    Outside those windows nothing is detected, which keeps hubs/hinge holes from being blurred."""
    cap = cv2.VideoCapture(video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    det = cv2.FaceDetectorYN.create(MODEL, "", (W, H), score, 0.3, 5000)
    out, i = {}, 0
    while True:
        ok, frame = cap.read()
        if not ok: break
        t = i / fps
        inw = windows is None or any(a <= t <= b for a, b in windows)
        if i % step == 0 and inw:
            _, f = det.detect(frame)
            if f is not None and len(f):
                boxes = []
                for r in f:
                    x, y, w, h = (int(v) for v in r[:4])
                    if H * MINFRAC <= h <= H * MAXFRAC and _skinish(frame, x, y, w, h):
                        boxes.append((x, y, w, h))
                if boxes: out[i] = boxes
        i += 1
    cap.release()
    return out, i

def mask_video(video, boxes, nframes, out_path, manual=(), fps=30):
    """White (blurred later) rectangles on black, one frame per source frame."""
    cap = cv2.VideoCapture(video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                          "-pix_fmt", "yuv420p", out_path], stdin=subprocess.PIPE)
    live = []  # (box, frames_left)
    for i in range(nframes):
        if i in boxes:
            live = [(b, HOLD) for b in boxes[i]] + [(b, n - 1) for b, n in live if n > 1]
        else:
            live = [(b, n - 1) for b, n in live if n > 1]
        m = np.zeros((H, W), np.uint8)
        for (x, y, w, h), _ in live:
            px, py = int(w * PAD), int(h * PAD)
            cv2.rectangle(m, (max(x - px, 0), max(y - py, 0)),
                          (min(x + w + px, W), min(y + h + py, H)), 255, -1)
        m[CAPTION[0]:CAPTION[1], :] = 0  # keep captions sharp
        t = i / fps
        for (t0, t1, x, y, w, h) in manual:
            if t0 <= t <= t1: cv2.rectangle(m, (x, y), (x + w, y + h), 255, -1)
        p.stdin.write(m.tobytes())
    p.stdin.close(); p.wait()
    return out_path

def blur_faces(src, dst, manual=(), radius=16, windows=None):
    """Detect + blur. Returns number of frames that carry a mask (0 = nothing found)."""
    boxes, n = detect(src, windows=windows)
    if not boxes and not manual:
        return 0
    mask = os.path.join(WORK, "mask_tmp.mp4")
    mask_video(src, boxes, n, mask, manual)
    fc = (f"[0:v]split=2[base][t];[t]boxblur=luma_radius={radius}:luma_power=2[bl];"
          "[1:v]format=gray,boxblur=8:1[m];[bl][m]alphamerge[blm];[base][blm]overlay=format=auto[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-i", mask, "-filter_complex", fc,
           "-map", "[v]"]
    if subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                       "stream=index", "-of", "csv=p=0", src], capture_output=True,
                      text=True).stdout.strip():
        cmd += ["-map", "0:a", "-c:a", "copy"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", dst]
    subprocess.run(cmd, check=True)
    os.remove(mask)
    return len(boxes)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    print("frames with faces:", blur_faces(src, dst))
