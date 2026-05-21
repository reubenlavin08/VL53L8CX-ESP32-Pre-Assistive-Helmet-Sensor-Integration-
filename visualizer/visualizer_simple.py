"""
Minimal VL53L8CX point cloud visualiser — raw data only.

No pose tracking, no trail, no FoV frustum, no rays, no world-frame memory.
Just opens the serial port, parses DATA: lines, projects 64 zones into 3D,
and renders them as coloured points. Useful for sanity-checking what the
sensor actually sees, with nothing in the way.

Usage:
    python visualizer_simple.py --port COM10 --baud 115200
"""

import argparse
import sys

import numpy as np
import serial
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets


# Sensor geometry (per ST VL53L8CX datasheet)
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


class SerialReader(QtCore.QThread):
    new_frame = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port, self.baud, self._stop = port, baud, False

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
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

        # The actual point cloud
        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((TOTAL_ZONES, 3)),
            color=np.tile((1.0, 1.0, 1.0, 0.0), (TOTAL_ZONES, 1)),
            size=14, pxMode=True,
        )
        self.view.addItem(self.scatter)

        self.status = self.statusBar()
        self.status.setStyleSheet("color: #cccccc; background-color: #0a0a0a;")
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

        self.frame_n += 1
        n_valid = int((~invalid).sum())
        if n_valid:
            mean = float(np.mean(distances[~invalid]))
            self.status.showMessage(f"Frame {self.frame_n}  |  valid {n_valid}/64  |  mean {mean:.0f} mm")
        else:
            self.status.showMessage(f"Frame {self.frame_n}  |  valid 0/64")

    def on_serial_error(self, msg):
        QtWidgets.QMessageBox.critical(
            self, "Serial error",
            f"Could not open serial port:\n\n{msg}\n\n"
            "If idf.py monitor or the v6 visualizer is running, close it first."
        )
        self.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="COM10")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--max-mm", type=int, default=4000)
    args = p.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = SimpleWindow(args.max_mm)
    win.show()

    reader = SerialReader(args.port, args.baud)
    reader.new_frame.connect(win.update_frame)
    reader.error.connect(win.on_serial_error)
    reader.start()

    code = app.exec()
    reader.stop()
    reader.wait(2000)
    sys.exit(code)


if __name__ == "__main__":
    main()
