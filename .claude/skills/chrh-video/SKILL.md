---
name: chrh-video
description: Make daily vertical promo videos (9:16, ~45 s) for Car Hauler Repair Houston from existing footage, the boss's music and voice-overs. Use when asked to write the day's 10 scripts, tag new footage, build/render videos, fix a shot, check a batch before it goes to the boss, or blur faces in approved videos.
---

# CHRH video production

You work inside the project folder `C:\CarHaulerRepairHouston` (or wherever it was copied — the whole folder must be
present: footage/, music/, voiceover/, pipeline/). Everything is driven by one command-line tool:

```
python pipeline/chrh.py status                     # what is where
python pipeline/chrh.py scan                       # tag new clips in footage/ (topics, dull seconds, foreign edits)
python pipeline/chrh.py check scripts/<file>.txt   # validate scripts + voice-over files
python pipeline/chrh.py build scripts/<file>.txt   # align -> pick shots -> render all videos of the file
python pipeline/chrh.py build scripts/<file>.txt key1 key2   # only some videos
python pipeline/chrh.py sheet output/<video>.mp4   # contact sheet: 24 frames with timecodes
python pipeline/chrh.py blur key1 key2             # face blur, ONLY after the boss approved those videos
```

Requirements on a fresh PC: Python 3.12, `winget install Gyan.FFmpeg`, then
`python -m pip install --user -r pipeline/requirements.txt`. Models are already in `pipeline/models/`.
(The operator's GUI `app\CHRH Video\CHRH Video.exe` does the same without Python.)

## Daily job: 10 videos (9 topical + 1 about the Cottrell partnership)

1. **New footage?** Run `status`; if "not tagged yet" > 0 run `scan`. Then look at the new clips yourself
   (`sheet footage/<clip>` or a mosaic) — the tagger gets the main topic right in ~5 of 6 clips. Fix wrong ones in
   `pipeline/library.json` → `clips[<file>]`: `cats`, `enabled`, `dull` (seconds never to use), `manual: true`.
   Disable: outdoor painting, someone else's finished edits with burned-in captions, clips that are mostly wall/sky.
2. **Write 10 scripts** into `scripts/topics_<MMDD>.txt` — format and rules in `references/scripts.md`.
   Facts ONLY from `references/facts.md`. Topics must not repeat earlier days (read older `scripts/topics_*.txt`).
3. `check` the file. The operator voices each script in ElevenLabs and saves `voiceover/<key>.mp3`.
4. `check` again (now it verifies the mp3s), then `build`. ~3–4 min per video. The previous batch's footage is
   forbidden automatically (`--allow-repeat` to switch off).
5. **Review every video** before handing over: open `output/CHRH_<Key>_v1.jpg` (contact sheet). Reject and fix:
   wall/stairs/tarp/sky/floor frames, blurry frames, foreign captions, the same clip 3+ times, outdoor painting,
   shots that contradict the words. Fix by marking the seconds `dull` (or the clip `enabled:false`) in
   library.json and running `build ... <key>` again — it re-picks shots and renders `_v2`.
6. Report to the operator: list of videos, what is weak (topic with no matching footage), what to film.

## Hard rules from the boss (details in `references/rules.md`)

- One trailer's story only with that trailer's footage; mixed footage → the script speaks about the shop in general.
- Correct process order on screen (sandblast → gray steel → masking → brown primer → red top coat).
- Painting only indoors on screen — the red trailer was painted outside, those clips are disabled.
- Only live shots: wide shop shots or close-ups of welds/beams; something happens every 3–4 s.
- Hook in the first line and a second hook mid-video (`[HOOK 2]` marker).
- Phone number on top the whole video, 4-second end card with the full address — the renderer does this.
- Music: instrumental tracks by the boss (DJ KOZ LOVE) with a small credit — the renderer does this.
- No face blur on first cuts; blur only approved videos (`blur`).
- Never invent specs, prices, causes, dimensions. The Cottrell warranty is COTTRELL's, not the shop's.

## Where things are

| Path | What |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | full project memory: rules, footage knowledge, history — read first |
| `pipeline/chrh.py` | the command line above |
| `pipeline/library.json` | clip library: topics + keywords, per-clip tags, dull seconds |
| `pipeline/autoplan.py` | script parsing, checks, shot planning, render driver |
| `pipeline/build.py` | ffmpeg render: crop/letterbox, grade, stabilisation, captions, phone bar, end card, audio |
| `scripts/topics_*.txt` | scripts per day; `scripts/batches/<date>.json` = what was built |
| `voiceover/<key>.mp3` | voice-overs; `music/` = the boss's tracks |
| `output/` | finished videos `CHRH_<Key>_vN.mp4` + contact sheets `.jpg` |

How the automatic editing works internally: `references/workflow.md`.
