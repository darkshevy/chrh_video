# How the pipeline works — from text to finished video

The short answer to "how is the video fitted to the voice-over": **the program knows the exact moment each word is
spoken** and cuts the picture on those words. Everything else is choosing *which* shot goes between two cuts, and
the styling.

```
script (text) ──► voice-over mp3 ──► alignment: word → time ──► phrases ──► cuts on words
                                                                       │
footage/ ──► clip library (topics, empty seconds) ──► one shot per phrase
                                                                       │
                       render pieces ──► join ──► voice + music + nat sound ──► mp4 + contact sheet
```

Everything is Python calling ffmpeg. No manual editing, no video editor.

## 1. Script and voice-over

- A script is one English paragraph of 115–125 words. Numbers are written as words (the voice reads digits
  unpredictably and the words would not match the text). `[HOOK 2]` marks the second hook; it is not read aloud.
- The voice-over is generated in ElevenLabs (voice "Alistair Kingsley") and saved as `voiceover/<key>.mp3`.
- The one hard requirement: **the voice must read exactly the text in the file.**

## 2. Alignment: which word is spoken when (`align.py`)

The core of the whole thing. It uses **pocketsphinx**, an offline speech recogniser, in *forced alignment* mode:
it is not asked "what was said" — it gets the known text and the audio and only finds where each word sits.

- The mp3 is converted to 16 kHz mono (ffmpeg); the text becomes a list of lower-case words.
- Each word's pronunciation comes from the CMU dictionary. Unknown words (Cottrell's, PTO, Comchek…) get a
  pronunciation guessed from the spelling, stored in `pipeline/extra_dict.txt` (editable).
- Output: `pipeline/align.json` — start and end of every word in seconds, e.g.
  `["brakes", 0.10, 0.52], ["locked", 0.52, 0.88] …` (1/100 s resolution).
- Safety check: the number of aligned words must equal the number of words in the text, otherwise the build stops
  ("the voice-over does not match the script").

## 3. Phrases and cuts (`autoplan.phrases`, `picker.split_long`)

- The text is split into phrases at punctuation. Phrases shorter than 1.3 s are merged with the next one.
  `[HOOK 2]` always starts a new phrase.
- One phrase = one shot. The cut is placed **0.06 s before the first word of the phrase**, so the picture changes
  exactly with the word — it feels "on beat".
- The boss's rule "something happens every 3–4 s": a phrase longer than 3.5 s is split again on a word boundary.
  Result: 16–22 shots per video, a change every 2–2.5 s on average.
- Video length = 0.6 s before the voice + voice length + 4 s end card.

## 4. Clip library: what is in the footage (`autotag.py`, `library.json`)

To put a hydraulics shot under "hydraulic cylinders", the program must know what each clip shows.

- Every second of every clip goes through **CLIP**, an OpenAI image model that turns a picture into a 512-number
  "meaning vector" (similar pictures → similar vectors). Model: `pipeline/models/clip_vision_q.onnx`, run on the CPU
  with onnxruntime.
- The frame is taken **as it will be cropped in the video** (centre 9:16 strip) — otherwise the program would "see"
  things that will not be in the vertical frame.
- The topic of a second is decided half by **examples** (the 15 most similar seconds from clips tagged by hand —
  nearest neighbours, class-balanced) and half by **text descriptions** ("a welder welding steel with bright sparks").
- Clip topics = those winning ≥ 20 % of its seconds: wide shop, close-up welds/beams, welding, hydraulics, aluminum,
  running gear, rust, grinder, people at work, yard, sandblasting.
- Switched off automatically: **empty seconds** (wall, stairs, tarp, sky, floor → `dull`), **outdoor painting**
  (boss rule — painting must be shown indoors), **someone else's finished edits** with burned-in captions
  (full-frame check, ≥ 6 seconds with captions).
- Accuracy on a leave-one-out test: main topic right for 40 of 48 clips. A manual fix (`"manual": true`) becomes an
  example and improves later tagging.

## 5. "Live" shot (`liveness.py`)

For every second of every clip, on the source file:
- **sharpness** — variance of the Laplacian (amount of crisp edges). Soft < 450, good > 700.
- **motion** — mean difference between frames 0.2 s apart. Static < 3, shaky > 35 (drone > 20).

