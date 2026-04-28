"""
VL53L8CX live 3D point cloud visualiser - v3 (PyQtGraph + threaded serial).

Why this rewrite:
  - mplot3d is software-rendered; rotating the view with the mouse felt slow
    because every drag event had to wait behind the data loop's redraw.
    PyQtGraph (Qt + OpenGL) is GPU-accelerated and rotation is now decoupled
    from the data pipeline.
  - Serial reads ran on the GUI thread, so a 1-second `readline` timeout
    could freeze input. The reader now lives in a QThread and pushes the
    latest frame to the GUI via a Qt signal.
  - Old drain order was: readline -> process -> drain. That always rendered
    the OLDEST queued frame. New order: drain first to find the newest
    complete `DATA:` line, then process that.
  - EMA alpha bumped 0.3 -> 0.6, cutting the 95% settling time from ~9
    frames to ~3 (~900 ms -> ~300 ms at 10 Hz).
  - Firmware clamps invalid zones to 4000 mm, which appeared as a phantom
    back-wall. Those are now masked to NaN and rendered transparent.

Sensor geometry:
  VL53L8CX FoV is 65 deg diagonal, 45 deg horizontal/vertical (per ST
  datasheet). Each of 8 zones along an axis subtends 45/8 = 5.625 deg.
"""

import argparse
import sys

import numpy as np
import serial
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets


ZONES_PER_SIDE   = 8
TOTAL_ZONES      = ZONES_PER_SIDE * ZONES_PER_SIDE
FOV_DEG_PER_AXIS = 45.0
ANGLE_PER_ZONE   = np.radians(FOV_DEG_PER_AXIS / ZONES_PER_SIDE)
EMA_ALPHA        = 0.6
INVALID_CLAMP_MM = 4000  # firmware sentinel for invalid zones


def precompute_zone_directions():
    directions = np.zeros((TOTAL_ZONES, 3))
    centre = (ZONES_PER_SIDE - 1) / 2.0
    for row in range(ZONES_PER_SIDE):
        for col in range(ZONES_PER_SIDE):
            h = (col - centre) * ANGLE_PER_ZONE
            v = (row - centre) * ANGLE_PER_ZONE
            x =  np.sin(h)
            y = -np.sin(v)
            z =  np.cos(h) * np.cos(v)
            directions[row * ZONES_PER_SIDE + col] = (x, y, z)
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
    error     = QtCore.pyqtSignal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port  = port
        self.baud  = baud
        self._stop = False

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
        except serial.SerialException as exc:
            self.error.emit(str(exc))
            return

        while not self._stop:
            # Drain everything currently buffered, then keep the newest valid frame.
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


class PointCloudWindow(QtWidgets.QMainWindow):
    def __init__(self, max_mm):
        super().__init__()
        self.max_mm     = max_mm
        self.directions = precompute_zone_directions()
        self.smoothed   = None
        self.frame_n    = 0

        self.setWindowTitle("VL53L8CX live point cloud (v3)")
        self.resize(1100, 800)

        central = QtWidgets.QWidget()
        layout  = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((10, 10, 10))
        self.view.opts["distance"] = max_mm * 1.6
        self.view.opts["elevation"] = 18
        self.view.opts["azimuth"]   = -65
        layout.addWidget(self.view)

        self.status = self.statusBar()
        self.status.showMessage("Waiting for data...")

        # Floor grid for visual reference
        grid = gl.GLGridItem()
        grid.setSize(x=max_mm * 2, y=max_mm * 2)
        grid.setSpacing(x=max_mm / 10, y=max_mm / 10)
        grid.translate(0, 0, -max_mm * 0.5)
        grid.setColor((255, 255, 255, 40))
        self.view.addItem(grid)

        # Sensor origin marker
        origin = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)),
            color=(1.0, 0.3, 0.3, 1.0),
            size=10,
            pxMode=True,
        )
        self.view.addItem(origin)

        # Live scatter
        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((TOTAL_ZONES, 3)),
            color=np.tile((1.0, 1.0, 1.0, 0.0), (TOTAL_ZONES, 1)),
            size=14,
            pxMode=True,
        )
        self.view.addItem(self.scatter)

        self.cmap = pg.colormap.get("viridis")

    def update_frame(self, distances):
        # Mask phantom back-wall (firmware clamps invalid -> 4000 mm)
        invalid = distances >= (INVALID_CLAMP_MM - 1)
        valid_distances = distances.copy()
        valid_distances[invalid] = np.nan

        if self.smoothed is None:
            self.smoothed = np.where(invalid, float(self.max_mm), distances)
        else:
            valid_mask = ~invalid
            self.smoothed[valid_mask] = (
                EMA_ALPHA * valid_distances[valid_mask]
                + (1.0 - EMA_ALPHA) * self.smoothed[valid_mask]
            )

        points = self.directions * self.smoothed[:, np.newaxis]
        # Axis remap so vertical depth maps the way mplot3d version did:
        # (sensor X, sensor Z=depth, sensor Y=up) -> (gl X, gl Y=depth, gl Z=up)
        gl_pts = np.column_stack([points[:, 0], points[:, 2], points[:, 1]])

        # Colour by smoothed distance, hide invalid zones via alpha=0.
        norm = np.clip(self.smoothed / self.max_mm, 0.0, 1.0)
        colors = self.cmap.map(norm, mode="float")
        colors[invalid, 3] = 0.0

        self.scatter.setData(pos=gl_pts, color=colors)

        self.frame_n += 1
        n_invalid = int(invalid.sum())
        self.status.showMessage(
            f"Frame {self.frame_n}   |   invalid zones: {n_invalid}/64"
        )

    def on_serial_error(self, msg):
        QtWidgets.QMessageBox.critical(
            self, "Serial error",
            f"Could not open serial port:\n\n{msg}\n\n"
            "If idf.py monitor is running, close it first (Ctrl+])."
        )
        self.close()


def main():
    parser = argparse.ArgumentParser(description="VL53L8CX 3D point cloud (PyQtGraph)")
    parser.add_argument("--port",   default="COM12", help="Serial port")
    parser.add_argument("--baud",   type=int, default=115200)
    parser.add_argument("--max-mm", type=int, default=4000,
                        help="Display range and colour-scale max (mm)")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    win = PointCloudWindow(args.max_mm)
    win.show()

    reader = SerialReader(args.port, args.baud)
    reader.new_frame.connect(win.update_frame)
    reader.error.connect(win.on_serial_error)
    reader.start()

    print(f"Listening on {args.port} @ {args.baud} baud...")

    exit_code = app.exec()

    reader.stop()
    reader.wait(2000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
