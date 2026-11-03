# Forced alignment: script words -> start/end seconds in the VO (pocketsphinx), stored in align.json.
# CLI:  python align.py decks miller ...      (int keys = old series parts)
# Code: align_keys(["decks"], log=print)  -> {key: [(word, start, end), ...]}
import sys, os, json, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import VOICE, PIPE
from scripts import S, norm, VO
# pocketsphinx is imported where it is used: it has no ready-made Windows build for every Python and fails to
# compile without a C compiler, and the menu, the montage and the voicing of finished videos ([A], which gets word
# timings from ElevenLabs) all import this module without ever aligning anything.
def Decoder(*a, **k):
    from pocketsphinx import Decoder as _D
    return _D(*a, **k)

AJ = os.path.join(PIPE, "align.json")
EXTRA = os.path.join(PIPE, "extra_dict.txt")   # "word  PH ON EM ES" per line — words the dictionary lacks

BUILTIN = {
    "sandblasting": "S AE N D B L AE S T IH NG", "bushing": "B UH SH IH NG",
    "crossmembers": "K R AO S M EH M B ER Z", "gussets": "G AH S AH T S",
    "comchek": "K AA M CH EH K", "efs": "IY EH F EH S", "ptos": "P IY T IY OW Z",
    "cottrell's": "K AA T R AH L Z", "pto": "P IY T IY OW",
}

# Rough spelling -> phones for words nobody entered yet. Alignment only needs something close;
# the result is saved to extra_dict.txt so it can be corrected by hand later.
_G2P = [("tion", "SH AH N"), ("ch", "CH"), ("sh", "SH"), ("th", "TH"), ("ph", "F"), ("ck", "K"), ("ng", "NG"),
        ("ee", "IY"), ("ea", "IY"), ("oo", "UW"), ("ou", "AW"), ("ow", "OW"), ("ai", "EY"), ("ay", "EY"),
        ("oi", "OY"), ("qu", "K W"), ("a", "AE"), ("b", "B"), ("c", "K"), ("d", "D"), ("e", "EH"), ("f", "F"),
        ("g", "G"), ("h", "HH"), ("i", "IH"), ("j", "JH"), ("k", "K"), ("l", "L"), ("m", "M"), ("n", "N"),
        ("o", "AA"), ("p", "P"), ("r", "R"), ("s", "S"), ("t", "T"), ("u", "AH"), ("v", "V"), ("w", "W"),
        ("x", "K S"), ("y", "Y"), ("z", "Z")]

def guess_phones(word):
    w = re.sub(r"[^a-z]", "", word.lower()); out = []; i = 0
    while i < len(w):
        for g, ph in _G2P:
            if w.startswith(g, i):
                if not (out and out[-1] == ph): out.append(ph)   # collapse doubled letters
                i += len(g); break
        else:
            i += 1
    return " ".join(out) or "AH"

def load_extra():
    d = dict(BUILTIN)
    if os.path.exists(EXTRA):
        for line in open(EXTRA, encoding="utf-8"):
            p = line.strip().split(None, 1)
            if len(p) == 2 and not p[0].startswith("#"): d[p[0].lower()] = p[1].upper()
    return d

def unknown_words(text):
    d = Decoder(); extra = load_extra()
    return sorted({w for w in norm(text) if d.lookup_word(w) is None and w not in extra})

def align_keys(keys, log=print):
    out = json.load(open(AJ)) if os.path.exists(AJ) else {}
    extra = load_extra()
    for k in keys:
        mp3 = os.path.join(VOICE, VO.get(k, f"part{k}.mp3"))
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                             capture_output=True).stdout
        dec = Decoder(bestpath=False)
        words = norm(S[k])
        new = {}
        for w in set(words):
            if w in extra: dec.add_word(w, extra[w], True)
            elif dec.lookup_word(w) is None:
                new[w] = guess_phones(w); dec.add_word(w, new[w], True)
        if new:
            with open(EXTRA, "a", encoding="utf-8") as f:
                for w, ph in sorted(new.items()): f.write(f"{w}  {ph}\n")
            log(f"{k}: new words added to extra_dict.txt with guessed pronunciation: {', '.join(sorted(new))}")
        dec.set_align_text(" ".join(words))
        dec.start_utt(); dec.process_raw(raw, full_utt=True); dec.end_utt()
        al = list(dec.seg())
        res = [(w.word, w.start_frame / 100, (w.end_frame + 1) / 100) for w in al
               if w.word not in ("<sil>", "<s>", "</s>", "(NULL)")]
        if len(res) != len(words):
            raise RuntimeError(f"{k}: alignment failed ({len(res)} of {len(words)} words) — "
                               f"the voice-over probably doesn't match the script text")
        out[str(k)] = res
        log(f"{k}: {len(res)} words aligned, speech ends at {res[-1][2]:.1f} s")
    json.dump(out, open(AJ, "w"))
    return {str(k): out[str(k)] for k in keys}

if __name__ == "__main__":
    align_keys([int(a) if a.isdigit() else a for a in sys.argv[1:]])