A window is usable only if all its seconds are sharp and not shaky. Thresholds were calibrated on shots rated by eye.

## 6. Choosing the shot for a phrase (`autoplan.pool_for`, `picker.best`)

1. Each topic has keywords (`library.json → categories → keywords`), e.g. hydraulics: hydraulic, cylinder, hose,
   pump, pto, leak… The words of the phrase are matched against them → a **pool of clips** ordered by fit.
   The last phrase (call to action) prefers the yard and the shop.
2. In every pool clip, every window of the needed length is tried (0.25 s steps) at 1× (and 0.8×/0.7× if the clip
   is short). Thrown out: soft/shaky seconds, empty seconds, seconds used in the **previous batch** ("don't repeat
   yesterday"), seconds already used in this video.
3. The best remaining window wins, in this order: variety inside the video (a clip at most twice) → seconds not
   shown before → vertical clip over landscape → normal speed → topic fit → sharpness.

## 7. Render (`build.py`)

Each shot is rendered as its own piece; pieces are joined without re-encoding.

- **Framing.** Vertical and large landscape sources are cropped to 1080×1920. Small landscape files (848×464 from a
  messenger) are shown full-width over a blurred copy of themselves — a crop would be a 4× upscale.
- **Stabilisation** of handheld footage — vidstab (two passes); drone footage is not stabilised.
- **Colour:** contrast, vibrance, warm highlights / cool shadows, light clarity and vignette.
- **Text** (ASS subtitles, drawn by libass inside ffmpeg): word-by-word captions (3 words on screen; spoken words
  solid, upcoming ones faded; timing from the alignment) · the hook sentence bigger in amber + a short white flash ·
  title for 3 s · phone number on top the whole video · music credit for the first 5 s · 4-second end card with
  name, phone and address. All text stays inside the centre 1:1 square because Facebook crops to a square.
- **Cottrell logo** (Cottrell video): overlaid for 2 s every time the word "Cottrell" is spoken, and on the end card.

## 8. Sound

- Voice: high-pass 80 Hz, compressor, a little 3.2 kHz presence, starts after 0.6 s.
- Original sound of the clips: 5 % (boss rule).
- Music (the boss's tracks): volume 0.225, **ducked while the voice speaks** (sidechain compressor), starts on a
  strong beat (beat grids precomputed in `pipeline/beats/` with librosa), fades in and out.
- Overall loudness −14 LUFS (social media standard).

To add a track: put the mp3 in `music/`, add the name to `tracks` in `library.json`, and create its beat grid:
`python -c "import librosa,json;y,sr=librosa.load('music/NAME.mp3');t,b=librosa.beat.beat_track(y=y,sr=sr,units='time');json.dump([float(x) for x in b],open('pipeline/beats/NAME.json','w'))"`.

## 9. Review

After rendering, a **contact sheet** (24 frames of the video with timecodes, `output/…jpg`) is made. It shows in
ten seconds: empty shots, foreign captions, repeats, shots that do not fit the words. Fix: mark the seconds as
`dull` (or disable the clip) in `library.json` / the Clip library tab and rebuild that video — shots are re-picked.

## 10. Face blur (after approval)

`faces.py`: the YuNet face detector runs only on shots from clips that contain people (otherwise it mistakes hubs and
bolt holes for faces); a skin-tone test rejects painted/rusty steel; boxes are held 0.5 s so the blur does not
flicker; the caption band is never blurred. Missed faces can be added by hand in `plan.BLUR`.

---

## Where to tune

| I want to change | Where |
|---|---|
| Sharpness / motion thresholds | `pipeline/liveness.py` |
| Cut more / less often | `MAXSHOT` in `pipeline/picker.py` |
| A topic or its keywords | `categories` in `pipeline/library.json` |
| Forbid seconds of a clip | `clips[<file>].dull` in `pipeline/library.json` |
| Colour | `GRADE` in `pipeline/build.py` |
| Fonts, sizes, positions of text | ASS styles in `make_ass` in `pipeline/build.py` |
| Phone / address | `PHONE`, `ADDRESS` in `pipeline/build.py` |
| Music / voice levels | `finish_music` in `pipeline/build.py` |
