# Microsoft Soundscape beacon — read from source, port-ready — 2026-08-20

You ordered: "deep dive into Microsoft Soundscape and definitely adopt
their audio beacon." Done — read from the actual MIT-licensed source.
**The 8 beacon WAVs are already in the repo:
`camera/assets/soundscape_beacon/` (+ LICENSE-MIT.txt), and 48 reference
source files are in `docs/soundscape-reference/`.** Build-ready.

## How the beacon actually works (from code)

**Asset-swap, not synthesis.** A beacon = a set of equal-length loopable
WAV "phrases," one per angular region, + a selector that picks which one
plays. No filtering — timbre changes by swapping the sample. Direction is
encoded by TIMBRE, never volume (volume always 1.0 in shipped beacons).

**The 4-region layout (modern "Current"/V2 beacon — the one to port):**
relative bearing angle = your heading minus bearing to target; 0 = dead
ahead.
- **A+** central 30° (≥345° or ≤15°) — the "you're on it" sound
- **A** 40° windows each side (305–345 / 15–55)
- **B** 70° windows (235–305 / 55–125)
- **Behind** the rest (125–235)

Other shipped styles: Classic (2-region, ±22.5° on-axis), Tactile/Drop/
Signal/Mallet (3-region), Flare/Shimmer/Ping (4-region), Slow/VerySlow
tempo variants (12/18 beats), plus two HAPTIC beacons: Wand (60° audio
window, full volume inside ±15°, heavy haptic on crossing the bearing)
and Pulse (heavy in ±15°, light in the 35° flanks) — **the Pulse pattern
maps directly onto our 3 temple motors.**

**The trick that makes it musical: beat-quantized switching.** Assets are
mono 44.1 kHz WAVs with a beat grid (V2 = 6 beats / 2.416 s). On every
heading update the selector re-runs; if the region changed, the swap is
scheduled **at the next beat boundary**, with a partial buffer bridging
to the loop. That one trick is 80% of the Soundscape feel — no glitching
while you scan your head.

**Distance is NOT in the beacon** — only 3D-engine attenuation +
periodic spoken distance callouts (throttle: spacing interpolates from
every 25 m far → every 10 m near; i.e. callout frequency rises with
relevance). A separate ProximityBeacon hum: near <20 m, far 20–30 m,
silent beyond.

**Arrival = hysteresis geofence**: enter ≤15 m → beacon silences + end
melody (Route_End.wav) + arrival callout; must leave ≥30 m to re-arm.
Keep the 2:1 ratio, scale the numbers (e.g. 1 m / 2 m for objects).

**No-heading behavior: dim, never stop** — if heading is lost the beacon
keeps playing at reduced presence and callouts are skipped. Silence must
never mean "arrived" or "gone."

## Other features worth stealing (→ IDEA-BANK)

- **Category-tiered trigger ranges**: objects/safety 10 m, places 20 m,
  landmarks 50 m; re-announce hysteresis (announce at 10 m, re-arm only
  after it leaves 20 m); ×6 ranges in vehicles; 60 s per-POI dedupe (we
  have this).
- **Callout grammar**: `{earcon} [Name], [distance]`, spatialized at the
  source bearing; ≤15 m → "close by"; **distance wording hedged by
  accuracy** — exact / "about" / "around" — map to detector confidence
  (we already hedge with "maybe"; adopt the 3-level scheme).
- **Intersection pattern**: each branch spoken FROM its direction ("goes
  left" rendered at left) → our doorway/corridor-branch callouts.
- **Around Me**: 4 quadrants, max ONE item per quadrant — perfect F9
  upgrade.
- **Community fork** (active): configurable beacon "ringing angle"
  (A+ half-angle as a setting — tighten ours to ±10°, our IMU beats a
  phone compass), Bose Frames head-tracking provider (reference for
  IMU-as-heading), NaviLens integration.

## Port plan (Python / sounddevice / 100 Hz IMU)

1. Load the 4 `Current_*.wav` buffers; one OutputStream callback with a
   persistent phrase-sample counter.
2. Per IMU yaw sample: relative bearing → region; on change set
   `pending_region`, swap at next beat boundary
   (`samples_per_beat = len(buf)//6`).
3. Spatialize with constant-power ILD pan (bone conduction: no HRTF
   needed); mild low-pass on Behind if ambiguous.
4. Distance stays OUT of the beacon; ProximityBeacon hum <2 m; arrival
   geofence 2:1 hysteresis; dim-don't-stop on IMU dropout.
5. A+ half-angle configurable, default ±10°.

Beacon targets = camera/ToF-locked objects instead of GPS points — we
run in Soundscape's best-case branch (head IMU) all the time.

Unverified: Amos Miller's psychoacoustics talks + Cities Unlocked study
numbers (fetch quota) — don't quote numbers from those.
