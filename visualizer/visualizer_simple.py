"""
Minimal VL53L8CX point cloud visualiser — raw data only.

No pose tracking, no trail, no FoV frustum, no rays, no world-frame memory.
Just opens the data source (USB serial OR WiFi TCP), parses DATA: lines,
projects 64 zones into 3D, and renders them as coloured points.

Usage (wired serial):
    python visualizer_simple.py --port COM10

Usage (WiFi TCP):
    python visualizer_simple.py --host 192.168.1.228
"""

import argparse
import socket
import sys

import numpy as np
import serial
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets


# Sensor geometry (per ST VL53L8CX datasheet).
# Visualizer auto-detects 8x8 (64 values) vs 4x4 (16 values) on each frame
# so it works through the full parameter sweep without restart.
FOV_DEG_PER_AXIS = 45.0
INVALID_CLAMP_MM = 4000   # firmware sentinel
SUPPORTED_ZONE_COUNTS = (64, 16)


def precompute_zone_directions(total_zones):
    """Unit vectors (X, Y, Z) pointing from sensor into each zone's cone center."""
    side = int(np.sqrt(total_zones))
    angle_per_zone = np.radians(FOV_DEG_PER_AXIS / side)
    directions = np.zeros((total_zones, 3))
    centre = (side - 1) / 2.0
    for row in range(side):
        for col in range(side):
            h = (col - centre) * angle_per_zone
            v = (row - centre) * angle_per_zone
            directions[row * side + col] = (
                np.sin(h),
                -np.sin(v),
                np.cos(h) * np.cos(v),
            )
    return directions


def parse_data_line(line):
    if not line.startswith("DATA:"):
        return None
    try:
        values = [int(v) for v in line[5:].split(",")]
    except ValueError:
        return None
    if len(values) not in SUPPORTED_ZONE_COUNTS:
        return None
    return np.asarray(values, dtype=float)


class SourceReader(QtCore.QThread):
    """Reads DATA: lines from either a serial port or a TCP socket.
    TCP mode auto-reconnects when the socket drops (e.g. measure.py
    takes the single client slot during a capture, ESP reboots from OTA)."""
    new_frame = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)

    def __init__(self, args):
        super().__init__()
        self.args = args
        self._stop = False

    def run(self):
        if self.args.host:
            backoff = 1.0
            while not self._stop:
                try:
                    self.status.emit(f"connecting to {self.args.host}:{self.args.tcp_port} ...")
                    sock = socket.create_connection(
                        (self.args.host, self.args.tcp_port), timeout=5)
                    sock.settimeout(1.0)
                except OSError as exc:
                    self.status.emit(f"connect failed ({exc}), retrying in {backoff:.0f}s")
                    for _ in range(int(backoff * 10)):
                        if self._stop:
                            return
                        self.msleep(100)
                    backoff = min(backoff * 1.5, 5.0)
                    continue
                backoff = 1.0
                self.status.emit("connected")
                f = sock.makefile("rb")
                try:
                    while not self._stop:
                        try:
                            raw = f.readline()
                        except (socket.timeout, TimeoutError):
                            continue
                        except OSError as exc:
                            # Buffered reader wraps socket timeouts as
                            # "cannot read from timed out object" — same thing,
                            # different exception type.
                            if "timed out" in str(exc):
                                continue
                            break       # any other OSError = treat as disconnect
                        if not raw:
                            break       # remote closed — reconnect
                        line = raw.decode("utf-8", errors="ignore").strip()
                        parsed = parse_data_line(line)
                        if parsed is not None:
                            self.new_frame.emit(parsed)
                finally:
                    try: f.close()
                    except Exception: pass
                    try: sock.close()
                    except Exception: pass
                if not self._stop:
                    self.status.emit("socket closed — reconnecting ...")
                    self.msleep(500)
        else:
            try:
                ser = serial.Serial(self.args.port, self.args.baud, timeout=1)
            except serial.SerialException as exc:
                self.error.emit(str(exc))
                return
            while not self._stop:
                # Drain to keep only newest frame
                latest = None
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                parsed = parse_data_line(line)
                if parsed is not None:
                    latest = parsed
                while ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    parsed = parse_data_line(line)
                    if parsed is not None:
                        latest = parsed
                if latest is not None:
                    self.new_frame.emit(latest)
            ser.close()

    def stop(self):
        self._stop = True


