"""
Combined single-view helmet ToF visualiser -- BOTH sensors in ONE 3D scene,
each at its real helmet mount angle.

Clean-data pipeline (kills the "noisy bumps"):
  * drops zones the sensor itself flags low-confidence: STATUS not in {5,6,9}
  * drops high-noise zones: per-zone SIGMA (mm std-dev) above --sigma-max
  * temporal EMA smoothing (--ema) on what survives
The firmware streams SIGMA:/STATUS: alongside the bottom DATA: frame; the top
(DATAT:) has distance only, so it falls back to the 4000=invalid sentinel.

Spatial grounding: faint FoV frustums, head sphere + nose line, floor plane.
Readability: connected surface-net, hot->cool colormap, FPS + nearest L/R title.

Usage (WiFi TCP):
    python visualizer_dual.py --host 192.168.1.228
Knobs:
    --ema 0.3        smoothing (lower = smoother/laggier)
    --sigma-max 20   drop zones noisier than this (mm)
"""
import argparse
import socket
import sys
import time

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

FOV = 45.0
INVALID = 4000
SUPPORTED = (64, 16)
GOOD_STATUS = (5, 6, 9)   # ST UM3109: 5=valid, 6=wrap-OK, 9=valid-low-signal

PITCH = {"bottom": -30.0, "top": 5.0}      # degrees, + = tilt up
Z_OFFSET = {"bottom": 0.0, "top": 250.0}   # mm vertical stack


# ---------------------------------------------------------------- geometry ---
def zone_dirs(total):
    side = int(round(np.sqrt(total)))
    apz = np.radians(FOV / side)
    d = np.zeros((total, 3))
    c = (side - 1) / 2.0
    for r in range(side):
        for cc in range(side):
            h = (cc - c) * apz
            v = (r - c) * apz
            d[r * side + cc] = (np.sin(h), -np.sin(v), np.cos(h) * np.cos(v))
    return d


def rot_x(deg):
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def to_gl(p, R, zoff):
    g = np.column_stack([p[:, 0], p[:, 2], p[:, 1]]).astype(np.float64)
    g = g @ R.T
    g[:, 2] += zoff
    return g


def ramp(t):
    t = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
    c0 = np.array([1.0, 0.25, 0.18]); c1 = np.array([0.95, 0.85, 0.20]); c2 = np.array([0.20, 0.55, 1.0])
    out = np.empty((len(t), 3))
    lo = t < 0.5
    out[lo] = c0 + (c1 - c0) * (t[lo] / 0.5)[:, None]
    hi = ~lo
    out[hi] = c1 + (c2 - c1) * ((t[hi] - 0.5) / 0.5)[:, None]
    return out


def frustum_segments(R, zoff, depth, half_deg):
    t = np.tan(np.radians(half_deg))
    cdir = np.array([[t, t, 1], [t, -t, 1], [-t, -t, 1], [-t, t, 1]], dtype=float)
    cdir /= np.linalg.norm(cdir, axis=1)[:, None]
    pts = to_gl(np.vstack([np.zeros((1, 3)), cdir * depth]), R, zoff)
    apex, cs = pts[0], pts[1:]
    segs = []
    for i in range(4):
        segs += [apex, cs[i]]
        segs += [cs[i], cs[(i + 1) % 4]]
    return np.array(segs)


def _nums(body):
    try:
        vals = [int(v) for v in body.split(",")]
    except ValueError:
        return None
    return np.asarray(vals, dtype=float) if len(vals) in SUPPORTED else None


def parse(line):
    if line.startswith("DATAT:"):  a = _nums(line[6:]);  return ("DATAT", a) if a is not None else None
    if line.startswith("DATA:"):   a = _nums(line[5:]);  return ("DATA", a) if a is not None else None
    if line.startswith("STATUS:"): a = _nums(line[7:]);  return ("STATUS", a) if a is not None else None
    if line.startswith("SIGMA:"):  a = _nums(line[6:]);  return ("SIGMA", a) if a is not None else None
    if line.startswith("Q:"):
        # Q:w,x,y,z[,status,headacc_rad] -- extra fields (mag-fusion quality) are
        # optional; take the first 4 as the quaternion.
        try:
            q = [float(v) for v in line[2:].split(",")]
        except ValueError:
            return None
        return ("Q", np.asarray(q[:4], dtype=float)) if len(q) >= 4 else None
    return None


