# Car Hauler Repair Houston — video production

Short vertical promo videos (9:16, 1080×1920, ~45 s) for Facebook / IG / TikTok / YT Shorts.
Client: Car Hauler Repair Houston, Houston TX, 832-708-5492. Boss reviews every video.
Handed over 2026-10-21 to Car Hauler Repair Houston (sold by the original operator David). Start with README.md,
OPERATOR_GUIDE.md and SCRIPT_PROMPT.md; internals in docs/HOW_IT_WORKS.md. Communicate with the new owners in English.

## Boss rules (from feedback — hard requirements)
1. **One topic / one project per video.** Never tell one trailer's story with footage from other trailers.
   If footage from several projects is mixed, the voice-over must speak generally about the service center.
2. **Process order must be correct on screen.** Sandblast/paint order: prep/disassembly (e.g. cylinder removal)
   → sandblasting (worker with blaster, dust) → **gray** bare steel → masking/taping → **brown** primer → **red** top coat.
   Sandblasting is expensive and complex — always show it before primer.
3. Stabilize shaky handheld shots (vidstab). Drone footage: no stabilization.
4. Original audio at **~5%** in the background, not muted.
5. Music: **instrumental only**, from the boss's tracks. Small credit at the bottom (DJ name + track title),
   visible ~5 s at the start, fade in/out, unobtrusive. Artist: **DJ KOZ LOVE** (the boss; soundcloud.com/dj-koz-love).
   Credit format "DJ KOZ LOVE  ·  <Track>" — set per video in `plan.py` TRACK (file + credit must match).
10. **Boss feedback 09-24 (applies to every new video):**
   - Pleasant color grade in every video (current `eq` grade is not enough — needs a real look/LUT).
   - Phone number **always visible at the top** of the frame (keep inside the 1:1 safe zone, y ≥ 420).
   - Stricter shot selection: either a WIDE shot or a CLOSE-UP of welds/beams. Dull, low-action work gets cut.
   - End card: full address for 3-4 s instead of "Houston, TX". Facebook page shows "6716 Long. Drive Houston, TX,
     United States, Texas 77087"; the company website writes it cleanly as **"6716 Long Drive, Houston, TX 77087"**
     — use the website form unless David says otherwise.
   - Some action every 3-4 s; hook at the start AND in the middle; more varied videos, not same-y.
   - **Blur OFF for now** — blur only after the first cut is approved, placed manually second by second.
     (Overrides the automatic part of rule 7: build with `finish_music(..., blur=False)` until told otherwise.)
   - Every day's batch of 10 must include 1 video about the partnership with **Cottrell**.
   - Also asked for: warranty types (done: see Verified facts) and a "master prompt" for scripts (done: SCRIPT_PROMPT.md).
7. **No recognizable people.** Boss 09-23: "the guy with the cigarette and the faces need to be cut out — people leave, and then
   there can be problems." Faces get a light blur — `pipeline/faces.py` (OpenCV YuNet, models/face_detection_yunet_*.onnx),
   run automatically by `finish_music(blur=True)` on the concatenated cut. Manual boxes for missed faces:
   `plan.BLUR[key] = [(t0,t1,x,y,w,h)]` in final 1080x1920 coords. Captions band (y 1240-1440) is never blurred.
   Settings that matter: the search runs ONLY inside shots whose clip is listed in `plan.PEOPLE` — wheel hubs, hinge
   holes and bolt heads otherwise get detected as faces; score 0.35 (profile faces under caps score 0.4-0.55);
   a skin-tone test rejects painted/rusty steel; boxes >22% of frame height dropped; 0.5 s hold bridges missed frames.
