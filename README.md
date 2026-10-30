# CHRH Video — automatic promo-video pipeline

Turns ready footage + a voice-over into finished vertical promo videos (9:16, 1080×1920, ~45 s) for
Facebook / Instagram / TikTok / YouTube Shorts, in the Car Hauler Repair Houston style: word-by-word captions,
phone number on screen, the boss's music, end card with the address. Ten videos a day is the intended rhythm.

- **Operators:** read `OPERATOR_GUIDE.md`. Everything is done in the desktop app `CHRH Video`.
- **Writing the scripts:** `SCRIPT_PROMPT.md` — paste it into ChatGPT / Claude to get the day's 10 scripts.
- **Programmer:** this file, then `docs/HOW_IT_WORKS.md` for the internals.
- **AI coding agent (Codex / Claude Code):** `AGENTS.md` (project memory) and the skill in `.codex/skills/chrh-video/`.

---

## 1. Quick start (Windows 10/11, nothing to install)

1. Copy the whole `CarHaulerRepairHouston` folder to the PC (any drive; keep the folder together).
2. Double-click **`CHRH Video.bat`** (or `app\CHRH Video\CHRH Video.exe`).
3. In the app: *Open script file…* → pick `scripts\topics_0929.txt` → *Check*. All ten rows must say OK.
4. Select one row → *Build selected*. After ~3 minutes `output\CHRH_<Key>_v2.mp4` appears. Double-click the row to play it.

The `.exe` contains Python, ffmpeg, all models and libraries. It must stay inside the project folder: it finds
`pipeline\`, `footage\`, `voiceover\` … by walking up from its own location.

## 2. Folder layout

| Folder / file | What |
|---|---|
| `app\CHRH Video\` | the built program (PyInstaller, ~670 MB incl. `bin\ffmpeg.exe`, `bin\ffprobe.exe`) |
| `footage\` | all source clips, any subfolders. `footage\_contact\` = contact sheets (previews), safe to delete |
| `music\` | the boss's tracks (DJ KOZ LOVE). Only the 7 instrumental ones are used |
| `voiceover\` | voice-overs, one mp3 per video: `<key>.mp3` |
| `scripts\` | scripts per day (`topics_*.txt`); `scripts\batches\<date>.json` = what was built |
| `output\` | finished videos `CHRH_<Key>_vN.mp4` + contact sheet `.jpg` per video |
| `pipeline\` | the source code, clip library, models (see §5) |
| `work\` | temporary render files and caches — can grow to many GB; delete freely when nothing is building |
| `docs\` | `HOW_IT_WORKS.md` (internals), `PROJECT_HISTORY.md` |

## 3. Daily workflow (summary)

1. New footage → put it in `footage\` → app tab **Clip library** → **Refresh** (auto-tags new clips).
2. Generate 10 scripts with `SCRIPT_PROMPT.md`, save as `scripts\topics_MMDD.txt`.
3. Record voice-overs (ElevenLabs, voice "Alistair Kingsley"), save as `voiceover\<key>.mp3`.
4. App → open the script file → **Check** → **Build all**. ~3–4 min per video.
5. Review each video (contact sheet = right-click the row). Send to the boss.
6. After approval: select the approved rows → **Blur faces** → `output\CHRH_<Key>_blur.mp4` is the version to post.

## 4. Running from source (for the programmer)

Requirements: Windows, Python 3.12, ffmpeg *full* build (needs libass + libvidstab).

```bat
winget install Gyan.FFmpeg
python -m pip install --user -r pipeline\requirements.txt
pythonw pipeline\app.py                 :: the GUI
python pipeline\chrh.py status          :: the same engine from the command line
```

Command line (`pipeline\chrh.py`):

```
status                       what is where: clips, batches, latest outputs
scan                         auto-tag new clips in footage\
check  SCRIPTS.txt           validate scripts + voice-over files (exit code 1 on errors)
build  SCRIPTS.txt [keys..]  align -> pick shots -> render; forbids the previous batch's footage
       --allow-repeat        allow reusing the previous batch's seconds
