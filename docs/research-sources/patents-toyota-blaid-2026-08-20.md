# Toyota BLAID patent portfolio — 2026-08-20 (sub-agent, condensed verbatim)

Part of the prior-art fleet. Toyota holds **40–60 blind-assistance filings**
(2014–2019 + 2023–25 revival; inventor Joseph Djugash alone: 55), incl. a
Canadian member **CA2936835** (check separately if ever filing/selling in
Canada).

## The five that matter, and the design-arounds

1. **US10217379** (neck/shoulder device; environment classification modifies
   audio/tactile settings + processor reallocation). Highest exposure if we
   vary verbosity by surroundings. OUR OUT: claim needs two-object
   correlation → preliminary→refined classification → processor
   reallocation; a verbosity rule driven by ToF zone occupancy sits outside
   all four limits.
2. **US9915545** (smart necklace "find mode": target + output-form input,
   branch nav-vs-relative-location, IMU updates). Live risk for a "find the
   door" mode. OUR OUT: no second output-form input, no branch — one
   always-on bearing+distance output.
3. **US9613505** (broadest: "one or more sensors" COVERS ToF; multi-motor
   directional vibration guiding an EXTREMITY along a trajectory). Only
   "extremity" saves us — whole-body locomotion is outside. **Never add
   hand/reach guidance without re-reading this claim.**
4. US9316502 (wheels + platform + display) / US10024678 (clip housing) —
   structural limits a helmet can't meet. Low risk.
5. **US9993384** (simultaneous audio outputs) — CLAIMS UNREAD (B1, no
   pre-grant pub) — the highest-value gap; bears on callout arbitration.

## The strategic answers

- Head/body-mounted DEPTH sensing: **not claimed** — independent claims say
  "camera/image sensor"; stereo only in dependents; mounting is
  neck/shoulder/chest throughout. No head-mounted independent claim found.
- Depth+camera fusion for callouts: **not claimed** (their fusion is
  camera+IMU+GPS).
- Door detection with state verification: **nothing found — genuinely open
  space** (nearest: room-state scanner US10408625).
- Our strongest distinguishers vs the whole family: **active multizone ToF,
  head mounting, fisheye optics, per-zone haptics for whole-body locomotion**.

Caveats: legal status/expiry UNVERIFIED for all (Google Patents blocked;
2014-15 priorities imply ~2034-35 nominal expiry, lapses common). Sources:
FreePatentsOnline claim texts (sequential fetch), WIPO Patentscope discovery.
