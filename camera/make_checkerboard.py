#!/usr/bin/env python3
"""
make_checkerboard.py - generate the calibration target PDF.

Produces a 9 x 12 square checkerboard of 20.0 mm squares = 8 x 11 INNER CORNERS,
sized to print on both US Letter and A4 with comfortable margins.

Inner corners are what OpenCV actually detects: the X-junctions where four squares
meet. A 9-wide, 12-tall grid of squares has 8 x 11 of them. Those two numbers go
into the capture and calibration scripts as BOARD = (8, 11).

Why 8 x 11 (one even, one odd): a board whose two corner counts have different
parity has no 180-degree rotational ambiguity, so the detector always agrees with
itself about which corner is first.

PRINT AT 100% / "ACTUAL SIZE". Do NOT use "Fit to page" / "Scale to fit" - that
silently resizes the squares and every distance you measure afterwards is wrong.
The PDF prints a ruler you can check with a real ruler before using it.

Usage:  python camera/make_checkerboard.py
Output: camera/checkerboard_8x11_20mm.pdf
"""
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

SQ_MM = 20.0          # square size in millimetres - MEASURE THIS AFTER PRINTING
COLS, ROWS = 9, 12    # squares
INNER = (COLS - 1, ROWS - 1)   # -> (8, 11) inner corners

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   f"checkerboard_{INNER[0]}x{INNER[1]}_{int(SQ_MM)}mm.pdf")

PW, PH = letter
bw, bh = COLS * SQ_MM * mm, ROWS * SQ_MM * mm
x0, y0 = (PW - bw) / 2.0, (PH - bh) / 2.0 + 6 * mm   # nudge up, leave room for the ruler

c = canvas.Canvas(OUT, pagesize=letter)
c.setTitle(f"Checkerboard {INNER[0]}x{INNER[1]} inner corners, {SQ_MM:g} mm squares")

# --- the board -------------------------------------------------------------
c.setFillColorRGB(0, 0, 0)
for r in range(ROWS):
    for col in range(COLS):
        if (r + col) % 2 == 0:
            c.rect(x0 + col * SQ_MM * mm, y0 + r * SQ_MM * mm,
                   SQ_MM * mm, SQ_MM * mm, stroke=0, fill=1)

# Thin outline so you can see whether the printer clipped an edge.
c.setStrokeColorRGB(0.6, 0.6, 0.6)
c.setLineWidth(0.4)
c.rect(x0, y0, bw, bh, stroke=1, fill=0)

# --- header ----------------------------------------------------------------
c.setFillColorRGB(0, 0, 0)
c.setFont("Helvetica-Bold", 11)
c.drawCentredString(PW / 2, y0 + bh + 16 * mm,
                    f"{INNER[0]} x {INNER[1]} inner corners   |   {SQ_MM:g} mm squares")
c.setFont("Helvetica-Bold", 9)
c.setFillColorRGB(0.75, 0, 0)
c.drawCentredString(PW / 2, y0 + bh + 10 * mm,
                    'PRINT AT 100% / "ACTUAL SIZE" - do NOT scale to fit')

# --- verification ruler ----------------------------------------------------
# Measure this with a real ruler. If it is not exactly 100 mm the print was
# scaled; either reprint or set SQ_MM to (20.0 * measured / 100.0) and note it.
ry = y0 - 14 * mm
c.setFillColorRGB(0, 0, 0)
c.setStrokeColorRGB(0, 0, 0)
c.setLineWidth(0.8)
c.line(x0, ry, x0 + 100 * mm, ry)
for i in range(11):
    x = x0 + i * 10 * mm
    c.line(x, ry, x, ry + (4 * mm if i % 5 == 0 else 2.5 * mm))
c.setFont("Helvetica", 8)
c.drawString(x0, ry - 9, "0")
c.drawString(x0 + 100 * mm - 10, ry - 9, "100 mm")
c.setFont("Helvetica-Bold", 8)
c.drawString(x0 + 108 * mm, ry - 3,
             "<- this must measure exactly 100 mm with a real ruler")

c.setFont("Helvetica", 7.5)
c.setFillColorRGB(0.3, 0.3, 0.3)
c.drawString(x0, ry - 22,
             "Glue to rigid flat board (foam-core / clipboard). Flatness matters more than print quality.")
c.drawString(x0, ry - 32,
             "Matte paper only - glossy paper reflects and the corner detector fails.")

c.showPage()
c.save()
print("wrote", OUT)
print(f"BOARD = {INNER}   SQUARE_MM = {SQ_MM}")
print("Print at 100%, verify the 100 mm ruler, then glue it flat.")
