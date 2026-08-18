# Assistive Helmet — Engineering Devlog

A running log of the build: problems, root causes, fixes, and lessons. Newest first.

---

## 2026-08-17 (evening) — Full hardware complete: motors + switch wired, ID'd, mounted

**Every subsystem is now wired and verified.** The helmet hardware is done.

### Motors (3× ERM coin, 2N3904 low-side, 1 kΩ base, no flyback — user's call)
- Wired to "the next 3 header pins after the ToFs" = **GPIO 17, 18, 8**.
- **Bug: GPIO 17 buzzed non-stop** — the old pause-switch code still configured
  17 as input+pullup, fighting the motor output. Switch code compiled out →
  fixed. Lesson: a reassigned pin's OLD role lives on until you grep for it.
- Then "two motors buzzing like crazy" = NOT a bug — the directional haptics
  were live and the desk was inside alert range. The system worked before we
  believed it.
- **Overheating scare handled remotely**: exploited the new `/api/motor`
  manual-hold to spam zero-duty pulses as an improvised kill switch while the
  real mute endpoint was built and flashed.
- **New firmware endpoints** (no more reflash-per-test):
  `GET /api/motor?i=0..2&duty=0..255&ms=20..2000` (manual pulse, overrides the
  ranging drive during the pulse) and `GET /api/haptics?en=0|1` (software mute).
- **Mounted-position ID (pulse test, user feedback): GPIO 17 = LEFT temple,
  18 = CENTER forehead, 8 = RIGHT temple.** Firmware's guess was wrong on all
  three; defines corrected and **OTA-flashed over WiFi** (USB kept dropping —
  OTA saved the session twice).

### Pause switch
- SPDT toggle: COM → **GPIO 3** (strapping pin, safe — JTAG role needs an
  unburned eFuse), outer → GND, internal pullup. Verified live: 4 clean
  transitions in `/api/status.haptics` while flipping.
- With the switch enabled it overrides the web toggle every frame.

### Pre-glue diagnostic (all PASS)
- Boot: A + B + IMU + WiFi + switch all up. Streams: both ToF at 28 Hz, IMU
  quats at 28 Hz (emitted per ranging frame), quaternion norm 1.0000, cal
  status 3/3, sample noise 0.5°. Zone-health snapshot was meaningless (sensors
  were lying against the desk reading 5–23 mm) — rerun facing open space
  before trusting field quality. Drift number (4.5°/min) also needs an
  untouched retest.

### Haptic contact issue (open)
Motor contact area on the forehead too small. Plan: rigid puck per motor to
spread vibration + foam preload behind it; couple to skin, DECOUPLE from
shell (shell radiates audible buzz next to the ears — masking risk).

