# CV fusion plan — 2026-08-16

Goal: every camera detection gets a real distance; every ToF hit gets an identity.
Laptop-side only — no firmware changes. Builds directly on `fusion_overlay.py` and
`solved_joint.json`.

## STATUS (updated 2026-08-16 night — v2 engine shipped)

**Superseded in part by `docs/MASTER-SYNTHESIS-2026-08-16.md`** — the BLV
research overturned the narration design (60 s cooldowns, no numbers in
walking speech, silence default, person deprioritized). cv_fusion.py v2
implements the full [BUILD NOW] list: silence-default hazard engine, 2-item
grammar, proximity ticker, F9 scene query, cane filter, ByteTrack IDs,
confidence hedging, brevity trainer (`callout_trainer.py`). Smoke-tested live
25 s+, left running. Human-in-loop validation pending.

## STATUS (2026-08-16 late evening, first autonomous run)

- **M1 DONE**: YOLO26n via ultralytics 8.4.120, **22 fps measured on this
  laptop's CPU at imgsz 416**. Live camera detection verified
  (`snapshots/m1_detect_test.jpg`).
- **M2 BUILT + hardware-verified headless**: `camera/cv_fusion.py`. Full path
  ran live (serial A+B + camera + YOLO + association + render:
  `snapshots/cvfusion_headless_test2.png`). One association bug found and fixed
  from live data (centroid-in-box missed an edge-standing person; added
  rect-overlap backup). Interactive session not yet run — user was away.
- **Research ingested** — two agent reports archived in
  `docs/research-sources/cv-{stack,redteam}-2026-08-16.md`. Decisions below.
- **M3 (demo captures) pending user** — needs a person walking scenes.

## Decisions locked in from the research (2026-08-16)

1. **Detector: YOLO26n @416** (NMS-free, quantization-friendly, AGPL fine).
2. **Never undistort for inference; fine-tune with fisheye-matched augmentation
   later** (documented 0.283→0.698 mAP jump on a comparable).
3. **Box depth = min over CLAIMED ZONES only** (zone values are already
   on-sensor averages; never average over box pixels — background bleed).
4. **Distance is never a track attribute** — re-derived from the current ToF
   frame every cycle (tracker ID switches would carry stale ranges).
5. **Next quick wins in priority order** (from the value-for-effort table):
   IMU ground-plane bbox ranging → fisheye-augmented fine-tune → ByteTrack+TTC
   on Tier-1 → alert-UX layer (1–2 Hz, hysteresis) — the RCT says feedback
   design, not the model, is the bottleneck.
6. **Claims language for all public write-ups** is fixed in the red-team file
   ("supplementary cue... not a substitute for a white cane"). Non-negotiable.
7. **Known open risks logged, not yet mitigated**: camera auto-exposure swings
   (lock it before outdoor demos), camera↔ToF latency at fast head turns
   (firmware timestamps + IMU de-rotation later), ToF range collapse in
   sunlight (demo indoors / overcast; measure before claiming outdoor range).

---

## Architecture

```
camera 1 ──► YOLO detector ──► boxes + labels
                                    │
COM9 GRID:A/B ──► zone quads ───────┼──► ASSOCIATION ──► labeled, ranged objects
(existing overlay math)             │         │
                                    ▼         ▼
                              live overlay: box + "person 1.8m"
                              + ToF-only alerts for unlabeled obstacles
```

## Design decisions

- **Detector: YOLOv8n via `ultralytics`** (pip install, pretrained COCO — person,
  car, bicycle, dog, chair, backpack...). Nano model, ~640px input: real-time-ish
  on laptop CPU, no GPU needed. Swappable later.
- **Run on the RAW fisheye frame.** YOLO is trained on normal lenses; detection
  quality degrades toward the periphery. Accepted for v1 — the ToF only covers the
  central ±45° anyway, which is the least-distorted region. (Fallback if bad:
  undistort a centre crop before detecting.)
- **Association = box ∩ zone quads.** For each detection box, collect zone quads
  whose centre falls inside it (plus quads overlapping >30% by area). Distance =
  **minimum** of those zones' ranges — for a walking aid, nearest part of the
  obstacle is the number that matters. Median as debug alternative.
- **No match ≠ discard, in BOTH directions:**
  - Detection with no zone overlap → label only, "range n/a" (outside ToF field
    or ToF dropout).
  - **ToF cluster with no detection → still an obstacle.** COCO has no class for
    a branch or a pole end-on — the exact head-height hazards this helmet exists
    for. Near zones (< 1.5 m) with no label render as "OBSTACLE" alert. This is
    the fusion story: CV names things, ToF never misses things.
- **Sync: latest-sample**, same as the overlay. Fine for the demo; firmware
  timestamps + IMU de-rotation stay on the future list.
- **Rates:** ToF 10 Hz, camera ~30 fps, YOLO maybe 5–15 fps on CPU. Run detection
  in a worker thread on the newest frame; overlay never blocks on it.

## Milestones

**M1 — detector standalone (~30 min)**
`pip install ultralytics`; new `camera/detect_test.py`: webcam → YOLOv8n → boxes.
Measure fps and detection quality on the fisheye feed, especially off-centre.
GATE: person detected reliably at 1–4 m in room light.

**M2 — fusion (`camera/cv_fusion.py`)** (~1 session)
Extend `fusion_overlay.py`: worker thread for YOLO, association as above,
render: labeled boxes with distances, zone quads dimmed to background, ToF-only
OBSTACLE alerts prominent. Keys inherit (s/t/m/c) + `y` toggle detection.
GATE: walk toward camera → "person 3.2m → 0.8m" tracks smoothly.

**M3 — demo scenarios + captures (~1 hr)**
Person approaching; chair at knee height; **branch/pole at head height (the
ToF-only alert)**; doorway. Snapshot each. These are the portfolio shots.

**M4 — stretch**
- Class→priority map for future haptics (person=dynamic, pole=static)
- Log fused tracks to JSON for the write-up metrics
- Compute path note: this stack ports to a Pi 5 / phone later; laptop is fine
  for the demo video.

## Risks

| risk | mitigation |
|---|---|
| YOLO too slow on this laptop | detect at 480px, skip frames, still fine at 5 fps |
| fisheye hurts detection at edges | ToF field is central; accept, note in write-up |
| box∩quad mismatch from parallax at <0.5 m | expected, calibrated t handles it — verify in M2 |
| USB instability (camera + ESP32 shared) | separate ports, re-enumerate before debugging |
