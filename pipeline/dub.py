# Voice a finished video with a script that arrives after it — a montage from [N] or a video edited by hand.
#
# The video comes first, the text later, so the video's length is fixed and the text has to fit it:
#   1. the text is taken as the boss sends it; the phone number becomes "the number on screen" (read aloud,
#      digits come out unpredictably, and it is on screen anyway)
#   2. a text clearly too long even for a sped-up voice is shortened by Claude: his words and facts, nothing added
#   3. ElevenLabs records it with word timings (same voice and settings as voice.py); a voice a little long is
#      sped up, at most 15 %
#   4. the standard look of the voiced videos goes on top:
#        word-by-word captions — always
#        a video edited by hand also gets: 1080x1920, the title at the start (Claude names the repair from the
#        text), the phone bar, 2 s of black with name, phone and address at the end, the boss's music under the
#        voice with its credit, the video's own sound at 5 % (boss rule 4)
#        a montage from [N] has title, phone bar and end card already; it gets captions and the voice
#   -> output\<name>_voiced.mp4; the video it came from is kept
#
#   python pipeline\dub.py output\my_edit.mp4 work\dub\text.txt
#   --landscape    a 1920x1080 result (horizontal posts), the overlays laid out for the wide frame
import os, sys, re, json, time, base64, random, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from paths import MUSIC, VOICE, WORK

MODEL = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"
XI = "https://api.elevenlabs.io/v1/text-to-speech"
XI_MODEL = "eleven_v4"                 # voice.py: the model, voice and settings the shop approved
VOICE_ID = "Dslrhjl3ZpzrctukrQSN"
STABILITY, SIMILARITY, SPEED = 0.6, 0.4, 1.0
WPS = 2.6           # words per second this voice reads at (script.py measures the same)
START = 0.6         # the voice starts after the title has appeared (build.PRE)
END_CARD = 2.0      # black card at the end (montage.END); the voice may run into it
MAX_TEMPO = 1.15
FPS = 30
PHONE_TXT, ADDRESS = "(832) 708-5492", "6716 Long Drive, Houston, TX 77087"
TRACKS = ["Thunder", "Hollywood waves", "Kama Sutra", "Fields of space", "Another Day", "Symphony one",
          "Hyde and seek"]       # the boss's instrumental tracks (CLAUDE.md: verified without vocals)
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path], text=True).strip())


def probe(path):
    """(width, height, has audio) as the picture is shown (phone rotation applied)."""
    o = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                 "stream=codec_type,width,height:stream_side_data=rotation", "-of", "json", path], text=True)
    st = json.loads(o).get("streams", [])
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    w, h = int(v.get("width", 1080)), int(v.get("height", 1920))
    rot = str(next((d.get("rotation") for d in v.get("side_data_list", []) if "rotation" in d), "0"))
    if rot.lstrip("-") in ("90", "270"): w, h = h, w
    return w, h, any(s.get("codec_type") == "audio" for s in st)


def clean(text):
    """One paragraph, the phone number replaced, no line breaks."""
    t = PHONE.sub("the number on screen", text)
    return re.sub(r"\s+", " ", t).strip()


def claude(prompt, key, max_tokens=2000):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            return "".join(p.get("text", "") for p in data.get("content", [])).strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise


def shorten(text, words, key):
    """Claude cuts the text to about `words` words without adding anything."""
    out = claude(f"This voice-over has to fit a short video: about {words} words, read aloud. It now has "
                 f"{len(text.split())}. Shorten it.\n\nRules: keep the owner's wording and facts; cut, do not "
                 "rewrite; add nothing new — no brands, numbers or claims that are not in the text. Keep the shop "
                 "name 'Car Hauler Repair Houston' once and a short call to action at the end ('call the number on "
                 "screen'). No digits: write numbers as words. One paragraph.\n\nReply with the shortened text "
                 f"only.\n\nTEXT:\n{text}", key)
    return " ".join(out.split()).strip('"')


