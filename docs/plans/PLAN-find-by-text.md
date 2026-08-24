# PLAN — Find-by-text ("helmet, find exit") + "read that"

Status: plan only, no code. Written 2026-08-23 against `camera/cv_fusion.py` @ current tree.

## Goal

Two new query-tier capabilities built on cloud OCR (nemotron-ocr-v2, NIM):

1. **Find-by-text** — the flagship. User says "helmet, find exit" (or, in dev,
   presses a key and types a word). The system OCRs the scene repeatedly while
   the user pans (same UX as the door scan: "searching… pan slowly"). When a
   detected word fuzzy-matches the target (case-insensitive, edit distance ≤ 1),
   it announces "found exit, ten o'clock, about 2 meters", locks the existing
   Soundscape beacon on the word's **world bearing** (IMU-anchored, exactly like
   door mode), and guides. While guiding it re-OCRs every ~2 s to re-fix the
   bearing. Arrival = door-mode geofence behavior.
2. **Read that** — single OCR pass of the center view; speak the largest /
   most-central text block. One shot, no beacon.

## Evidence

- **OCR engine benchmarked and picked** — `docs/research-sources/vlm-integration-2026-08-22.md`,
  "nemotron-ocr-v2 benchmark (2026-08-23)": endpoint
  `https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-ocr-v2` (dedicated CV-infer
  format, NOT chat completions); 1.3–2.4 s per image; returns **per-word text +
  confidence + normalized bounding boxes**; read "HEINZ / TOMATO KETCHUP /
  NET WT 397g" off a synthetic 720p label at 0.92 confidence. Boxes → pixel →
  `pixel_azimuth` means the beacon comes almost free.
- **The pattern to copy exists and works** — door mode in `cv_fusion.py`:
  `_door_scan()` (line ~801) scans newest frames while the user pans, anchors
  each hit in world bearing (`wb = az + yaw0` via `_yaw_now()`), clusters by
  `DOOR_CLUSTER_DEG`, announces candidates via `_say_q()`; the guiding block
  (line ~1247) re-fixes bearing every `DOOR_REDETECT_S` via `_door_redetect()`
  on a daemon thread and drives `bcn.update(rel, dim=stale, duck=speaking)`.
- **Client discipline to copy** — `camera/vlm.py`: key from `NVIDIA_API_KEY`
  env else git-ignored fallback files, `busy` single-flight Event, (5, 20)
  timeouts with one retry, honest spoken failures ("no connection"), every
  query appended to a jsonl log.
- **Pixel-size limits** — `docs/research-sources/transit-headsign-ocr-2026-08-20.md`:
  recognition needs **≥ 24–32 px character height**; at 1920 px across 119.58°
  the fisheye gives ~16 px/deg (our 720p pipeline: 1280 px → ~10.7 px/deg).
  Geometry: a 0.15 m character is ~8 px at 10 m on the 1920 px sensor — so
  find-by-text is honest at **label/signage range, roughly ≤ 5–8 m for normal
  sign text**, not across a parking lot. Set expectations in the spoken UX
  ("nothing found, get closer or pan").
- **Voice grammar constraint** — `camera/voice.py`: Vosk runs in **closed
  grammar mode** (`KaldiRecognizer(model, 16000, grammar)`), which
  force-matches everything to the phrase list. Open-vocabulary "find X" is
  not possible without leaving grammar mode (which reintroduces the
  false-accept problem the design exists to solve).

## Design

### New module: `camera/ocr.py` (mirror of vlm.py)

- `read(frame, cancel=None) -> list[Word] | None` where
  `Word = {"text", "conf", "box"}` with `box` normalized 0–1
  (x0, y0, x1, y1 — confirm exact field names against the live response on
  first call; the benchmark says normalized boxes, log one raw response).
- Same discipline as `vlm.py`: `_api_key()` copied verbatim (same NIM key
  works), module-level `busy = threading.Event()` single-flight,
  `requests.post(..., timeout=(5, 20))`, one retry on 5xx/exception, every
  call logged to `camera/ocr_log.jsonl` with latency + word count.