# ------------------------------------------------------------------- cloud ---
class Cloud:
    def __init__(self, view, tag, max_mm, ema, sigma_max):
        self.tag = tag
        self.max_mm = max_mm
        self.ema = ema
        self.sigma_max = sigma_max
        self.n = 16
        self.side = 4
        self.dirs = zone_dirs(self.n)
        self.R = rot_x(PITCH[tag])
        self.zoff = Z_OFFSET[tag]
        self.smoothed = None
        self.nearest_mm = self.near_left = self.near_right = None
        self.rays = gl.GLLinePlotItem(pos=np.zeros((0, 3)), width=1.5, antialias=True, mode="lines")
        self.rays.setGLOptions("translucent")
        view.addItem(self.rays)
        self.scatter = gl.GLScatterPlotItem(pos=np.zeros((self.n, 3)),
                                             color=np.zeros((self.n, 4), dtype=np.float32),
                                             size=16, pxMode=True)
        view.addItem(self.scatter)

    def render(self, dist, status, sigma):
        if len(dist) != self.n:
            self.n = len(dist)
            self.side = int(round(np.sqrt(self.n)))
            self.dirs = zone_dirs(self.n)
            self.smoothed = None

        # --- quality gate: drop low-confidence + noisy zones BEFORE smoothing ---
        valid = dist < (INVALID - 1)
        if status is not None and len(status) == self.n:
            valid &= np.isin(status.astype(int), GOOD_STATUS)
        if sigma is not None and len(sigma) == self.n:
            valid &= sigma <= self.sigma_max

        # --- temporal EMA on survivors; clean re-validation, hard-drop invalids ---
        if self.smoothed is None or len(self.smoothed) != self.n:
            self.smoothed = np.where(valid, dist, INVALID).astype(float)
        prev_invalid = self.smoothed >= (INVALID - 1)
        just_back = valid & prev_invalid
        keep = valid & ~prev_invalid
        self.smoothed[keep] = self.ema * dist[keep] + (1.0 - self.ema) * self.smoothed[keep]
        self.smoothed[just_back] = dist[just_back]
        self.smoothed[~valid] = INVALID

        d = self.smoothed
        good = d < (INVALID - 1)
        gl_pts = to_gl(self.dirs * d[:, None], self.R, self.zoff).astype(np.float32)
        rgb = ramp(d / self.max_mm).astype(np.float32)
        colors = np.ones((self.n, 4), dtype=np.float32)
        colors[:, :3] = rgb
        colors[:, 3] = np.where(good, 1.0, 0.0)

        self.scatter.setData(pos=gl_pts[good], color=colors[good])

        # trace rays: one beam from the sensor origin out to each valid point,
        # so the LENGTH of the beam = the measured distance. No inter-point net.
        origin = np.array([0.0, 0.0, self.zoff], dtype=np.float32)
        idx = np.where(good)[0]
        if len(idx):
            segs = np.empty((len(idx) * 2, 3), dtype=np.float32)
            cols = np.empty((len(idx) * 2, 4), dtype=np.float32)
            segs[0::2] = origin
            segs[1::2] = gl_pts[idx]
            cols[1::2] = colors[idx] * np.array([0.78, 0.78, 0.78, 0.9], dtype=np.float32)   # slightly darker at the point
            cols[0::2] = colors[idx] * np.array([0.28, 0.28, 0.28, 0.45], dtype=np.float32)  # dim at the helmet
            self.rays.setData(pos=segs, color=cols)
        else:
            self.rays.setData(pos=np.zeros((0, 3), dtype=np.float32))

        if good.any():
            self.nearest_mm = int(d[good].min())
            cols = np.arange(self.n) % self.side
            lm = good & (cols < self.side / 2.0); rm = good & (cols >= self.side / 2.0)
            self.near_left = int(d[lm].min()) if lm.any() else None
            self.near_right = int(d[rm].min()) if rm.any() else None
        else:
            self.nearest_mm = self.near_left = self.near_right = None


