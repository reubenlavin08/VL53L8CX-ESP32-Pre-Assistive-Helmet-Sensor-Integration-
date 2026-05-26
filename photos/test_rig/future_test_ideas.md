# Future test ideas — captured during 2026-05-24 tuning session

## Dynamic-scenario knobs (Phase B+ / wearable testing)

### VHV repeat count
- ULD API: `vl53l8cx_set_VHV_repeat_count(p_dev, count)` (line 695 in api.h)
- Controls how often SPAD bias voltage gets recalibrated. SPAD breakdown voltage drifts
  with temperature and ambient light.
- Important when conditions change — walking outdoors / indoors, sunny patches, hot vs
  cold environments. Default tuned for static use.
- Sweep values: {1, 10, 50, default, 100} — measure invalid-status rate during a walk
  that crosses light/temperature boundaries.

### Multi-target per zone
- Compile-time: `VL53L8CX_NB_TARGET_PER_ZONE` macro (1 → 4)
- Per zone, sensor can report up to N independent targets — useful for:
  - Glass / windows (see glass surface + wall behind)
  - Doorframe edges (zone straddling edge sees both near edge + far wall)
  - Cluttered scenes with overlapping objects
- Requires firmware + measure.py + visualizer refactor (current code uses
  `[z * NB_TARGET_PER_ZONE]` indexing for target 0 only).
- Cost: 4× per-zone data, 4× bandwidth.

### Integration time (AUTONOMOUS mode)
- ULD API: `vl53l8cx_set_integration_time_ms` (line 564)
- Only valid in AUTONOMOUS mode (not CONTINUOUS)
- Decoupling frequency from integration time — could test
  "low freq + max integration" for slow-moving / static use, vs
  "high freq + short integration" for fast head turns
- Not in current sweep because CONTINUOUS already maxes integration per frame.

### Detection thresholds plugin
- Header: `vl53l8cx_plugin_detection_thresholds.h`
- On-chip "interrupt only when distance < X" instead of host polling
- Could replace host-side buzzer threshold logic with sensor INT pin → faster latency
- Useful for low-power / battery-powered helmet revisions

## Phase B dynamic test ideas (separate from parameter sweep)

| Test | Setup | Measures |
|---|---|---|
| Pan test | Sensor on board, slow pan across blank wall | Phantom-trigger count during head turn |
| Approach test | Walk toward wall at normal pace | Distance-at-first-alert + stability |
| Hand wave | Sensor still, hand at 30 cm | Detection rate on moving small target |
| Doorway edge | Sensor at doorway edge | Mixed-pixel behavior at boundaries |
| Lighting change | Walk room → hallway → outdoor | Status-code distribution under changing ambient |
| Outdoor sun  | Direct midday sunlight on target | SNR collapse threshold |

## Threshold-related ideas (firmware features)

- Layered alert: 120 cm = slow chirp, 60 cm = fast chirp, 30 cm = solid tone
- Min-zone-count: require ≥2 adjacent zones below threshold to reduce single-pixel false alerts
- IMU-adaptive threshold: scale alert distance with walking speed
- CV-adaptive (Phase 2): different beep pattern for person vs wall vs static obstacle

## Directional haptic feedback ring (Phase 2-ish)

Add a ring of small haptic motors (~4-6) around the helmet rim, mapped to columns of the FoV. When an obstacle alerts:
- Left columns → buzz left-side motor
- Center columns → buzz front motor (or none — buzzer alone)
- Right columns → buzz right-side motor

Gives directional cues without needing audio. Could combine with the existing buzzer (urgency / distance) for a 2D alert language: buzzer says *"obstacle, close"*, haptic says *"on your left"*.

Considerations:
- Small ERM (eccentric rotating mass) or LRA (linear resonant actuator) motors. ERMs are ~$1, LRAs feel cleaner.
- Need GPIO PWM channels — ESP32-S3 has plenty.
- Mount inside helmet padding so motor contacts scalp/temple.
- Per-motor intensity could also encode "how many zones in that column are alerting" — more zones = stronger buzz.

## Ultrasonic curb / drop-off detection (later)

ToF helmet pitched 20° down can't see floor-level obstacles within ~3 m (FoV physics — see todo.md). Bottom of FoV is at sensor_height - 3m*tan(42.5°) = 186-275 = -89 cm. Anything closer is below floor.