8. **Paint only indoors on screen** (David 09-23). The red trailer was painted OUTSIDE in the field — those clips
   (покраска*, 14-49-39, 14-58-29/40, 14-49-08, IMG_0331, 14-59-44, 19-06-53, 19-07-*, Fresh paint, drones 0018-0024)
   must not illustrate painting/finish. For "finished paint" use the painted 5-car IN THE SHOP (Drone Directions
   "5 car decking …", drone 0025). Outdoor sandblasting close-ups of gray deck are OK; wide red-frame blast shots are not.
9. **Only "live" shots** — sharp and moving. `pipeline/liveness.py` measures on the SOURCE: sharp25 >= 700 (Laplacian),
   motion 3-20 drone / <=35 handheld (vidstab). `picker.py` + `replan_0923.py` pick windows per phrase from topic pools.
   The old 464x848 Miller batch fails sharpness everywhere — avoid unless the topic is that trailer.
6. Voice-over script rules (brief section 28): natural connected sentences, technically accurate,
   start with year/make/model if known, failure → repair steps in order → result → short brand statement/CTA.
   **Never invent** dimensions, materials, causes, OEM specs or procedures not provided.
   CTA should vary between videos (brief section 26).

## Verified facts (carhaulerrepairhouston.com, read 2026-09-24) — safe to use in scripts
- **Cottrell Authorized Warranty Repair Center** (site wording; the general script says "Certified" — prefer "Authorized").
  Cottrell warranty work done in their bay "without the dealer's week-long queue".
- **Warranty types:** (1) **6-month warranty on labor & workmanship** for completed repairs — "bring it back, we make it
  right"; (2) **Cottrell warranty repairs carry Cottrell's own coverage**; (3) temporary / limp-it-home fixes are flagged up
  front and are NOT covered by the 6-month warranty.
- **Pricing:** rough number on the phone, exact price in writing after inspection, $0 inspection/diagnostic fee,
  walk away for $0, nothing extra without approval ("work stops, you get a call").
- Same-day turnaround on most common failures; hoses crimped in-house, welding on site, most repairs don't wait on parts.
- 4 full-service bays for full-length multi-deck rigs; Mon–Sat 7 AM–6 PM, closed Sunday; secure overnight holding.
- Shop Director **Eugene** answers the phone directly; text reply within 15 min in shop hours; Spanish-speaking techs.
- Brands on site: Cottrell, Take 3, Sun Country, Boydstun, Delavan, Miller, Kaufman, custom multi-deck.
- ★ 5.0 from 25 Google reviews. Near America's Auto Auction Houston; off Gulf Fwy, 1.5 mi from I-45/I-610.
- Payment: cash, Visa, Mastercard, Amex, Cash App, Venmo, Comchek, EFS, T-Chek. No tow service of their own.
- Cottrell side (cottrelltrailers.com/warranty): 100+ authorized repair centers; owner starts a claim with Cottrell
  warranty dept 800-827-0132 (ext. 313/301) or online; repairs at non-authorized shops or without pre-authorization may
  not be covered; photos help the claim.
- **Cottrell Limited Warranty (eff. 10-22-25, read 09-24)** — it is COTTRELL's warranty, not the shop's; never phrase it
  as "we give you 36 months". Terms, from the In-Service Date approved by Cottrell/its dealer, new Headramp & Trailer:
  mainframe structure 36 months (excl. wear items: pivot points, linkages, track sheets, flippers);
  Cottrell-made hydraulic cylinders 12 months (cylinders/hoses/valves only if bought as a complete unit, else extra docs
  such as pressure readings & flow rates); paint — by the paint maker, 5 yrs / 500,000 mi (yrs 1-2 100% mat+labor,
  yr 3 100% mat/50% labor, yr 4 50/50, yr 5 50% mat/25% labor; track & moly-lubed surfaces excluded);
  axles, suspension, lighting, valves, hoses — by their component makers, but ALL claims go through Cottrell.
  Every warranty job needs Cottrell approval + work order BEFORE work starts; photos on request; failed parts returned.
  Original buyer only (not transferable). Void if modified/repaired by anyone other than Cottrell or its AUTHORIZED
  representatives, or accident/neglect/misuse. Buyer pays transportation. No loss-of-use / cargo-damage coverage.