class SimpleWindow(QtWidgets.QMainWindow):
    def __init__(self, max_mm=4000):
        super().__init__()
        self.max_mm = max_mm
        self.n_zones = 64                                # default; updated on first frame
        self.directions = precompute_zone_directions(self.n_zones)
        self.cmap = pg.colormap.get("viridis")

        self.setWindowTitle("VL53L8CX simple point cloud")
        self.resize(1100, 800)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((10, 10, 10))
        self.view.opts["distance"] = max_mm * 1.7
        self.view.opts["elevation"] = 18
        self.view.opts["azimuth"] = -65
        self.setCentralWidget(self.view)

        # Floor grid
        grid = gl.GLGridItem()
        grid.setSize(x=max_mm * 2, y=max_mm * 2)
        grid.setSpacing(x=max_mm / 10, y=max_mm / 10)
        grid.translate(0, 0, -max_mm * 0.5)
        grid.setColor((255, 255, 255, 35))
        self.view.addItem(grid)

        # Axes (X red, Depth green, Z up blue)
        L = max_mm * 0.55
        for pts, color, label, lpos in [
            (np.array([[0, 0, 0], [L, 0, 0]]),       (1.0, 0.35, 0.35, 1.0), "X (mm)",     (L * 1.05, 0, 0)),
            (np.array([[0, 0, 0], [0, max_mm, 0]]),  (0.35, 1.0, 0.45, 1.0), "Depth (mm)", (0, max_mm * 1.03, 0)),
            (np.array([[0, 0, 0], [0, 0, L]]),       (0.45, 0.6, 1.0, 1.0),  "Y (mm)",     (0, 0, L * 1.05)),
        ]:
            self.view.addItem(gl.GLLinePlotItem(pos=pts, color=color, width=2, antialias=True))
            self.view.addItem(gl.GLTextItem(pos=lpos, text=label, color=(220, 220, 220, 255)))

        # Rays from sensor origin to each point — visualises per-zone distance
        self.rays = gl.GLLinePlotItem(
            pos=np.zeros((self.n_zones * 2, 3), dtype=np.float32),
            color=np.zeros((self.n_zones * 2, 4), dtype=np.float32),
            width=1.2, mode="lines", antialias=True,
        )
        self.view.addItem(self.rays)

        # The actual point cloud
        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((self.n_zones, 3)),
            color=np.tile((1.0, 1.0, 1.0, 0.0), (self.n_zones, 1)),
            size=14, pxMode=True,
        )
        self.view.addItem(self.scatter)

        self.status = self.statusBar()
        self.status.setStyleSheet("color: #cccccc; background-color: #0a0a0a;")

        # Blinker — toggles bright/dim each frame so you can see refresh rate
        self.blink_label = QtWidgets.QLabel("●")
        self.blink_label.setStyleSheet(
            "color: #ff00aa; font-size: 22px; padding-left: 8px; padding-right: 8px;"
        )
        self.status.addPermanentWidget(self.blink_label)
        self.blink_state = False

        self.status.showMessage("Waiting for data...")
        self.frame_n = 0
        self.conn_state = "initializing"

        # Frame-rate decoupling: reader thread writes to self.latest_frame,
        # this timer renders the most recent one at 30 Hz. Older frames are
        # silently overwritten -- no Qt signal queue accumulation.
        self.latest_frame = None
        self._render_timer = QtCore.QTimer()
        self._render_timer.timeout.connect(self._render_latest)
        self._render_timer.start(33)  # ~30 Hz

    def receive_frame(self, distances):
        """Called from reader thread via signal — just stash the latest."""
        self.latest_frame = distances

    def _render_latest(self):
        """Called at fixed 30 Hz from the GUI thread."""
        if self.latest_frame is not None:
            distances = self.latest_frame
            self.latest_frame = None
            self.update_frame(distances)

    def update_status(self, msg):
        """Show connection state in the status bar when no data is flowing."""
        self.conn_state = msg
        if self.frame_n == 0:
            self.status.showMessage(msg)

    def update_frame(self, distances):
        # Adapt geometry if firmware switched resolution (8x8 ↔ 4x4)
        if len(distances) != self.n_zones:
            self.n_zones = len(distances)
            self.directions = precompute_zone_directions(self.n_zones)
            self.scatter.setData(
                pos=np.zeros((self.n_zones, 3)),
                color=np.tile((1.0, 1.0, 1.0, 0.0), (self.n_zones, 1)),
            )

        invalid = distances >= (INVALID_CLAMP_MM - 1)

        # Sensor-frame points -> GL frame (X, depth=sensor Z, up=sensor Y)
        pts_sensor = self.directions * distances[:, np.newaxis]
        gl_pts = np.column_stack([pts_sensor[:, 0], pts_sensor[:, 2], pts_sensor[:, 1]]).astype(np.float32)

        # Colour by distance (viridis); hide invalid by alpha=0
        norm = np.clip(distances / self.max_mm, 0.0, 1.0)
        colors = self.cmap.map(norm, mode="float").astype(np.float32)
        colors[invalid, 3] = 0.0
        self.scatter.setData(pos=gl_pts, color=colors)

        # Rays: one line segment per zone, origin -> point.
        ray_pos = np.zeros((self.n_zones * 2, 3), dtype=np.float32)
        ray_pos[1::2] = gl_pts
        ray_color = np.zeros((self.n_zones * 2, 4), dtype=np.float32)
        origin_col = colors.copy(); origin_col[:, 3] *= 0.10
        end_col    = colors.copy(); end_col[:, 3]    *= 0.55
        ray_color[0::2] = origin_col
        ray_color[1::2] = end_col
        self.rays.setData(pos=ray_pos, color=ray_color)

        # Blinker — toggle bright/dim each frame so refresh rate is visible
        self.blink_state = not self.blink_state
        col = "#ff00aa" if self.blink_state else "#3a002a"
        self.blink_label.setStyleSheet(
            f"color: {col}; font-size: 22px; padding-left: 8px; padding-right: 8px;"
        )

        self.frame_n += 1
        n_valid = int((~invalid).sum())
        side = int(np.sqrt(self.n_zones))
        res_label = f"{side}x{side}"
        if n_valid:
            mean = float(np.mean(distances[~invalid]))
            self.status.showMessage(
                f"Frame {self.frame_n}  |  {res_label}  |  valid {n_valid}/{self.n_zones}  |  mean {mean:.0f} mm  |  {self.conn_state}"
            )
        else:
            self.status.showMessage(
                f"Frame {self.frame_n}  |  {res_label}  |  valid 0/{self.n_zones}  |  {self.conn_state}"
            )

    def on_serial_error(self, msg):
        QtWidgets.QMessageBox.critical(
            self, "Connection error",
            f"Could not open data source:\n\n{msg}\n\n"
            "Close other monitors/visualizers on the same port, or verify the ESP's WiFi IP."
        )
        self.close()


def main():
    p = argparse.ArgumentParser()
    # Serial source (default)
    p.add_argument("--port", default="COM10", help="serial port (used when --host not given)")
    p.add_argument("--baud", type=int, default=115200)
    # WiFi source (alternative)
    p.add_argument("--host", default=None, help="ESP IP — if given, connect via TCP instead of serial")
    p.add_argument("--tcp-port", type=int, default=3333)
    # Display
    p.add_argument("--max-mm", type=int, default=4000)
    args = p.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = SimpleWindow(args.max_mm)
    win.show()

    reader = SourceReader(args)
    reader.new_frame.connect(win.receive_frame)  # save-latest, no render-per-frame
    reader.error.connect(win.on_serial_error)
    reader.status.connect(win.update_status)
    reader.start()

    code = app.exec()
    reader.stop()
    reader.wait(2000)
    sys.exit(code)


if __name__ == "__main__":
    main()
