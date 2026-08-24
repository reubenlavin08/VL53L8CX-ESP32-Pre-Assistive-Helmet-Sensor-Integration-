# PLAN — Gravity-frame head-clearance warning (FLAGSHIP)

Status: plan only, 2026-08-23. Sources read: `camera/cv_fusion.py`,
`camera/fusion_overlay.py`, `main/main.c`, `cad/extrinsics_measured.json`,
`docs/research-sources/implementation-guide-2026-08-20.md` §2.

## Goal

Warn "low clearance, duck" when a coherent overhead obstacle's clearance
above the wearer's head plane is less than a 10–15 cm margin, inside the
look-ahead distance (first alert at ≥ 2.0 m, hard alert at 1.2 m). Height is
computed in the GRAVITY (world) frame from IMU attitude, not in the sensor
frame — this is the novelty claim (implementation-guide §2: Muñoz 2025
*discarded* frames when the user looked up/down; we compensate instead).
13% of BVI people take a head-level hit at least monthly, cane or dog alike
(Manduchi & Coughlan CACM 2012).

## Evidence (what the code actually gives us)

- **Zone → camera-frame 3D points already exist.** `cv_fusion.py` "project
  all valid zones" loop (~line 877): for each valid zone
  `p_cam_ring = (tan_ae * z, z) @ R.T + t` using `ring = fo.zone_boundary_tans()`
  and `ex[S] = (R, t)` from `fo.load_extrinsics()` (joint calib preferred).
  Each zone lands in `zones` as `{poly, cen, z, S, row, az}`.
- **IMU attitude is live**: `imu_quat` (Q: lines from firmware, `_helmet_line`),
  `quat_to_R(w,x,y,z)`, and `mount_cal` (`visualizer/imu_mount_cal.json`).
  The IMU HUD block (~line 1319) computes `Rw = quat_to_R(...) @ mount_cal.T`
  = **helmet → world**, world Z up, helmet frame X right / Y fwd / Z up
  (`_pod_wireframe` comment). MAG-FREE GRV — fine: only gravity matters here.
- **Group geometry** (`cad/extrinsics_measured.json`): sensors are pure yaw
  ±22.5° in the CAMERA frame; the whole group (camera + both ToF) is tilted
  22.5° down as one rigid rotation. Fitted zone-centre span is **34.2 × 35.4°,
  not the datasheet 45°** (`_fov_note`).
- **Firmware already uses CLOSEST target order**: `main/main.c:145`
  `#define TARGET_ORDER VL53L8CX_TARGET_ORDER_CLOSEST`. So the §2 "single
  highest-leverage change" is already in. Caveat that remains: CLOSEST makes
  a thin branch visible but *noisier* (a 3 cm branch fills ~2% of a zone), and
  multi-target's 600 mm merge limit means a branch < 60 cm in front of a wall
  merges with it — persistence, not geometry, has to carry rejection.
- **Alert-distance math** (§2): dead time τ ≈ 0.8–1.0 s, blind cane speed
  0.68 m/s → first alert ≥ 2.0 m, hard 1.2 m, < 0.8 m already failed.
  Error budget: gravity-compensated ≈ 130 mm RSS vs 190 mm uncompensated;
  the 10–15 cm margin is viable ONLY with the IMU.

### The honest coverage problem (checked, not hand-waved)

Elevation coverage in the helmet frame, head level:
boresight is 22.5° **down**; fitted vertical zone-centre span 35.4° puts the
top-row centres at 22.5 − 17.7 ≈ **4.8° below horizontal** (top zone *edge*
≈ +1°, barely above horizontal). So with the head level the sensors see
essentially **nothing above the pod plane**. Concretely at 2 m the top-row
centre looks at a point ~170 mm *below* the pod.

What saves v1 (partially):
1. The pod sits on the helmet crown, so "head plane" ≈ sensor origin. The
   dangerous band for the *face/forehead* (the majority of head-level hits —
   branches, signs at 27–80 in, ADA §307) is BELOW the pod plane and IS
   covered by rows 0–1.
2. Gait pitch oscillates ±8° (§2). During the pitch-up phase the top edge
   sweeps to ≈ +9°, i.e. +315 mm at 2 m — the overhead band is swept
   intermittently every stride. The existing 0.8 s valid-sample hold
   (`tof_hist` median in cv_fusion) plus 3-of-5 persistence integrates those
   intermittent returns into a stable detection *in the world frame* —
   this only works because we height-classify per-sample with the
   simultaneous quaternion, which is exactly the flagship trick.
3. Anything strictly ABOVE helmet-top level while the head stays level
   (awning at +5 cm clearance, level walker) is genuinely invisible.

