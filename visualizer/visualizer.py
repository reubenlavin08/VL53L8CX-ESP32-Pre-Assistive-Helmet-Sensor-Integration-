"""
VL53L8CX live 3D point cloud visualiser - v5 (+ experimental 6-DOF pose).

v5 adds an experimental relative pose estimator (Kabsch / SVD-based rigid
registration on consecutive point clouds) that integrates per-frame
deltas into a cumulative sensor pose, and draws the resulting trajectory
trail behind the sensor body. See visualizer/pose_estimator.py for the
algorithm and its limits.

v4 (carried forward) added back the scientific look from the matplotlib
version while keeping the GPU-accelerated PyQtGraph engine:

  - Side colour bar showing the distance scale (mm) like matplotlib's cbar.
  - Coloured X / Depth / Y axis arrows with text labels at the endpoints.
  - Tick text every 1000 mm along the depth axis.
  - Sensor body modelled as a flat dark rectangle at the origin with a
    bright lens ring, so you can see where the sensor is relative to the
    points.
  - Field-of-view frustum drawn as 4 corner rays + a back square at the
    far range, marking the 45 deg horizontal/vertical FoV (65 deg diagonal)
    quoted in the ST datasheet.
  - One animated ToF beam per zone, updated every frame, fading from the
    sensor lens out to each measured point in the same colour as that
    point. Invalid zones (firmware sentinel == MAX_DISTANCE_MM) drop their
    alpha to zero so they don't render.

Carried over from v3:
  - Threaded serial reader (GUI never blocks on readline).
  - Drain-first pipeline (newest valid frame is what gets rendered).
  - EMA alpha = 0.6 (settles 95 percent in ~3 frames at 10 Hz).
  - Phantom back-wall (4000 mm clamps) hidden via per-zone alpha.
"""

import argparse
import sys
from collections import deque

import numpy as np
import serial
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from pose_estimator import RelativePoseEstimator


# ── Sensor geometry (per ST VL53L8CX datasheet) ─────────────────────────
ZONES_PER_SIDE   = 8
TOTAL_ZONES      = ZONES_PER_SIDE * ZONES_PER_SIDE
FOV_DEG_PER_AXIS = 45.0           # 65 deg diagonal, 45 deg horizontal/vertical
ANGLE_PER_ZONE   = np.radians(FOV_DEG_PER_AXIS / ZONES_PER_SIDE)

EMA_ALPHA        = 0.6
INVALID_CLAMP_MM = 4000           # firmware sentinel for invalid zones


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


# ── Background serial reader ─────────────────────────────────────────────
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