Adding an ultrasonic sensor (HC-SR04 or similar) aimed straight down could:
- Detect curbs / stairs / drop-offs by sudden depth change
- Detect raised obstacles right at user's feet that the ToF cone misses
- Complement, not replace, the main ToF

Trade-off: more wires, more power, more firmware complexity. Probably more relevant after camera (Phase 2) is in — at that point we'll have CV that can identify ground plane and curbs visually.

## Doorway false-alert problem (observed 2026-05-26)

When walking through a doorway, the helmet alerts non-stop on the empty doorframe / open passage. Reuben noticed this in dynamic use.

### Hypotheses
- **Side jambs entering FoV:** at 4×4 with horizontal FoV ~45°, the outer columns see the door jambs (~1 m away) as you pass through. CLOSEST returns those near surfaces, beep triggers.
- **Top of doorframe entering FoV:** with 20° downward pitch, the top jamb may dip into the upper row at close range.
- **Mixed-pixel noise on door edges:** edges of doorframes are classic mixed-pixel scenarios — half the SPADs see the jamb, half see the wall behind.

### Test ideas
- **STRONGEST vs CLOSEST swap** — if the jamb is at oblique incidence (weak return) and the far hallway wall is at normal incidence (strong return), STRONGEST could "see past" the jamb. If jamb is at normal incidence, STRONGEST = CLOSEST and nothing changes. Worth a controlled doorway pass to measure alert-rate delta.
- **Doorway-pattern detector (software, no sensor change):** if center 2 columns report ≥2 m AND outer columns report <1 m, classify as "passing through doorway" and suppress alert. Should be straightforward to add behind a runtime toggle.
- **Multi-target per zone** — would let one zone report jamb (target 0) + wall behind (target 1). Software could prefer the more distant target during doorway transit. Costs 4× per-zone data.

### What we're NOT doing right now (per 2026-05-26 conversation)
- Edge-column tighter threshold (e.g. outer columns alert only <50 cm) — Reuben deferred this. Would directly suppress doorway noise but risks missing real side obstacles.

## Borrowing-from-research-but-need-to-verify list

These were cited by my research agents but I haven't independently verified them in source code — would need to look directly before adopting:

- **ETH Matrix_ToF_Drones "median of center 4 pixels per column" motion-noise filter** — **FALSE. Verified 2026-05-26.** I read `Firmware/src/tof_driver/ToF_process.c` directly. There is no median filter. What ETH actually does (which is genuinely useful):
  - Accept only target_status ∈ {5, 9} AND nb_target_detected == 1 (same as our STATUS_FILTER_STRICT=0)
  - Binarize: pixel is "obstacle" if distance ≤ MAX_DISTANCE_TO_PROCESS
  - **DFS / flood-fill** to cluster connected obstacle pixels into "objects" (8-connected)
  - **MIN_PIXEL_NUMBER threshold** — discard objects smaller than N pixels. THIS is the noise-rejection mechanism (single-pixel spikes get dropped).
  - Pick the closest surviving object, use its min distance + centroid + bounding box to make a flight decision
  - Their distance bands: DIS_REACT=1400, DIS_SLOW=700, DIS_STOP=400, DIS_FEAR=150 mm (drone, not pedestrian — but the layered structure is what our `layered alert: 120/60/30 cm` idea was going for)
- **Ghaffari et al. 2025 multi-target settings** — **could not locate paper. Verified 2026-05-26.** Multiple search angles returned no results. Likely fabricated citation from earlier research agent. Drop from sources.

## Adaptive geometric calibration (Phase 3 — when IMU is installed)

Right now the per-zone slant→forward distance correction assumes a fixed sensor
height (195 cm) and a fixed level head orientation. In reality the head pitches
up/down constantly during walking, and the sensor tilt relative to the floor
changes with it.

Once an IMU is on the helmet:
- Live pitch reading → real-time correction to each zone's elevation angle
- Forward distance = slant × cos(zone_elevation + sensor_pitch)
- Eliminates the constant fudge factor; alert distances stay accurate even
  when the user looks down at their feet or up at a sign

Until the IMU arrives:
- Possibility: use the iPhone's built-in 9-DOF IMU as a stand-in. Apps like
  SensorLog or Phyphox stream IMU data over UDP/WiFi to a host. Mount iPhone
  next to sensor on helmet, parse the stream, fuse with ToF distances.
  Practical for prototyping if a real IMU breakout (e.g. BNO085) isn't on hand.
  Trade-offs: extra bulk, battery drain on phone, ~50 ms WiFi latency.
