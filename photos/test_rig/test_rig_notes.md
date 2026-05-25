# Test rig notes — 2026-05-24 tuning session

## Setup
- **Board**: 2× black foam board, edge-to-edge ≈ 30" wide × 48" tall
- **Board raised**: bottom now at ~8" above floor (top at ~56")
- **Sensor**: ESP32-S3 + SATEL-VL53L8 breakout, mounted on breadboard on top of Casio keyboard music-rest area
- **Sensor height**: 34.5" above floor
- **Sensor tilt**: eyeballed **5–10° downward** (not perfectly level — to factor in during per-zone analysis)
- **Surface**: matte black foam (worst-case low-return reflectance)
- **Lighting**: indoor, indirect daylight from window behind sensor

## FoV coverage at planned distances
Sensor 45° per axis. Board raised so center ~32" high (sensor at 34.5", so ~2.5" mismatch — close enough).

| Distance | Coverage | Notes |
|---|---|---|
| 48.5 cm | full | center FoV well within board |
| ~70 cm  | full | comfortable |
| ~90 cm  | full at horizontal edge (92 cm limit) | OK |

## Implication of downward tilt
- Top rows of 8×8 sample lower on the board (closer to sensor centerline)
- Bottom rows may catch carpet / desk / breadboard wires near close range
- For per-zone σ analysis later, expect a vertical gradient — bottom zones see closer ranges
- This is NOT corrected in firmware — raw zone geometry is reported as if sensor were horizontal

## Photos
- `rig_wide_full_setup.jpg` — full room view
- `rig_close_sensor_and_board.jpg` — sensor + board close-up
