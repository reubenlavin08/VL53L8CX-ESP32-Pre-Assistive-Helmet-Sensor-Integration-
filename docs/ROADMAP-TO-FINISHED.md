# Roadmap to finished — 2026-08-16

Two different finish lines. Ordered so every step is demoable on its own.

---

## A. Make it actually work for a blind person

The honest gap: today the fusion lives on a laptop as a debug view. The *helmet*
still runs old firmware with wrong pins and a known haptics bug. A blind user gets
value from the **haptics loop**, not the overlay — the overlay is our instrument.

### A1. Firmware consolidation (the unglamorous critical path)
> **User decision 2026-08-16: ToF wiring is FINAL** (A=6/7/4, B=15/16/5 — do not
> propose moving it). Buzzer/motors/IMU are NOT wired yet; user will supply their
> pins when he wires them. Blocked until then — do CV fusion first.
- [ ] Port new pin map into helmet firmware (`main.c:50-56`): ToF on 6/7/4 + 15/16/5
- [ ] Buzzer + 3 motors on pins TBD (user to supply); re-verify with the wave test
- [ ] **Fix the cos-table double-correction** — distance is already perpendicular;
      only the mount-pitch term belongs. This biases outer rows RIGHT NOW.
- [ ] Update stale `MOUNT_ROTATION_DEG = 270` / `MOUNT_PITCH_DEG` for the ±22.5° pair
- [ ] Reconnect IMU + haptics; end-to-end test on the actual helmet
- [ ] `vl53l8cx_set_VHV_repeat_count()` — periodic thermal recal (0.1 mm/°C drift,
      motors self-heat)

### A2. The haptic experience (this is the product)
- [ ] Walk-test the v11 directional mapping on the helmet, on a real head, moving
- [ ] Latency budget: ToF frame → motor pulse. Target < 150 ms end-to-end
- [ ] Sensor-dropout behavior: a blind user must *know* the device died —
      distinct heartbeat/alarm pattern, never silent failure
- [ ] Range tuning for walking speed: 4 m detection at 1.4 m/s = 2.8 s warning

### A3. Validation that means something
- [ ] **Blindfolded obstacle course.** The killer metric: canes miss head-height
      obstacles (branches, signs, open truck doors) — that is THIS device's reason
      to exist. Measure: detection rate for head-height obstacles, false-alert
      rate, walking speed with/without device.
- [ ] Log every run. n=5 runs beats n=0 science.

### A4. Physical finish
- [ ] Battery + power budget measured on COINCIDENT PEAKS (WiFi TX + 3 motor
      inrush ≈ 880 mA together; brownout fails late-session, never on the
      bench). 470–1000 µF bulk cap, stagger motor starts.
- [ ] Cable strain relief / connector discipline — **cables ended Cybathlon
      runs, not algorithms** (Sight Guide lost 2 runs to a cable + a camera)
- [ ] Weight + comfort check for a 20-minute wear
- [ ] **Motor SPL at the ear** — audible motors mask the hearing blind users
      navigate by (+33% obstacle contacts from auditory loss alone in trials).
      Falsifiable gate: measure it.

### A5. Red-team gates (full list: docs/research-sources/cv-redteam-2026-08-16.md)
- [ ] Claims language locked: "supplementary cue... not a substitute for a
      white cane" — never "replaces the cane", never "tested = works for
      blind users" from blindfolded runs
- [ ] Test protocol: cane stays in hand in every condition, two spotters,
      indoor course; the device is the variable
- [ ] "No ToF return" is its own state, never "clear" (glass reads empty)
- [ ] 50–200 ms haptic pulses, never continuous (habituation τ ≈ 90 s)
- [ ] Alert rate honest about false-positive base rate (alarm-fatigue disuse)
- [ ] Outdoor range measured before claimed (sunlight → ~1–1.5 m, not 4 m)

### What fusion is FOR (be honest in the pitch)
ToF alone drives the haptics. The camera adds what ToF can't: *what* the obstacle
is. The credible Stage-4+ story: camera classifies (person / vehicle / branch),
ToF ranges it, haptics encode urgency. Don't claim more than is built — the
calibrated projection is the foundation and is genuinely done.

---

## B. Make it a persuasive portfolio piece

The raw material is unusually good because the failures are documented. The
34°-vs-45° story — solver says one thing, physical measurement says another, both
turn out right because they measure different things — is the best engineering
narrative in the project. Lead with it.

### B1. The demo video (highest leverage, do after A2)
- Split screen: blindfolded walk through an obstacle course | live fusion overlay
- One take of a head-height obstacle (branch) that a cane sweep would miss
- 90 seconds max. No music-over-specs montage; show the thing working.

### B2. The write-up
- [ ] Distill DEVLOG → one narrative page: problem → three wrong hypotheses
      (killed with data) → root cause → measured result. Include the residual
      ladder table (18.15 → 5.51 mm) and the tilt-correlation plot.
- [ ] Numbers up front: rotation within 1.15° of CAD, 5.5 mm plane rms,
      calibration from 39 poses, 45° field verified at 6σ against the alternative
- [ ] The dead ends stay in. "Four probe attempts failed because the ToF saw
      something other than the probe" is what real engineering reads like.

### B3. Repo hygiene
- [ ] README: one architecture diagram (2×ToF + IMU + camera → ESP32 → haptics),
      one photo of the pod, one GIF of the overlay, quick-start
- [ ] Top-level doc map: READ-ME-FIRST already does this — surface it in README

### B4. The pitch frame
"Canes cover the ground. Nothing covers head height. This does, for ~$60 of
sensors" — then the engineering depth backs it up.

---

## Suggested order

1. A1 firmware (one session — everything else is blocked on a working helmet)
2. A2 haptic walk-test (same day)
3. A3 blindfold course + logging (needs a helper)
4. B1 video during A3 runs
5. B2/B3 write-up (can interleave)
6. A4 physical finish as needed for the video

Optional science: sharpener-99% recapture to confirm the centroid theory —
strengthens the write-up, not required for function.
