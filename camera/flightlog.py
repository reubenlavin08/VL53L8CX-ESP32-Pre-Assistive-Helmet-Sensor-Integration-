"""Flight logging: FP/hour metric + intervention clips (the measurement
layer). Design: docs/plans/PLAN-fp-hour-intervention-logging.md.

- events.jsonl: every spoken alert, audio toggle, FP vote, clip, heartbeat
- FP votes: implicit (user hushes audio within FP_WINDOW_S of a caution)
  and explicit (voice "wrong" / key x)
- 60 s rolling rings (2 fps 360p JPEG, ToF grids, 20 Hz IMU) dumped to a
  clip dir on trigger: override / explicit / manual / disagreement /
  directive. openpilot pattern at fleet-size 1.
- session_report.py turns sessions into FP/hour + alerts/hour numbers.

Privacy stance (UTILITY-ROADMAP): no persistent recording — the ring
lives in RAM and persists ONLY on explicit trigger events; sessions are
local-only and git-ignored.
"""

import json
import pathlib
import threading
import time
from collections import deque

import cv2
import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
SESS_ROOT = _HERE / "sessions"
FP_WINDOW_S = 10.0        # hush within this of a caution = implicit FP vote
CLIP_DEBOUNCE_S = 30.0    # global: at most one clip per this
DISAGREE_GAP_S = 120.0    # disagreement clips: a bad scene must not fill disk
HEARTBEAT_S = 60.0

_lock = threading.Lock()
_dir = None
_events = None
_last_alert = None        # (t, key, tier)
_last_clip = 0.0
_last_disagree = 0.0
_last_hb = 0.0
_last_frame_t = 0.0

_frames = deque(maxlen=120)              # (t, jpeg bytes) ~2 fps x 60 s
_tof = {"A": deque(), "B": deque()}      # (t, grid) trimmed to 60 s
_imu = deque(maxlen=1200)                # (t, w, x, y, z) ~20 Hz x 60 s
_imu_last_t = 0.0


def start_session(meta):
    global _dir, _events
    _dir = SESS_ROOT / time.strftime("%Y-%m-%d_%H%M%S")
    (_dir / "clips").mkdir(parents=True, exist_ok=True)
    (_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    _events = _dir / "events.jsonl"
    event("session_start")
    print(f"flightlog: {_dir}")


def event(kind, **fields):
    if _events is None:
        return
    fields["e"] = kind
    fields["t"] = round(time.time(), 2)
    line = json.dumps(fields)
    with _lock:
        try:
            with open(_events, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def heartbeat():
    global _last_hb
    now = time.time()
    if now - _last_hb >= HEARTBEAT_S:
        _last_hb = now
        event("heartbeat")


def spoken(text, key, tier, range_mm):
    """Hooked in speech_worker AFTER the filter gauntlet — logs exactly
    what the user hears. Directive utterances always earn a clip."""
    global _last_alert
    event("spoken", text=text, key=str(key), tier=tier,
          range_mm=round(float(range_mm), 0) if range_mm else None)
    if tier in ("caution", "directive"):
        _last_alert = (time.time(), str(key), tier)
        if tier == "directive":
            trigger_clip("directive")


def add_frame(frame):
    global _last_frame_t
    now = time.time()
    if now - _last_frame_t < 0.5:
        return
    _last_frame_t = now
    try:
        small = cv2.resize(frame, (640, 360))
        ok, jb = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            _frames.append((now, jb.tobytes()))
    except cv2.error:
        pass


def add_tof(sensor, grid):
    if grid is None:
        return
    now = time.time()
    dq = _tof[sensor]
    dq.append((now, np.asarray(grid, dtype=np.float32).copy()))
    while dq and now - dq[0][0] > 60.0:
        dq.popleft()


def add_imu(w, x, y, z):
    global _imu_last_t
    now = time.time()
    if now - _imu_last_t < 0.05:          # subsample ~20 Hz
        return
    _imu_last_t = now
    _imu.append((now, w, x, y, z))


def override(src):
    """User turned audio OFF. Implicit FP vote if a caution was recent —
    directives excluded (hushing during 'stop stop' is panic, not
    disagreement)."""
    event("audio_toggle", on=False, src=src)
    la = _last_alert
    if la and time.time() - la[0] < FP_WINDOW_S and la[2] == "caution":
        event("fp_vote", mode="implicit", alert_key=la[1],
              alert_t=round(la[0], 2),
              latency_s=round(time.time() - la[0], 2))
        trigger_clip("override")


def audio_on(src):
    event("audio_toggle", on=True, src=src)


def explicit_fp():
    la = _last_alert
    event("fp_vote", mode="explicit",
          alert_key=la[1] if la else None,
          alert_t=round(la[0], 2) if la else None,
          latency_s=round(time.time() - la[0], 2) if la else None)
    trigger_clip("explicit_fp")


def disagreement():
    """ToF-near + zero CV explanation, persisting — the built-in
    shadow-mode signal. Heavily rate-limited."""
    global _last_disagree
    now = time.time()
    if now - _last_disagree < DISAGREE_GAP_S:
        return
    _last_disagree = now
    trigger_clip("disagreement")


def trigger_clip(why):
    global _last_clip
    now = time.time()
    if _dir is None or now - _last_clip < CLIP_DEBOUNCE_S:
        return
    _last_clip = now
    event("clip", trigger=why)
    fr = list(_frames)
    tA = list(_tof["A"])
    tB = list(_tof["B"])
    im = list(_imu)
    threading.Thread(target=_save_clip, args=(why, fr, tA, tB, im),
                     daemon=True).start()


def _save_clip(why, fr, tA, tB, im):
    d = _dir / "clips" / f"{time.strftime('%H%M%S')}_{why}"
    try:
        d.mkdir(parents=True, exist_ok=True)
        for i, (t, b) in enumerate(fr):
            (d / f"frame_{i:03d}.jpg").write_bytes(b)
        for name, rows in (("tofA", tA), ("tofB", tB)):
            if rows:
                np.savez_compressed(
                    d / f"{name}.npz",
                    t=np.array([t for t, _ in rows]),
                    g=np.stack([g for _, g in rows]))
        with open(d / "imu.jsonl", "w", encoding="utf-8") as f:
            for row in im:
                f.write(json.dumps([round(float(v), 4) for v in row]) + "\n")
        (d / "why.json").write_text(json.dumps(
            {"trigger": why, "t": time.time(),
             "frames": len(fr), "tofA": len(tA), "tofB": len(tB)}))
    except OSError as e:
        event("clip_error", err=str(e))
