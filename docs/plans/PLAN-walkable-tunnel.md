# PLAN — Walkable-tunnel haptics (CONDITIONAL)

Status: plan only, 2026-08-23. Virtual-corridor guidance: motors fire only
when the wearer nears the corridor walls; **silence when centered**.

## Goal

Port the "Walkable Tunnel" guidance mode
(`docs/research-sources/patents-stripmine-2026-08-20.md`, guidance mode 1 and
build-shortlist item 1: "silence when centered; motors only near the corridor
walls — direct fit to v11 firmware") onto the existing 3-motor rig. v1:
a straight-ahead corridor of width **0.9 m**, walls inferred from the
left/right free-space the tier engine already measures. Error-correction,
not continuous steering — consistent with the silence-is-default doctrine.

## Evidence

- **Free-space analysis already exists** in `camera/cv_fusion.py`'s
  directive-tier block (~line 1046):
  `left = [zn["z"] for zn in upper if zn["az"] < -10]`,
  `right = [... zn["az"] > 10]`, `lmean = np.mean(left)`, `rmean = ...` —
  used today to choose "step right" vs "step left" vs "stop stop". The
  tunnel generalizes exactly this signal from a one-shot command into a
  continuous wall-proximity field. (Today it is computed only inside the
  `near_path < DIRECTIVE_MM` branch; the tunnel needs it every frame.)
- **The firmware drives the haptics autonomously.** `main/main.c`
  `ranging_task` fills per-motor urgency trackers
  (`motor_fwd/motor_thr/motor_active`, main.c:1424) straight from its own
  ToF frames and calls `haptic_apply()` (main.c:1509, squared duty curve +
  7/10 dominance weighting, `HAPTIC_DIRECTIONAL=1`). **Python currently has
  no continuous motor channel.** Host access today is exactly one endpoint:
  `GET /api/motor?i&duty&ms` (main.c:907) — pulses ONE motor, blocks its
  HTTP handler for `ms` (20–2000), then zeroes it, and sets
  `g_manual_hold_until_us = now + ms + 250 ms`, during which
  `haptic_apply()` returns early (main.c:1614) — i.e. **every host pulse
  suppresses the autonomous obstacle haptics for its duration + 250 ms.**
  There is also `GET /api/haptics?en=0|1` (software mute) and the motor map
  0=center 1=right 2=left (GPIO 18/8/17, ID-verified 2026-08-17 — note
  `helmet-haptic-mapping` memory of 7/15/16 is stale; main.c is truth).
- Corridor width 0.9 m ≈ 2×`BODY_HALF_W_MM` (350 mm) + margin; matches the
  patent's error-correction framing and GuideTouch's ≤2-motors rule.

## Design

### Corridor model (v1, python-side)

Straight ahead, half-width `W/2 = 450 mm`. Per fusion frame compute from
`upper` zones (rows 0–2, cane filter respected):
`lmean`, `rmean` as in the directive block, plus lateral clearance
`lat_l = min over left zones of (z·sin|az|)` (same for right) — the actual
sideways distance to the nearest flanking obstacle, which is the quantity a
"wall" is made of (a pole at 1.5 m and 15° is 390 mm off-track: inside the
wall). Wall pressure per side:
`press = clip((W/2 + RAMP − lat) / RAMP, 0, 1)`, RAMP = 300 mm →
zero when the nearest lateral obstacle is >750 mm off-axis, full at 450 mm.
Deadband + 2-frame smoothing so a centered walk is truly silent.
Map: left pressure → LEFT motor, right → RIGHT motor ("wall on that side"
convention — matches the firmware's existing directional mapping where the
obstacle side buzzes); CENTER stays reserved for the firmware's own
frontal-obstacle drive. Duty = firmware-style floor+squared curve
(`HAPTIC_DUTY_MIN=130` floor) scaled to a LOW ceiling (~170) so tunnel cues
stay clearly weaker than collision alerts.

### Motor access — the honest part, both options evaluated

The tunnel is computed on the laptop, but the motors belong to the firmware.

**Option A — `/api/motor` at low rate (no reflash).**
Pulse the wall-side motor, e.g. 90 ms at the computed duty, at 1–2 Hz per
side, only while `press > 0`. Verdict: workable as a same-day *prototype*
to validate the mapping and feel, but wrong for real use:
each pulse blanks `haptic_apply` for pulse+250 ms — at 2 Hz on each side the
autonomous obstacle haptics are suppressed a large fraction of the time,
inverting the safety hierarchy; the handler blocks an httpd task per pulse;
and it needs the WiFi link (dead in `--serial` field mode). Cap: prototype
only, one side at a time, never both above 1 Hz.

**Option B — small firmware change (recommended for v1 proper).**
Add `GET /api/tunnel?l=<0-255>&r=<0-255>&ttl=400`: store per-motor tunnel
duties + expiry `g_tunnel_until_us`. In `haptic_apply()` blend
`duty[m] = max(duty[m], tunnel[m])` while unexpired — obstacle urgency
always wins by construction (max), tunnel cues ride underneath, and an
expired TTL (host hiccup, WiFi drop) fails safe to pure autonomous mode.
~30 lines in main.c, register next to `motor_uri` (main.c:983), OTA flash.
Python posts at ~3 Hz with ttl=400 ms. Serial field mode: still no channel —
a later `TUN:l,r` line on the existing USB-CDC console would close that gap
(logged as v2; the console RX path doesn't exist today, so it is real work).

### Interaction rules

- Tunnel active only when: audio_on-equivalent master switch, no directive
  active (`directive_active` False), not in leveling/door/guide mode.
  A directive ("step right") pre-empts and zeroes tunnel duties.
- On-track ping (shortlist item 3) explicitly deferred to v2.
- Toggle on key `u` + voice "tunnel"; OFF is the default at launch.

## Implementation steps

1. `camera/cv_fusion.py`: hoist `lmean/rmean` out of the directive branch;
   add per-side `lat_l/lat_r` and wall-pressure computation (new
   `tunnel_state` dict), HUD line `TUN L▂ R▅` + corridor edge overlay.
2. `cv_fusion.py`: `tunnel_worker` thread — 3 Hz sender, Option A pulse mode
   (`--tunnel-proto`) first; keyed toggle `u`; hard mutual exclusion with
   `directive_active` and the modes above.
3. Bench-validate mapping and feel with Option A (one session, indoors).
4. `main/main.c`: `/api/tunnel` endpoint + `tunnel[]`/`g_tunnel_until_us`
   blend in `haptic_apply()` (max-blend, TTL fail-safe). OTA flash.
5. Switch python sender to Option B, delete/flag-gate the prototype path.
6. DEVLOG entry (incl. the Option A suppression finding, whatever it
   measures as).

## Test plan

1. Bench: pod on desk, boxes forming a 0.9 m gap. Slide the rig laterally —
   near-left box ⇒ LEFT motor ramps, centered ⇒ silence, both walls close
   (<0.9 m total) ⇒ both motors low duty (narrow-passage texture, verify it
   doesn't read as "stop").
2. Hallway walk (sighted, 1.2 m hallway): drift toward a wall ⇒ onset before
   shoulder contact (~450 mm), silence within ±20 cm of centre. Count false
   buzzes on a straight centered 20 m walk — target 0.
3. Priority: place a frontal obstacle while hugging a wall ⇒ firmware
   collision haptics (center + squared urgency) must dominate visibly;
   with Option B, confirm max-blend never dims an obstacle cue.
4. Fail-safe: kill the laptop app mid-walk ⇒ motors return to pure
   autonomous behavior within the TTL (≤400 ms).
5. Doorway: walk a 0.85 m door — both-walls cue appears, passable, no stop
   command triggered.

## Risks

- **Option A actively degrades safety** (haptic_apply hold-off) — treat as
  bench prototype only; never field-walk a blindfolded user on it.
- Zones vs walls: 3 columns of coarse zones make `lat` lumpy; a doorframe
  edge zone can flicker. The 0.8 s valid-hold median already smooths range;
  add the 2-frame pressure smoothing before trusting onset feel.
- Vocabulary collision: firmware already buzzes the obstacle-side motor for
  side obstacles — tunnel duty on the same motor at lower intensity could
  blur "wall near" vs "obstacle at side". Mitigate with the low duty
  ceiling; if still ambiguous, give tunnel a distinct texture (firmware
  pulse-train instead of steady) — v2, needs firmware pattern support.
- WiFi latency spikes → TTL expiry flapping; 3 Hz sender + 400 ms TTL gives
  one-miss tolerance. No tunnel in serial field mode until the v2 console
  channel.

## Effort

- Steps 1–3 (python + prototype + bench): 4–5 h.
- Steps 4–5 (firmware endpoint + blend + OTA + re-test): 3 h.
- Step 6 + hallway/door tests: 2 h.
- Total ≈ **9–10 h** (Option-A-only demo: ~4 h).

## Dependencies

- v11 directional haptic firmware flashed (`HAPTIC_DIRECTIONAL=1`) and WiFi
  link to the pod (`--host`, default 192.168.1.228).
- No IMU needed for v1 (corridor is body-relative straight-ahead).
- Firmware reflash for Option B. Route-following tunnels (waypoints/record-
  replay, shortlist item 6) are out of scope.
