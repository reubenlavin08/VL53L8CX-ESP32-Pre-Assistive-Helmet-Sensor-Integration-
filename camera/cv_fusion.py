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
import json
import pathlib
import threading
import time

import cv2
import numpy as np

import fusion_overlay as fo          # projection machinery + serial reader
import flightlog                     # FP/hour metric + intervention clips

# ── helmet-firmware source (post-flash) ──────────────────────────────────────
# The flashed helmet firmware streams over USB-serial AND TCP:3333:
#   DATA:d0..d15   sensor A     DATAT:d0..d15  sensor B     Q:w,x,y,z,st,acc
# Invalid zones arrive as 4000 (MAX_DISTANCE_MM), not 0 -- remapped here so all
# downstream logic keeps its ">0 = valid" convention. TCP is the default so the
# viewer never fights another tool for the COM port.
imu_quat = None          # latest [w,x,y,z], helmet firmware only
tap_event = None         # (count, t) from firmware TAP: lines
drop_state = None        # 1 = dropped, 0 = picked up (firmware DROP: lines)
from collections import deque as _dq
_yawh = _dq(maxlen=12)   # ~120 ms of yaw samples for the rate estimator
yaw_rate = 0.0           # deg/s, EMA-smoothed, signed
imu_stamp = 0.0


def _helmet_line(s):
    """Parse one helmet-firmware line (DATA:/DATAT:/Q:) into shared state."""
    global imu_quat, imu_stamp
    if s.startswith("DATA:") or s.startswith("DATAT:"):
        S = "B" if s.startswith("DATAT:") else "A"
        p = s.split(":", 1)[1].split(",")
        if len(p) != 16:
            return
        try:
            v = np.array([int(x) for x in p], float).reshape(4, 4)
        except ValueError:
            return
        v[v >= 4000] = 0.0              # firmware sends invalid as 4000
        with fo.lock:
            fo.latest[S] = v
            fo.stamp[S] = time.monotonic()
    elif s.startswith("Q:"):
        try:
            q = [float(x) for x in s[2:].split(",")[:4]]
        except ValueError:
            return
        imu_quat = q
        flightlog.add_imu(*q)
        # yaw-rate estimator (sterile-cockpit gate). Chip-frame yaw is fine
        # for a RATE -- mount_cal is constant and cancels in the delta.
        w_, x_, y_, z_ = q
        _yawh.append((imu_stamp,
                      np.degrees(np.arctan2(2 * (w_ * z_ + x_ * y_),
                                            1 - 2 * (y_ * y_ + z_ * z_)))))
        if len(_yawh) >= 2 and _yawh[-1][0] - _yawh[0][0] > 0.02:
            (t0y, y0y), (t1y, y1y) = _yawh[0], _yawh[-1]
            r = (((y1y - y0y + 180.0) % 360.0) - 180.0) / (t1y - t0y)
            globals()["yaw_rate"] = 0.7 * yaw_rate + 0.3 * r
        return
    if s.startswith("TAP:"):
        try:
            globals()["tap_event"] = (int(s[4:]), time.monotonic())
        except ValueError:
            pass
        return
    if s.startswith("DROP:"):
        try:
            globals()["drop_state"] = int(s[5:])
        except ValueError:
            pass
        imu_stamp = time.monotonic()


def helmet_reader(host, tcp_port):
    import socket
    buf = b""
    while fo.running:
        try:
            sk = socket.create_connection((host, tcp_port), timeout=3)
            sk.settimeout(1.0)
        except OSError:
            time.sleep(1.0)
            continue
        while fo.running:
            try:
                chunk = sk.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                _helmet_line(line.decode("utf-8", "replace").strip())
        try:
            sk.close()
        except OSError:
            pass


def helmet_serial_reader(port, baud):
    """FIELD MODE: same helmet-firmware lines over the USB cable -- no WiFi
    infrastructure needed while walking. The firmware prints every stream line
    to USB-CDC regardless of WiFi state (it boots fine with no AP in range)."""
    import serial
    while fo.running:
        try:
            sp = serial.Serial(port, baud, timeout=1)
        except Exception:
            time.sleep(1.5)
            continue
        buf = b""
        while fo.running:
            try:
                buf += sp.read(sp.in_waiting or 1)
            except Exception:
                break
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                _helmet_line(line.decode("utf-8", "replace").strip())
        try:
            sp.close()
        except Exception:
            pass


# ── phone viewer: MJPEG server so the rig is watchable from a pocket ─────────
# The laptop rides in a backpack; the phone joins the laptop's mobile hotspot
# and opens http://<laptop-ip>:<port>/ for the FULL annotated view (zones,
# detections, horizon, attitude inset) at ~10 fps.
phone_jpeg = None
phone_lock = threading.Lock()
phone_status = {"said": "", "audio": True, "mode": "idle", "gated": False,
                "dropped": False}   # updated each frame; served at /status


def phone_server(port):
    """PWA dashboard: installs to the iPhone home screen via Safari's
    Add to Home Screen (manifest + apple meta tag -> launches fullscreen,
    no App Store, no dev account). Live MJPEG view + status bar + big
    touch buttons that inject the SAME commands as voice/keys -- the
    phone is a silent remote for demos."""
    import io
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    # generated iris icon (concentric circles), cached once
    ic = np.zeros((512, 512, 3), np.uint8)
    ic[:] = (24, 18, 16)
    cv2.circle(ic, (256, 256), 200, (140, 90, 30), -1, cv2.LINE_AA)
    cv2.circle(ic, (256, 256), 200, (220, 170, 60), 14, cv2.LINE_AA)
    cv2.circle(ic, (256, 256), 90, (30, 24, 20), -1, cv2.LINE_AA)
    cv2.circle(ic, (310, 200), 34, (250, 240, 230), -1, cv2.LINE_AA)
    _, icon_png = cv2.imencode(".png", ic)
    icon_bytes = icon_png.tobytes()

    MANIFEST = json.dumps({
        "name": "Iris", "short_name": "Iris",
        "display": "standalone", "orientation": "portrait",
        "background_color": "#101216", "theme_color": "#101216",
        "start_url": "/", "icons": [{"src": "/icon.png",
                                     "sizes": "512x512",
                                     "type": "image/png"}]}).encode()

    PAGE = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.png">