# ── Main window ──────────────────────────────────────────────────────────
class PointCloudWindow(QtWidgets.QMainWindow):
    def __init__(self, max_mm):
        super().__init__()
        self.max_mm     = max_mm
        self.directions = precompute_zone_directions()
        self.smoothed   = None
        self.frame_n    = 0

        self.setWindowTitle("VL53L8CX live point cloud  -  v6 (world-frame memory)")
        self.resize(1300, 850)

        # Experimental 6-DOF relative pose estimator + trail buffer
        self.pose_estimator = RelativePoseEstimator()
        self.world_trail    = deque(maxlen=int(15 * 5))    # ~5 s at 15 Hz
        # Accumulated world-frame point cloud (each entry: (Nx3 world points, Nx4 RGBA))
        # Capped at ~6 s so old observations fade out before the pose drift shows.
        self.world_cloud    = deque(maxlen=int(15 * 6))

        # Central layout: GL view + side colour bar
        central = QtWidgets.QWidget()
        central.setStyleSheet("background-color: #0a0a0a;")
        h = QtWidgets.QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.setCentralWidget(central)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((10, 10, 10))
        self.view.opts["distance"]  = max_mm * 1.7
        self.view.opts["elevation"] = 18
        self.view.opts["azimuth"]   = -65
        h.addWidget(self.view, stretch=1)

        self._build_colorbar(h, max_mm)

        # Status bar - frame counter and stats
        self.status = self.statusBar()
        self.status.setStyleSheet("color: #cccccc; background-color: #0a0a0a;")
        self.status.showMessage("Waiting for data...")

        self.cmap = pg.colormap.get("viridis")

        # Build all the static and dynamic GL items
        self._build_floor_grid()
        self._build_axes(max_mm)
        self._build_sensor_body(max_mm)
        self._build_fov_frustum(max_mm)
        self._build_rays_and_scatter()
        self._build_trajectory_trail()

    # ── Side colour bar (ImageItem with viridis gradient) ────────────────
    def _build_colorbar(self, parent_layout, max_mm):
        cbar_widget = pg.GraphicsLayoutWidget()
        cbar_widget.setBackground((10, 10, 10))
        cbar_widget.setFixedWidth(120)
        plot = cbar_widget.addPlot()
        plot.setMouseEnabled(False, False)
        plot.setMenuEnabled(False)
        plot.hideAxis("left")
        plot.hideAxis("bottom")
        plot.showAxis("right")

        n_steps = 256
        lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, n_steps, alpha=False)
        # ImageItem wants (W, H, 3) in default col-major; (1, n_steps, 3) is a 1-wide bar
        grad = lut.reshape(1, n_steps, 3).astype(np.ubyte)
        img = pg.ImageItem(grad)
        img.setRect(QtCore.QRectF(0.0, 0.0, 1.0, float(max_mm)))
        plot.addItem(img)
        plot.setXRange(0, 1, padding=0)
        plot.setYRange(0, max_mm, padding=0)

        right = plot.getAxis("right")
        right.setLabel("Distance (mm)", color="#ffffff")
        right.setPen(pg.mkPen("#cccccc"))
        right.setTextPen(pg.mkPen("#ffffff"))

        parent_layout.addWidget(cbar_widget)

    # ── Floor grid ───────────────────────────────────────────────────────
    def _build_floor_grid(self):
        grid = gl.GLGridItem()
        grid.setSize(x=self.max_mm * 2, y=self.max_mm * 2)
        grid.setSpacing(x=self.max_mm / 10, y=self.max_mm / 10)
        grid.translate(0, 0, -self.max_mm * 0.5)
        grid.setColor((255, 255, 255, 35))
        self.view.addItem(grid)

    # ── Coloured axis arrows + text labels + depth ticks ─────────────────
    def _build_axes(self, max_mm):
        L = max_mm * 0.55  # axis arrow length

        # X axis - red (sensor horizontal)
        x_pts = np.array([[0, 0, 0], [L, 0, 0]])
        self.view.addItem(gl.GLLinePlotItem(
            pos=x_pts, color=(1.0, 0.35, 0.35, 1.0), width=2, antialias=True
        ))
        self.view.addItem(gl.GLTextItem(
            pos=(L * 1.05, 0, 0), text="X (mm)", color=(255, 100, 100, 255)
        ))

        # Y axis - green (depth, in front of sensor)
        y_pts = np.array([[0, 0, 0], [0, max_mm, 0]])
        self.view.addItem(gl.GLLinePlotItem(
            pos=y_pts, color=(0.35, 1.0, 0.45, 1.0), width=2, antialias=True
        ))
        self.view.addItem(gl.GLTextItem(
            pos=(0, max_mm * 1.03, 0), text="Depth (mm)", color=(120, 255, 140, 255)
        ))

        # Z axis - blue (vertical / sensor up)
        z_pts = np.array([[0, 0, 0], [0, 0, L]])
        self.view.addItem(gl.GLLinePlotItem(
            pos=z_pts, color=(0.45, 0.6, 1.0, 1.0), width=2, antialias=True
        ))
        self.view.addItem(gl.GLTextItem(
            pos=(0, 0, L * 1.05), text="Y (mm)", color=(140, 170, 255, 255)
        ))

        # Tick labels every 1000 mm along the depth axis
        for d in range(1000, max_mm + 1, 1000):
            self.view.addItem(gl.GLTextItem(
                pos=(0, d, -max_mm * 0.5),
                text=f"{d}",
                color=(180, 220, 200, 255),
            ))
            tick = gl.GLLinePlotItem(
                pos=np.array([[0, d, -max_mm * 0.5],
                              [0, d, -max_mm * 0.5 + max_mm * 0.02]]),
                color=(0.7, 0.85, 0.78, 0.8),
                width=1.5,
            )
            self.view.addItem(tick)

    # ── Sensor body: flat dark rectangle + bright lens ring ──────────────
    def _build_sensor_body(self, max_mm):
        s = max_mm * 0.025  # ~100 mm at default 4000 mm range

        # Sensor face: flat rectangle in the X-Z plane (Y = 0 = sensor face)
        verts = np.array([
            [-s, 0.0, -s],
            [ s, 0.0, -s],
            [ s, 0.0,  s],
            [-s, 0.0,  s],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
        face_colors = np.tile(np.array([0.18, 0.22, 0.30, 1.0]), (2, 1)).astype(np.float32)
        sensor = gl.GLMeshItem(
            vertexes=verts, faces=faces, faceColors=face_colors,
            smooth=False, drawEdges=True, edgeColor=(0.7, 0.85, 1.0, 1.0),
        )
        self.view.addItem(sensor)

        # Lens ring - small circle in the sensor face
        n = 36
        a = np.linspace(0, 2 * np.pi, n)
        r = s * 0.45
        ring = np.column_stack([
            r * np.cos(a),
            np.full(n, 0.5),  # just in front of the sensor face
            r * np.sin(a),
        ])
        self.view.addItem(gl.GLLinePlotItem(
            pos=ring, color=(0.9, 0.95, 1.0, 1.0),
            width=2, antialias=True, mode="line_strip",
        ))

        # Sensor label
        self.view.addItem(gl.GLTextItem(
            pos=(-s * 1.5, 0, s * 1.6),
            text="VL53L8CX",
            color=(220, 220, 230, 255),
        ))

    # ── 45 deg x 45 deg field-of-view frustum ────────────────────────────
    def _build_fov_frustum(self, max_mm):
        h = np.radians(FOV_DEG_PER_AXIS / 2.0)
        v = np.radians(FOV_DEG_PER_AXIS / 2.0)
        # Corners of the FOV cone projected to the max range, axis order
        # converted to GL space (x, depth=y, z=up = sensor +y inverted)
        corners = np.array([
            [ np.sin(h), np.cos(h) * np.cos(v), -(-np.sin(v))],
            [-np.sin(h), np.cos(h) * np.cos(v), -(-np.sin(v))],
            [-np.sin(h), np.cos(h) * np.cos(v), -( np.sin(v))],
            [ np.sin(h), np.cos(h) * np.cos(v), -( np.sin(v))],
        ]) * max_mm

        segs = []
        for c in corners:                           # 4 edges from origin
            segs.append([0, 0, 0]); segs.append(c)
        for i in range(4):                          # back square
            segs.append(corners[i])
            segs.append(corners[(i + 1) % 4])

        self.view.addItem(gl.GLLinePlotItem(
            pos=np.array(segs),
            color=(0.55, 0.75, 1.0, 0.35),
            width=1.2, mode="lines", antialias=True,
        ))

    # ── Animated ToF rays + the live point scatter ───────────────────────
    def _build_rays_and_scatter(self):
        self.rays = gl.GLLinePlotItem(
            pos=np.zeros((TOTAL_ZONES * 2, 3), dtype=np.float32),
            color=np.zeros((TOTAL_ZONES * 2, 4), dtype=np.float32),
            width=1.2, mode="lines", antialias=True,
        )
        self.view.addItem(self.rays)

        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((TOTAL_ZONES, 3)),
            color=np.tile((1.0, 1.0, 1.0, 0.0), (TOTAL_ZONES, 1)),
            size=14, pxMode=True,
        )
        self.view.addItem(self.scatter)

    # ── Trajectory trail (past sensor positions, in current sensor frame) ─
    def _build_trajectory_trail(self):
        self.trail_line = gl.GLLinePlotItem(
            pos=np.zeros((1, 3), dtype=np.float32),
            color=np.zeros((1, 4), dtype=np.float32),
            width=2.5, mode="line_strip", antialias=True,
        )
        self.view.addItem(self.trail_line)

        self.trail_head = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)),
            color=(1.0, 0.85, 0.3, 1.0),
            size=8, pxMode=True,
        )
        self.view.addItem(self.trail_head)

        # Accumulated world-frame cloud (re-projected into current sensor frame
        # each tick, faded by age) — gives the impression of points rotating
        # around the sensor as it pans.
        self.world_scatter = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)),
            color=np.zeros((1, 4), dtype=np.float32),
            size=6, pxMode=True,
        )
        self.view.addItem(self.world_scatter)

    def keyPressEvent(self, event):
        # 'R' resets the cumulative pose + clears the trail and world cloud
        if event.key() == QtCore.Qt.Key.Key_R:
            self.pose_estimator.reset()
            self.world_trail.clear()
            self.world_cloud.clear()
            self.status.showMessage("Pose reset.", 2000)
        else:
            super().keyPressEvent(event)

    # ── Per-frame update from the serial thread ──────────────────────────
    def update_frame(self, distances):
        # Mask phantom back-wall (firmware sentinel)
        invalid = distances >= (INVALID_CLAMP_MM - 1)

        if self.smoothed is None:
            self.smoothed = np.where(invalid, float(self.max_mm), distances)
        else:
            valid = ~invalid
            self.smoothed[valid] = (
                EMA_ALPHA * distances[valid]
                + (1.0 - EMA_ALPHA) * self.smoothed[valid]
            )

        # Sensor-frame points -> GL frame: (X, depth=sensor Z, up=sensor Y)
        points_sensor = self.directions * self.smoothed[:, np.newaxis]
        gl_pts = np.column_stack([
            points_sensor[:, 0],
            points_sensor[:, 2],
            points_sensor[:, 1],
        ]).astype(np.float32)

        # Per-point colours
        norm = np.clip(self.smoothed / self.max_mm, 0.0, 1.0)
        pt_colors = self.cmap.map(norm, mode="float").astype(np.float32)
        pt_colors[invalid, 3] = 0.0
        self.scatter.setData(pos=gl_pts, color=pt_colors)

        # Animated rays from sensor lens to each point
        ray_pos = np.zeros((TOTAL_ZONES * 2, 3), dtype=np.float32)
        ray_pos[1::2] = gl_pts                      # endpoints

        ray_color = np.zeros((TOTAL_ZONES * 2, 4), dtype=np.float32)
        # Origin vertex: same hue, lower alpha (beam fades from sensor)
        origin_col = pt_colors.copy()
        origin_col[:, 3] *= 0.10
        end_col    = pt_colors.copy()
        end_col[:, 3] *= 0.55
        ray_color[0::2] = origin_col
        ray_color[1::2] = end_col
        self.rays.setData(pos=ray_pos, color=ray_color)

        # ── Experimental 6-DOF pose: feed sensor-frame points to estimator ─
        valid_mask = ~invalid
        pose_updated = self.pose_estimator.update(points_sensor, valid_mask)
        if pose_updated:
            self.world_trail.append(self.pose_estimator.world_t.copy())

            # Stamp this frame's valid points into the world-frame cloud memory.
            # world_p = R_world @ sensor_p + t_world  (per row)
            valid_sensor_pts = points_sensor[valid_mask]
            world_pts        = (valid_sensor_pts @ self.pose_estimator.world_R.T
                                + self.pose_estimator.world_t)
            world_cols       = pt_colors[valid_mask].copy()
            world_cols[:, 3] = 1.0
            self.world_cloud.append((world_pts, world_cols))

        # ── Trail with per-vertex alpha fade (tail fades to transparent) ────
        if len(self.world_trail) >= 2:
            local = self.pose_estimator.trail_in_current_frame(np.array(self.world_trail))
            trail_gl = np.column_stack([local[:, 0], local[:, 2], local[:, 1]]).astype(np.float32)
            n = len(trail_gl)
            trail_colors = np.empty((n, 4), dtype=np.float32)
            trail_colors[:, 0] = 1.00
            trail_colors[:, 1] = 0.85
            trail_colors[:, 2] = 0.30
            trail_colors[:, 3] = np.linspace(0.05, 0.95, n)  # tail -> head
            self.trail_line.setData(pos=trail_gl, color=trail_colors)
            self.trail_head.setData(pos=trail_gl[-1:])
        else:
            self.trail_line.setData(pos=np.zeros((1, 3), dtype=np.float32),
                                    color=np.zeros((1, 4), dtype=np.float32))
            self.trail_head.setData(pos=np.zeros((1, 3), dtype=np.float32))

        # ── Accumulated world-frame cloud, transformed back into current
        #    sensor frame and faded by age. Old observations slide off to
        #    the side as the sensor rotates → cone effectively wraps around.
        if len(self.world_cloud) >= 1:
            n_frames = len(self.world_cloud)
            R_inv    = self.pose_estimator.world_R   # so local = (world - t) @ R_world
            t_w      = self.pose_estimator.world_t

            local_chunks  = []
            colour_chunks = []
            for i, (wpts, base_cols) in enumerate(self.world_cloud):
                age_norm = (n_frames - 1 - i) / max(1, n_frames - 1)  # 0 newest, 1 oldest
                local = (wpts - t_w) @ R_inv
                cols = base_cols.copy()
                cols[:, 3] = (1.0 - age_norm) * 0.35
                local_chunks.append(local)
                colour_chunks.append(cols)

            cloud = np.concatenate(local_chunks, axis=0)
            cols  = np.concatenate(colour_chunks, axis=0).astype(np.float32)
            cloud_gl = np.column_stack([cloud[:, 0], cloud[:, 2], cloud[:, 1]]).astype(np.float32)
            self.world_scatter.setData(pos=cloud_gl, color=cols)

        self.frame_n += 1
        n_invalid = int(invalid.sum())
        any_valid = n_invalid < 64
        cum_t  = self.pose_estimator.cumulative_translation_mm()
        cum_r  = self.pose_estimator.cumulative_rotation_deg()
        if any_valid:
            avg_valid = float(np.nanmean(np.where(invalid, np.nan, self.smoothed)))
            self.status.showMessage(
                f"Frame {self.frame_n:>5d}   |   "
                f"valid {64 - n_invalid:>2d}/64   |   "
                f"mean {avg_valid:6.0f} mm   |   "
                f"pose: dt={cum_t:7.0f} mm, dr={cum_r:5.1f} deg "
                f"(rejected {self.pose_estimator.frames_rejected})"
            )
        else:
            self.status.showMessage(
                f"Frame {self.frame_n:>5d}   |   valid 0/64   |   pose paused"
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