- No Cottrell trailers filmed in the shop yet (David 09-24) — Cottrell videos need new footage or honest general b-roll.

## Pipeline changes 09-24 (boss feedback applied in build.py)
- GRADE (build.py): lifted mids + vibrance + warm highlights/cool shadows + light clarity + vignette (variant "E",
  picked from a 3-way comparison — darker looks crushed the shop interior).
- Phone bar "CALL (832) 708-5492" at the top for the whole video (style Phone, y≈436, inside the 1:1 crop);
  titles moved down (TBrand 560 / TPart 610 / TName 740).
- END = 4.0 s; end card: CAR HAULER REPAIR HOUSTON + CALL phone + ADDRESS "6716 Long Drive, Houston, TX 77087".
- Mid-video hook: `[HOOK 2]` marker in the script text -> scripts.HOOK[key] (aligned-word index); captions of that
  sentence turn amber/bigger (CapHook) + 0.3 s white flash.
- `finish_music(..., blur=False)` by default (boss: blur only after the first cut is approved, placed manually).
- picker.split_long: no shot longer than 3.5 s (extra cuts on word boundaries).
- Partner logo: plan.LOGO[key] = (png, trigger word, width). Cottrell logo `pipeline/assets/cottrell_logo.{svg,png}`
  (vector taken from the header of cottrelltrailers.com, rendered with resvg_py). Shown 2 s on each spoken
  "Cottrell" after the title + on the end card. Needs the boss's OK to use the trademark.
- Scripts must not contain digits (the voice reads them unpredictably and alignment breaks) — write numbers as words;
  the phone number is on screen, the VO says "call the number on screen".

