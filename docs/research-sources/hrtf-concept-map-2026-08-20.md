# The HRTF pitch you sent, checked against our research — 2026-08-20

You sent a writeup calling HRTF a potential game changer and asked that
each concept be thoroughly investigated. **They already were** — the full
deep-dive is [[hrtf-spatial-audio-2026-08-20]] (design locked), plus
[[biosonar-2026-08-20]] and [[soundscape-beacon-2026-08-20]]. Here is
every concept from your text, with our verdict and where the evidence
AGREES or CORRECTS it.

| Concept in your text | Our verdict | Where |
|---|---|---|
| HRTF spatialization (ITD/ILD/spectral) | ✅ ADOPTED — azimuth via generic HRTF (KEMAR/slab), precomputed bank | hrtf doc, locked |
| Virtual sound beacon you walk toward | ✅ ADOPTED — Soundscape's actual beacon; WAVs + port plan already in repo | soundscape-beacon doc |
| **Pitch scaling = closer** | ⚠️ **CORRECTED** — pitch is reserved for ELEVATION (3 bands); proximity = pulse RATE. And never brighten near tones: 2–5 kHz is the human-echolocation band we must stay out of (locked −75 dB) | biosonar §audio-band lock |
| **Pulse frequency = proximity** (Geiger counter) | ✅ ADOPTED AND SHIPPED — the TTC ticker already does this (rate = K/TTC), improved: rate encodes time-to-collision, not raw distance, so a stationary you = silence | cv_fusion.py, live |
| **Volume attenuation = distance** | ❌ **REJECTED with evidence** — bats actively remove the loudness cue; blind users are poor at absolute-loudness distance; volume is reserved for CONFIDENCE (Soundscape's only volume use). Distance secondary cue = low-pass filter (muffled = far), which blind users learn instantly | biosonar + hrtf docs |
| Elevation via frequency/tone (bright=high, bass=ground) | ✅ ADOPTED — 3 pitch bands 400 Hz / 1 kHz / 2.5–3 kHz for ground/torso/head | hrtf doc |
| Bone conduction, ears open | ✅ ADOPTED, sharpened — WIRED transducers bonded to the shell (Bluetooth's 260 ms jitter breaks head-tracked audio; consumer band decouples from the IMU) | feasibility-pack §6 |
| Head tracking, low latency | ✅ COVERED — BNO085 at ~100 Hz, IMU extrapolation bridges the ToF's 67 ms; wired audio keeps the loop <30 ms | hrtf doc |
| Dead zones / don't sonify far objects | ✅ SHIPPED — silence-default engine, ticker silent beyond 2 s TTC, cooldowns | cv_fusion.py, live |
| Minimalist sounds (clicks, not music) | ✅ ADOPTED — sparse transients only; sustained/noise textures banned (they deny binaural masking release) | biosonar doc |
| **Personalized HRTF** (ear-photo scanning) vs generic | 🔬 THE ONE OPEN ITEM — we chose generic azimuth-only (front-back confusion mitigated by head-tracking + pitch-elevation instead of spectral elevation). Agent now researching whether phone-based personalization (Apple/Sony-style) is worth it on bone conduction | agent running |
| 3D screen-reader UI (notifications in a hemisphere) | 🕐 Interesting for menus later; not navigation-critical | — |

**Bottom line: your dad's instinct was right and it's already our locked
architecture** — spatial clicks from the obstacle's direction, rate =
urgency, pitch = height, volume = confidence only, wired bone
conduction, IMU head tracking. The two corrections that matter (no
pitch-for-proximity, no volume-for-distance) are evidence-backed, not
taste. The build is unblocked: assets in
`camera/assets/soundscape_beacon/`, port plan in the beacon doc,
transducers on the buy list (~$33).

One caveat on the text's science: "objects reflect high frequencies
differently based on height" is a loose description — real elevation
perception comes from pinna spectral filtering, which is exactly the
part that needs personalization and fails on bone conduction (bypasses
the outer ear entirely). That's WHY our design encodes elevation with
explicit pitch bands instead of trusting HRTF elevation. The agent will
confirm this call.
