"""Draws the app icon (stacked pages) with Qt: icon.ico for Windows and a
1024px icon.png that the macOS build turns into the app bundle's icon.
Run before building (build.ps1 does it); commit both files."""

import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen


def draw(size):
    """The artwork is laid out on a 256px grid and scaled to `size`."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.scale(size / 256, size / 256)
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
    f = QFont("Segoe UI")
    f.setPixelSize(45)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(34, 168, 118, 60), Qt.AlignCenter, "PDF")
    p.setPen(QPen(QColor("#9aa5b3"), 8))
    for y in (90, 116, 142):
        p.drawLine(42, y, 144, y)
    p.end()
    return img


app = QGuiApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
for name, size in (("icon.ico", 256), ("icon.png", 1024)):
    out = os.path.join(here, name)
    print("saved" if draw(size).save(out) else "FAILED", out)