### Open next session
1. Confirm the corrected motor order end-to-end (should pulse centre→right→left
   as channels 0→1→2 post-OTA; user hadn't confirmed before shutdown).
2. Re-run zone-health + IMU drift diagnostics with the pod facing open space.
3. `imu_mount_cal.py` — STILL not run; gates all IMU features.
4. Motor puck/foam mounting; v11 column→motor mapping redesign for the
   left/right sensor pair.
5. Dewarp A/B verdict (wardrobe-TV test) still unreported.

---

## 2026-08-17 — Helmet firmware flashed, IMU live, unified viewer, voice-guided leveling

### Firmware flashed + full stack verified
Flashed last night's rebuild (final ToF pins, perpendicular-distance fix) to
COM9. Boot log: sensor A ranging, sensor B online, WiFi up (192.168.1.228, TCP
3333 + HTTP viewer). **User wired the IMU onto sensor A's bus (6/7)** per
`docs/WIRING.md` — BNO085 online at 0x4A, handshake in 130 ms. The early
"no device at 0x4A" probe warning is cosmetic (fires before the IMU boots).
Only the 3 haptic motors remain unwired. **Hardware buzzer CANCELLED** (user
decision): the compute device's digital sounds replace it.

### Unified viewer: cv_fusion now speaks helmet-firmware
- New `--source helmet` (default): TCP reader for `DATA:`/`DATAT:`/`Q:` lines —
  ToF grids + IMU quaternion over WiFi, no COM-port contention. Firmware sends
  invalid zones as 4000, remapped to the ">0 = valid" convention.
- **Camera-index trap, twice in one morning**: USB re-enumeration moved the
  helmet cam 1→0; a brightness-based auto-pick then chose the LAPTOP webcam
  because the pod was lying lens-down. Fix: select by DirectShow device NAME
  ("HBV HD CAMERA") via pygrabber. Names, not indices, not brightness.
- **3D attitude inset** (top-right): cv2-wireframe of the pod (plate, cyan/
  yellow ±22.5° sensor panels, camera stub, up-post) rotating live with the
  IMU, plus a yaw compass ring. Artificial horizon on the main view once the
  mount cal exists.
- **winsound.Beep is full-volume with no gain control** — it drowned the
  speech (user: "can't hear what the commands are"). Replaced ticker + cue
  with generated low-amplitude WAVs (0.10 / 0.22 FS) via PlaySound, and the
  ticker now MUTES during utterances.

### IMU mount calibration + ball-mount leveling
- `visualizer/imu_mount_cal.py`: two-pose gravity alignment (level, nose-down)
  → R_chip_to_helmet. User's insight simplified it: the IMU board is mounted
  FLAT and SQUARE on the pod base, so the result is **snapped to the nearest
  of the 24 cardinal orientations**; the snap deviation doubles as a
  mounting-error measurement. NOT YET RUN — needs his hands.
- The pod hangs on a **ball camera mount** (new info) — attitude vs the helmet
  drifts on every re-clamp, which makes the IMU the alignment instrument:
  - `visualizer/mount_level.py`: standalone bubble level (bench use).
  - **cv_fusion key `l` = voice-guided leveling mode**: "tilt up 5" → "tilt
    left 2" → "level, lock it", auto-exits when confirmed. Hazard voice +
    ticker pause during it. The blind-user version of a spirit level.

### Open before next session
1. **Run `imu_mount_cal.py`** (2 min, user's hands) — everything IMU-labelled
   waits on it: horizon, attitude model truth, leveling-mode directions.
2. Wire 3 motors (user supplies pins) → firmware pin update + ID pulse test →
   temple-haptics direction channel (the [HW] track in MASTER-SYNTHESIS).
3. Walk-test the v2 voice + M3 demo captures.
4. IMU next uses: sterile-cockpit gate (suppress speech during fast head
   turns), ToF↔camera de-rotation, ground-plane bbox ranging.

---

## 2026-08-16 (night, autonomous run 2) — Callout engine v2: research says we were 30× too chatty

Third research stream landed (`research-sources/blv-usefulness-2026-08-16.md`)
and overturned parts of the evening's design. Everything merged into
`docs/MASTER-SYNTHESIS-2026-08-16.md`; all [BUILD NOW] items implemented and
smoke-tested against live hardware in one unattended pass.

### What the evidence overturned
- **2 s narration cadence** → Soundscape (open source — actual constants read
  from `AutoCalloutGenerator.swift`) never repeats an object within **60 s**
  and treats **silence as the default state**. Chatter is the #1 named
  abandonment cause in users' own words.
- **Numbers in walking speech** → no shipped product does it. Proximity is a
  **repetition rate** (parking-sensor pattern; Apple/Oko/biped all encode it
  non-verbally). Also van Erp 2020: 2-item recall ceiling while walking —
  "person left, 2" was already one item over.
- **Person callouts** → the *least*-wanted feature in BLV user studies ("the
  dog detects those people"). Head-height obstacles are the product: 13% of
  ~300 blind people suffer head-level accidents monthly, cane or dog
  regardless.

### Built (cv_fusion.py v2 + callout_trainer.py)
- **Silence-default engine**: routine tier deleted; speaks only hazards
  (<1.8 m or closing), directives, path-clear, sensors-lost. 60 s per-object
  cooldown, approach re-announces, stale queue items (>1.5 s) dropped unspoken.
- **Two-item grammar, no numbers**: "obstacle, left" / "maybe pole, ahead"
  ("maybe" = confidence hedging below 0.50, Soundscape's about/around pattern).
- **Proximity ticker**: sparse 600 Hz 40 ms blips, period 1.2 s→0.15 s over
  1.8 m→0.5 m, path-cone only. Distance now rides tempo, not words.
- **F9 scene query** (global hotkey): Apple two-tier verbosity — silence by
  default, detail on demand, numbers allowed there ("person ahead, about 2
  meters"), verbatim-Soundscape empty state: "There is nothing to call out
  right now."
- **Cane-blind-spot filter**: bottom ToF row (cane territory + mostly floor at
  the 22.5° mount) rendered but never spoken/ticked; hazards need rows 0–2.
- **Person deprioritized**: nearest hazard wins, no class priority.
- **ByteTrack**: worker switched `predict`→`track(persist=True)`; range history
  keyed by track ID so a second person can't inherit the first's history;
  closing (< −0.5 m/s) computed per-ID; distance still re-derived from the
  live ToF frame every cycle (red-team rule).
- **`--rate` flag** (blind listeners parse 8–22 syl/s; the ceiling is ours).
- **`camera/callout_trainer.py`**: flashcard drill for the brevity vocabulary,
  scores accuracy + reaction time — how pilots learn brevity, and the 60-second
  portfolio demo of the two-mode design.

### Verification
Compile-clean; ran 25 s+ against live camera + both ToF sensors without crash
(detector at ~10 fps seg + track, ticker and speech threads live). Left
running for the user's return. Untested pending a human: audible tick pacing,
F9 phrasing quality, directive feel while moving.

---

## 2026-08-16 (late evening, autonomous run) — Firmware fixed + CV fusion first light

User left the machine with "don't stop working until all is complete." Done in
sequence, everything verified as far as possible without hands:

### Firmware consolidated (built clean, NOT YET FLASHED — deliberate)
- ToF pins updated to the final wiring (A=6/7/4 bus0, B=15/16/5 bus1); bus
  ports swapped to match; sensor naming updated to A/left, B/right.
- **The cos-table double-correction is fixed**: `distance_mm` is perpendicular,
  so forward = z·cos(α+pitch)/**cos(α)** — the old slant factor applied a
  zone-elevation correction the value never contained, biasing outer rows ~8%.
- `MOUNT_PITCH` 30/−5 → 22.5/22.5 (group tilt), `MOUNT_ROTATION_DEG` 270 → 0
  (verify with viewer on first flash).
- Buzzer/motors parked on provisional free pins (40, 1/2/41) — NOT wired; user
  supplies real pins later. `idf.py build` passes, 1062/1062.
- **Not flashed because the CV work needs `tof_pin_test`'s GRID stream** on the
  ESP32 right now. Flash when switching back to helmet/haptics work.

### CV fusion built and hardware-verified (M1 + M2 of docs/CV-FUSION-PLAN.md)
- YOLO26n: **22 fps on laptop CPU at 416px**, live camera detection confirmed.
- `camera/cv_fusion.py`: detector in a worker thread, zone quads projected with
  the full joint calibration, box↔zone association in image space, box range =
  min over claimed zones, ToF-only near zones render as OBSTACLE alerts (CV
  can't name branches — ToF never misses them).
- **Headless end-to-end run against live hardware worked** — both sensors
  streaming, zones tiling with the designed centre seam visible on the room,
  detection + association + render verified
  (`camera/snapshots/cvfusion_headless_test*.png`).
- **Live data found a real bug immediately**: a person standing at the field
  edge overlapped zone quads but contained no zone centroid → no range.
  Fixed with a rect-overlap backup (>35% of zone area). Also caught, in one
  frame: the real person NOT detected while a clothes rack scored "person
  0.42" — the red-team's single-frame-detector warning, live. Tracking +
  temporal persistence is the planned answer, and alert logic must never
  gate a near ToF hit on CV agreement.

### Research pass (two Opus agents, reports archived verbatim)
`docs/research-sources/cv-stack-research-2026-08-16.md` — detector choice,
ToF+mono-depth fusion literature (CFPNet is nearly our hardware), what biped/
Sight Guide/the ETA RCT teach, value-for-effort ranking.
`docs/research-sources/cv-redteam-2026-08-16.md` — 21 ranked NOT-do-to items:
sunlight collapses ToF range to ~1 m; thin poles fall below the reflectance
floor; motor noise can erase the device's whole benefit (masking, +33%
contacts); cables ended Cybathlon runs, not algorithms; claims language fixed.
Decisions folded into `docs/CV-FUSION-PLAN.md` §Decisions.

---

## 2026-08-16 (evening) — The 8 mm residual diagnosed: signal-weighted zone centroids

> **Stage 4 first light, 21:30:** `camera/fusion_overlay.py` ran live against the pod
> (COM9 + camera 1) and the user confirmed it working. Both sensors' zone quads +
> surface-centroid dots rendered on the fisheye feed in real time.

Adversarial review of everything the earlier session left open. Ran the datasheet
(DS14161 Rev 12, now archived in `docs/datasheets/tof/` with extracted text), three
parallel research agents, and a residual autopsy on the captured pose data. Every
standing hypothesis was tested against data; one survived.

### The autopsy — five hypotheses, four executions
All run from the existing 17+22 poses, no new captures (`scratchpad/residual_autopsy.py`
logic now recorded here):

| hypothesis | test | verdict |
|---|---|---|
| tangent-uniform zone spacing | refit with tan-spaced rays | **worse** (8.58/9.29 vs 7.96/8.60) |
| per-zone distance bias | fit biases on even poses, score on odd | **fails CV** — held-out rms got worse |
| depth-scale mismatch (ToF or camera) | fit global z-scale / plane-d scale | rms barely moves (7.96→7.55 best) |
| fisheye periphery extrapolation | corner-coverage annulus + KB1–KB4 model-order sweep on the original 19 calib shots | **dead**: 39% of corners beyond 30° (max 61.8°), all four model orders agree within **0.08° at 45° off-axis**. Intrinsics contribute <0.1°, not 1.1° |
| effective (signal-weighted) zone centroids | free per-row/col ray table | **rms 7.96/8.60 → 4.22/4.80**, and A and B **independently agree on the table to ~1°** |

### The two signatures that identified it
1. **The error is per-POSE, not per-zone.** Per-zone mean residual is nearly flat
   (±2 mm) while total rms is 8 mm — so no static per-zone pattern exists. The
   variance lives *within* poses: ToF points fit their own plane at 3.1 mm but miss
   the camera's plane at ~7.4 mm. The planes disagree in **tilt**.
2. **Tilt disagreement correlates with board tilt** (+0.85 on sensor A). A lateral
   (angular) ray error is invisible on a frontal board — moving a point sideways on
   a frontal plane doesn't change its plane distance — and leaks into the residual
   in proportion to board tilt. Exactly what was observed.

### Root cause
**A zone's reported distance is a signal-weighted average over its cone, and the
signal is not uniform across the zone.** The VCSEL field of illumination is 43.4°
at 75% power and 57.9° at 10% (DS14161 §2.3) — outer zones are lit brightly on
their inner side and dimly on their outer side, so their *effective* centroid ray
is pulled inward. The 14% default sharpener (inter-zone bleed suppression) adds to
it. Fitted effective outer columns: ±13.4° where geometry says ±16.9°.

**Both prior measurements were right — they measure different things:**
- The tripod detection test measured the zone's geometric *bounds*: 45°, datasheet-true.
- The plane solver measured the zone's signal-weighted *centroid* on extended
  targets: ~34° effective span. Not a bug — a second, real property of the sensor.

Supporting fact from research: ST publishes per-zone ray tables
(`VL53L5_Zone_Pitch8x8`/`Zone_Yaw8x8`) — the real lens mapping is close to
tangent-uniform but off by up to ~1° per zone, i.e. ST themselves do not model the
field as uniform-in-angle. ST staff also confirm on the record that `distance_mm`
is **perpendicular, not radial** — closing that question permanently.

### The calibration that ships
Joint two-sensor solve with the CAD ToF-pair geometry enforced rigid (45.000°,
36.249 mm — known to sub-micron) and ONE shared effective ray table (same lens
design, two sensors): **rms 5.51 mm total** (A 5.59 / B 5.45, floors 3.08/3.27),
rotation 1.15° from CAD. Written to `camera/tof_calib_poses/solved_joint.json`.

**Usage rule for fusion:** geometric 45° bounds for *zone occupancy / frustum
drawing*; the effective centroid table for *extended-surface geometry*. A small
object in a zone can be anywhere in the geometric cone; a wall's reported distance
belongs to the effective centroid ray.

### Datasheet/research facts locked in (agent-verified, sources in the entry above)
- `distance_mm` is **perpendicular** — ST staff (John E KVAM) on the record, twice;
  the radial→perpendicular conversion happens on-chip. Closed permanently.
- 45° is **edge-to-edge** of the zone array; the 65° "diagonal" in DS14161 Table 2
  is an *empirical detection extent* (88% white target, 1 m, dark), geometrically
  inconsistent with 45×45 under any model — never derive zone angles from it.
- ST's own zone table is ≈ tangent-uniform but hand-tuned, ±1° accuracy, has a
  known bug (Yaw8x8 index 48: 203.20 should be 215.40), and no official 4×4 table
  exists. Sub-0.5° zone-geometry refinement is below the sensor's own spec.
- DS14161 §7.2.4: corner zones may degrade **up to 4%** vs the centre 4 (16 mm at
  400 mm). Cross-checked against our data: a per-zone *distance* bias would show on
  frontal boards, which it doesn't — so for our unit this term is small and the
  centroid explanation stands.
- Rx optical centre sits **1.720 mm** off package centre along the long axis
  (0.100 mm short axis), ray origin **0.736 mm** below the top face (Fig 26+28).
  Sign along the long axis still unresolved.
- Thermal: **0.1 mm/°C** drift even with autocal; autocal runs only at stream
  start — set `vl53l8cx_set_VHV_repeat_count()` for periodic recal once haptic
  motors (self-heat) run alongside ranging.
- 4×4 is spec'd ~2× tighter than 8×8 at range (±3-4% vs ±5%) — the mode we already
  stream.

### Lessons
- A residual that survives R, t, scale, and per-zone bias is telling you the
  *forward model* is wrong, not the parameters. List what each hypothesis would
  predict for the residual's **structure** (per-zone? per-pose? tilt-coupled?)
  before fitting anything.
- Two contradictory measurements can both be right. "What exactly does each one
  measure?" resolved a week-long 34°-vs-45° fight in one evening.
- Model-order sweeps (KB1→KB4) at identical RMS are the cheap, decisive test for
  extrapolation error — RMS itself carries no information about unsampled regions.

---

## 2026-08-16 — Stage 3 extrinsics: CAD geometry measured, first ToF↔camera calibration, and two of my own bugs

Long session. Took the pod from "nobody remembers how it was wired" to a measured
ToF→camera transform, via a rewire, a full CAD geometry survey, a working calibration
capture rig — and several false alarms that were all model errors, not hardware.

### Wiring recovered after the helmet remount
Everything had been unplugged to mount onto the bike helmet. Rebuilt the map from the
**firmware and the flashed ELF**, not from docs.

- Both ToF verified ranging on new pins: **A = SDA6/SCL7/PWREN4**, **B = SDA15/SCL16/PWREN5**.
- **The IMU runs I²C, not SPI.** The ELF contains `bno08x_init`, `sh2_open`,
  `i2c_master_transmit` ×7 and **zero** SPI symbols; a repo-wide sweep for
  `driver/spi_master.h`, `spi_bus_initialize`, `SPI2_HOST` matches nothing. The SPI work
  is real but older and on an **ESP32-C6 bench rig** (`docs/imu-bno085-bringup.md`).
  Confirmed physically: PS1 = PS0 = GND, the I²C strapping.
- **Lesson:** when memory and docs disagree, the compiled binary is the tiebreaker.
  Symbol presence in the ELF is not opinion.

### "Both sensors dead" — it was power, and the failure symmetry said so
Neither sensor answered on either bus; every address scan came back empty.

- **Root cause:** sensors unpowered.
- **The diagnostic that mattered:** *both* buses failing identically. Two independently
  wired sensors don't fail the same way by coincidence — that points at something shared
  (power, ground, rails), never at the data pins. Saved re-checking SDA/SCL.
- Full map written up in `docs/WIRING.md`.

### Black foam board vs white wall — measured instead of assumed
I claimed black would be too IR-absorbing at 940 nm. Built a surface-quality mode into
`tof_pin_test` reporting valid-zone count, frame jitter, sigma, and the sensor's own
**reflectance** estimate.

| Sensor B, same sensor | black board @756 mm | white wall @958 mm |
|---|---|---|
| valid zones | **16/16** | 12.8/16 |
| frame-to-frame | **5.76 mm** | 7.50 mm |
| reflectance | 9.4% | 56.3% |

- The board **is** dark at 940 nm (9.4%) — but at 76 cm it returns *more* signal
  (30.4 kcps/SPAD) than a 60%-reflective wall at 2.7 m (14.1). Signal falls as 1/r²;
  distance dominates reflectance.
- The white wall dropped 15% of its zones to **specular reflection** — a semi-gloss wall
  throws light away at the oblique angles our ±22.5° sensors view it from. Matt-and-dark
  beat bright-and-shiny.
- **Lesson:** visible colour does not predict near-IR behaviour, and the sensor reports
  its own reflectance estimate if you ask for it.

### CAD geometry: both ToF boresights measured to 0.003° of design
Measured PCB corners in SOLIDWORKS, derived full right-handed frames. Stored in
`cad/extrinsics_measured.json`; `docs/extrinsics_solve.py` re-derives every stored value
from the raw points so they cannot silently drift.

- Rectangle test on the right sensor: opposite sides equal, **diagonals within 0.022 µm**,
  4th corner **0.00 µm** off-plane, corner angle **90.0000°**.
- Both boresights within **0.003°** of the designed ±22.5° yaw + 22.5° group tilt.
- Both boards' up-axes identical to 4 dp and equal to `(0, cos22.5, sin22.5)`.
- **In the camera frame both sensors are PURE YAW** — pitch ≈ 0.0001°. The group tilt is
  common to camera and sensors so it cancels. The rigid-group construction verifying
  itself; a per-part tilt would leave residual pitch.
- **Trap recorded:** both sensors must use the board's *own left edge*, which is outboard
  on one and inboard on the other. Using mirror-corresponding edges flips the roll while
  every other check still passes.

### Bug #1: distance is PERPENDICULAR, not slant
Calibration residuals showed a strong radially-symmetric pattern — corners −14 mm, centre
+14 mm — recurring across poses (correlation 0.64). Chased a warped board, a radial sensor
bias, and crosstalk before testing the obvious.

- **Root cause:** treated `distance_mm` as slant range along the zone ray and computed
  `p = distance × unit_ray`. It is the **perpendicular (Z) distance**; correct form is
  `p = z × [tan(az), tan(el), 1]`.
- **Evidence:** same 23 poses, two interpretations — slant gives 12.02 mm plane rms and a
  −36.14 mm false dome; perpendicular gives **3.83 mm rms and −2.93 mm bow**, i.e. noise.
- **Cost:** a hunt for a warped board and a phantom sensor defect, plus false
  "zone off the board" flags in the capture tool.
- **Firmware implication, STILL UNFIXED:** `main.c:142` asserts "that stays as raw slant"
  and `compute_row_cos_table()` multiplies by `cos(zone_elevation + mount_pitch)`. If the
  value is already perpendicular, the zone-elevation half of that correction is applied to
  something that does not need it. The mount-pitch half is still required.
  **Live in the haptics and `/api/status` today.**
- **Lesson:** a radially-symmetric residual is a *geometry model* signature, not a defect
  signature. Test the model before blaming the hardware.

### Bug #2: camera frame x_right pointed the wrong way
The solve came back **179° from the CAD prior**, and I briefly concluded the sensor
identity mapping was backwards. It wasn't.

- **Root cause:** built the camera's `x_right` toward assembly +X. That is the wearer's
  **left**; image-right for a forward-facing camera is the wearer's **right** = −X. The
  wrong sign flipped x and y together — a 180° roll about the optical axis.
- **Derivation to keep:** right-handed with +Z forward and +Y up means a person facing +Z
  has their right along `Z × Y = −X`.
- **Fix:** corrected frame → rotation agreement went **179° → 2.0°**.
- **Lesson:** two opposite "left" conventions ran through the whole session —
  viewer-facing vs wearer-facing. Nearly every sign error traced back to it.
  Name the observer, not the side.

### Sensor identity — the error that cannot be caught downstream
`Sensor A` (pins 6/7/4) = **wearer's LEFT** = CAD `tof_right` (X = +18.67).

- Confirmed two independent ways: a hardware wave test, and from the axes (+X is
  screen-right viewing the front, i.e. the wearer's left; `tof_right` sits at X = +18.67).
- Get this backwards and every depth point lands **mirrored** while every geometric
  self-check still passes. Only visible in fused output.

### Calibration rig + first result
Built `camera/tof_calib_capture.py` (auto-capture on stillness + pose novelty, live
plane-residual colouring, live board-bow readout) and `camera/tof_calib_solve.py`.

- Auto-capture matters: a novelty gate (12°/80 mm) stops you collecting ten
  near-identical poses that look like ten measurements but constrain like one.
- **Colour zones by residual from a *curved* fit, not a plane.** With any board bow the
  corner zones sit ~14 mm off a plane while being perfectly on the board, and a flat-plane
  test flags them as off-board. A zone that has genuinely missed the edge is out by
  hundreds of mm.
- 17 poses, all 16/16 valid, condition number 4.0.
- **Result: rms 4.37 mm against a 3.08 mm noise floor, rotation 1.80° from CAD.**
- **The entrance pupil fell out of it** — 15.3 mm behind the CAD lens-face point, along
  camera +Z. Predicted in advance as the one term CAD structurally cannot see. Fixing `t`
  at the CAD value *raises* rms 4.37 → 10.14, so the data genuinely wants it.

### The 34°-vs-45° field: a long dead end, closed by physical measurement
The solver wanted a **34° zone field** where DS14161 says 45. Reported as a finding;
rejected twice by the user, correctly.

- Ruled out: warped board, radial bias, crosstalk (no cover glass; UM3109 §3.2 scopes it
  to a protective window), distance offset (degenerate — needs an absurd −79 mm),
  checkerboard scale (2.7%, wrong direction), 4×4 mode shrinking the field (nothing in
  UM3109 §4.3), the documented lens flip (§2.2 — real, but pure sign), all 4 rotations,
  transpose, and apex offset.
- **UM3109 §2.2:** the Rx lens "flips (horizontally and vertically) the captured image",
  so zone 0 sees the **top right** of the scene. Real, but mathematically identical to a
  sign change on the field — explains orientation, not magnitude.
- **Four probe attempts failed for the same reason each time — the ToF was seeing
  something other than the probe:** motion differencing tracked the whole arm while the
  ToF reported the hand; torch tracking failed because auto-exposure stops down; the
  checkerboard was taped to a 508 mm foam board covering >100% of the field; then the
  operator's body sat behind the sheet at the same depth.
- **What worked: checkerboard on a tripod, pod in hand.** Nothing else at that depth.
- **Verdict — column c0, the best-determined:**

| row | measured | agreement |
|---|---|---|
| r0c0 | −16.00 | 56.1% |
| r1c0 | −17.50 | 53.9% |
| r2c0 | −17.75 | 65.1% |
| r3c0 | −17.50 | 64.8% |

  mean **−17.19°, spread 0.72°**. Datasheet predicts −16.88 (**0.4° away, inside the
  spread**); the solver predicted −12.84 (**4.35° away, 6σ out**).

- **The datasheet is right. The pod has NO blind wedge** — inner edges meet at the camera
  axis as designed, zero-seam geometry intact. The 34° was the solver absorbing a model
  error not yet located.
- **Lesson:** a fitted parameter contradicting the datasheet by 25% is a bug hypothesis,
  not a finding. And a parameter degenerate with two others (offset, apex) cannot be a
  measurement however sharp its profile looks.

### Open
1. **Firmware pins + haptics move** — `main.c` still expects 1/2/5 and 41/42/40, and the
   ToF sensors now occupy the buzzer and all three motor pins. GPIO 1/2/41/42 are free.
2. **The cos-table double-correction** (bug #1) — live in haptics today.
3. **`MOUNT_ROTATION_DEG = 270` and `MOUNT_PITCH_DEG` are stale** — set for the old
   stacked mounting, not the ±22.5° pair.
4. **Sensor B not yet calibrated** — same procedure, `--sensor B`.
5. **Residual model error** — with FOV pinned at the datasheet 45°, rms is 7.96 mm against
   a 3.08 mm noise floor. Something is still unmodelled.
6. **SPAD offset** (1.72 mm along board-right, DS14161 Fig. 28) not yet applied.

---

## 2026-06-08 — Magnetometer A/B → mag-free decision, FREERTOS_HZ bug, drift cal

Resolved the IMU yaw-drift question by **measuring** instead of guessing, then fixed a
streaming bug it exposed and added drift-reducing calibration. End state: mag-free
**AR/VR-Stabilized Game Rotation Vector**, reliable streaming, dynamic yaw drift cut
~63%.

### The magnetometer A/B — why we went mag-free
Question (user's, fair): the motors are ~5 cm from the IMU through plastic — surely too
far to disturb a magnetometer? Tested it. Captured yaw + the BNO085's own mag accuracy
status (datasheet §3.1.5) sitting still, motors OFF vs ON, after a figure-8 calibration:

| Metric | motors OFF | motors ON |
|---|---|---|
| Mag accuracy | High (3), 100% | **Low (1)**, 897/921 samples |
| Heading uncertainty | 4.8° | **39°** (peak 59°) |
| Yaw noise (std) | 0.46° | 9.46° |
| Max step jump | 0.14° | **59.8°** |

The running motors' rotor magnet makes a **time-varying** field the fusion can't model
(static hard-iron it could). The chip's own confidence collapsed and it threw a ~60°
heading **jump** — which would land exactly during an obstacle alert. **Scale check:**
Earth's horizontal field here ≈ 18 µT; just ~1–3 µT of fluctuating stray field corrupts
heading, and a coin ERM motor at 5 cm plausibly makes a few µT (dipole, 1/r³). So the
"too far to matter" intuition was wrong at this spacing. **Decision: mag-free**
`SH2_ARVR_STABILIZED_GRV` (datasheet §3.1.6 p.39 literally recommends Game/AR-VR RV for
head-tracking in disturbed fields). Lever to reclaim the mag later = distance (1/r³).

### Bug — `FREERTOS_HZ=100` made the IMU task spin and starve the ToF loop
- **Symptom:** intermittent "no `DATA:`/`Q:` on this boot" while the IMU heartbeat kept
  climbing — i.e. the IMU service task ran but the ToF ranging loop never streamed.
  This was almost certainly the long-standing "~20% warm-reboot init flake."
- **Root cause:** `CONFIG_FREERTOS_HZ=100` → 10 ms tick → the service task's
  `vTaskDelay(pdMS_TO_TICKS(2))` computes `0.2 → 0 ticks` = **no delay**. The task
  free-spun (~2376 service calls/s measured, not the intended 500), monopolising the
  shared-I²C mutex and starving the ToF loop (prio 5) on unlucky scheduling boots.
- **Fix:** `CONFIG_FREERTOS_HZ=1000` (in `sdkconfig` + `sdkconfig.defaults`). The 2 ms
  delay is now real → the task paces at ~500 Hz and leaves the bus free. Fresh-boot
  streaming went from 0/3 to reliable; hub stays alive.
- **Lesson:** `pdMS_TO_TICKS(small)` silently truncates to 0 at a coarse tick rate —
  a "delay" that doesn't delay. Check the tick rate before trusting sub-10 ms `vTaskDelay`.

### Drift-reduction calibration (mag-free)
Mag-free yaw only drifts under motion (sitting still on a table the BNO085 auto-nulls the
gyro zero-rate offset, §3.1.3 — measured ~0°/min). Added in `bno08x_init`:
`sh2_setCalConfig(SH2_CAL_ACCEL | SH2_CAL_GYRO)` (gyro ZRO removal cuts drift, accel
anchors pitch/roll, mag OFF) and `sh2_setDcdAutoSave(true)` (persist calibration across
reboots, §3.4). Measured with a repeatable protocol (flat, two physical stops, 60 BPM
metronome, 40 s sweep, return to a marked reference): **drift +2.24° → +0.82°** (~63%,
matched ~195° excursions, N=1). DCD-across-power-cycle benefit still to verify.

### Files
- `components/bno08x/bno08x.c` — `SH2_ARVR_STABILIZED_GRV`; `setCalConfig` accel+gyro +
  `setDcdAutoSave`; `arvrStabilizedGRV` decode; `bno08x_get_status()`.
- `sdkconfig` + `sdkconfig.defaults` — `CONFIG_FREERTOS_HZ=1000`.
- `main/main.c` — `Q:` decoupled from the ToF frame gate (streams every loop iteration,
  6 fields incl. status).
- `visualizer/imu_capture.py` (mag A/B), `imu_drift_dynamic.py` (repeatable dynamic-drift
  test), `visualizer_dual.py` (`Q:` parser tolerant of extra fields).

---

## 2026-06-07 (later) — Magnetometer test mode + two streaming/serial gotchas

Switched the IMU to the **9-axis mag-fused Rotation Vector** to test whether the
magnetometer can kill the yaw drift of the 6-axis Game Rotation Vector (user asked;
datasheet §2.2.4 calls the mag-fused RV "the most accurate orientation estimate").
Now streams `Q:w,x,y,z,status,headacc_rad` — `status` 0..3 = mag calibration accuracy
(datasheet §3.1.5), `headacc_rad` = estimated heading accuracy. Uncalibrated, the chip
reports `status=0` and `headacc=π` (≈180°) — that's the datasheet's "no heading yet"
sentinel, **not** a bug; both improve after a figure-8.

### Bug — `Q:` (IMU) was gated behind the ToF frame, so a ToF stall killed IMU stream
- **Problem:** capture showed the IMU healthy (`hb: rv` climbing ~100 Hz) but **zero
  `Q:` lines**, and zero `DATA:`/`DATAT:`.
- **Root cause:** in `ranging_task`'s loop, `if (!got) { …; continue; }` (no fresh ToF
  frame) skipped the **rest of the loop, including the `Q:` block**. The IMU print was
  coupled to the ToF being ready — so any ToF stall silently took the IMU down with it.
- **Fix:** emit the `Q:` line **before** the `if (!got)` gate, every iteration,
  independent of the ToF. IMU and ToF now stream independently (verified: Q≈DATA≈DATAT
  ~28 Hz together).
- **Lesson:** keep independent data sources on independent emit paths; don't let one
  sensor's readiness gate another's output.

### Gotcha — never RTS-reset the USB-Serial-JTAG to start a capture
- **Problem:** the capture script pulsed RTS to reset the ESP on port open; it then hung
  forever on "waiting for IMU reports," and the port sometimes vanished (`FileNotFound`).
- **Root cause:** this board's serial is the ESP32-S3's **internal USB-Serial-JTAG**.
  An RTS reset reboots the chip, which **drops + re-enumerates the USB device** — the
  open handle goes stale, so the script reads a dead port. (A real external UART bridge
  survives this; the JTAG one cannot, because the bridge *is* the chip.)
- **Fix:** **don't reset** — just attach to the already-running stream (opening the JTAG
  port does not reset the ESP). Bonus: with no reset, the BNO085 keeps its calibration
  across capture runs (the firmware only soft-resets the hub on a real ESP reboot), so
  you calibrate once and can run motors-off / motors-on back-to-back.
- **Lesson:** USB-Serial-JTAG ≠ UART bridge. To force a clean reboot use `esptool`
  (`--before default_reset --after hard_reset`), not an RTS toggle on an open handle.

### Files
- `main/main.c` — `Q:` moved above the ToF `if(!got)` gate; now 6 fields with status.
- `components/bno08x/{bno08x.c,include/bno08x.h}` — `ROTATION_VECTOR` enable;
  `bno08x_get_status()` exposes accuracy + heading-accuracy.
- `visualizer/imu_capture.py` — attach-don't-reset capture; figure-8 calibrate phase
  then still-baseline record; motors-off vs motors-on A/B.
- `visualizer/visualizer_dual.py` — `Q:` parser tolerates the extra fields.

---

## 2026-06-07 — IMU fully working on the shared I²C bus (the full story)

The BNO085 now streams head orientation at **~100 Hz alongside BOTH VL53L8CX ToF
sensors** on the shared I²C_NUM_1 bus, and `Q:w,x,y,z` drives head orientation in
the visualizer. It took peeling back **three stacked, independent bugs** — each one
hid the next. All three + the dead ends are documented so this is debuggable if it
ever regresses. **The wiring was never the problem.**

### Bug 1 — wrong I²C address (0x4B → 0x4A)
- **Problem:** the probe ACKed at **0x4B** but no SHTP read ever decoded.
- **Root cause:** real address is **0x4A** (ADO grounded). The 0x4B "ACK" was a
  misleading write-only response.
- **Fix:** talk to 0x4A. **Lesson:** a write+ACK probe can lie — ground truth is
  *which address returns valid protocol data*, not which one ACKs.

### Bug 2 — the missed one-time SHTP advertisement (the `enable -> -2` wall)
- **Problem:** at 0x4A the handshake *still* failed — `sh2_getProdIds` silent,
  `sh2_setSensorConfig` returned **-2 (SH2_ERR_BAD_PARAM)**, `evt` stayed 0. Tell:
  it worked the **very first time** the board was freshly plugged in, then never
  again.
- **Root cause:** the BNO085 emits its SHTP **advertisement / reset-complete packet
  only ONCE, right after power-on.** Reflashing resets the **ESP, not the IMU** — so
  after boot #1 the advertisement was long gone, `sh2_open()` found nothing to read,
  no SHTP channels got set up, and `setSensorConfig` therefore had no control
  channel → -2.
- **Fix:** in `hal_open()`, send a **reset on the SHTP executable channel**
  (`{0x05,0x00,0x01,0x00,0x01}` = length 5, channel 1, cmd 1 = RESET) so the hub
  reboots and **re-advertises on every boot** — no manual power-cycle.
- **Lesson:** "works once after a physical unplug, dead on every soft reset" = a
  device that only advertises at power-on. Force the device reset in the HAL.

### Bug 3 — hub starvation during the ToF firmware upload (the low-rate / freeze)
- **Problem:** handshake fixed, but the IMU streamed a few reports then its rate
  collapsed/froze (`evt` stuck ~17, or `pkts` << `calls`).
- **Root cause:** `vl53l8cx_init()` uploads ~84 KB of ULD firmware over I²C — ~1 s
  during which the IMU got **zero servicing**. The BNO08x **self-starves** if it
  isn't serviced within ~1/10 of its report period (datasheet); a ~1 s gap killed it
  and no amount of fast servicing *afterward* brought it back.
- **Fix (three parts):**
  1. Bring the IMU up **AFTER** the ToF init, not before — no pre-ToF handshake means
     no starvation gap (the Bug-2 soft-reset makes the handshake work fine even with
     the idle ToF already on the bus).
  2. Give the IMU its **own ~500 Hz service task** — the main ranging loop is
     streaming-bound at ~33 Hz, far too slow to keep the hub alive.
  3. A **shared FreeRTOS mutex** serialises IMU vs ToF transactions on the bus.
- **Lesson:** the BNO08x is needy — service it continuously and fast or it stops.
  Never leave it unserviced through a long blocking init.

### Dead ends — DO NOT repeat these
- **`scl_wait_us = 20000`** (clock-stretch tolerance): I first blamed *and* then
  credited this for the handshake. It was **neither** — the handshake failure was
  Bug 2 (advertisement), not a stretch timeout. Left at default; a larger value is
  harmless but not the fix.
- **`i2c_master_bus_reset()` on every failed read:** thrashed the bus ~40 000×/s
  while the handshake was down. Removed.
- **Single-owner task** (service the IMU from the ranging loop, no 2nd task): killed
  the hard *stall* but the loop (~33 Hz) is too slow → hub starved (~2 Hz). Necessary
  insight, not sufficient alone.
- **Two-task + mutex on the loop reads only:** the IMU wedged during the *unmutexed*
  ToF init. Either the mutex must cover ALL shared-bus access, or the IMU must come up
  *after* init — we chose the latter (simpler, no managed-component edits).
- **Clock-matching both devices to 400 kHz:** irrelevant to all of the above.

### How it was found
One variable at a time + watch the chip's own heartbeat (`evt`/`pkts`/`calls`), plus
**two targeted web-research passes** that surfaced the two facts no amount of code
staring would reveal: *"advertises only once at power-on"* and *"self-starves if
under-serviced."*

### Files
- `components/bno08x/bno08x.c` — soft-reset in `hal_open`; `bno08x_init()` (handshake +
  block-until-reporting) + `bno08x_service()` + `bno08x_run_task()` (500 Hz task, mutex).
- `main/main.c` — IMU brought up after ToF init; `i2c1_mutex` shared with the ToF reads.
- `visualizer/visualizer_dual.py` — parses `Q:`; rotates the head-attached items by the
  quaternion; "Recenter IMU" zeroes the pose (game-RV yaw is arbitrary + drifts).
- *Cleanup TODO:* `managed_components/.../platform.{c,h}` got an unused
  `VL53L8CX_SetBusMutex` from the abandoned platform-mutex approach — inert, remove on
  next pass. Also strip the `hb`/`IMU PROBE` debug logging.

---

## 2026-06-06 — Dual-sensor integration, debug switch, visualizer overhaul, IMU bring-up

### System state at end of session
- **Two VL53L8CX ToF sensors** live on separate I²C buses:
  - Bottom (`I2C_NUM_1`, SDA=GPIO1, SCL=GPIO2), mounted ~30° **down** → ground/low obstacles.
  - Top (`I2C_NUM_0`, SDA=GPIO41, SCL=GPIO42), mounted ~5° **up** → head/overhead.
  - No address collision (both at 0x29 but on separate buses). Shared directional haptics + buzzer.
- **BNO085 IMU** wired onto the bottom I²C bus, **detected at 0x4B** (driver not yet written).
- Streams `DATA:` (bottom), `DATAT:` (top), `SIGMA:`, `STATUS:` over TCP:3333 + UART; `/api/status` JSON + phone heatmap viewer at `http://<ip>`.
- Desktop 3-D visualizer (`visualizer/visualizer_dual.py`) overhauled (see below).

### Haptic-pause debug switch (GPIO17)
- **Goal:** a physical switch to silence motors + buzzer while debugging the sensor.
- **Design:** SPDT, COM→GPIO17, one outer→GND, third pin empty; firmware uses the ESP's **internal pull-up**, so `HIGH=on`, `LOW(GND)=paused`. Switch carries **no power rail** — only ground — by design.
- **Problem:** with the switch wired COM→GPIO17, one outer→GND, one outer→**3.3V**, flipping it intermittently **bricked the ESP until a full power-cycle.**
- **Root cause:** putting both 3.3V *and* GND on the switch means a make-before-break (or bouncing) contact momentarily **shorts 3.3V→GND through the switch → brownout → USB-Serial-JTAG wedges → only a power-cycle recovers.**
- **Fix:** remove the 3.3V wire entirely. With the internal pull-up supplying "high," the switch can only ever connect GPIO17 to GND or let it float high — nothing to short. **Lesson:** a logic-level switch should never bridge a power rail; let the MCU's pull-up provide the high side.

### Firmware gotcha: `HAPTIC_TEST` left enabled
- **Problem:** after flashing, the device ran a motor-pulse test and **skipped sensor ranging entirely** ("sensor ranging SKIPPED").
- **Root cause:** `#define HAPTIC_TEST 1` had been left on from a 2026-06-05 motor-ID session ("set back to 0 after" — never done).
- **Fix:** set `HAPTIC_TEST 0` / `HAPTIC_ID_MODE 0`. **Lesson:** temporary build flags need a hard "revert" checkpoint; a stray `1` cost a confusing debugging detour.

### Visualizer overhaul (desktop 3-D)
- **Launch gotcha:** the PyQtGraph window *did* launch from the agent's tooling but opened **behind** other windows (and in a non-foreground session), so it looked like "it never launched." **Fix:** verify via Win32 `EnumWindows` (the window title also reports stream state) and force-foreground it; don't assume a launch failure. Burned ~an hour misdiagnosing this as session-0 GUI isolation.
- **Lag at >500 frames:** per-frame Qt signal accumulation. **Fix:** reader thread writes a shared "latest frame" dict; the GUI timer pulls only the newest → fixed cost, no backlog.
- **"Noisy bumps" / hard to read:** raw per-zone distance jumps were amplified by a connect-the-dots surface mesh. **Fix:** the firmware already streams `SIGMA:`/`STATUS:` per zone — now the viz **drops low-confidence zones** (STATUS ∉ {5,6,9}) and **high-noise zones** (SIGMA > threshold) *before* rendering, plus stronger temporal EMA.
- **Readability research:** ST/RealSense/LiDAR practice all flatten to fixed 2-D (heatmap / range-image / top-down) for *live* reading; a free-floating 3-D point cloud is good for offline scanning, poor for at-a-glance distance. Kept the 3-D (user preference) but added depth aids.
- **Final 3-D form (user-directed):** clean points at measured positions + **trace rays** from the helmet to each point (length = distance, no inter-point net); faint FoV frustums; head model + floor plane; hot→cool distance colormap; **preset-view buttons** (Front / 3⁄4 / Top / Side); FPS + nearest-L/R readout. Note: forward axis = GL +Y, so "front" camera sits on +Y looking back.
- **TCP-client clog:** repeated viz relaunches + device resets left stale TCP clients on the ESP (MAX 4) → new viz got ~1 FPS. **Fix:** device reset clears the client table; run a single viz instance.

### IMU bring-up (BNO085 over I²C)
- **Protocol selection:** the BNO085 picks I²C/UART/SPI from strap pins **PS1/PS0, read only at power-on.** I²C = **PS1=0, PS0=0** (both GND). (Prior SPI work used PS1=1/PS0=1.)
- **Problem:** not detected on the bus despite "correct" wiring.
- **Root causes (two):**
  1. Wired to GPIO1/2 (**bottom** bus) while the probe only checked GPIO41/42 (**top** bus) — added a probe to both buses.
  2. PS pins left from the earlier SPI config → chip booted in the wrong protocol. And an **ESP soft-reset does not power-cycle the IMU**, so the wrong mode persisted until a true power-cycle re-latched the PS pins.
- **Fix:** PS1=PS0=GND + full power-cycle → **BNO085 ACKs at 0x4B.**
- **Board-mapping lesson:** the cheap GY-BNO08X clone has an **unreliable silkscreen** — SDA/SCL had to be swapped from the labels, and ADO reads 0x4B despite being grounded (onboard pull-up or inverted mapping). **The I²C probe is ground-truth; trust the address that ACKs (0x4B), not the silkscreen.**
- **Driver status:** SH-2/SHTP is required (no simple register read on BNO085). CEVA `sh2` C sources copied to `components/bno08x/sh2/`. The available `esp32_BNO08x` library is **SPI-only**, so the I²C SHTP transport (HAL: open/read/write/getTimeUs, with SHTP header-peek + chunked cargo reads) must be written from scratch. **Next session.**

### Backlog logged
- **ToF↔ToF mutual interference** (two sensors' 940 nm emissions cross-talking) — investigate right after the IMU works. See `photos/test_rig/future_test_ideas.md`.
