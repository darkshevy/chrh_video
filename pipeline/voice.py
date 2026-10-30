# Record the voice-overs for a script file through the Magnific API (ElevenLabs Turbo v2.5).
#
# The build needs voiceover\<key>.mp3 for every script, read word for word — the captions are built from the
# text, and the cuts are placed on the aligned words, so a voice that improvises breaks the whole edit. Sending
# the text straight from the script file removes that failure mode: what gets recorded is exactly what is in
# the file, with the [HOOK 2] marker stripped the way a human reader would skip it.
#
# Two routes. With ELEVENLABS_API_KEY set it goes straight to ElevenLabs on v4 — every model is available and
# the audio comes back in one call. Magnific is the fallback (--magnific): one key, but only Turbo v2.5, which
# reads flatly. Either way a paid tier is needed: a free account has no commercial rights, and library voices
# are blocked on it entirely.
#   setx MAGNIFIC_API_KEY "..."
#   setx ELEVENLABS_API_KEY "..."
#
#   python pipeline\voice.py scripts\topics_1027.txt           record whatever has no mp3 yet
#   python pipeline\voice.py scripts\topics_1027.txt upperdeck just this one
#   --magnific       use Magnific instead of ElevenLabs (only has Turbo v2.5)
#   --models         list the model ids your ElevenLabs account can use, then stop
#   --force          record again, overwriting existing mp3 files
#   --voice ID       a different voice for this run
#   --stability 0.6  0 to 1; higher is steadier and flatter, lower is more expressive
#   --speed 1.0      0.7 to 1.2
#   --model NAME     an ElevenLabs model other than the default eleven_turbo_v2_5. Only that one is documented,
#                    but the field is a plain string, so eleven_multilingual_v2, eleven_v3 and eleven_flash_v2_5
#                    are worth trying — an unknown name comes back as an error rather than silently ignored.
import os, sys, json, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()
sys.path.insert(0, HERE)
os.chdir(HERE)
import autoplan
from paths import VOICE

API = "https://api.magnific.com/v1/ai/voiceover"
ENGINE = "elevenlabs-turbo-v2-5"
VOICE_ID = "Dslrhjl3ZpzrctukrQSN"     # Hey Its Brad — clear American narrator
STABILITY = 0.6                        # steady rather than theatrical: these are informational videos
SIMILARITY = 0.4
SPEED = 1.0
XI = "https://api.elevenlabs.io/v1/text-to-speech"
XI_MODEL = "eleven_v4"                 # the one the shop approved; --model switches it


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"): return sys.argv[i + 1]
    return default


def post(url, body, key, method="POST"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"x-magnific-api-key": key, "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


def audio_url(obj):
    """The docs do not pin down where the URL sits, so look for it rather than assume."""
    found = []

    def walk(x):
        if isinstance(x, str) and x.startswith("http") and not found: found.append(x)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj.get("data", obj))
    return found[0] if found else None


# The docs disagree about the path: the method page gives /v1/ai/voiceover/<engine>, the overview page gives
# /v1/ai/voiceover. Try them in turn and remember whichever answers, so only the first clip pays for the probe.
PATHS = [f"{API}/{ENGINE}", API, f"{API}/elevenlabs", "https://api.magnific.com/v1/ai/text-to-speech"]
_good = None


def create(body, apikey, log=print):
    global _good
    tried = []
    for p in ([_good] if _good else PATHS):
        try:
            r = post(p, body, apikey)
            if not _good: log(f"   (endpoint: {p})")
            _good = p
            return r
        except RuntimeError as e:
            tried.append(f"{p} -> {e}")
            if "HTTP 404" not in str(e) and "HTTP 405" not in str(e): raise
    raise RuntimeError("none of the voiceover endpoints answered:\n   " + "\n   ".join(tried))


def record(text, key, apikey, voice, stab, sim, speed, model=None, log=print):
    body = {"text": text, "voice_id": voice, "stability": float(stab),
            "similarity_boost": float(sim), "speed": float(speed), "use_speaker_boost": True}
    if model:
        # Only the engine-specific path exists, so a different model means a different path. Build candidates
        # from the name the way their own path is spelled (hyphens, "elevenlabs-" prefix) and try them.
        global _good, PATHS
        m = model.strip().replace("_", "-")
        if not m.startswith("elevenlabs"): m = "elevenlabs-" + m.removeprefix("eleven-")
        _good = None
        PATHS = [f"{API}/{m}", f"{API}/{model}", f"{API}/{model.replace('_', '-')}"]
        PATHS = list(dict.fromkeys(PATHS))
    task = create(body, apikey, log=log)
    d = task.get("data", task)
    tid = d.get("task_id") or d.get("id")
    if not tid: raise RuntimeError(f"no task id in the reply: {json.dumps(task)[:300]}")
    # status lives either beside the create path or at the root of the service, depending on the doc page
    status_paths = [f"{_good}/{tid}" if _good else None, f"{API}/{tid}", f"{API}/{ENGINE}/{tid}"]
    status_paths = [p for p in dict.fromkeys(x for x in status_paths if x)]
    good_status = None
    for _ in range(120):                    # up to about four minutes
        time.sleep(2)
        st, tried = None, []
        for p in ([good_status] if good_status else status_paths):
            try:
                st = post(p, None, apikey, method="GET")
                if not good_status: log(f"   (status: {p})")
                good_status = p
                break
            except RuntimeError as e:
                tried.append(f"{p} -> {e}")
                if "HTTP 404" not in str(e): raise
        if st is None:
            raise RuntimeError("cannot read the task status:\n   " + "\n   ".join(tried))
        s = (st.get("data", st) or {}).get("status", "")
        if s == "COMPLETED":
            url = audio_url(st)
            if not url: raise RuntimeError(f"finished but no audio url: {json.dumps(st)[:300]}")
            return url
        if s == "FAILED": raise RuntimeError(f"the service reported FAILED: {json.dumps(st)[:300]}")
    raise RuntimeError("timed out waiting for the audio")


