# Boss rules (from the project memory AGENTS.md / CLAUDE.md)

Rule 10 (09-24) overrides the automatic blur of rule 7.
Cyrillic names below are real footage file names (пескоструй = sandblasting, покраска = painting, сварка = welding).

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