- Input: single BGR frame, JPEG-encoded q70 base64 (same `_encode` shape,
  no hand crop). The CV-infer endpoint takes an image payload, not chat
  messages — write the request per the benchmark script's format, and keep
  a `# NOTE: NOT chat completions` comment.
- Frame choice: `vlm.sharpest(frames)` reused (import from vlm) — blur kills
  OCR even harder than VLM.

### Find state machine (parallel to `door` dict in cv_fusion main)

`find = {"target": None, "state": "idle"|"scanning"|"guiding", "sel": None,
"reocr_t": 0.0, "lock": threading.Lock()}`

- **Trigger**: voice `find_<word>` command (see grammar below) or dev key
  `f` → prompt on stdin/HUD for arbitrary typed word.
- **Scan** (`_find_scan(target)`, daemon thread, modeled on `_door_scan`):
  say "searching" immediately (latency UX — OCR round-trips are 1.3–2.4 s
  each, a scan is 2–3 round-trips over ~5–6 s of panning). Loop while
  `t < FIND_SCAN_S` (~6 s): grab newest frame + `yaw0 = _yaw_now()`
  **at grab time** (the round-trip is seconds long; yaw must be sampled when
  the frame was taken, not when the response lands), call `ocr.read`, fuzzy
  match each word: casefold both, accept if `Levenshtein(word, target) <= 1`
  (write a 10-line DP helper, no dependency; also accept substring hit for
  multi-word OCR tokens). On match: center of box → pixel coords
  (`x * W, y * H`) → `pixel_azimuth(px, py)` → `wb = az + yaw0`.
- **Range**: text height is unknown (no DOOR_HEIGHT_MM equivalent), so:
  1. **ToF association** — reuse the zones list: if any valid zone within
     ±8° of the word's azimuth and rows 0–2, take its median range. Works
     < 4 m, which is exactly the label/indoor-sign regime.
  2. Else say **"ahead"** with no number. Never invent a distance from
     bbox height.
- **Announce**: `"found exit, ten o'clock, about 2 meters"` (clock via the
  existing `clock_hour`/o'clock phrasing in `_door_scan`; range phrase only
  when ToF-associated). Multiple distinct matches: cluster by
  `DOOR_CLUSTER_DEG`-style bearing bins, announce ≤ 2, prefer highest
  confidence — but unlike doors, auto-lock the best match (the user asked
  for a specific word; no selection menu needed). No match after the scan:
  "didn't find exit, get closer or pan and try again".
- **Guide**: copy the door guiding block verbatim in structure:
  `rel = _wrap(sel["wb"] - cur_yaw)` when IMU present, `bcn.update(rel,
  dim=stale, duck=speaking)`, mute on `audio_on`/`level_mode`, arrival when
  ToF range < 1200 mm and |rel| < 25° (or, with no ToF range ever, arrival
  by user "stop" only — say so at lock time: "guiding, say stop when done").
  Re-OCR every `FIND_REOCR_S = 2.0` s on a daemon thread (`_find_reocr`,
  mirror of `_door_redetect`): re-match the word, update `wb`/`seen`;
  stale > 4 s → beacon dims. Mutual exclusion with door mode and object
  guide, same yield pattern as keys `d`/`g`.

### "Read that" (voice `read`, key `r` — check `r` is unbound; it is)

Single `ocr.read` on sharpest of `vlm_frames`. Group words into lines by
box y-overlap; score each line by (area × centrality); speak the top block,
first ~12 words, via `_say_q`. "no text visible" on empty result.

### Voice grammar (the honest limit)

Open-vocab "find X" clashes with the closed Vosk grammar — **we do not
solve open vocabulary in v1**. Instead:

- Curated findable-word list in `voice.py` PHRASES:
  `"find exit"`, `"find washroom"`, `"find sale"`, `"find ketchup"`,
  `"find open"`, `"find push"`, `"find pull"` → tokens `find:exit` etc.
  (`FIND_WORDS = [...]` list, PHRASES generated from it), plus `"read that"`
  → `read`. Grammar stays closed; false-accept behavior unchanged.
- **Arbitrary words are dev-keyboard only** (key `f` → type the word in the
  console). Document this limit in the plan and the spoken help.