def title_of(text, key):
    """(TITLE, SUB) for the opening card, from the text; a plain fallback without a key."""
    if key:
        try:
            out = claude("Name this car hauler repair video for its opening title card. Reply with JSON only: "
                         '{"title": "2-4 words, max 22 characters, capitals", "sub": "max 30 characters, capitals, '
                         'the gist"}. Only what the text says.\n\nTEXT:\n' + text, key, 300)
            a, b = out.find("{"), out.rfind("}")
            d = json.loads(out[a:b + 1])
            return str(d.get("title", "")).upper()[:22].strip(), str(d.get("sub", "")).upper()[:30].strip()
        except Exception as e:
            print(f"(no title from Claude: {e})")
    return "CAR HAULER REPAIR", ""


# ------------------------------------------------------------------ the voice
def record(text, out):
    """ElevenLabs with timestamps -> mp3 at `out`, [(word, start, end)]. Without timings (another route, an
    error) the words are spread over the audio by their length — rougher captions, but captions."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key: raise RuntimeError("no ELEVENLABS_API_KEY")
    body = json.dumps({"text": text, "model_id": XI_MODEL,
                       "voice_settings": {"stability": STABILITY, "similarity_boost": SIMILARITY,
                                          "speed": SPEED, "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"{XI}/{VOICE_ID}/with-timestamps", data=body, headers={
        "xi-api-key": key, "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"ElevenLabs HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    open(out, "wb").write(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    return words_from_chars(al.get("characters", []), al.get("character_start_times_seconds", []),
                            al.get("character_end_times_seconds", [])) or spread(text, duration(out))


def words_from_chars(chars, starts, ends):
    words, cur, t0, t1 = [], "", None, None
    for ch, a, b in zip(chars, starts, ends):
        if ch.isspace():
            if cur: words.append((cur, t0, t1)); cur = ""
            continue
        if not cur: t0 = a
        cur += ch; t1 = b
    if cur: words.append((cur, t0, t1))
    return words


def spread(text, dur):
    ws = text.split()
    total = sum(len(w) + 1 for w in ws)
    t, out = 0.15, []
    for w in ws:
        d = (dur - 0.3) * (len(w) + 1) / total
        out.append((w, t, t + d * 0.92)); t += d
    return out


# ------------------------------------------------------------------ the overlays
ASS_HEAD = """[Script Info]
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
Style: EndBig,Arial,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,5,60,60,0,1
Style: EndSub,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1.5,5,60,60,0,1
Style: EndAddr,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,3,1.5,5,60,60,0,1
Style: Phone,Arial,46,&H0023A6F5,&H0023A6F5,&H00000000,&H64000000,-1,0,0,0,100,100,2,0,3,10,0,8,60,60,436,1
Style: Credit,Arial,34,&H40FFFFFF,&H40FFFFFF,&H60000000,&H80000000,0,0,0,0,100,100,1.5,0,1,1.5,1,2,60,60,440,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# The same look laid out for a 1920x1080 frame (horizontal posts): captions low and wider, title top centre
# under the phone bar, end card centred, the music credit small in the bottom-left corner.
ASS_HEAD_LAND = ASS_HEAD.replace("PlayResX: 1080\nPlayResY: 1920", "PlayResX: 1920\nPlayResY: 1080")
for _old, _new in [
        ("Style: Cap,Arial,84,", "Style: Cap,Arial,72,"), (",2,70,70,540,1\nStyle: TBrand", ",2,120,120,70,1\nStyle: TBrand"),
        (",8,60,60,560,1\nStyle: TPart,", ",8,60,60,120,1\nStyle: TPart,"), ("Style: TPart,Arial,104,", "Style: TPart,Arial,90,"),
        (",8,60,60,610,1\nStyle: TName,", ",8,60,60,160,1\nStyle: TName,"), ("Style: TName,Arial,62,", "Style: TName,Arial,52,"),
        (",8,60,60,740,1\nStyle: TPartS", ",8,60,60,270,1\nStyle: TPartS"), (",8,60,60,620,1\nStyle: TNameS", ",8,60,60,170,1\nStyle: TNameS"),
        (",8,60,60,750,1\nStyle: EndBig", ",8,60,60,270,1\nStyle: EndBig"),
        (",8,60,60,436,1\nStyle: Credit", ",8,60,60,30,1\nStyle: Credit"),
        ("Style: Credit,Arial,34,&H40FFFFFF,&H40FFFFFF,&H60000000,&H80000000,0,0,0,0,100,100,1.5,0,1,1.5,1,2,60,60,440,1",
         "Style: Credit,Arial,30,&H40FFFFFF,&H40FFFFFF,&H60000000,&H80000000,0,0,0,0,100,100,1.5,0,1,1.5,1,1,50,60,30,1")]:
    assert _old in ASS_HEAD_LAND, _old
    ASS_HEAD_LAND = ASS_HEAD_LAND.replace(_old, _new, 1)


