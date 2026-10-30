# "Живой" кадр: в кадре есть движение (камера или работа), он резкий и не дёрганый.
# Меряем на ИСХОДНИКЕ (у готового ролика мешают вшитые субтитры и апскейл).
#   motion  — median |frame(t) - frame(t+0.2 s)|, grayscale 180 px wide, 0..255
#   sharp25 — 25-й перцентиль дисперсии лапласиана (фокус), grayscale 360 px wide
# Калибровка 09-23 по кадрам, просмотренным глазами:
#   хорошие: сварка 16/4042, дуга 9/893, рабочий 9/997, дрон в цеху 13/1802, болгарка 19/834
#   плохие : размытый пол 16/11, блик 24/382, мыльные крупные планы Miller 23/388-420, ступица 25/421
import cv2, numpy as np

def measure(path, t0, t1):
    cap = cv2.VideoCapture(path); cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int((t1 - t0) * fps); fr = []; i = 0
    while i < n:
        ok, x = cap.read()
        if not ok: break
        if i % 3 == 0:
            g = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY); h = int(g.shape[0] * 360 / g.shape[1])
            fr.append(cv2.resize(g, (360, h), interpolation=cv2.INTER_AREA))
        i += 1
    cap.release()
    st = max(1, int(round(0.2 * fps / 3)))
    if len(fr) <= st + 1: return 0.0, 0.0
    small = [cv2.resize(x, (180, x.shape[0] // 2)).astype(np.int16) for x in fr]
    mot = [np.abs(small[j] - small[j + st]).mean() for j in range(len(small) - st)]
    shp = [cv2.Laplacian(x, cv2.CV_64F).var() for x in fr]
    return float(np.median(mot)), float(np.percentile(shp, 25))

def grade(mot, shp):
    if shp < 450: return "SOFT"
    if mot > 23: return "SHAKY"
    if mot < 3: return "STATIC"
    if shp < 700 or mot > 20: return "ok"
    return "LIVE"
