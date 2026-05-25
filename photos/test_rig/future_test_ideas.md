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
