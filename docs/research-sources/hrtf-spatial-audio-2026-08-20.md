# HRTF spatial audio + sonification design — 2026-08-20 (Opus agent, condensed verbatim)

**One-line answer: azimuth-only generic HRTF on broadband ticks; repetition
rate = distance; 3 pitch bands = elevation class; loudness CONSTANT (dim =
low confidence); precomputed HRIR bank through `sounddevice`. Everything
fancier is overkill.**

## Evidence anchors
- Generic HRTF fine for AZIMUTH, bad for elevation (Wenzel 1993; Spagnol
  2018: ~6-14° horizontal vs 9-24° vertical error). Individualized HRTFs buy
  ~nothing (Begault 2001); **head tracking demolishes front-back confusion —
  and only SELF-generated motion does** (Wightman & Kistler 1999).
- **Blind listeners: azimuth normal-to-superior (peripheral especially,
  Röder 1999); ELEVATION collapses in noise (Zwiers 2001); never require
  comparing two remembered sound positions (Gori 2014 bisection deficit).**
  → pitch bands for elevation, never HRTF elevation.
- PGS line (Loomis 1998/2005, Klatzky 2006): spatialized audio beats speech
  directions on time, preference, AND working-memory load.
- **Bone conduction: azimuth survives nearly identically (MacDonald 2006);
  elevation collapses (Barde 2016). Calibrate ILD→percept per user; don't
  reason from skull acoustics.** Occluding earbuds in transparency mode are
  3× WORSE (AirPods Pro: 6.8°→19.6°) — "open ear" must be physically open.
- Distance: RATE is the strongest lever (urgency literature; Weber ~5%
  below 20 Hz → 6-8 field-usable steps); loudness is a bad absolute cue
  (Kolarik 2016 — blind users good at RELATIVE, deficient at ABSOLUTE
  distance). Secondary free cue: low-pass with distance (Maimon 2024).
- **Closest analogue validates the whole approach**: Paré 2021 — head depth
  camera + bone conduction + binaural azimuth + redundant distance coding;
  30 MIN training; blind participants NAVIGATED FASTER THAN SIGHTED
  CONTROLS (113s vs 180s, p<.01).

## Soundscape's readable design decisions (steal list)
- Direction = TIMBRE SWAP on the beat (4 angular regions; brighter =
  on-axis, low-passed = behind), rendered on a fixed 1 m "ring" —
  **distance-volume coupling killed by construction** (`.real` never
  instantiated in the codebase).
- **Volume is used for exactly one thing: CONFIDENCE** (dim when heading
  unknown). Steal this.
- Arrival at 15 m = earcon + beacon MUTES (not swells).
- Head-yaw calibration: 200-sample rolling window, accepted at stdev <10°.

## LOCKED CUE DESIGN (implement this)
| Channel | Mapping |
|---|---|
| Sound | 15 ms broadband click, raised-cosine, 300 Hz–8 kHz — never a pure tone |
| Azimuth | HRTF bank, 5° bins, ~10° usable |
| Distance | rate = 1.0·(0.4/d)^k Hz: 4 m→1 Hz, 0.4 m→8 Hz, buzz <0.4 m |
| Distance 2° | one-pole low-pass 8 kHz@0.5 m → 1.5 kHz@4 m |
| Elevation | 3 pitch bands: ~400 Hz ground/drop-off, ~1 kHz torso, ~2.5-3 kHz head |
| Loudness | CONSTANT; dim = low confidence only |
| Gating | event-driven; TTS only for LABELS, spatialized at bearing |

## Pipeline (a weekend)
`pip install slab sounddevice numpy`. Bake offline: 3 elev × 37 az bins via
`slab.Binaural(click).at_azimuth(az).externalize()` (KEMAR default) → float32
bank. Runtime: one `sd.OutputStream` callback (48 kHz, blocksize 256),
per-obstacle phase accumulators, biquad low-pass. **Delete winsound.**
KEY ARCHITECTURAL POINT: live obstacles are ALREADY head-relative (sensors on
the head) — no IMU transform needed. IMU earns its keep for: world-fixed
beacons, **inter-frame azimuth extrapolation** (ToF 67 ms/frame is the
latency bottleneck; rotate last azimuth by yaw delta at 100 Hz — highest-
value IMU use in the audio path), gravity for elevation classes.
Latency budget: ToF 67 ms + audio 15-25 ms; IMU extrapolation brings
motion-to-sound inside the ~60 ms window.

## Validation gate
Paré-style: blindfolded testers, 30 min familiarization → azimuth pointing
(<15° MAE) + obstacle course (>70% detection, ~85-92% avoidance). Miss the
gate = cue design wrong, not the HRTF.

## Upgrade path
PyOpenAL/OpenAL-Soft (SADIE II D1 built in) when >4 sources; pybinsim for
measured BRIRs; bone conduction at mastoid + 5-min per-user ILD sweep; slight
reverb (mediumRoom −20 dB) if in-head complaints.

## Overkill list (don't)
Steam Audio, pyroomacoustics, individualized HRTFs, HRTF elevation,
ambisonics, occlusion sim, full-depth-map soundscapes, absolute-loudness
distance.

Flagged approximate (paywalled): exact Wenzel/Begault/Hellier/Mills numbers,
~60 ms threshold. Loomis 2005 + Klatzky 2006 per-condition times = the
number-set worth chasing via library access.
