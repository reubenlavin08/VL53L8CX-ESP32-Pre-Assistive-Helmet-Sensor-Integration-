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
# Change ZONES_PER_SIDE to 8 (for 8x8 = 64 zones) or 4 (for 4x4 = 16 zones)
# to match the firmware's SENSOR_RESOLUTION.
ZONES_PER_SIDE = 8
TOTAL_ZONES = ZONES_PER_SIDE * ZONES_PER_SIDE
FOV_DEG_PER_AXIS = 45.0
ANGLE_PER_ZONE = np.radians(FOV_DEG_PER_AXIS / ZONES_PER_SIDE)
INVALID_CLAMP_MM = 4000   # firmware sentinel


def precompute_zone_directions():
    """Unit vectors (X, Y, Z) pointing from sensor into each zone's cone center."""
    directions = np.zeros((TOTAL_ZONES, 3))
    centre = (ZONES_PER_SIDE - 1) / 2.0
    for row in range(ZONES_PER_SIDE):
        for col in range(ZONES_PER_SIDE):
            h = (col - centre) * ANGLE_PER_ZONE
            v = (row - centre) * ANGLE_PER_ZONE
            directions[row * ZONES_PER_SIDE + col] = (
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
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=float)


class SourceReader(QtCore.QThread):
    """Reads DATA: lines from either a serial port or a TCP socket."""
    new_frame = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, args):
        super().__init__()
        self.args = args
        self._stop = False

    def run(self):
        if self.args.host:
            try:
                sock = socket.create_connection((self.args.host, self.args.tcp_port), timeout=5)
                sock.settimeout(1.0)
            except OSError as exc:
                self.error.emit(f"TCP connect to {self.args.host}:{self.args.tcp_port} failed: {exc}")
                return
            f = sock.makefile("rb")
            try:
                while not self._stop:
                    try:
                        raw = f.readline()
                    except socket.timeout:
                        continue
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="ignore").strip()
                    parsed = parse_data_line(line)
                    if parsed is not None:
                        self.new_frame.emit(parsed)
            finally:
                f.close()
                sock.close()
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
        self.directions = precompute_zone_directions()
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
            pos=np.zeros((TOTAL_ZONES * 2, 3), dtype=np.float32),
            color=np.zeros((TOTAL_ZONES * 2, 4), dtype=np.float32),
            width=1.2, mode="lines", antialias=True,
        )
        self.view.addItem(self.rays)

        # The actual point cloud
        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((TOTAL_ZONES, 3)),
            color=np.tile((1.0, 1.0, 1.0, 0.0), (TOTAL_ZONES, 1)),
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

    def update_frame(self, distances):
        invalid = distances >= (INVALID_CLAMP_MM - 1)

        # Sensor-frame points -> GL frame (X, depth=sensor Z, up=sensor Y)
        pts_sensor = self.directions * distances[:, np.newaxis]
        gl_pts = np.column_stack([pts_sensor[:, 0], pts_sensor[:, 2], pts_sensor[:, 1]]).astype(np.float32)

        # Colour by distance (viridis); hide invalid by alpha=0
        norm = np.clip(distances / self.max_mm, 0.0, 1.0)
        colors = self.cmap.map(norm, mode="float").astype(np.float32)
        colors[invalid, 3] = 0.0
        self.scatter.setData(pos=gl_pts, color=colors)

        # Rays: 64 line segments, each from origin (0,0,0) to its zone's point.
        # Two vertices per ray: idx 0 = origin (faded), idx 1 = point (brighter).
        ray_pos = np.zeros((TOTAL_ZONES * 2, 3), dtype=np.float32)
        ray_pos[1::2] = gl_pts
        ray_color = np.zeros((TOTAL_ZONES * 2, 4), dtype=np.float32)
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
        if n_valid:
            mean = float(np.mean(distances[~invalid]))
            self.status.showMessage(f"Frame {self.frame_n}  |  valid {n_valid}/64  |  mean {mean:.0f} mm")
        else:
            self.status.showMessage(f"Frame {self.frame_n}  |  valid 0/64")

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
    reader.new_frame.connect(win.update_frame)
    reader.error.connect(win.on_serial_error)
    reader.start()

    code = app.exec()
    reader.stop()
    reader.wait(2000)
    sys.exit(code)


if __name__ == "__main__":
    main()
