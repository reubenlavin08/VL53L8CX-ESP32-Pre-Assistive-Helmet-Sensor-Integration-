# SESSION HANDOFF — 2026-08-16 — Stage 3 extrinsics

> **NIGHT UPDATE — read these two first tomorrow:**
> 1. `docs/MASTER-SYNTHESIS-2026-08-16.md` — all four research streams merged;
>    [BUILD NOW] items are DONE, [HW] items wait on the motor/IMU rewire.
> 2. `docs/DEVLOG.md` — two new entries on top (residual diagnosis; callout
>    engine v2).
>
> Where things stand: `camera/cv_fusion.py` is the live system — seg+track
> detection, ToF-ranged, silence-default voice with ticker + F9 query + brevity
> mode + trainer. Helmet firmware is FIXED AND BUILT but NOT FLASHED (the ESP32
> must keep running `tof_pin_test/` for the fusion stream; flash only when
> returning to haptics work). ToF wiring is FINAL; buzzer/motors/IMU pins TBD
> from the user. Next session candidates: live A/B of the v2 voice on a walk,
> M3 demo captures, or the [HW] rewire.

**Read `cad/READ-ME-FIRST.md` first, then this.** This is the newest state and wins on
conflicts. Full narrative with root causes is in `docs/DEVLOG.md` (2026-08-16 entry).

---

## 1. WHERE THINGS STAND IN ONE LINE