**Re-aim option if field tests show it matters** ("vertical splay"): reduce
the group tilt to ~10–12°, or pitch ONE sensor up so A covers −40..0° and B
covers −10..+25°. Cost: new pod CAD (see `START-HERE.md` — rotation order is
load-bearing), reprint, re-run the joint ToF↔camera calibration
(`camera/tof_calib_solve.py`), and the cane-filter row semantics change
per-sensor. Not in this plan's scope; v1 ships on current hardware with the
limitation stated in the DEVLOG.

## Design

### Transform chain (our variable names)

For every valid zone (use the zone CENTRE ray, `eff` effective-centroid
tangents from `fo.load_extrinsics()`, not the boundary ring — the centroid is
where an extended surface's range belongs):

```
p_sensor = [eff_x[c]*z, eff_y[r]*z, z]            # sensor frame, mm
R, t = ex[S]                                      # solved_joint.json
p_cam   = R @ p_sensor + t                        # camera frame (+x r, +y dn, +z fwd)
p_helmet= R_CH @ p_cam                            # camera -> helmet (fixed, from CAD)
Rw      = quat_to_R(*imu_quat) @ mount_cal.T      # helmet -> world (IMU HUD block)
p_world = Rw @ p_helmet                           # world: Z up, gravity-true
h       = p_world[2]                              # height above pod origin, mm
d_fwd   = hypot(p_world[0], p_world[1])           # horizontal look-ahead, mm
```

`R_CH` (camera→helmet) is a constant from the CAD construction: camera axes
in helmet coords are `cam_x=(1,0,0)`, `cam_y=(0,−sin22.5°,−cos22.5°)`,
`cam_z=(0,cos22.5°,−sin22.5°)` → `R_CH = [[1,0,0],[0,−s,c],[0,−c,−s]]ᵀ`
columns-as-axes (derive once, verify against
`extrinsics_measured.json` `_board_up_note`: board up-axis =
(0, cos22.5, sin22.5)). Small translation offsets (t is mm, ~30 mm arms) are
below the 130 mm error budget; keep them anyway, they're free.

### Decision rule

- `HEAD_MARGIN_MM = 120` (setting, 100–150), `POD_ABOVE_HEAD_MM ≈ 30`
  (pod origin sits a touch above the scalp; measured once).
- Hazard band: `-100 < h < HEAD_MARGIN_MM` **and** `abs(azimuth) inside the
  same range-adaptive path cone the tier engine uses** (reuse the
  `BODY_HALF_W_MM` formula) — an awning off to the side is not a duck.
  Lower bound −100 mm keeps forehead-height intrusions; anything lower is
  the ordinary obstacle pipeline's job.
- Distance staging: `d_fwd < 2000` → arm; `d_fwd < 1200` → hard.
- **3-of-5 persistence** (§2's cheapest awning-vs-branch mitigation): a ring
  buffer of the last 5 fusion frames; alert only if ≥3 contained a hazard-band
  zone. Planarity/extent testing (real awning-vs-branch discrimination) is
  explicitly DEFERRED — v1 treats any persistent overhead return as duckable.
- Alert output:
  - Speech: `"low clearance, duck"` as tier **directive** (pre-cue earcon
    comes free from `speech_worker`), key `"DUCK"`, repeat window
    `DIRECTIVE_REPEAT_S`; at the 2.0 m stage use caution-tier
    `"low branch ahead"` once.
  - Haptic: distinct all-3-motor **double pulse** (2 × 120 ms, 150 ms gap,
    full duty). Reality check: firmware drives haptics autonomously; python
    can only reach motors via `GET /api/motor?i&duty&ms` (main.c:907), which
    pulses ONE motor, blocks its HTTP task for `ms`, and holds off
    `haptic_apply` for `ms`+250 ms. Three sequential calls ≈ 1.2 s and
    mask obstacle haptics — acceptable for a directive-tier event but ugly.
    Proper fix (small): add `GET /api/pattern?p=duck` to main.c that plays
    the double pulse on all 3 motors from the firmware side (~25 lines,
    reuses `haptic_set` + `g_manual_hold_until_us`). Plan assumes the
    endpoint; fall back to speech-only if unflashed.

### No IMU → feature OFF, honestly

If `imu_quat is None or now - imu_stamp > 1.0` or `mount_cal is None`:
clearance watch is disabled and says so ONCE ("clearance watch off, no
attitude") — never silently degrade to a sensor-frame top-row rule, which §2
calls the fatal flaw. HUD shows `CLR: off`.

### Wearer/helmet height

Not actually needed for the core rule — the pod IS the head plane (that is
the win of putting the sensor on the helmet). One parameter,
`POD_ABOVE_HEAD_MM`, measured with a ruler; optionally confirmed by reusing
the leveling flow (key `l`): while level, have the wearer stand facing a
doorframe of known height and check the reported `h` of the header zone —
a 2-minute calibration note in the runbook, not code.

## Implementation steps

1. `camera/cv_fusion.py` — add `R_CH` constant + derivation comment next to
   `quat_to_R`; verify numerically against `cad/extrinsics_measured.json`
   (board up-axis check) in a throwaway assert.
2. `cv_fusion.py` zones loop — while zones are being built (we already have
   `z`, `r`, `c`, `R`, `t` in scope), also compute `p_world` per zone when
   `imu_quat` is fresh; stash `zn["h"]` (mm above pod) and `zn["d_fwd"]`.
   One extra 3×3 matmul per valid zone (≤32) — negligible.
3. `cv_fusion.py` — new `clearance_watch(zones, now)` block after the tier
   engine: hazard-band + path-cone filter, 5-frame ring buffer, 3-of-5 vote,
   staging at 2.0/1.2 m, speech via `speech_next` (directive), HUD line
   (`CLR 1.4m +9cm` style) and magenta highlight of the offending zone polys.
4. `main/main.c` — `/api/pattern` endpoint: `p=duck` → all-3 double pulse
   via `haptic_set`, guarded by `g_manual_hold_until_us`; register URI next
   to `motor_uri` (main.c:983). OTA flash.
5. `cv_fusion.py` — fire the pattern (background thread, `urllib` GET to
   `--host`) on hard-stage entry only, rate-limited to 1/2 s; skip silently
   in `--serial` field mode (no HTTP path).
6. Logging for the test plan: `--log-clearance` flag appends
   `t, S, r, c, z, h, d_fwd, pitch, voted, stage` CSV per hazard-band zone.
7. `docs/DEVLOG.md` entry incl. the coverage-geometry limitation and the
   splay re-aim option (Problem→Root cause→Fix→Lesson format).

## Test plan (INDOORS, controlled)

Rig: broom handle taped across a doorway, height set with a tape measure.
Wearer height known → true clearance known to ±1 cm.

1. **Static height accuracy**: stand 2.0 m back, broom at head+30 cm /
   head+10 cm / head−5 cm. Logged `h` vs tape truth; pass = |err| ≤ 130 mm
   (the §2 gravity-compensated budget). Repeat with head pitched ±15° —
   `h` must NOT move more than the budget (this is the whole feature).
2. **Approach**: walk at the broom at head+5 cm from 4 m. Pass = caution by
   2.0 m, "duck" directive by 1.2 m, zero alerts when broom at head+30 cm.
3. **Persistence/false-alarm**: 10-minute normal indoor walk, doorways of
   legal height, ceiling fixtures. Pass = 0 duck alerts (Pittet: a
   false-alarming device is worse than none).
4. **Gait sweep check**: log which gait-phase pitch values produced the
   hazard-band samples — quantifies how much detection depends on the ±8°
   oscillation (feeds the splay decision).
5. **No-IMU**: kill the Q: stream; confirm single "clearance watch off"
   and no clearance alerts.

## Risks

- **Upward coverage is marginal** (see Evidence): a level-headed walker under
  a high-but-too-low awning may get late or no warning; detection leans on
  gait pitch sweep. Mitigation: measure it (test 4); if inadequate, the
  vertical-splay re-aim (new pod CAD + recalibration, ~a weekend) is the fix.
- CLOSEST + multi-target 600 mm merge: branch <60 cm before a wall reports a
  blended range — persistence still fires, range may read long. Document.
- `mount_cal` staleness after a ball-mount re-clamp: leveling flow exists
  (key `l`); clearance heights are wrong until re-leveled. Add the check to
  FIELD-TEST-RUNBOOK preflight.
- Latency chain (ToF 30 Hz + 0.8 s median hold + 3-of-5 vote ≈ 0.5–1.0 s)
  eats most of τ — that is exactly why first-alert is at 2.0 m, don't shave it.
- `/api/motor` fallback masks autonomous obstacle haptics during the pulse
  window — use the firmware pattern endpoint, not the fallback, for field use.

## Effort

- Steps 1–3 (core, speech-only): 4–5 h incl. numeric verification.
- Step 4–5 (haptic pattern + trigger): 2 h + OTA flash.
- Step 6–7 + indoor test session: 3 h.
- Total ≈ **9–10 h**.

## Dependencies

- IMU streaming (`Q:` lines) + `visualizer/imu_mount_cal.json` present.
- Joint extrinsics (`camera/tof_calib_poses/solved_joint.json`).
- Firmware reflash only for the haptic pattern (speech path needs none).
- No new hardware. Splay re-aim is a separate, explicitly deferred project.