<title>Iris</title>
<style>
 *{margin:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
 body{background:#101216;color:#e8e6e0;font-family:-apple-system,system-ui,sans-serif;
      height:100vh;display:flex;flex-direction:column;
      padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
 #v{width:100%;flex:1;object-fit:contain;background:#000;min-height:0}
 #bar{padding:10px 14px;font-size:15px;min-height:44px;
      border-top:1px solid #2a2e36;color:#9fd8a4}
 #said{color:#e8e6e0;font-weight:600}
 #grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px 14px 16px}
 button{background:#1c2027;border:1px solid #333a45;color:#e8e6e0;
        border-radius:14px;padding:18px 0;font-size:17px;font-weight:600}
 button:active{background:#2a3140}
 #mute.off{background:#5a1f1f;border-color:#7c2c2c}
</style></head><body>
<img id="v" src="/stream">
<div id="bar"><span id="mode">idle</span> · <span id="said"></span></div>
<div id="grid">
 <button onclick="cmd('around')">What's around</button>
 <button onclick="cmd('describe')">Describe</button>
 <button id="mute" onclick="toggleMute()">Mute</button>
 <button onclick="cmd('flag')">Flag that</button>
</div>
<script>
let audioOn=true;
function cmd(c){fetch('/cmd?c='+c)}
function toggleMute(){cmd(audioOn?'quiet':'audio_on')}
setInterval(async()=>{try{
 const s=await(await fetch('/status')).json();
 audioOn=s.audio;
 document.getElementById('mode').textContent=s.mode+(s.gated?' · gated':'')+(s.dropped?' · DROPPED':'');
 document.getElementById('said').textContent=s.said;
 const m=document.getElementById('mute');
 m.textContent=audioOn?'Mute':'Unmute'; m.className=audioOn?'':'off';
}catch(e){}},600);
</script></body></html>"""

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=fr")
                self.end_headers()
                try:
                    while fo.running:
                        with phone_lock:
                            j = phone_jpeg
                        if j is not None:
                            self.wfile.write(b"--fr\r\nContent-Type: image/jpeg\r\n"
                                             + f"Content-Length: {len(j)}\r\n\r\n".encode()
                                             + j + b"\r\n")
                        time.sleep(0.09)
                except (ConnectionError, OSError):
                    pass
            elif self.path == "/manifest.json":
                self._send(MANIFEST, "application/manifest+json")
            elif self.path == "/icon.png":
                self._send(icon_bytes, "image/png")
            elif self.path == "/status":
                self._send(json.dumps(phone_status).encode(),
                           "application/json")
            elif self.path.startswith("/cmd?c="):
                c = self.path.split("=", 1)[1]
                if c in ("around", "describe", "quiet", "audio_on",
                         "flag", "stop", "doors", "guide", "hand", "read"):
                    import voice
                    voice.commands.put(c)   # same dispatch as spoken commands
                self._send(b"{}", "application/json")
            else:
                self._send(PAGE.encode(), "text/html")

    try:
        ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
    except OSError as e:
        print(f"phone server: {e}")


# camera -> helmet rotation (constant, from the CAD construction: the whole
# sensor group is pitched 22.5 deg down; camera axes in helmet coords are
# cam_x=(1,0,0), cam_y=(0,-s,-c), cam_z=(0,c,-s), s/c = sin/cos 22.5).
# Verified: p_cam=(0,0,1) (boresight) -> helmet (0, c, -s) = forward+down.
_S225 = np.sin(np.radians(22.5))
_C225 = np.cos(np.radians(22.5))
R_CH = np.array([[1.0, 0.0, 0.0],
                 [0.0, -_S225, _C225],
                 [0.0, -_C225, -_S225]])

HEAD_MARGIN_MM = 120.0    # clearance margin above the pod plane (100-150)
TUNNEL_HALF_MM = 450.0    # virtual corridor half-width (0.9 m total)
TUNNEL_NEAR_MM = 1200.0   # wall proximity where cueing starts
TUNNEL_SEND_S = 0.25      # host->firmware duty update cadence


def quat_to_R(w, x, y, z):
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


# ── cylindrical dewarp for the DETECTOR ONLY (2026-08-17) ────────────────────
# YOLO mislabelled half the room ("thinks half the things in my room are tvs")
# because COCO detectors are trained on straight lenses. Borrowed from the
# ubc-cam project's finding: the detector degrades before anything else, so
# dewarp ITS input and leave all geometry on the raw frame. Cylindrical keeps
# the full 120° horizontal field (rectilinear at 120° would stretch the edges
# absurdly). Mapping precomputed once; per-frame cost is one cv2.remap.
CYL_W, CYL_H = 832, 416
CYL_HFOV, CYL_VFOV = np.deg2rad(114), np.deg2rad(57)


def build_cyl(K, D):
    """Returns (map_x, map_y) for remap raw->cyl, and cyl_to_raw(pts Nx2)."""
    u = (np.arange(CYL_W) / CYL_W - 0.5) * CYL_HFOV          # azimuth
    v = (np.arange(CYL_H) / CYL_H - 0.5) * CYL_VFOV          # elevation (down +)
    az, el = np.meshgrid(u, v)
    # direction in camera frame (+x right, +y down, +z fwd), then to the
    # normalized plane the fisheye model distorts from
    x = np.sin(az) * np.cos(el)
    y = np.sin(el)
    z = np.cos(az) * np.cos(el)
    pts = np.stack([x / z, y / z], -1).reshape(1, -1, 2)
    px = cv2.fisheye.distortPoints(pts.astype(np.float64), K, D).reshape(CYL_H, CYL_W, 2)
    map_x = px[..., 0].astype(np.float32)
    map_y = px[..., 1].astype(np.float32)

    def cyl_to_raw(p):
        """Map Nx2 cylindrical pixels back to raw-fisheye pixels."""
        p = np.asarray(p, float)
        a = (p[:, 0] / CYL_W - 0.5) * CYL_HFOV
        e = (p[:, 1] / CYL_H - 0.5) * CYL_VFOV
        d = np.stack([np.sin(a) * np.cos(e) / (np.cos(a) * np.cos(e)),
                      np.sin(e) / (np.cos(a) * np.cos(e))], -1)
        return cv2.fisheye.distortPoints(d.reshape(1, -1, 2), K, D).reshape(-1, 2)

    return map_x, map_y, cyl_to_raw


use_dewarp = True        # key 'w' toggles; A/B the mislabel rate live
_cyl = {"maps": None, "fn": None}


def open_camera(idx):
    """Open a camera index at 720p MJPG; None if it gives no usable frames.
    USB re-enumeration swaps indices between sessions (bit us 2026-08-17: the
    helmet cam moved 1 -> 0 and the viewer showed the dark laptop cam), so
    --cam auto probes 0-3 and keeps the BRIGHTEST working feed."""
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None, -1.0
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    for _ in range(3):
        cap.read()
    ok, f = cap.read()
    if not ok or f is None:
        cap.release()
        return None, -1.0
    return cap, float(f.mean())


# ── 3D attitude inset: wireframe pod + compass, pure cv2 lines ───────────────
# Helmet-frame (X right, Y forward, Z up) vertices, mm-ish. A recognisable
# cartoon of the rig: base plate, two ToF stubs yawed ±22.5°, camera barrel,
# and an up-post so vertical is legible at a glance.
def _pod_wireframe():
    def yawed(deg, sign):
        a = np.deg2rad(deg)
        c, s = np.cos(a), np.sin(a)
        # small square panel facing forward, yawed about Z
        pts = np.array([[-8, 0, -8], [8, 0, -8], [8, 0, 8], [-8, 0, 8]], float)
        R = np.array([[c, -sign * s, 0], [sign * s, c, 0], [0, 0, 1]])
        return pts @ R.T + np.array([sign * 20, 24, 0])
    plate = np.array([[-30, -12, -4], [30, -12, -4], [30, 20, -4], [-30, 20, -4],
                      [-30, -12, 4], [30, -12, 4], [30, 20, 4], [-30, 20, 4]], float)
    cam = np.array([[-6, 20, -6], [6, 20, -6], [6, 32, 0], [-6, 32, 0],
                    [-6, 20, 6], [6, 20, 6]], float)
    up = np.array([[0, 0, 4], [0, 0, 26], [-4, 0, 20], [4, 0, 20]], float)
    segs = []
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7)]:
        segs.append((plate[i], plate[j], (200, 200, 200)))
    for q, col in ((yawed(22.5, -1), (255, 220, 80)),     # A = wearer LEFT, cyan
                   (yawed(22.5, +1), (60, 230, 230))):    # B = RIGHT, yellow
        for i in range(4):
            segs.append((q[i], q[(i + 1) % 4], col))
    for i, j in [(0, 1), (0, 2), (1, 3), (2, 3), (4, 5), (0, 4), (1, 5)]:
        if max(i, j) < len(cam):
            segs.append((cam[i], cam[j], (90, 200, 90)))
    segs.append((up[0], up[1], (80, 255, 160)))
    segs.append((up[2], up[1], (80, 255, 160)))
    segs.append((up[3], up[1], (80, 255, 160)))
    return segs


POD_SEGS = _pod_wireframe()
# fixed isometric view of the WORLD frame: from behind-right-above the wearer
_ca, _sa = np.cos(np.deg2rad(35)), np.sin(np.deg2rad(35))
_ce, _se = np.cos(np.deg2rad(25)), np.sin(np.deg2rad(25))
VIEW = np.array([[_ca, _sa, 0],
                 [_sa * _se, -_ca * _se, _ce]])   # rows: screen x, screen y(up)


def draw_attitude_inset(view, R_hw, yaw_deg, size=210):
    """Top-right inset: the pod wireframe rotated by helmet->world R, plus a
    yaw compass ring (boot-relative -- the IMU is mag-free by design)."""
    H, W = view.shape[:2]
    x0, y0 = W - size - 10, 10
    cx, cy = x0 + size // 2, y0 + size // 2 + 8
    cv2.rectangle(view, (x0, y0), (x0 + size, y0 + size), (30, 30, 30), -1)
    cv2.rectangle(view, (x0, y0), (x0 + size, y0 + size), (90, 90, 90), 1)
    sc = size / 110.0
    for a, b, col in POD_SEGS:
        pa = VIEW @ (R_hw @ a); pb = VIEW @ (R_hw @ b)
        cv2.line(view, (int(cx + pa[0] * sc), int(cy - pa[1] * sc)),
                 (int(cx + pb[0] * sc), int(cy - pb[1] * sc)), col, 1, cv2.LINE_AA)
    # compass ring (top strip of the inset)
    rcx, rcy, rr = x0 + size - 30, y0 + 26, 18
    cv2.circle(view, (rcx, rcy), rr, (120, 120, 120), 1, cv2.LINE_AA)
    ya = np.deg2rad(yaw_deg)
    cv2.line(view, (rcx, rcy),
             (int(rcx + rr * np.sin(ya)), int(rcy - rr * np.cos(ya))),
             (80, 255, 160), 2, cv2.LINE_AA)
    cv2.putText(view, "yaw", (rcx - 14, rcy + rr + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1, cv2.LINE_AA)
    cv2.putText(view, "attitude", (x0 + 8, y0 + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

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
# Path cone is RANGE-ADAPTIVE (2026-08-20 biosonar review found the bug):
# a fixed 15 deg cone is +-8 cm at 0.3 m -- narrower than a torso, so a pole
# about to clip a shoulder was OUTSIDE it. Derive from body clearance:
# half-angle = atan(BODY_HALF_W / range), capped. 11 deg far -> 41 deg near,
# the same narrow-far/wide-near strategy bats use entering the terminal buzz
# (Jakobsen & Surlykke 2010, 40->90 deg).
BODY_HALF_W_MM = 350.0
PATH_CONE_MAX_DEG = 45.0
CAUTION_MM = 1800.0       # caution tier ceiling
CLOSING_MPS = -0.5        # range rate for the "closing"/"hot" aspect word
CONF_HEDGE = 0.50         # below this confidence the callout says "maybe"
GATE_ON_DPS = 100.0       # sterile cockpit: gate CAUTION above this yaw rate
GATE_OFF_DPS = 60.0       # release below this...
GATE_OFF_DWELL_S = 0.25   # ...sustained this long
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
        flightlog.spoken(text, key, tier, rng)
        phone_status["said"] = text
        global speaking
        try:
            speaking = True                # ticker mutes so words stay audible
            if tier == "directive":
                import winsound            # TCAS-style pre-cue: tone buys parse time
                winsound.PlaySound(str(CUE_WAV),
                                   winsound.SND_FILENAME | winsound.SND_NODEFAULT)
            eng = pyttsx3.init()
            eng.setProperty("rate", SPEECH_RATE)
            eng.say(text)
            eng.runAndWait()
            eng.stop()
            del eng
        except Exception as e:
            print(f"tts: {e}")
        finally:
            speaking = False


# shared with the ticker thread: (ttc_seconds_or_None, range_mm_or_None).
# TTC-BASED (2026-08-20 biosonar review): the old range-based law saturated at
# 6.67 Hz from 800 mm inward (the most urgent 0.4 s carried no information)
# and delivered FEWER ticks the faster you walked. Rate = K/TTC gives ~6 ticks
# per approach regardless of speed, a terminal cue at a fixed TIME margin
# (the bat strategy, Melcon 2007), and a stationary user goes SILENT -- which
# kills the alarm-fatigue failure that sank the BuzzClip.
tick_state = [(None, None, 0.0)]
speaking = False          # ticker mutes while an utterance plays (masking)
TTC_ON_S = 2.0            # start ticking below this time-to-contact
TTC_TERM_S = 0.6          # terminal cue below this (~human stop reaction)
TICK_RATE_MIN, TICK_RATE_MAX = 0.8, 12.0
TICK_K = 5.0              # rate = K / TTC
STANDOFF_MM = 500.0       # stationary heartbeat only inside this range


def _make_tone(path, freq, ms, amp):
    """Small sine WAV with a 5 ms fade envelope. winsound.Beep is full-volume
    with no gain control and drowned the speech (user feedback 2026-08-17);
    PlaySound with a quiet file gives us amplitude control."""
    import wave, struct
    sr = 22050
    n = int(sr * ms / 1000)
    env = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (sr * 0.005))
    s = (amp * env * np.sin(2 * np.pi * freq * np.arange(n) / sr) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(struct.pack(f"<{n}h", *s))


import tempfile
_SND = pathlib.Path(tempfile.gettempdir())
TICK_WAV = _SND / "helmet_tick.wav"
CUE_WAV = _SND / "helmet_cue.wav"
TERM_WAV = _SND / "helmet_term.wav"
# 600/1250 Hz sit -75/-70 dB below the 2-5 kHz band. The echolocation-band
# ban was VOIDED by user ruling 2026-08-20 (CALLOUT-PROTOCOL 9) -- these
# frequencies stay because they work, not because the band is protected.
_make_tone(TICK_WAV, 600, 40, 0.10)      # quiet blip
_make_tone(CUE_WAV, 1250, 90, 0.22)      # directive pre-cue, present not painful


def _make_trill(path, freq, ms, amp, mod_hz):
    """Terminal cue: amplitude-modulated 'trill' -- a CATEGORY change, not a
    faster tick (humans fuse click trains ~20-30 Hz, so there is no audible
    'faster'; the bat's 170 Hz buzz has no discrete human analogue)."""
    import wave, struct
    sr = 22050
    n = int(sr * ms / 1000)
    env = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (sr * 0.005))
    mod = 0.5 * (1 + np.sin(2 * np.pi * mod_hz * np.arange(n) / sr))
    s = (amp * env * mod * np.sin(2 * np.pi * freq * np.arange(n) / sr)
         * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(struct.pack(f"<{n}h", *s))


_make_trill(TERM_WAV, 600, 280, 0.16, 22)


def _tone_array(freq, ms, amp, mod_hz=None, sr=22050):
    n = int(sr * ms / 1000)
    env = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (sr * 0.005))
    s = amp * env * np.sin(2 * np.pi * freq * np.arange(n) / sr)
    if mod_hz:
        s *= 0.5 * (1 + np.sin(2 * np.pi * mod_hz * np.arange(n) / sr))
    return s.astype(np.float32)


TICK_ARR = _tone_array(600, 40, 0.10)
TERM_ARR = _tone_array(600, 280, 0.16, mod_hz=22)

# ── Soundscape beacon guidance (key 'g') ─────────────────────────────────
# Port of Microsoft Soundscape's 4-region audio beacon (camera/beacon.py,
# assets are the original MIT-licensed WAVs). Lock a detected object and a
# continuous musical tone leads you to it: timbre says how far off-axis
# your head is, stereo pan says which side, arrival plays the outro melody.
# Full design notes: docs/research-sources/soundscape-beacon-2026-08-20.md
from beacon import Beacon
GUIDE_ARRIVE_MM = 1000.0     # arrival geofence -- outro + "arrived", guide ends
GUIDE_LOST_S = 8.0           # target unseen this long -> "guide lost", stop

# ── Scan-and-select DOOR guidance (key 'd', then 1/2/3) ──────────────────
# Design: docs/research-sources/last-meter-doors-2026-08-22.md. COCO has no
# door class, so the scan runs YOLO-World (open-vocabulary) ON DEMAND only.
# Flow: 'd' -> "scanning, pan slowly" (3.5 s) -> up to 3 candidates spoken
# with clock bearing + rough range -> user presses 1/2/3 -> Soundscape
# beacon locks on the door's WORLD bearing (IMU-anchored, so it survives
# leaving the frame); a slow re-detect loop re-fixes bearing/range while
# guiding. Never guides anywhere the user didn't pick.
DOOR_CLASSES = ["door", "glass door", "doorway", "double door"]
DOOR_SCAN_S = 3.5            # scan window while the user pans
DOOR_CONF = 0.12             # open-vocab confidences run low; cluster+vote
DOOR_CLUSTER_DEG = 14.0      # world-bearing bin -> one candidate per cluster
DOOR_REDETECT_S = 1.2        # bearing re-fix cadence while guiding
DOOR_HEIGHT_MM = 2030.0      # standard door leaf for bbox-height ranging

# ── Find-by-text (voice "find <word>" / key f) + "read that" (key r) ─────
# docs/plans/PLAN-find-by-text.md. Cloud OCR (camera/ocr.py, nemotron-ocr-v2)
# with per-word normalized boxes -> pixel azimuth -> the same world-bearing
# beacon lock as door mode. Range only from ToF association -- never invented.
FIND_SCAN_S = 6.0            # OCR rounds while the user pans (~2-3 round trips)
FIND_REOCR_S = 2.0           # bearing re-fix cadence while guiding
FIND_EDIT_MAX = 1            # fuzzy match tolerance (Levenshtein)
FIND_ARRIVE_MM = 1200.0
FIND_MIN_CONF = 0.6          # OCR hallucination floor
FIND_MIN_LEN = 3             # never match tokens shorter than this


def _lev(a, b):
    """Levenshtein distance, tiny DP -- no dependency."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ticker_worker():
    """TTC-based proximity ticker (see tick_state comment). Discrete ticks
    accelerate with 1/time-to-contact; below TTC_TERM_S a distinct trill
    fires; a stationary user hears only a slow standoff heartbeat when
    something sits inside STANDOFF_MM. MUTES during speech (masking).

    SPATIALIZED (PLAN-spatialized-clicks): each tick is panned to the
    hazard's azimuth via beacon.ClickPlayer -- the tick now says WHERE,
    not just how soon. Mono winsound fallback if audio output fails."""
    import winsound
    player = None
    try:
        from beacon import ClickPlayer
        player = ClickPlayer()
        player._ensure()
    except Exception as e:
        print(f"ticker: stereo unavailable ({e}), mono fallback")
        player = None

    def play(path, arr, az):
        if player is not None:
            try:
                player.play(arr, az)
                return
            except Exception:
                pass
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME
                               | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    while running:
        ttc, rng, az = tick_state[0]
        if speaking or (ttc is None and (rng is None or rng > STANDOFF_MM)):
            time.sleep(0.1)
            continue
        if ttc is not None and ttc <= TTC_TERM_S:
            play(TERM_WAV, TERM_ARR, az)   # terminal: category change
            time.sleep(0.30)
        elif ttc is not None and ttc <= TTC_ON_S:
            rate = float(np.clip(TICK_K / ttc, TICK_RATE_MIN, TICK_RATE_MAX))
            play(TICK_WAV, TICK_ARR, az)
            time.sleep(max(0.06, 1.0 / rate))
        else:                              # stationary near something: heartbeat
            play(TICK_WAV, TICK_ARR, az)
            time.sleep(1.0 / TICK_RATE_MIN)


AROUND_REPEAT_S = 10.0    # repeat within this = next depth layer
SECTOR_EDGE_DEG = 20.0    # front-left | front-center | front-right split


def _sector(az):
    if az < -SECTOR_EDGE_DEG:
        return "front-left"
    if az > SECTOR_EDGE_DEG:
        return "front-right"
    return "front-center"


def _around_text(items, layer):
    """Around-Me phrasing. Layer 1 = labels+sectors (terse); layer 2 = same
    items with ranges. Sectors are camera-honest: we see ~120 deg forward,
    nothing behind -- and say so rather than overreach."""
    if not items:
        return "nothing close in front"
    if layer == 1:
        txt = "; ".join(f"{it['name']} {it['sector']}" for it in items)
        return txt + ". behind you I can't see"
    return "; ".join(f"{it['name']} {it['sector']}, "
                     f"{spoken_dist(it['rng'], walking=False)}"
                     for it in items)


def direction_word(az_deg):
    """Wearer-relative direction, TERSE. Long phrases proved unusable live
    ('takes way too long to hear') -- three words max, no qualifiers."""
    a = az_deg
    if a < -25: return "hard left"
    if a < -6:  return "left"
    if a <= 6:  return "ahead"
    if a <= 25: return "right"
    return "hard right"


STRIDE_M = 0.7            # per-user, overwritten by stride_cal.json
UNITS_MODE = "auto"       # steps|meters|auto (auto: walking=steps, query=meters)


def spoken_steps(mm):
    """Distances as calibrated steps -- body-scaled and directly executable
    (UTILITY-ROADMAP delivery invariant). Whole steps, always hedged; past
    ~20 steps a count stops being countable -> meters."""
    steps = (mm / 1000.0) / STRIDE_M
    if steps < 2:
        return "right there"
    if steps <= 20:
        return f"about {int(round(steps))} steps"
    return f"about {mm / 1000.0:.0f} meters"


def spoken_dist(mm, walking):
    if UNITS_MODE == "steps" or (UNITS_MODE == "auto" and walking):
        return spoken_steps(mm)
    m = mm / 1000.0
    return "about 1 meter" if m < 1.3 else f"about {m:.0f} meters"


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
        dw = use_dewarp and _cyl["maps"] is not None
        inp = (cv2.remap(frame, *_cyl["maps"], cv2.INTER_LINEAR)
               if dw else frame)
        r = model.track(inp, imgsz=IMGSZ, conf=CONF, persist=True,
                        tracker="bytetrack.yaml", verbose=False)[0]
        dets = []
        polys = r.masks.xy if r.masks is not None else [None] * len(r.boxes)
        for b, poly in zip(r.boxes, polys):
            name = names[int(b.cls)]
            tid = int(b.id) if b.id is not None else None
            xyxy = b.xyxy[0].tolist()
            poly_ok = poly is not None and len(poly) >= 3
            if dw:
                # map results back to RAW-fisheye coordinates: all geometry,
                # association and display stay on the raw frame
                if poly_ok:
                    poly = _cyl["fn"](poly).astype(np.float32)
                x0, y0, x1, y1 = xyxy
                corners = _cyl["fn"]([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
                xyxy = [float(corners[:, 0].min()), float(corners[:, 1].min()),
                        float(corners[:, 0].max()), float(corners[:, 1].max())]
            dets.append({"name": name, "conf": float(b.conf),
                         "xyxy": xyxy,
                         "tid": tid,
                         "poly": poly.astype(np.float32) if poly_ok else None,
                         "tier1": name in TIER1})
        with det_lock:
            det_latest = dets
            det_frame_id = fid


def main():
    global running, use_dewarp, phone_jpeg, STRIDE_M, UNITS_MODE, tap_event, drop_state
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cam", type=int, default=-1,
                    help="-1 = auto (USB re-enumeration moves indices)")
    ap.add_argument("--no-audio", action="store_true", help="start with audio off")
    ap.add_argument("--mode", default="plain", choices=["plain", "brevity"],
                    help="callout language (docs/CALLOUT-PROTOCOL.md)")
    ap.add_argument("--rate", type=int, default=240,
                    help="TTS words/min (blind users parse far faster than sighted)")
    ap.add_argument("--source", default="helmet", choices=["helmet", "pintest"],
                    help="helmet = flashed firmware via TCP (default); "
                         "pintest = tof_pin_test GRID: over serial")
    ap.add_argument("--host", default="192.168.1.227", help="helmet firmware IP")
    ap.add_argument("--tcp-port", type=int, default=3333)
    ap.add_argument("--serial", action="store_true",
                    help="FIELD MODE: read the helmet stream over USB serial "
                         "(--port) instead of WiFi TCP")
    ap.add_argument("--units", default="auto",
                    choices=["steps", "meters", "auto"],
                    help="spoken distances (auto: walking=steps, query=meters)")
    ap.add_argument("--calibrate-stride", action="store_true",
                    help="30-s console stride calibration, then exit")
    ap.add_argument("--serve", type=int, default=8123,
                    help="phone-viewer port (0 = off). Open http://<laptop-ip>:PORT")
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

    if args.calibrate_stride:
        d = float(input("distance walked (m)? "))
        n = int(input("steps taken? "))
        s = d / n
        if not 0.4 <= s <= 1.0:
            raise SystemExit(f"stride {s:.2f} m outside 0.4-1.0 -- remeasure")
        (ROOT / "camera" / "stride_cal.json").write_text(json.dumps(
            {"stride_m": round(s, 3), "steps_counted": n, "dist_m": d,
             "t": time.strftime("%Y-%m-%d %H:%M")}))
        print(f"stride {s:.2f} m saved")
        return
    UNITS_MODE = args.units
    try:
        STRIDE_M = json.loads((ROOT / "camera" / "stride_cal.json")
                              .read_text())["stride_m"]
        print(f"stride: {STRIDE_M:.2f} m (calibrated)")
    except (OSError, KeyError, ValueError):
        print(f"stride: {STRIDE_M:.2f} m (default -- run --calibrate-stride)")

    global SPEECH_RATE
    SPEECH_RATE = args.rate
    flightlog.start_session({"mode": args.mode, "rate": args.rate,
                             "source": args.source,
                             "serial": bool(args.serial)})

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K = cal["K"]
    D = cal["D"].reshape(4, 1)
    mx, my, cyl_fn = build_cyl(K, D)
    _cyl["maps"] = (mx, my)
    _cyl["fn"] = cyl_fn
    joint, cadex, eff = fo.load_extrinsics()
    use_joint = joint is not None
    ring = fo.zone_boundary_tans()
    P = ring.shape[2]

    if args.source == "helmet" and args.serial:
        threading.Thread(target=helmet_serial_reader, args=(args.port, args.baud),
                         daemon=True).start()
    elif args.source == "helmet":
        threading.Thread(target=helmet_reader, args=(args.host, args.tcp_port),
                         daemon=True).start()
    else:
        threading.Thread(target=fo.reader, args=(args.port, args.baud),
                         daemon=True).start()
    if args.serve:
        threading.Thread(target=phone_server, args=(args.serve,), daemon=True).start()
        print(f"phone viewer: http://<this-machine's-ip>:{args.serve}/")

    # IMU mount calibration (visualizer/imu_mount_cal.py) -- optional
    mount_cal = None
    mc_path = ROOT / "visualizer" / "imu_mount_cal.json"
    if mc_path.exists():
        mount_cal = np.array(json.loads(mc_path.read_text())["R_chip_to_helmet"], float)
        print("IMU mount calibration loaded")
    if args.cam < 0:
        # auto = find the helmet camera BY NAME ("HBV HD CAMERA"). Brightness
        # heuristics fail when the pod is lying lens-down (picked the laptop
        # webcam, 2026-08-17). DirectShow name order matches OpenCV indices.
        cam_idx = None
        try:
            from pygrabber.dshow_graph import FilterGraph
            names = FilterGraph().get_input_devices()
            print("cameras:", names)
            for i, n in enumerate(names):
                if "HBV" in n.upper():
                    cam_idx = i
                    break
        except Exception as e:
            print(f"name enumeration failed ({e}); falling back to index 1")
        if cam_idx is None:
            cam_idx = 1
        print(f"using camera {cam_idx} (helmet)")
        cap, _ = open_camera(cam_idx)
    else:
        cap, _ = open_camera(args.cam)
    if cap is None or not cap.isOpened():
        running = False
        raise SystemExit("no usable camera found")

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
    level_mode = False
    level_done = False
    level_last_say = 0.0
    rng_hist = {}          # key -> [(t, range_mm)] for 1 s median smoothing
    path_hist = []         # (t, near_path_mm) for the TTC estimate
    guide = None           # beacon target: {tid, name, az, yaw, seen, rng, muted}
    bcn = None             # Beacon instance, created on first 'g'
    voice_around = False   # voice "what's around" -> F9 on the next frame
    disagree_since = None  # ToF-near-with-no-CV-explanation persistence
    gated = False          # sterile-cockpit speech gate (head-turn)
    gate_below_since = None
    gate_entered = 0.0
    around_state = {"t": 0.0, "layer": 0, "items": []}
    cur_scene = {"dets": [], "alerts": []}   # live refs for query closures
    last_tap = 0.0
    dropped = False
    drop_n = 0
    next_drop_say = 0.0
    clr_ring = []          # last-5-frames hazard votes (3-of-5 persistence)
    clr_last_pattern = 0.0
    clr_off_said = False
    tunnel_on = False      # walkable-tunnel haptics (key n; TCP mode only)
    tunnel_last = 0.0

    # -- VLM describe (keys 'v' = ahead, 'h' = in my hand) -------------------
    # docs/VLM-BUILD-SPEC.md. Cloud NIM only (no local option on either
    # machine: GTX 1650 = 20-25 s, field laptop = Iris Xe). Pull-only,
    # query tier, honest spoken failures, single-flight.
    import vlm as vlm_mod
    import ocr as ocr_mod
    from collections import deque
    vlm_frames = deque(maxlen=10)      # recent frames for sharpest-of-N

    # -- voice commands (wake word "helmet"; "stop"/"quiet" ungated) ---------
    # docs/research-sources/voice-commands-2026-08-23.md. Half-duplex: the
    # recognizer drops mic frames while our own TTS speaks.
    import voice as voice_mod
    voice_mod.start(is_speaking=lambda: speaking)

    # -- door mode state ---------------------------------------------------
    door = {"model": None, "state": "idle",   # idle|scanning|choose|guiding
            "cands": [], "sel": None, "redetect_t": 0.0, "lock": threading.Lock()}
    find = {"target": None, "state": "idle",  # idle|scanning|guiding
            "sel": None, "reocr_t": 0.0, "lock": threading.Lock()}

    def _door_preload():
        try:
            from ultralytics import YOLO as _Y
            m = _Y(str(ROOT / "yolov8s-worldv2.pt"))
            m.set_classes(DOOR_CLASSES)
            m.predict(np.zeros((64, 64, 3), np.uint8), imgsz=416, verbose=False)
            door["model"] = m
            print("door scanner ready")
        except Exception as e:
            print(f"door scanner unavailable: {e}")
    threading.Thread(target=_door_preload, daemon=True).start()

    def _yaw_now():
        if imu_quat is None or time.monotonic() - imu_stamp > 1.0:
            return None
        w_, x_, y_, z_ = imu_quat
        Rq = quat_to_R(w_, x_, y_, z_)
        if mount_cal is not None:
            Rq = Rq @ mount_cal.T
        f_ = Rq @ np.array([0, 1, 0])
        return float(np.degrees(np.arctan2(-f_[0], f_[1])))

    def _wrap(a):
        return ((a + 180.0) % 360.0) - 180.0

    def _door_scan():
        """3.5 s scan: detect doors on the newest frames while the user pans,
        anchor each in WORLD bearing (az + yaw at grab), cluster, keep <=3."""
        hits = []            # (world_bearing_or_az, used_imu, range_mm, conf)
        t0 = time.monotonic()
        last_fid = -1
        while time.monotonic() - t0 < DOOR_SCAN_S:
            with fb_lock:
                fid, frame = frame_box["id"], frame_box["frame"]
            if frame is None or fid == last_fid:
                time.sleep(0.03)
                continue
            last_fid = fid
            yaw0 = _yaw_now()
            r = door["model"].predict(frame, imgsz=640, conf=DOOR_CONF,
                                      verbose=False)[0]
            for b in r.boxes:
                x0, y0, x1, y1 = b.xyxy[0].tolist()
                az = pixel_azimuth((x0 + x1) / 2, (y0 + y1) / 2)
                if az is None:
                    continue
                rng = float(np.clip(K[1, 1] * DOOR_HEIGHT_MM /
                                    max(20.0, y1 - y0), 800, 20000))
                wb = az + yaw0 if yaw0 is not None else az
                hits.append((wb, yaw0 is not None, rng, float(b.conf)))
        # cluster by bearing
        cands = []
        for wb, has_imu, rng, conf in sorted(hits, key=lambda h: -h[3]):
            for c in cands:
                if abs(_wrap(wb - c["wb"])) < DOOR_CLUSTER_DEG:
                    c["n"] += 1
                    break
            else:
                cands.append({"wb": wb, "imu": has_imu, "rng": rng,
                              "conf": conf, "n": 1})
        # order: most central to current heading first (destination bearing
        # unknown without the phone handoff), keep 3
        yawn = _yaw_now() or 0.0
        cands.sort(key=lambda c: abs(_wrap(c["wb"] - yawn)))
        cands = cands[:3]
        with door["lock"]:
            door["cands"] = cands
            door["state"] = "choose" if cands else "idle"
        if not cands:
            _say_q("no doors found, try panning and press d again")
            return
        parts = []
        for i, c in enumerate(cands):
            rel = _wrap(c["wb"] - yawn)
            hr = int(round(rel / 30.0)) % 12
            hr = 12 if hr == 0 else hr
            parts.append(f"door {i+1}, {hr} o'clock, "
                         f"{spoken_dist(c['rng'], walking=True)}")
        _say_q("; ".join(parts) + ". press a number to select")

    def _say_q(text):
        global speech_next
        with speech_lock:
            speech_next = (text, f"DOOR{time.monotonic()}", 0, "query",
                           time.monotonic())

    def _vlm_ask(question, hand):
        """One VLM launch path shared by keys v/h and Around-Me layer 3."""
        if vlm_mod.busy.is_set():
            _say_q("still working")
            return
        ctx = "; ".join(f"{d['name']} {d['range_mm']/1000:.1f}m"
                        for d in cur_scene["dets"] if d.get("range_mm"))[:200]
        _say_q("looking")
        threading.Thread(target=vlm_mod.describe,
                         args=(list(vlm_frames), question),
                         kwargs={"sensor_ctx": ctx, "hand_mode": hand,
                                 "speak": _say_q}, daemon=True).start()

    def around_me_trigger(now):
        """ONE responder for F9, voice "what's around", and the tap gesture.
        Repeat within AROUND_REPEAT_S peels a layer: labels -> ranges -> VLM."""
        st = around_state
        if now - st["t"] > AROUND_REPEAT_S:
            st["layer"] = 0
        st["t"] = now
        st["layer"] = st["layer"] % 3 + 1
        if st["layer"] == 3:
            _vlm_ask("Describe what is ahead.", False)
            return
        if st["layer"] == 1:
            best = {}
            for d in cur_scene["dets"]:
                if not d.get("range_mm"):
                    continue
                x0a, y0a, x1a, y1a = d["xyxy"]
                az = pixel_azimuth((x0a + x1a) / 2, (y0a + y1a) / 2)
                if az is None:
                    continue
                nm = (d["name"] if d["conf"] >= CONF_HEDGE
                      else f"maybe {d['name']}")
                sec = _sector(az)
                if sec not in best or d["range_mm"] < best[sec]["rng"]:
                    best[sec] = {"name": nm, "sector": sec, "az": az,
                                 "rng": d["range_mm"], "tid": d.get("tid")}
            for zn in cur_scene["alerts"]:
                az = zn.get("az")
                if az is None:
                    continue
                sec = _sector(az)
                if sec not in best:
                    best[sec] = {"name": "obstacle", "sector": sec, "az": az,
                                 "rng": zn["z"], "tid": None}
            order = {"front-left": 0, "front-center": 1, "front-right": 2}
            st["items"] = sorted(best.values(),
                                 key=lambda i: order[i["sector"]])
        else:
            # layer 2 re-answers THE SAME items, re-ranged if still tracked
            for it in st["items"]:
                for d in cur_scene["dets"]:
                    if (d.get("tid") is not None and d["tid"] == it["tid"]
                            and d.get("range_mm")):
                        it["rng"] = d["range_mm"]
        _say_q(_around_text(st["items"], st["layer"]))

    def _range_at_az(rel_az):
        """Median ToF range near a wearer-relative azimuth (head band rows).
        None past ToF reach -- callers must not invent distances."""
        zs = [zn["z"] for zn in cur_scene.get("zones", [])
              if zn["row"] < 3 and zn.get("az") is not None
              and abs(zn["az"] - rel_az) < 8.0]
        return float(np.median(zs)) if zs else None

    def _match_target(words, target):
        """Best fuzzy word match: casefold, split multi-word tokens,
        Levenshtein <= FIND_EDIT_MAX or substring, conf floor."""
        best = None
        for w in words:
            if w["conf"] < FIND_MIN_CONF:
                continue
            for tok in w["text"].casefold().split():
                if len(tok) < FIND_MIN_LEN:
                    continue
                if _lev(tok, target) <= FIND_EDIT_MAX or target in tok:
                    if best is None or w["conf"] > best["conf"]:
                        best = w
        return best

    def _find_scan(target):
        t0s = time.monotonic()
        hit = None
        while time.monotonic() - t0s < FIND_SCAN_S:
            with fb_lock:
                frm = frame_box["frame"]
            if frm is None:
                time.sleep(0.1)
                continue
            yaw0 = _yaw_now()          # AT GRAB TIME -- the round trip is
            words = ocr_mod.read(frm)  # seconds long (the #1 likely bug)
            if words is None:
                _say_q("no connection, find cancelled")
                with find["lock"]:
                    find["state"] = "idle"
                return
            w = _match_target(words, target)
            if w is not None:
                Hf, Wf = frm.shape[:2]
                az = pixel_azimuth(w["cx"] * Wf, w["cy"] * Hf)
                if az is not None:
                    hit = {"wb": az + yaw0 if yaw0 is not None else az,
                           "imu": yaw0 is not None, "conf": w["conf"],
                           "seen": time.monotonic(), "muted": False}
                    break
        if hit is None:
            _say_q(f"didn't find {target}, get closer or pan and try again")
            with find["lock"]:
                find["state"] = "idle"
            return
        yawn = _yaw_now() or 0.0
        rel = _wrap(hit["wb"] - yawn)
        hr = int(round(rel / 30.0)) % 12
        hr = 12 if hr == 0 else hr
        rngmm = _range_at_az(rel)
        phrase = f"found {target}, {hr} o'clock"
        if rngmm:
            phrase += f", {spoken_dist(rngmm, walking=True)}"
        with find["lock"]:
            find["sel"] = hit
            find["state"] = "guiding"
            find["reocr_t"] = 0.0
        bcn.update(rel)
        bcn.start()
        _say_q(phrase + ". guiding, say stop when done")

    def _find_reocr():
        with fb_lock:
            frm = frame_box["frame"]
        if frm is None or find["sel"] is None:
            return
        yaw0 = _yaw_now()
        words = ocr_mod.read(frm)
        if not words:
            return
        w = _match_target(words, find["target"])
        if w is None:
            return
        Hf, Wf = frm.shape[:2]
        az = pixel_azimuth(w["cx"] * Wf, w["cy"] * Hf)
        if az is None:
            return
        wb = az + yaw0 if yaw0 is not None else az
        if abs(_wrap(wb - find["sel"]["wb"])) < 30.0:
            with find["lock"]:
                find["sel"]["wb"] = wb
                find["sel"]["seen"] = time.monotonic()

    def _read_that():
        words = ocr_mod.read(vlm_mod.sharpest(list(vlm_frames)))
        if words is None:
            _say_q("reading failed, no connection")
            return
        if not words:
            _say_q("no text visible")
            return
        # top block = biggest x most central; speak its whole line
        def score(w):
            cen = 1.0 - min(1.0, abs(w["cx"] - 0.5) + abs(w["cy"] - 0.5))
            return w["w"] * w["h"] * (0.3 + cen)
        best = max(words, key=score)
        line = [w for w in words
                if abs(w["cy"] - best["cy"]) < max(best["h"], 0.03)]
        line.sort(key=lambda w: w["cx"])
        _say_q(" ".join(w["text"] for w in line)[:140])

    def _cancel_find(say=True):
        if find["state"] != "idle":
            if bcn:
                bcn.stop()
            with find["lock"]:
                find["state"] = "idle"
                find["sel"] = None
            if say:
                _say_q("find off")
            return True
        return False

    def start_find(word):
        nonlocal bcn, guide
        if door["state"] != "idle":
            with door["lock"]:
                door["state"] = "idle"
                door["sel"] = None
        if guide is not None:
            guide = None
        if bcn is None:
            bcn = Beacon()
        else:
            bcn.stop()
        with find["lock"]:
            find["target"] = word
            find["state"] = "scanning"
            find["sel"] = None
        _say_q(f"searching for {word}, pan slowly")
        threading.Thread(target=_find_scan, args=(word,), daemon=True).start()

    def _send_tunnel(l, r):
        try:
            import urllib.request
            urllib.request.urlopen(
                f"http://{args.host}/api/tunnel?l={l}&r={r}&ttl=500",
                timeout=1).read()
        except OSError:
            pass

    def _duck_pattern():
        """Fire the firmware all-motor double pulse (GET /api/pattern?p=duck).
        Silent no-op on failure or in --serial field mode."""
        try:
            import urllib.request
            urllib.request.urlopen(
                f"http://{args.host}/api/pattern?p=duck", timeout=2).read()
        except OSError:
            pass
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
        vlm_frames.append(frame)       # ring for sharpest-of-N (keys v/h)
        flightlog.add_frame(frame)
        flightlog.heartbeat()

        ex = joint if (use_joint and joint) else cadex
        now = time.monotonic()
        # helmet->world attitude for the clearance watch (None = feature off)
        Rw_att = None
        if imu_quat is not None and now - imu_stamp < 1.0 and mount_cal is not None:
            _w, _x, _y, _z = imu_quat
            Rw_att = quat_to_R(_w, _x, _y, _z) @ mount_cal.T
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
            flightlog.add_tof(S, g)
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
                zn_rec = {"poly": poly.astype(np.int32),
                          "cen": poly.mean(0), "z": z, "S": S, "row": rr}
                if Rw_att is not None:
                    # gravity-frame height: cam -> helmet (fixed R_CH) ->
                    # world (live IMU). THE flagship trick: height-classify
                    # per-sample with the simultaneous attitude, so gait
                    # pitch sweeps integrate instead of corrupting.
                    p_cam = allp[i * P:(i + 1) * P].mean(0)
                    p_w = Rw_att @ (R_CH @ p_cam)
                    zn_rec["h"] = float(p_w[2])
                    zn_rec["d_fwd"] = float(np.hypot(p_w[0], p_w[1]))
                zones.append(zn_rec)

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
        cur_scene["dets"] = dets

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
        if not alert_zones:
            disagree_since = None
        for zn in alert_zones:
            cv2.polylines(view, [zn["poly"]], True, (0, 0, 255), 3, cv2.LINE_AA)
        if alert_zones:
            near = min(zn["z"] for zn in alert_zones)
            ranged_any = any(d.get("range_mm") for d in dets)
            if near < 1000 and not ranged_any:
                if disagree_since is None:
                    disagree_since = now
                elif now - disagree_since > 1.0:
                    flightlog.disagreement()
            else:
                disagree_since = None
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
            if audio_on:
                flightlog.audio_on("F8")
            else:
                flightlog.override("F8")
        f8_was_down = f8_now

        # ── TIER ENGINE v2 (docs/MASTER-SYNTHESIS-2026-08-16.md) ─────────────
        # Silence is the default. Autonomous speech = hazards + commands only;
        # F9 answers "what's around me" on demand. Proximity rides the ticker.
        global speech_next
        # azimuth per zone, cached
        for zn in zones:
            if "az" not in zn:
                zn["az"] = pixel_azimuth(*zn["cen"])
        cur_scene["alerts"] = [zn for zn in alert_zones
                               if zn.get("az") is not None]
        cur_scene["zones"] = zones
        # CANE FILTER: bottom row is the cane's territory (and, worn at 22.5°
        # down, mostly the floor itself) -- rendered, never spoken/ticked.
        # Head/torso/waist band = rows 0-2.
        upper = [zn for zn in zones if zn["row"] < 3 and zn["az"] is not None]
        # range-adaptive cone: each zone judged against the half-angle its OWN
        # range implies (near zone -> wide cone, far zone -> narrow)
        path = [zn for zn in upper
                if abs(zn["az"]) < min(np.degrees(np.arctan2(BODY_HALF_W_MM,
                                                             max(zn["z"], 1.0))),
                                       PATH_CONE_MAX_DEG)]
        near_path = min((zn["z"] for zn in path), default=None)
        # TTC for the ticker: closing rate from ~1 s of near_path history
        now_t = now
        if near_path is not None:
            path_hist.append((now_t, near_path))
        path_hist[:] = [(t, v) for t, v in path_hist if now_t - t < 1.2]
        ttc = None
        if near_path is not None and len(path_hist) >= 4:
            (t0h, v0h), (t1h, v1h) = path_hist[0], path_hist[-1]
            closing = (v0h - v1h) / 1000.0 / max(0.2, t1h - t0h)   # m/s toward
            if closing > 0.05:
                ttc = (near_path / 1000.0) / closing
        near_az = 0.0
        if near_path is not None and path:
            near_az = min(path, key=lambda zn: zn["z"]).get("az") or 0.0
        tick_state[0] = ((ttc, near_path, near_az)
                         if (audio_on and not dropped) else (None, None, 0.0))

        # drop alarm (firmware DROP: lines): announce at directive tier,
        # repeat every 10 s until picked up; hazard callouts are garbage
        # while the helmet is on the floor -- suppressed via `dropped`.
        if drop_state == 1:
            if not dropped:
                dropped = True
                drop_n = 0
                next_drop_say = now
            if now >= next_drop_say:
                drop_n += 1
                with speech_lock:
                    speech_next = ("helmet dropped", f"DROP{drop_n}", 0,
                                   "directive", now)
                next_drop_say = now + 10.0
        elif drop_state == 0 and dropped:
            dropped = False
            drop_state = None
            with speech_lock:
                speech_next = ("helmet picked up", "DROPCLR", 0, "query", now)

        # sterile-cockpit gate: CAUTION speech suppressed during fast head
        # turns (stale azimuth words + collides with deliberate scanning).
        # Directive, sensors-lost, query, ticker: NEVER gated.
        imu_fresh = imu_quat is not None and now - imu_stamp < 0.3
        rate_now = abs(yaw_rate) if imu_fresh else 0.0
        if not gated and rate_now > GATE_ON_DPS:
            gated = True
            gate_entered = now
            gate_below_since = None
            flightlog.event("gate_enter", yaw_rate=round(rate_now, 1))
        elif gated:
            if rate_now < GATE_OFF_DPS:
                if gate_below_since is None:
                    gate_below_since = now
                elif now - gate_below_since > GATE_OFF_DWELL_S:
                    gated = False
                    flightlog.event("gate_exit",
                                    dur_s=round(now - gate_entered, 2))
            else:
                gate_below_since = None

        if audio_on and not level_mode and not dropped:
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
                    if not gated:
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
                            if gated:
                                flightlog.event("gated", text=text,
                                                yaw_rate=round(abs(yaw_rate), 1),
                                                range_mm=round(rng))
                            else:
                                with speech_lock:
                                    speech_next = (text,
                                                   f"{stem}:{direction_word(az)}",
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
        if (f9_now and not f9_was_down) or voice_around:
            voice_around = False
            around_me_trigger(now)
        f9_was_down = f9_now

        # ── BEACON GUIDANCE (key 'g'): Soundscape 4-region beacon ────────────
        # While the target is in frame its azimuth comes straight from the
        # detector (already wearer-relative). When it leaves frame, the IMU
        # yaw delta keeps an estimate alive (head-as-gimbal) and the beacon
        # DIMS -- Soundscape's no-heading behavior: dim, never stop.
        cur_yaw = None
        if imu_quat is not None and now - imu_stamp < 1.0:
            w_, x_, y_, z_ = imu_quat
            Rg = quat_to_R(w_, x_, y_, z_)
            if mount_cal is not None:
                Rg = Rg @ mount_cal.T
            fwd_g = Rg @ np.array([0, 1, 0])
            cur_yaw = float(np.degrees(np.arctan2(-fwd_g[0], fwd_g[1])))

        def _angdiff(a):
            return ((a + 180.0) % 360.0) - 180.0

        if guide is not None and bcn is not None:
            tgt = next((d for d in dets if d["tid"] is not None
                        and d["tid"] == guide["tid"]), None)
            if tgt is None and guide["tid"] is None:
                same = [d for d in dets if d["name"] == guide["name"]]
                tgt = same[0] if same else None
            if tgt is not None:
                x0g, y0g, x1g, y1g = tgt["xyxy"]
                az_t = pixel_azimuth((x0g + x1g) / 2, (y0g + y1g) / 2)
                if az_t is not None:
                    guide.update(az=az_t, yaw=cur_yaw, seen=now)
                    if tgt["range_mm"]:
                        guide["rng"] = tgt["range_mm"]
                cv2.rectangle(view, (int(x0g), int(y0g)), (int(x1g), int(y1g)),
                              (255, 0, 255), 3)
            lost = now - guide["seen"]
            if lost > GUIDE_LOST_S:
                bcn.stop()
                with speech_lock:
                    speech_next = ("guide lost", f"GL{now}", 0, "query", now)
                guide = None
            elif not audio_on or level_mode:
                if not guide.get("muted"):
                    bcn.stop()
                    guide["muted"] = True
            else:
                if guide.get("muted"):
                    bcn.start()
                    guide["muted"] = False
                rel = guide["az"]
                if lost > 0.5 and cur_yaw is not None and guide["yaw"] is not None:
                    # world-fixed target: rel = az0 + (yaw0 - yaw_now).
                    # SIGN NOTE: assumes IMU yaw is + in the same sense as
                    # pixel azimuth (+ = wearer's right). Verify live; if the
                    # beacon runs AWAY from a lost target, flip this sign.
                    rel = guide["az"] + _angdiff(guide["yaw"] - cur_yaw)
                if (guide.get("rng") and guide["rng"] < GUIDE_ARRIVE_MM
                        and lost < 0.5):
                    bcn.stop(arrived=True)      # Route_End outro
                    with speech_lock:
                        speech_next = (f"arrived, {guide['name']}", f"GA{now}",
                                       0, "query", now)
                    guide = None
                else:
                    bcn.update(rel, dim=lost > 0.5, duck=speaking)
        if guide is not None:
            cv2.putText(view, f"GUIDING {guide['name']}"
                        + ("  (est)" if now - guide["seen"] > 0.5 else ""),
                        (12, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (255, 0, 255), 2, cv2.LINE_AA)

        # ── DOOR MODE state machine (key 'd', then 1..3) ─────────────────────
        def _door_redetect():
            with fb_lock:
                frm = frame_box["frame"]
            if frm is None or door["sel"] is None:
                return
            y0w = _yaw_now()
            r = door["model"].predict(frm, imgsz=640, conf=DOOR_CONF,
                                      verbose=False)[0]
            best, bd = None, 25.0
            for b in r.boxes:
                x0d, y0d, x1d, y1d = b.xyxy[0].tolist()
                azd = pixel_azimuth((x0d + x1d) / 2, (y0d + y1d) / 2)
                if azd is None:
                    continue
                wbd = azd + y0w if y0w is not None else azd
                dv = abs(_wrap(wbd - door["sel"]["wb"]))
                if dv < bd:
                    bd = dv
                    best = (wbd, float(np.clip(
                        K[1, 1] * DOOR_HEIGHT_MM / max(20.0, y1d - y0d),
                        500, 20000)))
            if best is not None:
                with door["lock"]:
                    door["sel"]["wb"], door["sel"]["rng"] = best
                    door["sel"]["seen"] = time.monotonic()

        if door["state"] == "guiding" and door["sel"] is not None \
                and bcn is not None:
            c = door["sel"]
            if door["model"] is not None and now - door["redetect_t"] > DOOR_REDETECT_S:
                door["redetect_t"] = now
                threading.Thread(target=_door_redetect, daemon=True).start()
            if not audio_on or level_mode:
                if not c.get("muted"):
                    bcn.stop()
                    c["muted"] = True
            else:
                if c.get("muted"):
                    bcn.start()
                    c["muted"] = False
                rel = (_wrap(c["wb"] - cur_yaw) if (cur_yaw is not None and c["imu"])
                       else 0.0)
                stale = now - c.get("seen", 0) > 4.0
                if c["rng"] < 1200 and abs(rel) < 25 and not stale:
                    bcn.stop(arrived=True)
                    _say_q("door reached")
                    with door["lock"]:
                        door["state"] = "idle"
                        door["sel"] = None
                else:
                    bcn.update(rel, dim=stale, duck=speaking)
        if door["state"] != "idle":
            lbl = {"scanning": "DOOR SCAN...", "choose":
                   f"DOORS: {len(door['cands'])} found - press 1..{len(door['cands'])}",
                   "guiding": "GUIDING door"}[door["state"]]
            cv2.putText(view, lbl, (12, 162), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (0, 200, 255), 2, cv2.LINE_AA)

        # ── FIND MODE guiding (voice "find <word>" / key f) ──────────────────
        if find["state"] == "guiding" and find["sel"] is not None \
                and bcn is not None:
            c = find["sel"]
            if now - find["reocr_t"] > FIND_REOCR_S and not ocr_mod.busy.is_set():
                find["reocr_t"] = now
                threading.Thread(target=_find_reocr, daemon=True).start()
            if not audio_on or level_mode:
                if not c.get("muted"):
                    bcn.stop()
                    c["muted"] = True
            else:
                if c.get("muted"):
                    bcn.start()
                    c["muted"] = False
                rel = (_wrap(c["wb"] - cur_yaw)
                       if (cur_yaw is not None and c["imu"]) else 0.0)
                stale = now - c.get("seen", 0) > 5.0
                rngmm = _range_at_az(rel)
                if rngmm and rngmm < FIND_ARRIVE_MM and abs(rel) < 25 \
                        and not stale:
                    bcn.stop(arrived=True)
                    _say_q(f"{find['target']} reached")
                    with find["lock"]:
                        find["state"] = "idle"
                        find["sel"] = None
                else:
                    bcn.update(rel, dim=stale, duck=speaking)
        if find["state"] != "idle":
            cv2.putText(view, f"FIND '{find['target']}' "
                        + ("SCANNING..." if find["state"] == "scanning"
                           else "GUIDING"),
                        (12, 188), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (255, 180, 0), 2, cv2.LINE_AA)

        # ── CLEARANCE WATCH: gravity-frame head clearance (FLAGSHIP) ─────────
        # Warn when a persistent overhead return sits within HEAD_MARGIN_MM of
        # the pod plane inside the path cone. World-frame, IMU-compensated --
        # the novelty claim (Munoz 2025 discarded tilted frames; we use them).
        # No IMU/mount-cal -> feature OFF and says so ONCE (a sensor-frame
        # top-row rule is the fatal flaw per implementation-guide sec 2).
        if Rw_att is not None:
            haz = []
            for zn in zones:
                if "h" not in zn or zn.get("az") is None:
                    continue
                half = min(np.degrees(np.arctan2(BODY_HALF_W_MM,
                                                 max(zn["d_fwd"], 1.0))),
                           PATH_CONE_MAX_DEG)
                if abs(zn["az"]) > half:
                    continue
                if -100.0 < zn["h"] < HEAD_MARGIN_MM and zn["d_fwd"] < 2500.0:
                    haz.append(zn)
            clr_ring.append(bool(haz))
            if len(clr_ring) > 5:
                clr_ring.pop(0)
            nearest = min((zn["d_fwd"] for zn in haz), default=None)
            if sum(clr_ring) >= 3 and nearest is not None \
                    and audio_on and not dropped and not level_mode:
                if nearest < 1200.0:
                    with speech_lock:
                        speech_next = ("low clearance, duck", "DUCK",
                                       nearest, "directive", now)
                    if not args.serial and now - clr_last_pattern > 2.0:
                        clr_last_pattern = now
                        threading.Thread(target=_duck_pattern,
                                         daemon=True).start()
                elif nearest < 2000.0 and not gated:
                    with speech_lock:
                        speech_next = ("low branch ahead", "CLRWARN",
                                       nearest, "caution", now)
            for zn in haz:
                cv2.polylines(view, [zn["poly"]], True, (255, 0, 255), 3,
                              cv2.LINE_AA)
            if haz and nearest is not None:
                hmin = min(zn["h"] for zn in haz)
                cv2.putText(view, f"CLR {nearest/1000:.1f}m {hmin/10:+.0f}cm",
                            (12, 214), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                            (255, 0, 255), 2, cv2.LINE_AA)
        elif not clr_off_said and imu_quat is not None:
            clr_off_said = True     # IMU streams but no mount cal -> honest
            if mount_cal is None:
                _say_q("clearance watch off, no attitude calibration")

        # ── WALKABLE TUNNEL (key n): motors ONLY near the corridor walls ─────
        # .lumen's error-correction pattern -- silence when centered
        # (PLAN-walkable-tunnel; firmware /api/tunnel max-blend, TTL-guarded).
        if tunnel_on and not args.serial and now - tunnel_last > TUNNEL_SEND_S:
            tunnel_last = now
            def _wall(lo, hi):
                zs = [zn["z"] * np.sin(np.radians(abs(zn["az"])))
                      for zn in upper
                      if lo <= zn["az"] <= hi and zn["z"] < 3000]
                return min(zs) if zs else None
            lat_l = _wall(-60.0, -10.0)
            lat_r = _wall(10.0, 60.0)
            def _duty(lat):
                if lat is None or lat > TUNNEL_NEAR_MM:
                    return 0
                x = max(0.0, min(1.0, (TUNNEL_NEAR_MM - lat)
                                 / (TUNNEL_NEAR_MM - TUNNEL_HALF_MM)))
                return int(90 + 110 * x)
            dl, dr = _duty(lat_l), _duty(lat_r)
            if (dl or dr) and audio_on and not dropped:
                threading.Thread(target=_send_tunnel, args=(dl, dr),
                                 daemon=True).start()
        if tunnel_on:
            cv2.putText(view, "TUNNEL", (12, 240), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (0, 255, 120), 2, cv2.LINE_AA)

        # ── LEVELING MODE: voice-guided ball-mount alignment (key 'l') ───────
        # The pod hangs on a ball camera mount; every re-clamp needs squaring.
        # A blind user can't watch a bubble, so the device coaches: "tilt up 5"
        # ... "level, lock it". Hazard speech + ticker pause while active.
        if level_mode and imu_quat is not None and now - imu_stamp < 1.0 \
                and mount_cal is not None:
            w_, x_, y_, z_ = imu_quat
            Rw_ = quat_to_R(w_, x_, y_, z_) @ mount_cal.T
            fwd_ = Rw_ @ np.array([0, 1, 0])
            rgt_ = Rw_ @ np.array([1, 0, 0])
            p_ = np.degrees(np.arcsin(np.clip(-fwd_[2], -1, 1)))   # + = nose down
            r_ = np.degrees(np.arcsin(np.clip(-rgt_[2], -1, 1)))   # + = right down
            tick_state[0] = (None, None)   # ticker silent during leveling
            if now - level_last_say > 1.5:
                level_last_say = now
                if abs(p_) < 1.0 and abs(r_) < 1.0:
                    if not level_done:
                        level_done = True
                        msg = "level, lock it"
                    else:
                        msg = None
                        level_mode = False        # auto-exit once confirmed
                else:
                    level_done = False
                    if abs(p_) >= abs(r_):
                        msg = f"tilt {'up' if p_ > 0 else 'down'} {abs(round(p_))}"
                    else:
                        msg = f"tilt {'left' if r_ > 0 else 'right'} {abs(round(r_))}"
                if msg:
                    with speech_lock:
                        speech_next = (msg, f"LVL{now}", 0, "query", now)
            cv2.putText(view, f"LEVELING  pitch {p_:+5.1f}  roll {r_:+5.1f}",
                        (12, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (60, 200, 255), 2, cv2.LINE_AA)

        # ── IMU HUD: artificial horizon + attitude readout ───────────────────
        # Camera boresight is pitched 22.5° down when the helmet is level, so
        # the horizon sits ~22.5° ABOVE image centre at rest and moves with
        # head pitch; the line banks with roll. Small-angle fisheye mapping
        # (y ≈ fy·θ) is plenty for a HUD.
        if imu_quat is not None and now - imu_stamp < 1.0:
            w_, x_, y_, z_ = imu_quat
            if mount_cal is not None:
                Rw = quat_to_R(w_, x_, y_, z_) @ mount_cal.T   # helmet -> world
                fwd = Rw @ np.array([0, 1, 0])
                rgt = Rw @ np.array([1, 0, 0])
                pitch = np.degrees(np.arcsin(np.clip(-fwd[2], -1, 1)))
                roll = np.degrees(np.arcsin(np.clip(-rgt[2], -1, 1)))
                yaw = np.degrees(np.arctan2(-fwd[0], fwd[1]))
                cam_pitch = pitch + 22.5          # boresight vs horizon
                cy_off = int(K[1, 1] * np.deg2rad(cam_pitch))
                cx0, cy0 = int(K[0, 2]), int(K[1, 2]) - cy_off
                th = np.deg2rad(roll)
                dx, dy = int(400 * np.cos(th)), int(400 * np.sin(th))
                cv2.line(view, (cx0 - dx, cy0 - dy), (cx0 + dx, cy0 + dy),
                         (80, 255, 160), 2, cv2.LINE_AA)
                for s_ in (-1, 1):                 # wing ticks
                    cv2.line(view, (cx0 + s_ * dx, cy0 + s_ * dy),
                             (cx0 + s_ * dx, cy0 + s_ * dy + 12),
                             (80, 255, 160), 2, cv2.LINE_AA)
                cv2.putText(view, f"pitch {pitch:+5.1f}  roll {roll:+5.1f}  "
                            f"yaw {yaw:+6.1f}", (12, 84),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 255, 160), 1,
                            cv2.LINE_AA)
                draw_attitude_inset(view, Rw, yaw)
            else:
                # no mount cal yet: show the chip frame raw so rotation is at
                # least visible; axes will look wrong until the cal is run
                Rw = quat_to_R(w_, x_, y_, z_)
                draw_attitude_inset(view, Rw, 0.0)
                cv2.putText(view, "IMU live (uncalibrated -- run "
                            "visualizer/imu_mount_cal.py)", (12, 84),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 255), 1,
                            cv2.LINE_AA)

        mode = "JOINT" if (use_joint and joint) else "CAD"
        gflag = "  GATED" if gated else ""
        voice = "BREVITY" if brevity else "plain"
        cv2.putText(view, f"CV fusion  [{mode}]{gflag}  det {'on' if show_det else 'OFF'}"
                    f"{'/dewarp' if use_dewarp else '/raw'}  "
                    f"audio {'on' if audio_on else 'OFF'} ({voice})  zones {len(zones)}",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (240, 240, 240), 2,
                    cv2.LINE_AA)

        phone_status.update(
            audio=audio_on, gated=gated, dropped=dropped,
            mode=("door " + door["state"] if door["state"] != "idle" else
                  "find " + find["state"] if find["state"] != "idle" else
                  "guiding" if guide is not None else
                  "tunnel" if tunnel_on else "idle"))
        if args.serve:
            ok_j, jb = cv2.imencode(".jpg", view,
                                    [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok_j:
                with phone_lock:
                    phone_jpeg = jb.tobytes()

        cv2.imshow("CV fusion", view)
        k = cv2.waitKey(1) & 0xFF

        # -- voice command -> same dispatch as the keys ----------------------
        try:
            vc = voice_mod.commands.get_nowait()
        except Exception:
            vc = None
        if vc:
            if vc == "describe":
                k = ord("v")
            elif vc == "hand":
                k = ord("h")
            elif vc == "doors":
                k = ord("d") if door["state"] == "idle" else k
            elif vc in ("sel1", "sel2", "sel3"):
                k = ord("1") + int(vc[-1]) - 1
            elif vc == "guide":
                k = ord("g")
            elif vc == "stop":
                if _cancel_find():
                    pass
                elif door["state"] != "idle":
                    k = ord("d")               # cancels door mode
                elif guide is not None:
                    k = ord("g")               # cancels object guide
            elif vc == "quiet":
                audio_on = False
                flightlog.override("voice")
            elif vc == "audio_on":
                audio_on = True
                flightlog.audio_on("voice")
                _say_q("audio on")
            elif vc == "wrong":
                flightlog.explicit_fp()
                _say_q("noted")
            elif vc == "flag":
                flightlog.trigger_clip("manual")
                _say_q("flagged")
            elif vc == "around":
                voice_around = True
            elif vc.startswith("find:"):
                start_find(vc[5:])
            elif vc == "read":
                _say_q("reading")
                threading.Thread(target=_read_that, daemon=True).start()

        # tap gesture (firmware TAP: lines). Double-tap = describe -- the
        # zero-hands query; single taps ignored (bump-prone). 1 s debounce,
        # 0.5 s staleness so a queued tap can't fire late.
        te = tap_event
        if te is not None:
            tap_event = None
            tcount, t_tap = te
            if (tcount == 2 and now - t_tap < 0.5
                    and now - last_tap > 1.0):
                last_tap = now
                k = ord("v")
        if k == ord("q"):
            break
        elif k == ord("y"):
            show_det = not show_det
        elif k == ord("a"):
            audio_on = not audio_on
        elif k == ord("b"):
            brevity = not brevity
        elif k == ord("l"):
            level_mode = not level_mode
            level_done = False
        elif k == ord("w"):
            use_dewarp = not use_dewarp
        elif k in (ord("v"), ord("h")):
            _vlm_ask("What am I holding?" if k == ord("h")
                     else "Describe what is ahead.", k == ord("h"))
        elif k == ord("f"):
            if find["state"] != "idle":
                _cancel_find()
            else:
                def _ask_word():
                    wd = input("find word: ").strip().casefold()
                    if wd:
                        start_find(wd)
                threading.Thread(target=_ask_word, daemon=True).start()
        elif k == ord("r"):
            _say_q("reading")
            threading.Thread(target=_read_that, daemon=True).start()
        elif k == ord("n"):
            tunnel_on = not tunnel_on
            _say_q(f"tunnel {'on' if tunnel_on else 'off'}")
        elif k == ord("u"):
            UNITS_MODE = {"auto": "steps", "steps": "meters",
                          "meters": "auto"}[UNITS_MODE]
            _say_q(f"units {UNITS_MODE}")
        elif k == ord("x"):
            flightlog.explicit_fp()
            _say_q("noted")
        elif k == ord("t"):
            show_text = not show_text
        elif k == ord("m") and joint is not None:
            use_joint = not use_joint
        elif k == ord("d"):
            if door["state"] in ("choose", "guiding"):
                if bcn:
                    bcn.stop()
                with door["lock"]:
                    door["state"] = "idle"
                    door["sel"] = None
                _say_q("door mode off")
            elif door["model"] is None:
                _say_q("door scanner still loading, try again in a moment")
            elif door["state"] == "idle":
                if guide is not None:          # object guide yields to door mode
                    if bcn:
                        bcn.stop()
                    guide = None
                with door["lock"]:
                    door["state"] = "scanning"
                _say_q("scanning for doors, pan slowly")
                threading.Thread(target=_door_scan, daemon=True).start()
        elif door["state"] == "choose" and k in (ord("1"), ord("2"), ord("3")):
            i = k - ord("1")
            if i < len(door["cands"]):
                with door["lock"]:
                    door["sel"] = dict(door["cands"][i], seen=now, muted=False)
                    door["state"] = "guiding"
                    door["redetect_t"] = 0.0
                if bcn is None:
                    bcn = Beacon()
                rel0 = (_wrap(door["sel"]["wb"] - cur_yaw)
                        if (cur_yaw is not None and door["sel"]["imu"]) else 0.0)
                bcn.update(rel0)
                bcn.start()
                _say_q(f"guiding to door {i+1}")
        elif k == ord("g"):
            if door["state"] != "idle":        # door mode yields to object guide
                if bcn:
                    bcn.stop()
                with door["lock"]:
                    door["state"] = "idle"
                    door["sel"] = None
            if guide is not None:
                if bcn:
                    bcn.stop()
                guide = None
                with speech_lock:
                    speech_next = ("guide off", f"GO{now}", 0, "query", now)
            else:
                # lock the nearest ranged detection; fall back to any det
                cands = ([d for d in dets if d["range_mm"]]
                         or [d for d in dets if d["tid"] is not None] or dets)
                locked = None
                if cands:
                    d = min(cands, key=lambda d: d["range_mm"] or 1e9)
                    x0g, y0g, x1g, y1g = d["xyxy"]
                    azg = pixel_azimuth((x0g + x1g) / 2, (y0g + y1g) / 2)
                    if azg is not None:
                        guide = {"tid": d["tid"], "name": d["name"], "az": azg,
                                 "yaw": cur_yaw, "seen": now,
                                 "rng": d["range_mm"], "muted": False}
                        if bcn is None:
                            bcn = Beacon()
                        bcn.update(azg)
                        bcn.start()
                        locked = d["name"]
                with speech_lock:
                    speech_next = ((f"guiding to {locked}" if locked
                                    else "nothing to guide to"),
                                   f"GS{now}", 0, "query", now)
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
