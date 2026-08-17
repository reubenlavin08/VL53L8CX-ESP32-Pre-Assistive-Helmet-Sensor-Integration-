"""CV FUSION -- YOLO detections + ToF zones, live: every detection gets a real
distance, every near ToF hit gets a label (or an OBSTACLE alert if CV is blind
to it -- branches and poles have no COCO class, and they are the whole point).

    python camera/cv_fusion.py --port COM9 --cam 1

Builds on fusion_overlay.py (projection machinery imported from it) and the
2026-08-16 research pass (docs/CV-FUSION-PLAN.md):
  - YOLO26n at imgsz=416: ~22 fps on this laptop's CPU, measured. NMS-free,
    quantization-friendly -- the current edge-first pick.
  - Detector runs in a WORKER THREAD on the newest frame only; the overlay
    never blocks on inference, boxes lag <=1 detector period (~50 ms).
  - Distance for a box = MINIMUM over the zones it overlaps, never the mean:
    a box always contains background pixels, and averaging bleeds far
    background into the obstacle's range (documented fusion pitfall). For a
    walking aid the nearest part is the right number anyway.
  - Zone<->box association is done in IMAGE space with the zones' projected
    quads: centroid-in-box, plus quad-box IoU-ish overlap as backup. This uses
    the full calibration (R, t, pupil) rather than a naive angular map, so
    parallax at close range is handled by construction.
  - ToF-only alert: any zone nearer than ALERT_MM whose quad is claimed by no
    detection renders as an OBSTACLE banner. CV names things; ToF never
    misses things.
  - Tier-1 moving classes (person, cyclist, vehicles, dog) get a thicker box +
    priority colour -- they are the ones that will get a tracker + TTC next.

AUDIO NARRATION (the assistive output, laptop TTS for now): speaks the single
most important thing -- "person, 2 meters, slightly left" -- never a firehose.
Rules straight from the red-team file (alarm fatigue is what gets devices
abandoned, and users probability-match their trust to your false-alarm rate):
  - at most one utterance per SPEAK_PERIOD (2 s), latest-wins queue of depth 1
  - priority: near unlabeled OBSTACLE > nearest ranged detection > nothing.
    A ToF hit is NEVER suppressed just because CV has no name for it.
  - hysteresis: the same object+direction repeats only if its range moved
    >0.5 m or REPEAT_S has passed -- approaching things talk, static scenery
    shuts up after one mention
  - direction from the CALIBRATED camera model (undistorted azimuth of the box
    centre), not raw pixel fraction -- the fisheye makes those very different
Keys: q quit  s snapshot  y toggle detector  t zone distance text  m calib toggle
      a toggle audio
"""
import argparse
import pathlib
import threading
import time

import cv2
import numpy as np

import fusion_overlay as fo          # projection machinery + serial reader

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIDE = fo.SIDE
ALERT_MM = 1500.0                    # ToF-only obstacle banner threshold
CONF = 0.35
IMGSZ = 416
TIER1 = {"person", "bicycle", "car", "motorcycle", "bus", "truck", "dog"}

det_lock = threading.Lock()
det_latest = []                      # list of dicts: name, conf, xyxy, tier1
det_frame_id = -1
running = True

# ── audio narration ──────────────────────────────────────────────────────────
# v2 engine (2026-08-16 master synthesis): SILENCE IS THE DEFAULT STATE.
# Autonomous speech = hazards and commands only; everything else is on-demand
# (F9). Soundscape-derived suppression; proximity is a TICK RATE, not a number.
REPEAT_S = 60.0           # per-object cooldown (Soundscape: 60 s, was 5)
RANGE_DELTA_MM = 500.0    # approach by this much re-announces inside cooldown
STALE_S = 1.5             # queued speech older than this is dropped unspoken
DIRECTIVE_REPEAT_S = 1.2  # directive tier repeats this often while active
DIRECTIVE_MM = 800.0      # anything nearer in the path cone -> command
PATH_CONE_DEG = 15.0      # "in the path" = within this azimuth of straight ahead
CAUTION_MM = 1800.0       # caution tier ceiling
CLOSING_MPS = -0.5        # range rate for the "closing"/"hot" aspect word
CONF_HEDGE = 0.50         # below this confidence the callout says "maybe"
# proximity ticker: parking-sensor repetition-rate encoding (the pattern every
# shipped product uses instead of speaking numbers). Sparse 40 ms blips.
TICK_NEAR_S, TICK_FAR_S = 0.15, 1.2      # period at DIRECTIVE_MM .. CAUTION_MM
SPEECH_RATE = 240         # overridden by --rate; blind users parse 8-22 syl/s