sheet  VIDEO.mp4             contact sheet (24 frames with timecodes)
blur   KEY [KEY..]           face blur for approved videos
```

**After changing any `pipeline\*.py`, rebuild the exe:** close the app, run `pipeline\rebuild_exe.bat`
(needs `pyinstaller`, included in requirements). Data files (`library.json`, `align.json`, `extra_dict.txt`,
`scripts\batches\*.json`) are read at runtime and do not need a rebuild.

Self-test of the exe without a window (results in `work\app.log`):
```bat
"app\CHRH Video\CHRH Video.exe" --selftest scripts\topics_0929.txt
"app\CHRH Video\CHRH Video.exe" --run brakes scripts\topics_0929.txt
```

## 5. Code map (`pipeline\`)

| File | Role |
|---|---|
| `app.py` | Tkinter GUI (Batch / Clip library / Log tabs), runs jobs in a worker thread |
| `chrh.py` | command-line front end |
| `autoplan.py` | parse script files, checks, register a batch, split text into phrases, pick shots, render driver |
| `align.py` | forced alignment of the script to the voice-over with pocketsphinx → `align.json` (word start/end times) |
| `autotag.py` | CLIP (ONNX) auto-tagging of clips: topics, dull seconds, outdoor painting, foreign edits with captions |
| `liveness.py` | sharpness (Laplacian variance) and motion per second of a clip |
| `picker.py` | chooses the best clip window for each phrase (variety, freshness, topic, sharpness) |
| `build.py` | ffmpeg render: crop/letterbox, stabilisation, colour grade, ASS captions, phone bar, end card, logo, audio mix |
| `faces.py` | face blur (YuNet) for approved videos |
| `contact.py` | contact sheets |
| `paths.py` | all folder paths; finds the project root (also from the exe) |
| `library.json` | clip library: topics + keywords, one record per clip (enabled, topics, dull seconds, manual) |
| `scripts.py`, `plan.py` | legacy hand-made videos (first weeks); new batches live in `scripts\batches\` |
| `models\` | CLIP image model, YuNet face model, CLIP prompt embeddings |
| `assets\` | Cottrell logo (vector + PNG) |
| `beats\` | beat grids of the music tracks (music starts on a beat) |
| `extra_dict.txt` | pronunciations for words the speech dictionary lacks |

Legacy one-off planners (`replan_0923.py`, `replan_0924.py`, `plan_0923b.json`, `plan_0924.json`) are kept only so
that old videos can be re-rendered; new work never needs them.

## 6. Common maintenance

| Task | Where |
|---|---|
| Phone number / address on screen | `PHONE`, `ADDRESS` in `pipeline\build.py` → rebuild exe |
| Colour grade | `GRADE` in `pipeline\build.py` |
| Caption font / sizes / positions | ASS styles in `make_ass()` in `pipeline\build.py` |
| Cut more or less often | `MAXSHOT` in `pipeline\picker.py` (3.5 s) |
| Sharpness / motion thresholds | `pipeline\liveness.py` |
| New topic or keywords | `categories` in `pipeline\library.json` (no rebuild) |
| Disable a clip or some seconds | app → Clip library, or `clips[<file>].enabled` / `.dull` in `library.json` |
| Add a music track | mp3 into `music\`, add its name to `tracks` in `library.json`, beat grid: see `docs\HOW_IT_WORKS.md` |
| Partner logo | `logos` in `library.json` (PNG with transparency in `pipeline\assets\`) |

## 7. Known limits

- The editor matches shots to **words**, not to meaning: it cannot know that a clip shows *brakes* unless a clip
  tagged "running gear" exists. Topics with no matching footage get general shop shots. Film what the scripts talk about.
- Auto-tagging gets the main topic right in about 5 of 6 clips — glance over new clips after **Refresh**.
- Footage received through messengers is 848×464; it is shown letterboxed over a blurred copy. Original phone
  files (full resolution) give much better results.
- Voice-overs are made by hand in ElevenLabs; the voice must read exactly the script text.
- The Cottrell logo is Cottrell's trademark — confirm the partnership agreement allows it in ads.