> **⚠️ EVENING UPDATE (same day): the 8 mm residual is DIAGNOSED and the fusion
> overlay is BUILT.** Root cause: signal-weighted zone centroids (VCSEL illumination
> roll-off pulls outer zones' effective rays inward on extended targets). §4 below is
> kept as history; the resolution lives in the DEVLOG "2026-08-16 (evening)" entry and
> `cad/extrinsics_measured.json` → `OPEN_PROBLEM_residual_8mm.RESOLUTION_2026_08_16`.
> Shipping calibration: `camera/tof_calib_poses/solved_joint.json` (joint rigid
> two-sensor solve, rms 5.51 mm, rotation 1.15° from CAD). Overlay:
> `camera/fusion_overlay.py` (**verified live against hardware 2026-08-16 21:30** —
> user confirmed working; Stage 4 first light).
> Datasheets now archived under `docs/datasheets/tof/` with extracted text.

Both ToF sensors are calibrated to the camera. Rotation agrees with CAD to ~2–4°.
~~An unexplained ~8 mm systematic residual remains~~ — resolved, see banner above.

---

## 2. HARDWARE STATE (as of session end)

| | |
|---|---|
| ESP32-S3 | **COM9** (`VID_303A&PID_1001`, native USB-Serial-JTAG) |
| Helmet camera (HBV-1716WA) | OpenCV **index 1**; index 0 is the laptop's built-in |
| Firmware running | `tof_pin_test/` — NOT the helmet firmware |
| Haptics + buzzer + IMU | **DISCONNECTED** (user unplugged them for the rewire) |

### Verified wiring (see `docs/WIRING.md` for the full map)

| | Sensor A | Sensor B |
|---|---|---|
| SDA / SCL / PWREN | **6 / 7 / 4** | **15 / 16 / 5** |
| I²C bus | `I2C_NUM_0` | `I2C_NUM_1` |
| physical side | **wearer's LEFT** | **wearer's RIGHT** |
| CAD frame | **`tof_right`** | **`tof_left`** |

⚠️ **The identity mapping is counter-intuitive and load-bearing.** Two opposite "left"
conventions were in play all session: CAD "left" means viewing the FRONT of the assembly
(= the wearer's RIGHT). Get it backwards and every depth point lands **mirrored** while
every geometric self-check still passes. Confirmed two independent ways — a hardware wave
test, and from the axes (+X is screen-right viewing the front = the wearer's left, and
`tof_right` sits at X = +18.67).

### ⚠️ USB is flaky
The ESP32 and the camera each dropped off Windows entirely, more than once, mid-session.
They share a connection. If a tool reports "cannot open camera 1" or COM9 missing,
re-enumerate before debugging anything else. Putting them on separate laptop ports
directly is worth doing.

---

## 3. THE NUMBERS

### CAD geometry — verified, trustworthy
`cad/extrinsics_measured.json`, re-derivable via `python docs/extrinsics_solve.py`
(prints `ALL CHECKS PASS`).

- Both boresights within **0.003°** of the designed ±22.5° yaw + 22.5° group tilt
- Right sensor rectangle test: diagonals within **0.022 µm**, 4th corner **0.00 µm**
  off-plane, corner angle **90.0000°**
- In the camera frame both sensors are **pure yaw**, pitch ≈ 0.0001° — the group tilt is
  common to camera and sensors and cancels
- Baseline 36.2488 mm, boresight separation **45.0000°**

### Measured calibration
Sensor A: `camera/tof_calib_poses_SENSOR_A/` (17 poses) + `solved_A.json`
Sensor B: `camera/tof_calib_poses/` (22 poses) + `solved_B.json`

⚠️ **`camera/tof_calib_poses/poses.json` currently holds the SENSOR B run.** The capture
tool overwrites it. Sensor A's run is archived in `tof_calib_poses_SENSOR_A/`. The B file
also contains `A` entries — **they are garbage**, recorded while the pod was aimed at B.

| | A | B |
|---|---|---|
| poses | 17 | 22 |
| all 16 zones valid | yes | 22/22 |
| plane-fit noise floor | 3.08 mm | 3.27 mm |
| conditioning | 4.0 | 3.8 |
| rms, FOV=45, R+t free | **7.96 mm** | **8.60 mm** |
| rotation vs CAD | 4.40° | 3.70° |
| entrance-pupil shift (CAD R and t, only dz free) | **+15.8 mm** | **+12.8 mm** |

**The pupil shift is a real finding** — two independent datasets, same physical camera,
agreeing to 3 mm on a parameter CAD structurally cannot see (the true entrance pupil sits
~14 mm behind the lens-face point picked in CAD).

---

## 4. ⚠️ THE OPEN PROBLEM: ~8 mm systematic residual

| model | A rms | B rms |
|---|---|---|
| CAD R, CAD t, nothing free | 18.15 | 16.76 |
| + pupil shift only | 10.64 | 13.20 |
| + free translation | 10.25 | 10.15 |
| + free rotation too | **7.96** | **8.60** |
| **noise floor** | **3.08** | **3.27** |

**~8 mm survives everything a rigid transform can do.** That is a MODEL error, not a pose
error. Letting the field-of-view float absorbs it (rms drops to 4.4–5.0) but drives the
fitted field to ~34–36°, which is **wrong** — see §5.

**Scale of the impact:** 8 mm at 400 mm = **1.1° = ~12 px** at 1280 px / 119.58°.
Visible on an overlay if you look for it; not fatal for obstacle detection.

### Ruled out (do not re-test without a new reason)
- warped board — real but minor, fixed with a new board (bow −36 mm → −1 mm)
- radial sensor bias — **was not real**, it was the slant/perpendicular bug (§6)
- crosstalk — pod has **no cover glass**; UM3109 §3.2 scopes crosstalk to a protective window
- distance offset — degenerate with FOV, needs an absurd −79 mm
- apex offset (ray fan origin ≠ distance reference) — same degeneracy, needs +78 mm
- checkerboard scale — moves rms by 0.07 mm; fitted scale implies 20.13 mm vs 19.6 assumed
- 4×4 mode shrinking the field — **nothing in UM3109 §4.3** says resolution changes the FoV
- the documented lens flip (UM3109 §2.2) — real, but flipping BOTH axes is a 180° rotation,
  absorbed by R, no magnitude effect
- **single-axis mirrors** — genuinely tested: rms 36.36 vs 8.60. Current mapping is correct
- all 4 grid rotations, and transpose (transpose gives 21.49 vs 4.39)

### Not yet tried
- **Camera fisheye model error at the periphery.** Intrinsics RMS is 0.30 px overall, but a
  119° lens can have systematic error at the edges, and the board was often off-centre.
  This would bias solvePnP's plane poses. **Best remaining hypothesis.**
- **Joint solve of both sensors** with the CAD ToF-to-ToF geometry enforced as rigid
  (baseline 36.2488 mm, separation 45.0000° are known to sub-micron). Far fewer free
  parameters; the error would have nowhere to hide. Also the translations are currently
  inconsistent — A and B solve to Y = +25.78 and +12.97 when CAD says they are identical.
- **Per-zone distance bias** — a genuinely per-zone additive term, not a global offset.

---

## 5. THE FIELD-OF-VIEW QUESTION — RESOLVED, DO NOT REOPEN

**The field is 45° per axis (65° diagonal), as the datasheet says. The pod has NO blind
wedge.** The zero-seam geometry holds: two sensors at ±22.5° with 45° fields put their
inner edges on the camera's optical axis.

The solver's repeated ~34–36° is **a bug in the pipeline**, not a sensor property. Both
sensors produce the same deviation from separate datasets, which is what a systematic
model error looks like.

**Measured physically** with `tof_pin_test/tof_fov_ruler.py` — checkerboard on a tripod,
pod in hand. Column c0, the best-determined:

| row | measured | agreement |
|---|---|---|
| r0c0 | −16.00 | 56.1% |
| r1c0 | −17.50 | 53.9% |
| r2c0 | −17.75 | 65.1% |
| r3c0 | −17.50 | 64.8% |

mean **−17.19°, spread 0.72°**. Datasheet 45° predicts −16.88 (**0.4° away, inside the
spread**). The solver's 34.2° predicts −12.84 (**4.35° away, 6σ out**).

⚠️ **Use FOV = 45° for fusion.** It is the datasheet value, independently measured, and
physically sensible. It costs ~4 mm of rms — that residual IS the unfound bug — but a
fabricated 34° field would distort the geometry.

**The probe only works if the ToF sees NOTHING but the checkerboard.** Four attempts
failed because something else was at the same depth: the arm behind a hand, a torch the
camera could not lock, a 508 mm foam board covering >100% of the field, then the
operator's body behind the sheet. Tripod + handheld pod is the setup that works.

---

## 6. ⚠️ TWO BUGS FOUND — ONE IS STILL LIVE IN THE HELMET FIRMWARE

### distance_mm is PERPENDICULAR, not slant  ← FIRMWARE STILL WRONG
`p = z × [tan(az), tan(el), 1]`, **not** `distance × unit_ray`.

Evidence: same 23 poses, two interpretations — slant gives 12.02 mm plane rms and a
−36.14 mm false dome; perpendicular gives **3.83 mm rms and −2.93 mm bow**, i.e. noise.

**`main.c:142` asserts "that stays as raw slant"** and `compute_row_cos_table()`
multiplies each row by `cos(zone_elevation + mount_pitch)`. If the value is already
perpendicular, the **zone-elevation half of that correction is applied to something that
does not need it**. The mount-pitch half is still required. **This is live in the haptics
and `/api/status` right now** and biases the outer rows.

### Camera frame x_right had the wrong sign  ← fixed
Image-right for a forward-facing camera is the wearer's RIGHT = assembly **−X**, not +X.
Right-handed with +Z forward and +Y up means a person facing +Z has their right along
`Z × Y = −X`. The wrong sign flipped x and y together (a 180° roll) and made the solve
disagree with CAD by 179°. Fixed; agreement went to 2.0°.

---

## 7. TOOLS BUILT THIS SESSION

| file | what it does |
|---|---|
| `tof_pin_test/` | standalone firmware: wiring test, surface quality, `GRID:A,...` stream. **`TARGET_ORDER_CLOSEST`**, 4×4, 10 Hz |
| `tof_pin_test/tof_id_viewer.py` | side-by-side labelled grids — identify which sensor is which |
| `tof_pin_test/tof_fov_ruler.py` | zone-field ruler: on/off-board scoring, bow readout, edge mode |
| `camera/tof_calib_capture.py` | **the calibration rig.** Auto-capture on stillness + pose novelty, live plane-residual colouring, live board-bow readout |
| `camera/tof_calib_solve.py` | the extrinsics solver |
| `camera/tof_zone_bounds.py` | checkerboard-probe zone-angle measurement (the one that worked) |
| `camera/tof_zone_angles.py` | blob-tracking version — **failed, kept only as a record** |
| `docs/extrinsics_solve.py` | verifies `extrinsics_measured.json` re-derives from raw points |

### Capture-tool design points worth keeping
- **Novelty gate (12°/80 mm)** — stops ten near-identical poses that look like ten
  measurements but constrain like one
- **Colour zones by residual from a CURVED fit, not a plane.** With any board bow the
  corner zones sit ~14 mm off a plane while perfectly on the board; a flat-plane test
  flags them as off-board. A zone that has genuinely missed the edge is out by hundreds of mm
- **Save raw data BEFORE analysis.** A crash in the reporting code destroyed 2573 good
  frames once. Capture is expensive; analysis is not

---

## 8. NEXT STEPS, IN ORDER

1. **BUILD THE FUSION OVERLAY.** Use CAD rotation, fitted translation including the pupil
   shift, FOV = 45°. Run it against the `tof_pin_test` `GRID:` stream on COM9 — no firmware
   change or rewiring needed. **A 12 px systematic error has a shape** (inward, outward,
   radial, one-sided), and seeing that shape on a real image will likely identify the
   remaining bug faster than more fitting. This is both the deliverable and the diagnostic.
2. **Joint two-sensor solve** with the CAD ToF-pair geometry enforced (see §4).
3. **Firmware:** update pin defines (`main.c:50-56`), move buzzer + 3 motors off
   6/7/15/16 to the now-free 1/2/41/42, and fix the cos-table double-correction (§6).
4. **`MOUNT_ROTATION_DEG = 270` and `MOUNT_PITCH_DEG` are stale** — set for the old stacked
   top/bottom mounting, not the current ±22.5° left/right pair.
5. **SPAD offset** — 1.72 mm along board-right, 0.10 mm along board-up (DS14161 Fig. 28,
   quoted in `cad/DESIGN-REFERENCE.md:20-23`). Sign unresolved: which end Rx is on.

---

## 9. HOW THE USER WORKS (respect this)

- **He pushes back when a number smells wrong, and he has been right every time this
  session** — on the black board, on the sensor identity, and twice on the 34° field.
  When he objects, re-derive; do not restate.
- Wants **everything logged** for a portfolio write-up. Keep `docs/DEVLOG.md` current in
  Problem → Root cause → Fix → Lesson form, **including the dead ends** — the failed probe
  attempts are the most instructive part of this session.
- Prefers **datasheet-first**: read the primary document before trial-and-error. UM3109 is
  downloadable and its text extracts fine with `pypdf` (WebFetch fails — the PDF is
  image-based to that reader).
- Practical constraints are real: he has two hands, no optical bench, and precise manual
  positioning is not achievable. Design tests around that.
