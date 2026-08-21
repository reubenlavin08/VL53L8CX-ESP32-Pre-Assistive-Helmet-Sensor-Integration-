# An Assistive Helmet from Two $6 Depth Sensors: Calibration, Fusion, and a Silence-Default Interface

**Reuben Lavin — public technical disclosure, 2026-08-20**
Repository: https://github.com/reubenlavin08/vl53l8cx-pointcloud-esp32 (MIT)
Full engineering log: `docs/DEVLOG.md` · Research corpus: `docs/research-sources/`

## Purpose of this document

This is a **defensive publication**: a dated, public, citable disclosure
of the methods below, placed in the open specifically so that they remain
free for anyone to use. This work is an **efficient implementation of
known techniques on a $6 sensor and an ESP32** — the individual
techniques have rich prior art (cited inline); what is disclosed here is
the specific working combination, its calibration method, and its
measured constants.

## 1. System

Head-mounted assistive device for blind and low-vision users:

- 2× ST VL53L8CX 8×8 multizone time-of-flight sensors (yawed ±22.5°,
  group-pitched 22.5° down, seam-abutted for a ~90°×45° field), on two
  independent I2C buses of an ESP32-S3; 15 Hz.
- BNO085 IMU (0x4A, shared bus, ~100 Hz), run **magnetometer-free**
  (game rotation vector) because the temple vibration motors corrupt
  the magnetic field; only orientation deltas are consumed.
- Fisheye USB camera (measured 119.58°×63.12°), calibrated with the
  OpenCV fisheye model; YOLO-class segmentation + ByteTrack on a host
  computer; mask-based (not box-based) association of depth zones to
  detections.
- 3 temple/forehead vibration motors (2N3904 low-side drive); wired
  bone-conduction audio; physical mute switch.
- All streaming over serial or TCP; OTA firmware update.

## 2. Calibration methods disclosed

**2.1 Signal-weighted zone centroids ("effective field").** A multizone
ToF zone's reported range on extended surfaces does not correspond to
the zone's geometric center ray: VCSEL illumination roll-off (field of
illumination ~43.4° at 75%) pulls each zone's effective centroid inward.
We measure a per-zone **effective direction table** from planar-target
poses and use it for metric projection, while retaining the geometric
45° field for detection-bounds reasoning. On our units the effective
centroid field is ≈34°. This resolved a persistent 8 mm planarity
residual. Prior art in spirit: lidar self-calibration (Glennie & Lichti,
2010); what is disclosed is its application to consumer multizone
SPAD sensors with per-zone effective-ray tables.

**2.2 Joint rigid two-sensor solve.** Both sensors' extrinsics are
solved jointly with the CAD-known inter-sensor transform (45.000°,
36.249 mm) enforced as a rigid constraint and one shared effective
table; result 5.51 mm rms against planar truth, 1.15° from CAD.

**2.3 Perpendicular-range correction.** VL53L8CX reports perpendicular
(not radial) distance; forward range used for alerting is
`z·cos(α+pitch)/cos(α)` per zone elevation α and mount pitch.

**2.4 IMU mount calibration.** Two-pose gravity alignment plus cardinal
snap; motors-on gyro behavior verified separately.

## 3. Interface methods disclosed

**3.1 Silence-default callout engine.** Derived from Microsoft
Soundscape's open-source design (MIT): 60 s per-object cooldown,
approach-based re-announcement (>0.5 m closer), 1.5 s stale-drop,
two-item utterance cap, no numbers while walking, confidence hedging
("maybe"), on-demand rich query tier, explicit sensor-loss callout
("silence must never mean safe").

**3.2 Time-to-contact ticker.** Proximity is rendered as a discrete
tick train whose rate follows time-to-contact, not distance:
`rate = K/TTC` (K=5, clamped 0.8–12 Hz), a distinct amplitude-modulated
trill below TTC 0.6 s, silence above TTC 2 s, and a slow standoff
heartbeat when stationary near an obstacle. This yields a
constant-information approach cue at any walking speed and total
silence for a stationary user. Inspired by bat terminal-buzz behavior;
prior art: parking-sensor rate coding, ALVU (Katzschmann et al., 2018).

**3.3 Range-adaptive path cone.** The hazard cone half-angle follows
body width over range: `min(atan2(350 mm, range), 45°)` — wide near,
narrow far.

**3.4 Directional temple haptics.** Three-motor layout with hard
left/center/right regions, dominance weighting and a squared intensity
curve; patterns restricted to ≤2 simultaneous motors (recognition
accuracy falls sharply beyond — cf. GuideTouch, arXiv:2601.13813).

**3.5 Head-clearance rule.** Overhead safety margin is evaluated in the
gravity frame via IMU compensation (head pitch in gait is ±8°, which
otherwise consumes the entire margin under standard doorways).

## 4. Prior art acknowledged (deliberately and gratefully)

- **eLife 2018 (CARA / Microsoft HoloLens study)** — head-swept depth
  mapping with auditory feedback for blind users.
- **DiscoBand** (UIST 2022) — wearable multizone-ToF array sensing.
- **DELTAR** (ECCV 2022) — consumer ToF + camera depth fusion.
- **Glennie & Lichti 2010** — lidar self-calibration methodology.
- **Zebedee** (Bosse et al.) — motion-swept sparse lidar mapping.
- **ALVU** (Katzschmann, Araki, Rus, IEEE TNSRE 2018) — ToF array +
  haptic belt for blind navigation.
- **Microsoft Soundscape** (MIT open source) — audio beacon and
  callout design language; assets and constants reused under MIT.
- **GuideTouch** (arXiv:2601.13813) and **Xu et al. 2023** (Sensors
  23:9598) — head/torso-worn active ranging with haptic/audio warning.
- **Muñoz et al. 2025** (Sci Rep) — forehead stereo + Jetson head-level
  obstacle detection.
- Patents in the adjacent space, none of which this non-commercial
  research build practices as claimed: Toyota US9915545 family, Apple
  US8381107, Phase One US8189058, dotlumen US2022/0282985, Glidance
  WO2025137615.

## 5. What is NOT claimed

No claim is made to novelty of: multizone ToF sensing, ToF+camera
fusion, wearable obstacle detection, spatial audio guidance, or
vibrotactile direction cues. The contribution is the documented,
reproducible, low-cost working combination and its measured constants,
published so it stays unpatentable by anyone.

*This document, the repository history, and the tagged release
constitute the dated disclosure. MIT license.*