# Brevity vocabulary (docs/CALLOUT-PROTOCOL.md §4). PLAIN says the same thing
# in ordinary words; the decision engine is identical.
BREV_NAME = {"person": "man", "car": "car", "bus": "car", "truck": "car",
             "motorcycle": "car", "bicycle": "bike", "dog": "dog",
             "obstacle": "block"}
CLOCK_WORD = {10: "ten", 11: "eleven", 12: "twelve", 1: "one", 2: "two"}


def clock_hour(az_deg):
    h = 12 + int(round(az_deg / 30.0))
    return ((h - 1) % 12) + 1
speech_lock = threading.Lock()
speech_next = None        # latest-wins slot: (text, key, range_mm)
speech_last = {}          # key -> (t_spoken, range_mm)


def speech_worker():
    """pyttsx3's runAndWait() goes permanently silent after the first call
    when reused inside a thread (long-standing SAPI event-loop bug -- observed
    live 2026-08-16: one callout, then nothing). Workaround: a FRESH engine
    per utterance. ~100 ms of init per say, irrelevant at a 2 s cadence.

    TIER RULES (v2, docs/MASTER-SYNTHESIS-2026-08-16.md):
      directive -- earcon + speak NOW, repeat every DIRECTIVE_REPEAT_S.
      caution   -- immediate, 60 s per-object cooldown, approach re-announces.
      query     -- immediate, always spoken (the user explicitly asked).
      There is NO routine tier: silence is the default state (Soundscape).
      Anything sitting in the queue longer than STALE_S is dropped unspoken --
      a stale callout is misinformation, not information.
    """
    import pyttsx3
    global speech_next
    while running:
        time.sleep(0.05)
        now = time.monotonic()
        with speech_lock:
            item, speech_next = speech_next, None
        if item is None:
            continue
        text, key, rng, tier, born = item
        if now - born > STALE_S and tier != "query":
            continue                       # world moved on; don't narrate the past
        prev = speech_last.get(key)
        if tier == "directive":
            if prev and now - prev[0] < DIRECTIVE_REPEAT_S:
                continue
        elif tier != "query" and prev and (now - prev[0] < REPEAT_S):
            # Approach-only re-announce inside the cooldown: range increase
            # is never urgent, and association flapping would chatter.
            if rng > prev[1] - RANGE_DELTA_MM:
                continue
        speech_last[key] = (now, rng)
        try:
            if tier == "directive":
                import winsound            # TCAS-style pre-cue: tone buys parse time
                winsound.Beep(1250, 90)
            eng = pyttsx3.init()
            eng.setProperty("rate", SPEECH_RATE)
            eng.say(text)
            eng.runAndWait()
            eng.stop()
            del eng
        except Exception as e:
            print(f"tts: {e}")


# shared with the ticker thread: current hazard range (mm) or None when clear
tick_range = None


def ticker_worker():
    """Proximity as repetition rate -- the parking-sensor pattern every shipped
    product uses instead of speaking numbers. 40 ms 600 Hz blips, period
    interpolated TICK_FAR_S..TICK_NEAR_S over CAUTION_MM..DIRECTIVE_MM.
    Spectrally sparse with real silence between blips (bone-conduction masking
    evidence: May & Walker 2017)."""
    import winsound
    while running:
        r = tick_range
        if r is None:
            time.sleep(0.1)
            continue
        f = np.clip((r - DIRECTIVE_MM) / (CAUTION_MM - DIRECTIVE_MM), 0, 1)
        period = TICK_NEAR_S + f * (TICK_FAR_S - TICK_NEAR_S)
        try:
            winsound.Beep(600, 40)
        except Exception:
            pass
        time.sleep(max(0.05, period - 0.04))


def direction_word(az_deg):
    """Wearer-relative direction, TERSE. Long phrases proved unusable live
    ('takes way too long to hear') -- three words max, no qualifiers."""
    a = az_deg
    if a < -25: return "hard left"
    if a < -6:  return "left"
    if a <= 6:  return "ahead"
    if a <= 25: return "right"
    return "hard right"


def spoken_range(mm):
    """Bare number = meters, half-meter steps; 'close' under 0.75 m. The unit
    word is dropped entirely -- the convention is learnable in one use and
    saves ~a second per utterance."""
    m = mm / 1000.0
    if m < 0.75:
        return "close"
    step = round(m * 2) / 2
    return f"{step:g}"