def ts(t):
    t = max(t, 0.0); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def captions(words, per_line=3):
    """Word-by-word captions as in build.make_ass: three words at a time, the spoken and past ones solid,
    the coming ones dimmed; a new group at punctuation or a pause."""
    groups, cur = [], []
    for i, (w, a, b) in enumerate(words):
        if cur:
            pw, pa, pb = words[cur[-1]]
            if len(cur) >= per_line or re.search(r"[.,:;?!]$", pw) or a - pb > 0.25:
                groups.append(cur); cur = []
        cur.append(i)
    if cur: groups.append(cur)
    show = lambda w: re.sub(r"[.,:;]", "", w).replace("{", "").replace("}", "")
    ev = []
    for gi, g in enumerate(groups):
        nxt = words[groups[gi + 1][0]][1] if gi + 1 < len(groups) else None
        for j, wi in enumerate(g):
            st = words[wi][1]
            if j + 1 < len(g): en = words[g[j + 1]][1]
            else:
                en = words[wi][2] + 0.35
                if nxt is not None: en = min(en, nxt)
            parts = ["{\\alpha" + ("&H00&" if jj <= j else "&H9A&") + "}" + show(words[w2][0]) for jj, w2 in enumerate(g)]
            ev.append(f"Dialogue: 1,{ts(st)},{ts(max(en, st + 0.05))},Cap,,0,0,0,," + " ".join(parts))
    return ev


def overlays(total, title, sub, credit, land=False):
    """Title, phone bar, end card and music credit — the voiced videos' layout (build.make_ass)."""
    e0 = total - END_CARD
    cx, y1, y2, y3 = (960, 430, 600, 670) if land else (540, 860, 1075, 1160)     # end card lines
    ev = [f"Dialogue: 2,{ts(0.15)},{ts(3.3)},TBrand,,0,0,0,,{{\\fad(300,350)}}CAR HAULER REPAIR HOUSTON",
          f"Dialogue: 2,{ts(0.25)},{ts(3.3)},{'TPart' if len(title) <= 13 else 'TPartS'},,0,0,0,,{{\\fad(300,350)}}{title}"]
    if sub: ev.append(f"Dialogue: 2,{ts(0.40)},{ts(3.3)},{'TName' if len(sub) <= 22 else 'TNameS'},,0,0,0,,{{\\fad(300,350)}}{sub}")
    ev += [f"Dialogue: 2,{ts(e0 + 0.1)},{ts(total + 0.1)},EndBig,,0,0,0,,{{\\fad(350,0)\\pos({cx},{y1})}}CAR HAULER\\NREPAIR HOUSTON",
           f"Dialogue: 2,{ts(e0 + 0.3)},{ts(total + 0.1)},EndSub,,0,0,0,,{{\\fad(350,0)\\pos({cx},{y2})}}CALL {PHONE_TXT}",
           f"Dialogue: 2,{ts(e0 + 0.5)},{ts(total + 0.1)},EndAddr,,0,0,0,,{{\\fad(350,0)\\pos({cx},{y3})}}{ADDRESS}",
           f"Dialogue: 3,{ts(0.0)},{ts(e0 + 0.2)},Phone,,0,0,0,,{{\\fad(400,300)}}CALL {PHONE_TXT}"]
    if credit: ev.append(f"Dialogue: 2,{ts(0.8)},{ts(5.8)},Credit,,0,0,0,,{{\\fad(500,700)}}{credit}")
    return ev


