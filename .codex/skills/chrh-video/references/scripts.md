# Writing the scripts

## File format (what `chrh.py check/build` and the GUI read)

```
=== brakes | LOCKED ON THE SCALE | BRAKES & AIR SYSTEMS | Thunder
Brakes locked up on the scale? That's the kind of stop ... [HOOK 2] Why does the air side matter so much? ... Call the number on screen.

=== cottrellclaim | COTTRELL CLAIM? | HOW WARRANTY WORK HAPPENS | Hollywood waves
Something failed on your Cottrell while it's still under warranty. What now? ...
```

- Header: `=== key | TITLE | SUBTITLE | Track`. `key` = lowercase latin, unique across ALL days (it names the
  voice-over file `voiceover/<key>.mp3` and the output). TITLE ≤ 22 chars (auto-shrinks past 13).
- Track: one of `Thunder, Hollywood waves, Kama Sutra, Fields of space, Another Day, Symphony one, Hyde and seek`
  (instrumental tracks by the boss). Rotate them. Tracks with vocals must never be used.
- A key containing `cottrell` (or the word Cottrell said 2+ times) gets the Cottrell logo automatically.

## Text rules

- 115–125 words ≈ 40 s of voice ≈ 45 s video. One paragraph.
- **No digits.** Write numbers as words ("six-month", "thirty-six months"): the voice reads digits unpredictably
  and the word timing breaks. The phone number is on screen — say "call the number on screen".
- First sentence = hook (a question or the customer's problem). Put `[HOOK 2]` right before a second hook sentence
  around the middle (a question works best). The operator does NOT read the marker aloud.
- Natural connected sentences; problem → what we do (in the right order) → result → short call to action.
  Vary the call to action between videos.
- Start with year/make/model when the video is about one known trailer.
- Facts only from `facts.md`. Never invent dimensions, materials, causes, specs, prices or procedures.
- One video per day about the Cottrell partnership. Do not claim anything about Cottrell trailers on screen —
  none were filmed in the shop.
- Before writing, list topics of previous days (`scripts/topics_*.txt`) and pick new angles. Good sources of
  angles: the "What we fix" list, pricing/approval policy, warranty types, same-day, bays/location, fleet,
  reviews, the Cottrell warranty terms (one aspect per video).
- If a word is unknown to the aligner, `check` warns; it guesses a pronunciation and stores it in
  `pipeline/extra_dict.txt` (fix by hand if the alignment looks off: `word  PH ON EM ES`, CMU phones).
