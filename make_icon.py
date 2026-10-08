"""Draws icon.ico (stacked pages) with Qt. Run once before building."""

import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

app = QGuiApplication(sys.argv)
S = 256
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
for dx, dy, shade in ((54, 18, "#b9c3cf"), (36, 38, "#dde3ea")):
    p.setPen(QPen(QColor("#5b6675"), 6))
    p.setBrush(QColor(shade))
    p.drawRoundedRect(QRectF(dx, dy, 150, 196), 14, 14)
p.setPen(QPen(QColor("#5b6675"), 6))
p.setBrush(QColor("white"))
p.drawRoundedRect(QRectF(18, 58, 150, 196 - 4), 14, 14)
p.setPen(Qt.NoPen)
p.setBrush(QColor("#d6453d"))
p.drawRoundedRect(QRectF(34, 168, 118, 60), 10, 10)
p.setPen(QColor("white"))
f = QFont("Segoe UI", 34)
f.setBold(True)
p.setFont(f)
p.drawText(QRectF(34, 168, 118, 60), Qt.AlignCenter, "PDF")
p.setPen(QPen(QColor("#9aa5b3"), 8))
for y in (90, 116, 142):
    p.drawLine(42, y, 144, y)
p.end()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
print("saved" if img.save(out) else "FAILED", out)