def find_track(seed):
    """One of the boss's instrumental tracks, picked by the video's name so a re-run keeps the same one."""
    have = {}
    for f in os.listdir(MUSIC) if os.path.isdir(MUSIC) else []:
        k = re.sub(r"[^a-z]", "", os.path.splitext(f)[0].lower())
        if f.lower().endswith((".mp3", ".wav", ".m4a")): have[k] = f
    names = [t for t in TRACKS if re.sub(r"[^a-z]", "", t.lower()) in have]
    if not names: return None, None, 0.0
    t = random.Random(seed).choice(names)
    f = os.path.join(MUSIC, have[re.sub(r"[^a-z]", "", t.lower())])
    off = 0.0
    try:   # start on a beat near 30 s into the track, as the voiced videos do
        bt = json.load(open(os.path.join(HERE, "beats", t + ".json")))
        off = max(0.0, min(bt, key=lambda x: abs(x - 30.0)) - START)
    except Exception:
        pass
    return f, t, off


# ------------------------------------------------------------------ run
def main():
    if len(sys.argv) < 3: sys.exit("usage: python pipeline\\dub.py VIDEO.mp4 TEXT.txt")
    video, tpath = (os.path.abspath(a) for a in sys.argv[1:3])
    if not os.path.exists(video): sys.exit(f"no such video: {video}")
    text = clean(open(tpath, encoding="utf-8-sig").read())
    if not text: sys.exit("the text file is empty")
    akey = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    montage = "_montage_" in os.path.basename(video).lower()   # title, phone bar and end card are already in it
    land = "--landscape" in sys.argv and not montage            # 1920x1080 result for horizontal posts
    D0 = duration(video)
    D = D0 if montage else D0 + END_CARD                       # a hand edit gets the black end card added
    room = D - START - END_CARD - 0.2
    words = len(text.split())
    print(f"{'montage' if montage else 'your video'}: {D0:.1f} s"
          + ("" if montage else f" + {END_CARD:.0f} s end card") +
          f"; room for the voice ~{room:.1f} s (~{int(room * WPS)} words); the text has {words} words")
    # shorten only what a speed-up cannot absorb: every word of his kept is worth more than a perfect fit
    if words > room * WPS * (MAX_TEMPO - 0.03):
        if not akey: sys.exit("the text is too long for the video and there is no ANTHROPIC_API_KEY to shorten it")
        text = shorten(text, int(room * WPS * 0.97), akey)
        print(f"\nshortened to {len(text.split())} words:\n  {text}\n")
    if re.search(r"\d", text): print("note: the text still has digits; the voice may read them oddly")

    stem = os.path.splitext(os.path.basename(video))[0]
    os.makedirs(VOICE, exist_ok=True)
    mp3 = os.path.join(VOICE, "dub_" + re.sub(r"[^a-z0-9_]", "", stem.lower()) + ".mp3")
    print("recording the voice-over…")
    timed = record(text, mp3)
    L = duration(mp3)
    tempo = 1.0
    if L > room:
        tempo = min(MAX_TEMPO, L / room)
        if L / tempo > D - START - 0.3:
            sys.exit(f"the voice is {L:.1f} s even at {MAX_TEMPO:.2f}x and the video is {D:.1f} s — shorten the "
                     f"text, or make the video about {L + START + END_CARD:.0f} s")
        print(f"voice {L:.1f} s, sped up {tempo:.2f}x to fit")
    else:
        print(f"voice {L:.1f} s, fits")
    timed = [(w, START + a / tempo, START + b / tempo) for (w, a, b) in timed]

    title, sub = ("", "") if montage else title_of(text, akey)
    track, tname, toff = (None, None, 0.0) if montage else find_track(stem)
    credit = f"DJ KOZ LOVE  ·  {tname}" if tname else ""
    d = os.path.join(WORK, "dub"); os.makedirs(d, exist_ok=True)
    ass = os.path.join(d, stem + ".ass")
    open(ass, "w", encoding="utf-8").write((ASS_HEAD_LAND if land else ASS_HEAD) + "\n".join(
        ([] if montage else overlays(D, title, sub, credit, land)) + captions(timed, 5 if land else 3)) + "\n")
    if not montage: print(f"title: {title}" + (f" / {sub}" if sub else "") + (f"; music: {tname}" if tname else ""))

    w, h, has_audio = probe(video)
    out = os.path.splitext(video)[0] + "_voiced.mp4"
    rel = os.path.relpath(ass, WORK).replace("\\", "/")        # ffmpeg runs in work\: a drive colon breaks filters
    ms = int(START * 1000)
    vo = (("atempo=%.4f," % tempo if tempo != 1.0 else "") +
          f"adelay={ms}|{ms},aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,"
          "acompressor=threshold=0.09:ratio=3:attack=10:release=220,equalizer=f=3200:t=q:w=1.4:g=2,volume=1.5")
    if montage:
        fc = f"[0:v]ass={rel}[v];[1:a]{vo},apad[vo];[vo]loudnorm=I=-14:TP=-1.5[a]"
        cmd = ["-i", video, "-i", mp3]
    else:
        # the picture: 1080x1920 (a landscape edit whole over a blurred copy), then 2 s of black for the card
        W_, H_ = (1920, 1080) if land else (1080, 1920)
        if land and w >= h:
            pic = "scale=1920:1080:flags=lanczos:force_original_aspect_ratio=increase,crop=1920:1080"
        elif land:     # a vertical edit in a horizontal post: whole, over a blurred copy
            pic = ("split=2[bg][fg];[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                   "boxblur=28:2,eq=brightness=-0.10:saturation=0.9[b];[fg]scale=-2:1080:flags=lanczos[f];"
                   "[b][f]overlay=(W-w)/2:(H-h)/2")
        elif w > h:
            pic = ("split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                   "boxblur=28:2,eq=brightness=-0.10:saturation=0.9[b];[fg]scale=1080:-2:flags=lanczos[f];"
                   "[b][f]overlay=(W-w)/2:(H-h)/2")
        else:
            pic = "scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase,crop=1080:1920"
        fc = (f"[0:v]{pic},fps={FPS},format=yuv420p,setsar=1[p];"
              f"color=c=black:s={W_}x{H_}:r={FPS}:d={END_CARD},format=yuv420p,setsar=1[k];"
              f"[p][k]concat=n=2:v=1:a=0,ass={rel}[v];"
              f"[1:a]{vo},asplit=2[vo][vk];[vk]apad=whole_dur={D + 1:.2f}[key];")
        cmd = ["-i", video, "-i", mp3]
        mix, n = ["[vo]"], 1
        if track:
            cmd += ["-ss", f"{toff:.3f}", "-t", f"{D + 0.5:.3f}", "-i", track]
            fc += (f"[2:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.225,afade=t=in:st=0:d=0.4,"
                   f"afade=t=out:st={D - 1.6:.2f}:d=1.6[mus];"
                   "[mus][key]sidechaincompress=threshold=0.05:ratio=4:attack=25:release=400[md];")
            mix.append("[md]"); n += 1
        else:
            fc += "[key]anullsink;"
        if has_audio:
            fc += "[0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=95,lowpass=f=11000,volume=0.05,apad[nat];"
            mix.append("[nat]"); n += 1
        fc += ("".join(mix) + f"amix=inputs={n}:duration=longest:normalize=0," if n > 1 else "[vo]") + \
              "apad,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *cmd, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{D:.3f}", "-movflags", "+faststart", out],
                   check=True, cwd=WORK)
    open(os.path.join(d, stem + "_text.txt"), "w", encoding="utf-8").write(text + "\n")
    print(f"\ndone: output\\{os.path.basename(out)}  ({D:.1f} s, voice {L / tempo:.1f} s)")


if __name__ == "__main__":
    main()