- Future path (out of scope, note only): a second free-decode Vosk pass on
  the audio tail after "helmet find", or streaming cloud ASR for the one
  armed utterance.

## Implementation steps

1. `camera/ocr.py` — new module per Design; copy `_api_key`/`_log`/retry
   skeleton from `camera/vlm.py`; log one full raw response on first success
   to pin the box schema. (~90 lines)
2. `camera/voice.py` — add `FIND_WORDS` list + generated `find <w>` phrases
   and `"read that"`; tokens `find:<w>` and `read`. (~10 lines)
3. `cv_fusion.py` — constants block near DOOR_*: `FIND_SCAN_S = 6.0`,
   `FIND_REOCR_S = 2.0`, `FIND_EDIT_MAX = 1`, `FIND_ARRIVE_MM = 1200`.
4. `cv_fusion.py` — `_lev(a, b)` edit-distance helper + `_find_scan(target)`
   + `_find_reocr()` next to `_door_scan`/`_door_redetect`; ToF-association
   helper `_range_at_az(az, zones)` (shared — door mode could adopt it later).
5. `cv_fusion.py` — `find` state dict + guiding block placed directly after
   the door-mode block (~line 1277), same mute/dim/arrival structure.
6. `cv_fusion.py` — dispatch: voice `find:<w>` and `read` in the voice→key
   block (~line 1377); key `f` (typed word via `input()` on a thread so the
   frame loop never blocks) and key `r`; "stop" cancels find mode like door
   mode (extend the `vc == "stop"` branch).
7. HUD: `FIND '<word>' SCANNING…` / `GUIDING '<word>'` putText next to the
   door-mode label.
8. Update `docs/DEVLOG.md` per project convention.

## Test plan

- **Unit (offline)**: `_lev` cases (exit/exlt/EXIT/exits); box→pixel→azimuth
  on a synthetic word at known image position; line-grouping for "read that".
- **Bench (online)**: printed "EXIT" sheet at 1.5 m / 3 m / 5 m — measure
  found/miss vs distance and log px char height from boxes; confirms the
  transit-doc pixel floor for our lens. Ketchup bottle at 0.5 m ("read that").
- **Pan test**: sheet at 45° off-axis; verify world-bearing lock survives
  looking away and back (beacon dims then re-centers) — the door-mode sign
  caveat (cv_fusion.py line ~1201) applies here too.
- **Latency**: "searching" ack within 300 ms of the command; first
  found/failed verdict ≤ 8 s.
- **Failure honesty**: WiFi off → "no connection" spoken, mode exits clean.

## Risks

- **Response schema drift** — box format is from one benchmark run; pin it
  from a logged raw response before writing the parser (datasheet-first).
- **Free-tier NIM queue variance** (VLM saw 2.3–6.4 s) → scans may fit only
  1–2 OCR frames; mitigate by extending scan window while user still pans,
  and never blocking the frame loop (all network on daemon threads).
- **Yaw-at-grab bookkeeping** — pairing a seconds-old response with current
  yaw would smear bearings by the whole pan; the design samples yaw at frame
  grab, but this is the #1 likely bug.
- **OCR hallucination on texture** — require conf ≥ 0.6 for a match; edit
  distance ≤ 1 on short words ("EXIT"/"EXIT"-like "EXIT?"): cap matches to
  words of length ≥ 3.
- **Connectivity requirement** — same as VLM; field rig is hotspot-connected
  (accepted in the research doc), but the failure must always be spoken.
- **IMU absent** → fall back to camera-relative azimuth like door mode does
  (`c["imu"]` flag pattern), beacon only meaningful while the word is
  near-frame.

## Effort

- ocr.py client + schema pinning: **2–3 h**
- Find state machine + guiding + dispatch: **3–4 h**
- Voice grammar + "read that": **1–1.5 h**
- Bench + pan testing, tuning: **2 h**
- **Total: ~8–10 h** (two sessions).

## Dependencies

- NVIDIA_API_KEY (already in place for vlm.py; same fallback files).
- Network connectivity at run time (hotspot in field).
- Working IMU yaw (`_yaw_now`) for world-bearing lock — degrades, not blocks.
- No new Python packages (requests, numpy, cv2 already in use).