## Desktop app "CHRH Video" (09-28) — automatic editor, no Claude needed for a batch
- **.exe build (09-28):** `app/CHRH Video/CHRH Video.exe` (PyInstaller onedir, 632 MB incl. ffmpeg+ffprobe in `bin/`).
  Needs no Python/ffmpeg/fonts on the PC, but must stay INSIDE the project folder (finds ROOT by walking up to pipeline/).
  Desktop shortcut + `CHRH Video.bat` start the exe. Code is frozen: after editing pipeline/*.py run
  `pipeline/rebuild_exe.bat`. Data (library.json, align.json, extra_dict.txt, batches, footage) stays editable outside.
  Self-test without window: `"CHRH Video.exe" --selftest <scripts.txt>` / `--run <key> <scripts.txt>` → work/app.log.
- Python mode still works: `pythonw pipeline/app.py`.
- **CLI for agents (09-29):** `python pipeline/chrh.py status|scan|check|build|sheet|blur` — same engine as the GUI.
  `build` forbids the previous batch's footage automatically. Portable skill for Codex/Claude:
  `.codex/skills/chrh-video/` (copy in `.claude/skills/`, zip `CHRH_skill_chrh-video.zip`): SKILL.md + references
  (rules, facts, scripts format, workflow = how the auto-editing works). AGENTS.md = copy of this file for Codex —
  re-copy after editing CLAUDE.md.
- **Auto-tagging (09-29):** `autotag.py` + CLIP ONNX (`pipeline/models/clip_vision_q.onnx`, Xenova/clip-vit-base-patch32
  quantized; text prompts precomputed in `clip_prompts.json` via `build_prompts()`, needs `tokenizers`, dev only).
  Each second is cropped like the final 9:16 frame and labelled by 15 nearest seconds of HAND-tagged clips
  (class-balanced) + text prompts (50/50). Leave-one-clip-out: top topic right 40/48, 81% topic recall. Also flags
  dull seconds (wall/stairs/tarp/sky) and outdoor painting (→ clip disabled). Embeddings cached in work/clip_cache/.
- library.json schema: `categories` (label, keywords) + `clips[filename]` = {enabled, cats, dull, manual, reason, share}.
  manual=true records are the teacher; a manual fix in the app improves later scans. App tab "Clip library":
  "Refresh: find new clips and auto-tag", use on/off, re-tag selected/all, filter. Backup of the old schema:
  work/library_backup_0929.json.
- Operator pastes ready scripts (format `=== key | TITLE | SUB | Track` + text, or the topics_*.txt format), drops
  voiceover/<key>.mp3, presses "Check" → "Build all". Output: output/CHRH_<Key>_vN.mp4 + contact sheet .jpg.
- Code: `autoplan.py` (parse, check, register → scripts/batches/<date>.json, phrases at punctuation, pools by keywords,
  plan via picker, render, blur_key), `align.py` (align_keys(); unknown words get guessed phones, saved to
  extra_dict.txt), `library.json` (categories → clip names + keywords, dull ranges, people, tracks, logos).
  Clips not listed in library.json are never used — new footage must be tagged in the app's "Clip library" tab.
- picker ranking: variety inside the video (same clip ≤2) > fresh seconds > real speed > topic fit > sharpness.
- From Python/Claude: `import autoplan; autoplan.load_all_batches()` makes batch videos renderable by build.py.
- Tested 09-28 on the fleet script: 20 shots, no slow-mo, no dull frames. Scripts still come from outside (Claude chat).

## New footage 09-25 (56 clips, uploaded 09-29) — all 848x464 / 464x848 (messenger-compressed)
- 21 landscape clips incl. long drone flights: 5CC5 (3.5 min inside the shop), EC86 (shop → yard, white enclosed hauler),
  263A (shop → building exterior; after 80 s only a sedan on gravel = dull), 8373 (shop; after 41.5 s floor/lockers = dull).
- Good action: blast hood + hose (0657, D2DF), plasma cutting (E0CB), MIG welding (DAC3, 82E5), grinder sparks
  (0C0D, B815), two workers on a new deck frame (3195), impact gun on a hub (5187), orange carrier in the shop (A51D),
  finished gray decks (611F), forklift loading a carrier (291B), red + green haulers in the yard (1B8B).
- DISABLED — someone else's finished edits with burned-in captions/phone cards: 9CC7 (sandblasting promo), 727A
  ("Stinger fifth wheel tong +24 inch"), A9F4 ("king pin plate replaced"). autotag now flags these automatically
  (full-frame CLIP overlay check, ≥6 hit seconds → "someone else's edit with captions").
- build.py fit mode: landscape source with height < 720 is shown full-width over a blurred copy of itself (1.3x
  upscale instead of 4x for a 9:16 crop). picker prefers vertical clips, letterbox only when needed.
- autoplan.plan_keys(keys, hard_keys=[yesterday's keys]) forbids yesterday's seconds; fallback is logged.

## Voice
ElevenLabs v3 via Magnific, voice **Alistair Kingsley**, Speed 1x, Expressive, 40% similarity.
v3 reads fast: ~170–210 wpm → ~125 words ≈ 41 s VO ≈ 45 s video.
The operator generates the VO by hand and saves voiceover/<key>.mp3.

## Footage knowledge
- "Red trailer" project (outdoors, field): sandblasted (clips пескоструй/пескоструй2/пескоструй3),
  then **gray** stage (14-49-39, 14-49-46, 14-58-29 mid, покраска 0–15 s, 14-59-44 0–5 s, 14-49-30 lights),
  **brown primer** (покраска 16–25 s), **red top coat** (покраска2 0–7 s, IMG_0331, 14-49-08, 14-58-40, drone DJI_2026092017xx).
  Proof gray = same trailer: покраска2 at 8–10 s shows red lower frame, gray upper.
- Old shop batch (0A2F…D867, 464×848): **Miller 2007 7-car hauler — bushing & partial hinge replacement**
  (boss said "I think Miller 2007 7-car" — confirm before voicing).
- Other jobs: orange/primed trailer 14-48-45; black trailer 14-48-57, 14-50-04, 14-50-11;
  aluminum slotted decks 14-48-17/20/24/26 (fine for a general "decks" video).
- Sun Valley 2012 5-car hauler (first test video) footage 1.mp4–11.MOV: decks, welding.
- Uploaded 2026-09-22 (red trailer, AFTER red top coat): masking tape on red frame 19-07-16, 19-07-22;
  non-skid rolled on rails 19-07-05 (3–5 s), 19-07-11; fresh texture 19-07-08, 19-07-02; black non-skid decks
  "Just a quick sneak peek…"; finished "Fresh paint, next step NO-SKID", 19-06-53.
  Other 09-22: aluminum deck welding 19-03-53 (0–4 s usable), aluminum deck close-up 19-04-49,
  white enclosed trailer rear post 19-04-15, storage compartment repair (19-04-40, "Storage Compartment Repair" 1/2).

## Google Drive folders (owner acesteelwelding@gmail.com, "anyone with link" reader)
- New marketing materials: 1fFFiAggvfhMmRqGuY75QbmDqAvMAcHjh (38 iPhone MOV originals, photos, 13 drone clips Jul 25)
- Inclosed trailer roof install: 1pUX7fKikrmPs8Z21MBZBipsl2sh4Tmv7 (new topic: enclosed trailer roof)
- Glasses: 1TzJmXdlQgMNYat5GolALo5bErnVfzhrc (likely POV smart-glasses footage)
- Drone footage: 1qO-yZHTzDUYTeYGMUTPPDVcwaQE3zC0p (long 4K flights, up to 2.5 GB)
- Drone Directions: 1Wz2tUU2yIYhADkA1OH9B2PYaJNLUIpnX (named: "5 car decking …", "shop east to west", "yard footage")
- Car Hauler Pics: 15eyu5UMkd4cOBIaR5BAoFUAT0ZAe6lnd
Direct download: `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`

## Pipeline (pipeline/)
- `scripts.py` — VO texts per video; `align.py` — pocketsphinx forced alignment → word timings (`align.json`).
- `plan.py` — shot lists: `(cut_word_index, clip_prefix, in_point, speed, zoom)`; cut lands 0.06 s before the word.
- `build.py` — per-segment render (scale/crop to 1080×1920, grade `eq=contrast=1.07:saturation=1.12`, unsharp,
  vidstab, 30 fps, ASS captions burned per segment), concat, audio mix.
  `render(k)`, `finish(k)`, `finish_music(k, target_seconds)`.
- `vd.py` — vocal detector (UVR-MDX-NET-Voc_FT.onnx from github TRvlvr/model_repo) to verify instrumental tracks.
- Paths come from `pipeline/paths.py` (footage/, music/, voiceover/, work/, output/ under the project root). Footage is
  indexed recursively, so clips can live in any subfolder of footage/. ffmpeg runs with cwd=work/ (a drive colon breaks filter args).
- Handover docs (2026-10-21): README.md, OPERATOR_GUIDE.md, SCRIPT_PROMPT.md, docs/HOW_IT_WORKS.md. UI is in English.

Specs: PRE=0.6 s before VO, END card 4.0 s (since 09-24). Captions: **Arial** Bold 84 (was "Poppins" in the styles, but libass
never found the per-user Poppins and rendered Arial — every approved video is Arial; set explicitly 09-28), word-by-word (current + past words
opaque, upcoming dimmed), MarginV 540. **All text must stay inside the Facebook 1:1 centre crop (y 420–1500)** —
title MarginV 470/520/650, credit MarginV 440 (boss feedback 09-22). Title: brand small amber + "PART N" + name.
End card: dimmed overlay, "CAR HAULER / REPAIR HOUSTON", "HOUSTON, TX · 832-708-5492" (amber #F5A623).
Audio: VO highpass 80 + compressor + 3.2 kHz presence; nat 0.05; music Thunder.mp3 at volume 0.225,
sidechain-ducked by VO (threshold 0.05, ratio 4), fades; loudnorm I=-14 TP=-1.5. Result: music ~19 dB under VO.
Music start aligned to a beat (thunder_beats.json, 123 BPM).
Instrumental tracks (verified): Thunder, Hollywood_waves, Hyde_and_seek, Kama_Sutra, Fields_of_space,
Another_Day, Symphony_one. Vocal: Tribal_soul, Let_it_be, Airplane_remix_new, DM, The_one_for_you,
Wanna_be_bad, If_I_Loved, Lucky_wind, Salty_breeze. I_see_U borderline — avoid.

## Windows setup
- ffmpeg full build with libass + libvidstab: `winget install Gyan.FFmpeg`
- Python packages: `python -m pip install --user -r pipeline/requirements.txt` (only needed to run from source / rebuild the exe)
- Fonts: none needed — captions use Arial (ships with Windows).

## Current status (handover 2026-10-21)
- Batches built: 09-22 paint series, 09-23 ten topics, 09-24 ten topics (Cottrell logo), 09-29 ten topics on the
  09-25 footage (`scripts/topics_0929.txt`, batch `scripts/batches/2026-09-29.json`). Latest version of every video in output/.
- Open items: boss OK for the Cottrell trademark in ads; film Cottrell trailers in the bay; film masking on gray steel;
  ask for original phone files instead of messenger copies; Google Drive folders "New marketing materials", "Glasses",
  "Drone footage", "Inclosed trailer roof install" were never downloaded.
- Daily routine: OPERATOR_GUIDE.md. Agents: `python pipeline/chrh.py …` or the skill `.codex/skills/chrh-video/`.

## Pending scripts (not yet voiced)
**Sandblast & paint** (124 words; drop the cylinder clause if not confirmed):
Sandblasting is one of the most demanding jobs we do at Car Hauler Repair Houston, and it's the step that decides how long a paint job will last. Before blasting, the trailer is prepared, and equipment like the cylinders is removed. Then our team blasts the entire frame, cutting through old paint and rust until the whole trailer is down to bare gray steel. Next, every element that needs protection is masked and taped, and the trailer gets a coat of brown primer to seal the fresh metal. The final stage is the red top coat, laid over the primer for a clean, durable finish. Paint can only be as good as the surface underneath it. Contact Car Hauler Repair Houston for sandblasting and paint.

**Miller 2007 — bushings & hinges** (112 words):
This 2007 Miller seven-car hauler came into Car Hauler Repair Houston with worn-out hinge points. The bushings were broken, several hinges were worn far past their service life, and the platform was badly damaged, so it no longer operated the way it should. Our team replaced the bushings and partially replaced the hinges that were too worn to keep, restoring the pivot points that every platform movement depends on. Worn bushings and hinges don't fix themselves, and the longer they're ignored, the more damage they do to the rest of the trailer. Now this Miller's platform is ready to work correctly again. Need hinge or bushing repair? Contact Car Hauler Repair Houston.

**Decks — general** (125 words):
At Car Hauler Repair Houston, deck work is a big part of what we do. Decks take more abuse than almost any other part of a car hauler, and every vehicle that's loaded and unloaded wears them down a little more. Damaged decks slow down loading and put the cars you haul at risk, so it pays to fix them before they fail. We repair damaged decks and build new ones in our shop, working in both steel and aluminum, from perforated deck sections to complete deck replacements, and right now we're also building aluminum ramps. Whatever style your trailer runs, we build decks to fit it. Want to see more of our deck work? Check out our page, or contact Car Hauler Repair Houston.

Note: Cyrillic names in this file (пескоструй = sandblasting, покраска = painting, сварка = welding, зеркальная поверхность = mirror surface) are real footage file names — keep them.