def detector_worker(get_frame):
    """Run YOLO-seg on the newest frame, forever. Never blocks the render loop.

    SEGMENTATION, not boxes-only (2026-08-16, from live chair testing): a box
    is 40-60% background, so box-based zone claiming kept grabbing the WALL
    zones behind the chair and the announced range flapped 1.2<->2.5 m. With
    masks, a zone is claimed only if its centre lands on the object itself.
    yolo26n-seg: 99 ms on this CPU at 416 -- 10 fps, fine in a worker thread."""
    global det_latest, det_frame_id, running
    from ultralytics import YOLO
    model = YOLO(str(ROOT / "yolo26n-seg.pt"))
    names = model.names
    while running:
        fid, frame = get_frame()
        if frame is None or fid == det_frame_id:
            time.sleep(0.005)
            continue
        # track(), not predict(): ByteTrack IDs let range history follow the
        # OBJECT, so a second person entering the frame can't inherit the
        # first one's history. Distance itself is still re-derived from the
        # current ToF frame every cycle (red-team #5: never a track attribute).
        r = model.track(frame, imgsz=IMGSZ, conf=CONF, persist=True,
                        tracker="bytetrack.yaml", verbose=False)[0]
        dets = []
        polys = r.masks.xy if r.masks is not None else [None] * len(r.boxes)
        for b, poly in zip(r.boxes, polys):
            name = names[int(b.cls)]
            tid = int(b.id) if b.id is not None else None
            dets.append({"name": name, "conf": float(b.conf),
                         "xyxy": b.xyxy[0].tolist(),
                         "tid": tid,
                         "poly": None if poly is None or len(poly) < 3
                                 else poly.astype(np.float32),
                         "tier1": name in TIER1})
        with det_lock:
            det_latest = dets
            det_frame_id = fid


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cam", type=int, default=1)
    ap.add_argument("--no-audio", action="store_true", help="start with audio off")
    ap.add_argument("--mode", default="plain", choices=["plain", "brevity"],
                    help="callout language (docs/CALLOUT-PROTOCOL.md)")
    ap.add_argument("--rate", type=int, default=240,
                    help="TTS words/min (blind users parse far faster than sighted)")
    args = ap.parse_args()

    # F8 toggles audio GLOBALLY (no window focus needed) via GetAsyncKeyState —
    # the OpenCV 'a' key only works when the viewer window has focus, which is
    # never true while walking around testing.
    import ctypes
    VK_F8, VK_F9 = 0x77, 0x78
    def f8_pressed():
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_F8) & 0x8000)
    def f9_pressed():
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_F9) & 0x8000)

    global SPEECH_RATE
    SPEECH_RATE = args.rate

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K = cal["K"]
    D = cal["D"].reshape(4, 1)
    joint, cadex, eff = fo.load_extrinsics()
    use_joint = joint is not None
    ring = fo.zone_boundary_tans()
    P = ring.shape[2]

    threading.Thread(target=fo.reader, args=(args.port, args.baud), daemon=True).start()
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        running = False
        raise SystemExit(f"cannot open camera {args.cam}")

    frame_box = {"id": 0, "frame": None}
    fb_lock = threading.Lock()

    def get_frame():
        with fb_lock:
            return frame_box["id"], frame_box["frame"]

    threading.Thread(target=detector_worker, args=(get_frame,), daemon=True).start()
    threading.Thread(target=speech_worker, daemon=True).start()
    threading.Thread(target=ticker_worker, daemon=True).start()

    def pixel_azimuth(px, py):
        """Signed azimuth (deg, + = wearer's right) of a pixel, through the
        calibrated fisheye model -- raw pixel fraction is badly wrong here."""
        u = cv2.fisheye.undistortPoints(
            np.array([[[px, py]]], np.float64), K, D,
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-10))
        if abs(u).max() > 1e5:            # sentinel: undistort failed
            return None
        return float(np.degrees(np.arctan(u[0, 0, 0])))

    outline = {"A": (255, 220, 80), "B": (60, 230, 230)}
    show_det, show_text = True, False
    audio_on = not args.no_audio
    brevity = args.mode == "brevity"
    directive_active = False
    blind_said = False
    f8_was_down = False
    f9_was_down = False
    rng_hist = {}          # key -> [(t, range_mm)] for 1 s median smoothing
    tof_hist = {"A": [], "B": []}      # (t, grid) valid-hold window per sensor
    snapdir = ROOT / "camera" / "snapshots"
    snapdir.mkdir(exist_ok=True)
    nsnap = 0

    while running:
        ok, frame = cap.read()
        if not ok:
            continue
        with fb_lock:
            frame_box["id"] += 1
            frame_box["frame"] = frame

        ex = joint if (use_joint and joint) else cadex
        now = time.monotonic()
        # -- project all valid zones (same batch pattern as fusion_overlay) --
        zones = []          # {poly (P,2), centroid, z, sensor}
        for S in ("A", "B"):
            with fo.lock:
                g = None if fo.latest[S] is None else fo.latest[S].copy()
                age = now - fo.stamp[S]
            if g is None or age > 1.0:
                continue
            # Per-zone VALID-SAMPLE HOLD, 0.8 s window. Measured root cause of
            # the chair flap (20 s raw capture, 2026-08-16): the chair occupies
            # exactly one zone (A r3c3 ~950 mm) whose return DROPS OUT 60% of
            # frames -- weak signal from a partial-fill dark-mesh target at the
            # field edge. When valid it is ALWAYS the chair, never the wall.
            # So: each zone's value = median of its valid samples in the last
            # 0.8 s; no valid samples in the window -> zone invalid. Bridges
            # the dropouts; an intermittent-but-real near target holds steady.
            h = tof_hist[S]
            h.append((now, g))
            h[:] = [(t, gg) for t, gg in h if now - t < 0.8]
            stack = np.stack([gg for _, gg in h])
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gm = np.nanmedian(np.where(stack > 0, stack, np.nan), axis=0)
            g = np.where(np.isnan(gm), 0.0, gm)
            R, t = ex[S]
            quads, zs, rows = [], [], []
            for r in range(SIDE):
                for c in range(SIDE):
                    z = g[r, c]
                    if z <= 0:
                        continue
                    tan_ae = ring[r, c]
                    quads.append(np.column_stack([tan_ae[:, 0] * z,
                                                  tan_ae[:, 1] * z,
                                                  np.full(P, z)]))
                    zs.append(z)
                    rows.append(r)
            if not quads:
                continue
            allp = np.vstack(quads) @ R.T + t
            front = allp[:, 2] > fo.MIN_Z_CAM
            proj = np.full((len(allp), 2), np.nan)
            if front.any():
                uv, _ = cv2.fisheye.projectPoints(
                    allp[front].reshape(1, -1, 3).astype(np.float64),
                    np.zeros(3), np.zeros(3), K, D)
                proj[front] = uv.reshape(-1, 2)
            for i, (z, rr) in enumerate(zip(zs, rows)):
                poly = proj[i * P:(i + 1) * P]
                if np.isnan(poly).any():
                    continue
                zones.append({"poly": poly.astype(np.int32),
                              "cen": poly.mean(0), "z": z, "S": S, "row": rr})

        with det_lock:
            dets = list(det_latest) if show_det else []

        # -- associate: MASK first (zone centre on the object itself), box
        # fallback for detections without a usable mask. Box-era logic kept
        # for the fallback: centroid-in-box, then rect-overlap >35%. --
        claimed = set()
        for d in dets:
            x0, y0, x1, y1 = d["xyxy"]
            mask_poly = d.get("poly")
            zhit = []
            for i, zn in enumerate(zones):
                cx, cy = zn["cen"]
                if mask_poly is not None:
                    if cv2.pointPolygonTest(mask_poly, (float(cx), float(cy)),
                                            False) >= 0:
                        zhit.append(i)
                    continue
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    zhit.append(i)
                    continue
                zx0, zy0 = zn["poly"].min(0)
                zx1, zy1 = zn["poly"].max(0)
                ow = max(0, min(x1, zx1) - max(x0, zx0))
                oh = max(0, min(y1, zy1) - max(y0, zy0))
                zarea = max(1, (zx1 - zx0) * (zy1 - zy0))
                if ow * oh > 0.35 * zarea:
                    zhit.append(i)
            if zhit:
                d["range_mm"] = min(zones[i]["z"] for i in zhit)
                d["zrows"] = {zones[i]["row"] for i in zhit}
                claimed.update(zhit)
            else:
                d["range_mm"] = None
                d["zrows"] = set()

        # -- render --
        view = frame.copy()
        fillbuf = frame.copy()
        for zn in zones:
            cv2.fillPoly(fillbuf, [zn["poly"]], fo.depth_color(zn["z"]))
        view = cv2.addWeighted(fillbuf, 0.22, view, 0.78, 0)
        for zn in zones:
            cv2.polylines(view, [zn["poly"]], True, outline[zn["S"]], 1, cv2.LINE_AA)
            if show_text:
                cx, cy = zn["cen"].astype(int)
                cv2.putText(view, f"{zn['z']:.0f}", (cx - 18, cy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1,
                            cv2.LINE_AA)

        # ToF-only near obstacles: unclaimed + close = CV-blind hazard
        alert_zones = [zn for i, zn in enumerate(zones)
                       if i not in claimed and zn["z"] < ALERT_MM]
        for zn in alert_zones:
            cv2.polylines(view, [zn["poly"]], True, (0, 0, 255), 3, cv2.LINE_AA)
        if alert_zones:
            near = min(zn["z"] for zn in alert_zones)
            cv2.putText(view, f"OBSTACLE (unlabeled) {near/1000:.1f} m",
                        (12, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.85,
                        (0, 0, 255), 2, cv2.LINE_AA)

        for d in dets:
            x0, y0, x1, y1 = [int(v) for v in d["xyxy"]]
            col = (0, 80, 255) if d["tier1"] else (90, 200, 90)
            cv2.rectangle(view, (x0, y0), (x1, y1), col, 3 if d["tier1"] else 2)
            if d.get("poly") is not None:
                cv2.polylines(view, [d["poly"].astype(np.int32)], True, col, 1,
                              cv2.LINE_AA)
            rng = f" {d['range_mm']/1000:.1f}m" if d["range_mm"] else " ?m"
            cv2.putText(view, f"{d['name']} {d['conf']:.2f}{rng}",
                        (x0, max(20, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        col, 2, cv2.LINE_AA)

        # F8 global toggle (edge-triggered)
        f8_now = f8_pressed()
        if f8_now and not f8_was_down:
            audio_on = not audio_on
        f8_was_down = f8_now

        # ── TIER ENGINE v2 (docs/MASTER-SYNTHESIS-2026-08-16.md) ─────────────
        # Silence is the default. Autonomous speech = hazards + commands only;
        # F9 answers "what's around me" on demand. Proximity rides the ticker.
        global speech_next, tick_range
        # azimuth per zone, cached
        for zn in zones:
            if "az" not in zn:
                zn["az"] = pixel_azimuth(*zn["cen"])
        # CANE FILTER: bottom row is the cane's territory (and, worn at 22.5°
        # down, mostly the floor itself) -- rendered, never spoken/ticked.
        # Head/torso/waist band = rows 0-2.
        upper = [zn for zn in zones if zn["row"] < 3 and zn["az"] is not None]
        path = [zn for zn in upper if abs(zn["az"]) < PATH_CONE_DEG]
        near_path = min((zn["z"] for zn in path), default=None)
        tick_range = (near_path if audio_on and near_path is not None
                      and near_path < CAUTION_MM else None)

        if audio_on:
            if near_path is not None and near_path < DIRECTIVE_MM:
                # DIRECTIVE: command, chosen by where the free space is
                left = [zn["z"] for zn in upper if zn["az"] < -10]
                right = [zn["z"] for zn in upper if zn["az"] > 10]
                lmean = np.mean(left) if left else 0
                rmean = np.mean(right) if right else 0
                if max(lmean, rmean) < 1200:
                    cmd = "stop stop"
                elif rmean >= lmean:
                    cmd = "break right" if brevity else "step right"
                else:
                    cmd = "break left" if brevity else "step left"
                directive_active = True
                with speech_lock:
                    speech_next = (cmd, "DIRECTIVE", near_path, "directive", now)
            else:
                if directive_active and (near_path is None or near_path > 1000):
                    directive_active = False
                    with speech_lock:
                        speech_next = ("clean" if brevity else "path clear",
                                       "CLEAR", 0, "caution", now)
                # CAUTION: nearest hazard, no class priority (person callouts
                # are the LEAST-wanted feature; nearest threat wins, period).
                cand = None      # (spoken-name, key, raw_range, azimuth)
                hz = [zn for zn in alert_zones
                      if zn["row"] < 3 and zn.get("az") is not None]
                if hz:
                    zn = min(hz, key=lambda z: z["z"])
                    cand = ("obstacle", "obstacle", zn["z"], zn["az"])
                ranged = [d for d in dets if d["range_mm"]
                          and any(r < 3 for r in d["zrows"])]
                if ranged:
                    d = min(ranged, key=lambda d: d["range_mm"])
                    if cand is None or d["range_mm"] < cand[2]:
                        x0, y0, x1, y1 = d["xyxy"]
                        az = pixel_azimuth((x0 + x1) / 2, (y0 + y1) / 2)
                        if az is not None:
                            nm = (d["name"] if d["conf"] >= CONF_HEDGE
                                  else f"maybe {d['name']}")
                            key = f"id{d['tid']}" if d["tid"] else d["name"]
                            cand = (nm, key, d["range_mm"], az)
                if cand is not None:
                    name, stem, raw_rng, az = cand
                    hist = rng_hist.setdefault(stem, [])
                    hist.append((now, raw_rng))
                    hist[:] = [(t, v) for t, v in hist if now - t < 1.0]
                    if len(hist) >= 3:
                        rng = float(np.median([v for _, v in hist]))
                        (t0h, v0h), (t1h, v1h) = hist[0], hist[-1]
                        rate = ((v1h - v0h) / 1000.0 / max(0.2, t1h - t0h))
                        closing = rate < CLOSING_MPS
                        if rng < CAUTION_MM or closing:
                            # TWO items max (van Erp: recall ceiling walking).
                            # No numbers -- the ticker carries proximity.
                            if brevity:
                                nm = BREV_NAME.get(name.replace("maybe ", ""), name)
                                text = f"{nm}, {CLOCK_WORD.get(clock_hour(az), 'twelve')}"
                                if closing:
                                    text += ", hot"
                            else:
                                text = f"{name}, {direction_word(az)}"
                                if closing:
                                    text += ", closing"
                            with speech_lock:
                                speech_next = (text, f"{stem}:{direction_word(az)}",
                                               rng, "caution", now)

            # sensor-loss callout: silence must never mean "safe"
            with fo.lock:
                worst_age = max(now - fo.stamp[s] if fo.stamp[s] else 99 for s in "AB")
            if worst_age > 1.5 and not blind_said:
                blind_said = True
                with speech_lock:
                    speech_next = ("blind" if brevity else "sensors lost",
                                   "BLIND", 0, "directive", now)
            elif worst_age < 0.5:
                blind_said = False

        # F9: on-demand scene query -- the Apple two-tier verbosity pattern.
        # Numbers ARE allowed here (stationary aiming context), hedged by
        # association coarseness: "about".
        f9_now = f9_pressed()
        if f9_now and not f9_was_down:
            parts = []
            ranged = sorted([d for d in dets if d["range_mm"]],
                            key=lambda d: d["range_mm"])[:2]
            for d in ranged:
                x0, y0, x1, y1 = d["xyxy"]
                az = pixel_azimuth((x0 + x1) / 2, (y0 + y1) / 2)
                if az is None:
                    continue
                nm = d["name"] if d["conf"] >= CONF_HEDGE else f"maybe {d['name']}"
                m = d["range_mm"] / 1000.0
                parts.append(f"{nm} {direction_word(az)}, about "
                             f"{'1 meter' if m < 1.3 else f'{m:.0f} meters'}")
            if not parts and alert_zones:
                zn = min(alert_zones, key=lambda z: z["z"])
                az = zn.get("az")
                if az is not None:
                    parts.append(f"obstacle {direction_word(az)}, about "
                                 f"{max(1, round(zn['z']/1000))} meters")
            text = ("; ".join(parts) if parts
                    else "There is nothing to call out right now")
            with speech_lock:
                speech_next = (text, f"QUERY{now}", 0, "query", now)
        f9_was_down = f9_now

        mode = "JOINT" if (use_joint and joint) else "CAD"
        voice = "BREVITY" if brevity else "plain"
        cv2.putText(view, f"CV fusion  [{mode}]  det {'on' if show_det else 'OFF'}  "
                    f"audio {'on' if audio_on else 'OFF'} ({voice})  zones {len(zones)}",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (240, 240, 240), 2,
                    cv2.LINE_AA)

        cv2.imshow("CV fusion", view)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        elif k == ord("y"):
            show_det = not show_det
        elif k == ord("a"):
            audio_on = not audio_on
        elif k == ord("b"):
            brevity = not brevity
        elif k == ord("t"):
            show_text = not show_text
        elif k == ord("m") and joint is not None:
            use_joint = not use_joint
        elif k == ord("s"):
            p = snapdir / f"cvfusion_{nsnap:03d}.png"
            cv2.imwrite(str(p), view)
            print(f"saved {p}")
            nsnap += 1

    running = False
    fo.running = False
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
