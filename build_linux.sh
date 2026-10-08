#!/usr/bin/env bash
# Builds nous-pdf_<version>_amd64.deb for Linux Mint / Ubuntu / Debian.
# Run on Linux from the project folder, with the venv set up
# (python3 -m venv .venv && .venv/bin/pip install -r requirements.txt):
#   bash build_linux.sh
# GitHub builds it on version tags (see .github/workflows/build.yml).
#
# The package installs the app to /opt/nous-pdf, a `nous-pdf` command,
# a menu entry, icons, and registers it for PDFs (Open With / default app).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
VERSION=$(tr -d '[:space:]' < VERSION)
PKG=nous-pdf

"$PY" -m PyInstaller --noconfirm --clean --windowed --name NousPDF \
    --add-data "$PWD/icon.ico:." \
    --distpath dist --workpath build --specpath build \
    --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf \
    "$PWD/nouspdf.py"

STAGE=build/deb
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/opt" "$STAGE/usr/bin" "$STAGE/usr/share/applications"
cp -a dist/NousPDF "$STAGE/opt/$PKG"
ln -s "/opt/$PKG/NousPDF" "$STAGE/usr/bin/$PKG"

# Icons at the sizes desktops look for
QT_QPA_PLATFORM=offscreen "$PY" - "$STAGE" "$PKG" <<'EOF'
import os, sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage
app = QGuiApplication(sys.argv[:1])
stage, pkg = sys.argv[1], sys.argv[2]
src = QImage("icon.png")
for size in (48, 64, 128, 256, 512):
    d = os.path.join(stage, f"usr/share/icons/hicolor/{size}x{size}/apps")
    os.makedirs(d, exist_ok=True)
    src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(os.path.join(d, pkg + ".png"))
EOF

cat > "$STAGE/usr/share/applications/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Nous PDF
GenericName=PDF Viewer
Comment=View PDFs and rearrange, duplicate, delete and rotate pages
Exec=$PKG %f
Icon=$PKG
Terminal=false
Categories=Office;Viewer;
MimeType=application/pdf;
Keywords=PDF;pages;viewer;merge;
StartupWMClass=NousPDF
EOF

SIZE_KB=$(du -sk "$STAGE" | cut -f1)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: lionthroat <lionthroat@users.noreply.github.com>
Homepage: https://nouspdf.lionthroat.com
Installed-Size: $SIZE_KB
Depends: libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libxkbcommon-x11-0, libegl1, libgl1, libfontconfig1, libdbus-1-3
Description: Lightweight PDF viewer with a page panel
 Nous PDF opens PDFs and lets you rearrange, duplicate, delete and rotate
 pages, merge PDFs by dragging them in, find text, and select and copy text.
 Free and open source (AGPL-3.0).
EOF

# Files root-owned and world-readable, whatever the build machine's umask was
chmod -R u+rwX,go+rX,go-w "$STAGE"
OUT="${PKG}_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "Built: $OUT ($(du -h "$OUT" | cut -f1))"