# the value that follows an option is not a script key — drop it before reading the keys
TAKES_VALUE = {"--voice", "--stability", "--similarity", "--speed", "--model"}
if "--direct" in sys.argv: pass   # kept for habit; ElevenLabs is the default now
def record_xi(text, apikey, voice, stab, sim, speed, model, log=print):
    """ElevenLabs answers with the audio itself, so there is no task to poll."""
    body = json.dumps({"text": text, "model_id": model or XI_MODEL,
                       "voice_settings": {"stability": float(stab), "similarity_boost": float(sim),
                                          "speed": float(speed), "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"{XI}/{voice}", data=body, headers={
        "xi-api-key": apikey, "content-type": "application/json", "accept": "audio/mpeg"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if attempt < 3: time.sleep(2 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up after retries")


if "--models" in sys.argv:
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not k: sys.exit('set the key first:  $env:ELEVENLABS_API_KEY = "..."')
    rq = urllib.request.Request("https://api.elevenlabs.io/v1/models", headers={"xi-api-key": k})
    with urllib.request.urlopen(rq, timeout=60) as r: ms = json.load(r)
    for m in (ms if isinstance(ms, list) else ms.get("models", [])):
        tts = m.get("can_do_text_to_speech", True)
        print(f'  {m.get("model_id"):32s} {m.get("name","")}' + ("" if tts else "   (not text-to-speech)"))
    sys.exit(0)

args, skip = [], False
for a in sys.argv[1:]:
    if skip: skip = False; continue
    if a.startswith("--"):
        skip = a in TAKES_VALUE
        continue
    args.append(a)
if not args: sys.exit("usage: python pipeline\\voice.py SCRIPTS.txt [KEY ...] [--force]")
spath = args[0]; spath = spath if os.path.isabs(spath) else os.path.join(START, spath)
wanted = [a.lower() for a in args[1:]]
force = "--force" in sys.argv
voice = opt("--voice", VOICE_ID)
stab = opt("--stability", STABILITY)
sim = opt("--similarity", SIMILARITY)
speed = opt("--speed", SPEED)
model = opt("--model")

xikey = os.environ.get("ELEVENLABS_API_KEY", "").strip()
mgkey = os.environ.get("MAGNIFIC_API_KEY", "").strip()
# ElevenLabs wins when its key is there: it has every model, Magnific only has Turbo v2.5.
direct = ("--magnific" not in sys.argv) and (xikey or "--direct" in sys.argv)
if direct and not xikey: sys.exit('set the key:  $env:ELEVENLABS_API_KEY = "..."')
if not direct and not mgkey: sys.exit('no API key. Set ELEVENLABS_API_KEY, or MAGNIFIC_API_KEY with --magnific')
apikey = xikey if direct else mgkey

vids = autoplan.parse_batch(open(spath, encoding="utf-8").read())
if not vids: sys.exit(f"no scripts found in {args[0]}")
if wanted: vids = [v for v in vids if v["key"] in wanted]
if not vids: sys.exit(f"none of {wanted} found in {args[0]}")

os.makedirs(VOICE, exist_ok=True)
print(f"{'ElevenLabs' if direct else 'Magnific'}: voice {voice}, stability {stab}, "
      f"similarity {sim}, speed {speed}, model {model or (XI_MODEL if direct else ENGINE)}")
done, skipped, failed = [], [], []
for v in vids:
    k = v["key"]
    out = os.path.join(VOICE, f"{k}.mp3")
    if os.path.exists(out) and not force:
        skipped.append(k); continue
    text = autoplan.clean_text(v["text"])        # the [HOOK 2] marker is not read aloud
    if not text:
        print(f"{k}: no text in the script file"); failed.append(k); continue
    print(f"{k}: {len(text.split())} words, recording…")
    try:
        if direct:
            audio = record_xi(text, apikey, voice, stab, sim, speed, model)
        else:
            url = record(text, k, apikey, voice, stab, sim, speed, model=model)
            with urllib.request.urlopen(url, timeout=180) as r: audio = r.read()
        with open(out + ".tmp", "wb") as f: f.write(audio)
        os.replace(out + ".tmp", out)
        print(f"{k}: saved to voiceover\\{k}.mp3")
        done.append(k)
    except Exception as e:
        print(f"{k}: FAILED {e}")
        failed.append(k)

print(f"\nrecorded {len(done)}" + (f", skipped {len(skipped)} that already had audio" if skipped else "")
      + (f", failed {len(failed)}: {', '.join(failed)}" if failed else ""))
if skipped and not force: print("(add --force to record those again)")
