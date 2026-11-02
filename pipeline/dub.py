# Voice a finished montage with a script that arrives after it.
#
# The boss picks the shots first and writes the text later, so the video's length is fixed and the text has to
# fit it, not the other way round:
#   1. the text is taken as he sends it (paragraphs, exclamation marks, the phone number); the phone number
#      becomes "the number on screen" — read aloud, digits come out unpredictably, and it is on screen anyway
#   2. if it is clearly longer than the video can carry, Claude shortens it to fit: his words and facts, nothing
#      added
#   3. ElevenLabs records it (voice.py, same voice and settings as the voiced videos)
#   4. a voice still a little long is sped up, at most 15 %; it may run on into the black end card
#   5. the voice is laid under the video with the same processing as the voiced videos -> ..._voiced.mp4
#      (the silent montage is kept)
#
#   python pipeline\dub.py output\CHRH_Deckinginstallation_montage_v1.mp4 work\dub\text.txt
import os, sys, re, json, time, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MODEL = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"
WPS = 2.6           # words per second this voice reads at (script.py measures the same)
START = 0.5         # the voice starts after the title has appeared
END_CARD = 2.0      # montage.END: black card at the end, the voice may run into it
MAX_TEMPO = 1.15
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path], text=True).strip())


def clean(text):
    """One paragraph, the phone number replaced, no line breaks."""
    t = PHONE.sub("the number on screen", text)
    return re.sub(r"\s+", " ", t).strip()


def shorten(text, words, key):
    """Claude cuts the text to about `words` words without adding anything."""
    prompt = (f"This voice-over has to fit a short video: about {words} words, read aloud. It now has "
              f"{len(text.split())}. Shorten it.\n\nRules: keep the owner's wording and facts; cut, do not "
              "rewrite; add nothing new — no brands, numbers or claims that are not in the text. Keep the shop "
              "name 'Car Hauler Repair Houston' once and a short call to action at the end ('call the number on "
              "screen'). No digits: write numbers as words. One paragraph.\n\nReply with the shortened text "
              f"only.\n\nTEXT:\n{text}")
    body = json.dumps({"model": MODEL, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            return " ".join("".join(p.get("text", "") for p in data.get("content", [])).split()).strip('"')
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise


def main():
    if len(sys.argv) < 3: sys.exit("usage: python pipeline\\dub.py VIDEO.mp4 TEXT.txt")
    video, tpath = (os.path.abspath(a) for a in sys.argv[1:3])
    if not os.path.exists(video): sys.exit(f"no such video: {video}")
    raw = open(tpath, encoding="utf-8-sig").read()
    text = clean(raw)
    if not text: sys.exit("the text file is empty")

    D = duration(video)
    room = D - START - END_CARD - 0.2          # seconds of picture before the black card
    words = len(text.split())
    print(f"video {D:.1f} s, room for the voice ~{room:.1f} s (~{int(room * WPS)} words); the text has {words} words")
    # shorten only what a speed-up cannot absorb: every word of his kept is worth more than a perfect fit
    if words > room * WPS * (MAX_TEMPO - 0.03):
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key: sys.exit("the text is too long for the video and there is no ANTHROPIC_API_KEY to shorten it")
        target = int(room * WPS * 0.97)
        text = shorten(text, target, key)
        print(f"\nshortened to {len(text.split())} words:\n  {text}\n")
    if re.search(r"\d", text): print("note: the text still has digits; the voice may read them oddly")

    # record through voice.py: same voice, model and settings as every other voice-over
    stem = os.path.splitext(os.path.basename(video))[0]
    dkey = "dub_" + re.sub(r"[^a-z0-9_]", "", stem.lower())
    d = os.path.join(ROOT, "work", "dub"); os.makedirs(d, exist_ok=True)
    spath = os.path.join(d, f"{dkey}.txt")
    open(spath, "w", encoding="utf-8").write(f"=== {dkey} | DUB | DUB | Thunder\n{text}\n")
    open(os.path.join(d, f"{dkey}_text.txt"), "w", encoding="utf-8").write(text + "\n")
    if subprocess.call([sys.executable, os.path.join(HERE, "voice.py"), spath, dkey, "--force"]) != 0:
        sys.exit("the voice-over did not record")
    from paths import VOICE
    mp3 = os.path.join(VOICE, f"{dkey}.mp3")

    L = duration(mp3)
    can = D - START - 0.3                      # to the very end, over the black card if it must
    tempo = 1.0
    if L > room:
        tempo = min(MAX_TEMPO, L / room)
        if L / tempo > can:
            sys.exit(f"the voice is {L:.1f} s even at {MAX_TEMPO:.2f}x and the video is {D:.1f} s — shorten the "
                     f"text, or build the montage longer ([N], about {L + START + END_CARD:.0f} s)")
        print(f"voice {L:.1f} s, sped up {tempo:.2f}x to fit")
    else:
        print(f"voice {L:.1f} s, fits")

    out = os.path.splitext(video)[0] + "_voiced.mp4"
    ms = int(START * 1000)
    # the voice chain of build.finish_music: highpass, compressor, presence; loudness as the voiced videos
    af = (("atempo=%.4f," % tempo if tempo != 1.0 else "") +
          f"adelay={ms}|{ms},aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,"
          "acompressor=threshold=0.09:ratio=3:attack=10:release=220,equalizer=f=3200:t=q:w=1.4:g=2,"
          "volume=1.5,apad,loudnorm=I=-14:TP=-1.5")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", mp3, "-filter_complex", f"[1:a]{af}[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{D:.3f}", "-movflags", "+faststart", out], check=True)
    print(f"\ndone: output\\{os.path.basename(out)}  ({D:.1f} s, voice {L / tempo:.1f} s)")


if __name__ == "__main__":
    main()