# ------------------------------------------------------------------ reader ---
class Reader(QtCore.QThread):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self._stop = False
        self.state = "connecting"
        self.latest = {"bottom": None, "top": None}
        self.quat = None   # latest IMU orientation quaternion (w, x, y, z), or None

    def run(self):
        backoff = 1.0
        while not self._stop:
            try:
                self.state = f"connecting {self.args.host}:{self.args.tcp_port}"
                sock = socket.create_connection((self.args.host, self.args.tcp_port), timeout=5)
                sock.settimeout(1.0)
            except OSError as e:
                self.state = f"retry ({e})"
                for _ in range(int(backoff * 10)):
                    if self._stop:
                        return
                    self.msleep(100)
                backoff = min(backoff * 1.5, 5.0)
                continue
            backoff = 1.0
            self.state = "connected"
            f = sock.makefile("rb")
            sig = None
            sta = None
            try:
                while not self._stop:
                    try:
                        raw = f.readline()
                    except (socket.timeout, TimeoutError):
                        continue
                    except OSError as e:
                        if "timed out" in str(e):
                            continue
                        break
                    if not raw:
                        break
                    p = parse(raw.decode("utf-8", "ignore").strip())
                    if not p:
                        continue
                    kind, arr = p
                    if kind == "SIGMA":
                        sig = arr
                    elif kind == "STATUS":
                        sta = arr
                    elif kind == "DATA":
                        self.latest["bottom"] = (arr, sta, sig)
                    elif kind == "DATAT":
                        self.latest["top"] = (arr, None, None)
                    elif kind == "Q":
                        self.quat = arr
            finally:
                try: f.close()
                except Exception: pass
                try: sock.close()
                except Exception: pass

    def stop(self):
        self._stop = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.228")
    ap.add_argument("--tcp-port", type=int, default=3333)
    ap.add_argument("--max-mm", type=int, default=4000)
    ap.add_argument("--floor-mm", type=int, default=1400)
    ap.add_argument("--ema", type=float, default=0.3, help="smoothing 0..1 (lower=smoother)")
    ap.add_argument("--sigma-max", type=float, default=20.0, help="drop zones noisier than this (mm)")
    args = ap.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Helmet ToF -- combined")
    win.resize(1180, 880)

    view = gl.GLViewWidget()
    view.setBackgroundColor((8, 9, 12))
    view.opts["distance"] = args.max_mm * 1.9
    view.opts["elevation"] = 18
    view.opts["azimuth"] = 68

    # side button column: snap the camera to preset views
    central = QtWidgets.QWidget()
    hbox = QtWidgets.QHBoxLayout(central)
    hbox.setContentsMargins(0, 0, 0, 0); hbox.setSpacing(0)
    bar = QtWidgets.QWidget()
    vb = QtWidgets.QVBoxLayout(bar)
    vb.setContentsMargins(6, 8, 6, 8); vb.setSpacing(6)
    PRESETS = [("Front", 90, 0), ("3/4 view", 68, 18), ("Top", 90, 89), ("Side", 0, 0)]
    for label, az, el in PRESETS:
        b = QtWidgets.QPushButton(label)
        b.setMinimumWidth(92)
        b.clicked.connect(lambda checked=False, a=az, e=el: view.setCameraPosition(azimuth=a, elevation=e))
        vb.addWidget(b)
    recenter_btn = QtWidgets.QPushButton("Recenter IMU")
    recenter_btn.setMinimumWidth(92)
    recenter_btn.setToolTip("Face forward + hold still, then click to zero head orientation")
    vb.addWidget(recenter_btn)
    vb.addStretch(1)
    hbox.addWidget(bar)
    hbox.addWidget(view, 1)
    win.setCentralWidget(central)

    grid = gl.GLGridItem()
    grid.setSize(x=args.max_mm * 2, y=args.max_mm * 2)
    grid.setSpacing(x=args.max_mm / 10, y=args.max_mm / 10)
    grid.setColor((255, 255, 255, 12))
    view.addItem(grid)

    floor = gl.GLGridItem()
    floor.setSize(x=args.max_mm * 2, y=args.max_mm * 2)
    floor.setSpacing(x=args.max_mm / 5, y=args.max_mm / 5)
    floor.translate(0, 0, -args.floor_mm)
    floor.setColor((90, 160, 110, 45))
    view.addItem(floor)

    L = args.max_mm * 0.35
    for pts, col in [
        (np.array([[0, 0, 0], [L, 0, 0]]),           (1.0, 0.4, 0.4, 0.8)),
        (np.array([[0, 0, 0], [0, args.max_mm, 0]]), (0.4, 1.0, 0.5, 0.8)),
        (np.array([[0, 0, 0], [0, 0, L]]),           (0.5, 0.65, 1.0, 0.8)),
    ]:
        view.addItem(gl.GLLinePlotItem(pos=pts, color=col, width=2, antialias=True))

    head = gl.GLMeshItem(meshdata=gl.MeshData.sphere(rows=12, cols=12, radius=90),
                         smooth=True, color=(0.55, 0.57, 0.65, 1.0), shader="shaded")
    view.addItem(head)
    nose = gl.GLLinePlotItem(pos=np.array([[0, 0, 0], [0, 240, 0]]),
                             color=(0.7, 0.7, 0.78, 0.9), width=2, antialias=True)
    view.addItem(nose)

    fcol = {"bottom": (0.22, 0.75, 1.0, 0.28), "top": (1.0, 0.62, 0.22, 0.28)}
    frustums = []
    for tag in ("bottom", "top"):
        segs = frustum_segments(rot_x(PITCH[tag]), Z_OFFSET[tag], args.max_mm, FOV / 2.0)
        fr = gl.GLLinePlotItem(pos=segs.astype(np.float32), color=fcol[tag], width=1.0, antialias=True, mode="lines")
        fr.setGLOptions("translucent")
        view.addItem(fr)
        frustums.append(fr)

    clouds = {"bottom": Cloud(view, "bottom", args.max_mm, args.ema, args.sigma_max),
              "top": Cloud(view, "top", args.max_mm, args.ema, args.sigma_max)}

    # Everything rigidly attached to the head -> rotated by the IMU each frame so
    # the cloud tilts/turns with your head, while floor + grid stay world-fixed.
    helmet_items = [head, nose] + frustums
    for c in clouds.values():
        helmet_items += [c.scatter, c.rays]

    reader = Reader(args)
    reader.start()

    # IMU head orientation. The game-rotation-vector has an arbitrary yaw reference
    # and the IMU is mounted at an unknown angle, so we "recenter": capture the
    # current quaternion as the neutral pose and show every later orientation
    # relative to it. (Yaw also drifts slowly with no magnetometer -> re-recenter.)
    q_ref = [None]

    def do_recenter():
        if reader.quat is not None:
            w, x, y, z = reader.quat
            q_ref[0] = QtGui.QQuaternion(float(w), float(x), float(y), float(z))
    recenter_btn.clicked.connect(do_recenter)

    def apply_orientation():
        q = reader.quat
        if q is None:
            return
        try:
            cur = QtGui.QQuaternion(float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            if q_ref[0] is None:
                q_ref[0] = cur
            rel = q_ref[0].conjugated() * cur      # orientation relative to neutral
            m = QtGui.QMatrix4x4()
            m.rotate(rel)
            for it in helmet_items:
                it.setTransform(m)
        except Exception as e:
            print("orientation skip:", e)

    frames = [0]; last = [time.time()]; fps = [0.0]

    def fmt(c):
        if c.nearest_mm is None:
            return "--"
        lr = f" (L{c.near_left} R{c.near_right})" if (c.near_left is not None and c.near_right is not None) else ""
        return f"{c.nearest_mm}mm{lr}"

    def tick():
        for tag, cloud in clouds.items():
            d = reader.latest[tag]
            if d is not None:
                reader.latest[tag] = None
                try:
                    cloud.render(*d)
                except Exception as e:
                    print("render skip:", e)
        apply_orientation()
        frames[0] += 1
        now = time.time()
        if now - last[0] >= 0.5:
            fps[0] = frames[0] / (now - last[0]); frames[0] = 0; last[0] = now
            win.setWindowTitle(f"Helmet ToF -- {reader.state} -- {fps[0]:.0f} FPS"
                               f" | bottom {fmt(clouds['bottom'])} | top {fmt(clouds['top'])}")

    timer = QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(50)

    win.show()
    code = app.exec()
    reader.stop()
    reader.wait(2000)
    sys.exit(code)


if __name__ == "__main__":
    main()
