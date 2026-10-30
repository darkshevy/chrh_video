# Operator guide — 10 videos a day

You need: the project folder on a Windows PC, an AI chat (ChatGPT or Claude) for the scripts, and an
ElevenLabs account for the voice. Start the program with **`CHRH Video.bat`** (or the desktop shortcut).

## Step 1 — New footage (only when there is some)

1. Copy the new video files into `footage\` (a new subfolder is fine, e.g. `footage\2026-10-21\`).
   Use original phone files when possible — files sent through WhatsApp/Telegram are small and look soft.
2. In the program open the **Clip library** tab → press **Refresh: find new clips and auto-tag**.
   About 3 seconds per clip. The program decides for each clip:
   - its topics (wide shop shot, welding, hydraulics, running gear, aluminum, rust, yard, sandblasting…),
   - which seconds are empty (wall, stairs, tarp, sky, floor) — those are never used,
   - whether to switch the clip off: outdoor painting, someone else's finished edit with captions, mostly empty.
3. Set *Show:* to **auto** and look over the new rows. Double-click a row to see the clip's frames.
   If a topic is wrong: tick the right boxes on the right → **Save as manual**. Manual clips teach the program, so
   the next clips are tagged better. **Disable selected** keeps a clip out of all videos.

## Step 2 — Ten scripts

1. Open `SCRIPT_PROMPT.md`, copy the prompt into ChatGPT or Claude, attach (or paste) `AGENTS.md` so it has the facts.
   Tell it which topics were already used (it can read older `scripts\topics_*.txt`).
2. Save the answer as `scripts\topics_MMDD.txt` (e.g. `topics_1021.txt`).
3. In the program, **Batch** tab → **Open script file…** → **Check**. Red = must fix (digits in the text, missing
   text). Yellow = advice. The voice-over column says "—" until the mp3 files exist.

Rules the boss set for the text: a hook in the first sentence, a second hook mid-video marked `[HOOK 2]`, numbers
written as words, only true facts, a different call to action each time, one video a day about the Cottrell partnership.

## Step 3 — Voice-over

ElevenLabs v3 (we used it through Magnific): voice **Alistair Kingsley**, speed 1×, Expressive, similarity 40 %.

- Generate one file per script. Do **not** read the `[HOOK 2]` marker. Do not change words.
- Save as `voiceover\<key>.mp3` — the key is the first word after `===` in the script file (e.g. `brakes.mp3`).
- If the voice stumbles, regenerate rather than editing the text: captions are built from the text.

## Step 4 — Build

1. **Check** again — every row should say OK and show the voice-over length.
2. **Build all**. Roughly 3–4 minutes per video; the progress bar shows which one is running. **Stop** finishes
   the current step and stops.
3. Videos appear in `output\` as `CHRH_<Key>_v1.mp4` (a rebuild makes `_v2`, `_v3` …).

The program automatically: cuts on the words, changes shot every 2–3.5 s, never reuses the previous day's
footage, adds captions word by word, the phone number on top, the boss's music with a small credit, the title,
the end card with the address, and the Cottrell logo in the Cottrell video.

## Step 5 — Review (do not skip)

Right-click a row → contact sheet (24 frames of the video). Look for: a shot of a wall or the sky, the same clip
too often, a shot that contradicts the words, outdoor painting, captions from someone else's video.

To fix: Clip library → find the clip → **Disable selected** (or tick the right topics) → back to Batch →
select the video → **Build selected**. The shots are picked again.

## Step 6 — Boss approval and face blur

Send the videos to the boss. After he approves: select those rows → **Blur faces (selected, after approval)** →
post `output\CHRH_<Key>_blur.mp4`. (Faces stay sharp on first cuts on purpose — the boss wants to see the cut first.)

## Housekeeping

- `work\` grows by several GB a day — delete its contents when no build is running.
- `output\` keeps every version; delete old `_v1` files when a `_v2` replaced them.
- The Log tab (and `work\app.log`) shows what happened if something fails.
