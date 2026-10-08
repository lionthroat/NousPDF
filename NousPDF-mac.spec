# PyInstaller recipe for the macOS app bundle, "Nous PDF.app".
# Built by .github/workflows/build-mac.yml on GitHub's Mac machines:
#   python -m PyInstaller --noconfirm --clean NousPDF-mac.spec
# (needs Pillow, which turns icon.png into the .icns macOS wants)
import os

root = SPECPATH
with open(os.path.join(root, "VERSION")) as f:
    VERSION = f.read().strip()

a = Analysis(
    [os.path.join(root, "nouspdf.py")],
    datas=[(os.path.join(root, "icon.ico"), ".")],
    excludes=["PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf",
              "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NousPDF", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="NousPDF")
app = BUNDLE(
    coll,
    name="Nous PDF.app",
    icon=os.path.join(root, "icon.png"),
    bundle_identifier="com.lionthroat.nouspdf",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Nous PDF",
        "CFBundleShortVersionString": VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        # Lets Finder offer Nous PDF in "Open With" and as the default for PDFs
        "CFBundleDocumentTypes": [{
            "CFBundleTypeName": "PDF Document",
            "CFBundleTypeRole": "Editor",
            "LSItemContentTypes": ["com.adobe.pdf"],
            "LSHandlerRank": "Alternate",
        }],
    },
)
