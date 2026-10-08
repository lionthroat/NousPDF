# Nous PDF

A lightweight desktop PDF viewer with the one Acrobat feature that should never
have been paywalled: a page panel where you can rearrange, duplicate, delete
and rotate pages. Free and open source, for Windows and Mac.

## Download

**Step-by-step instructions: https://nouspdf.lionthroat.com**

Or straight from the [latest release](https://github.com/lionthroat/NousPDF/releases/latest):

- **Windows 10/11:** `NousPDF-Setup.exe`. Installs for your account only (no admin needed).
- **Mac, M1 and newer:** `NousPDF-mac-apple-silicon.zip`
- **Mac, Intel:** `NousPDF-mac-intel.zip`

Nous PDF isn't signed with a paid Microsoft or Apple certificate, so both
systems warn you once before the first run:

- **Windows:** "Windows protected your PC" → **More info** → **Run anyway**.
  Your browser may also ask whether to keep the download: **Keep** → **Keep anyway**.
- **Mac:** after the first "can't be opened" message, open **System Settings →
  Privacy & Security**, scroll down, and click **Open Anyway** next to Nous PDF.
  If macOS ever says the app "is damaged", run this once in Terminal:
  `xattr -cr "/Applications/Nous PDF.app"`

**Make it your default PDF app:**

- **Windows:** right-click any PDF → **Open with** → **Choose another app** →
  **Nous PDF** → **Always**.
- **Mac:** select any PDF in Finder → **File → Get Info** → **Open with: Nous PDF**
  → **Change All…**

## What it does

- Opens PDFs in a scrolling view (fit width by default, Ctrl+wheel to zoom)
- **Page panel** on the left:
  - drag pages to reorder (Shift/Ctrl-click to move several at once)
  - **Duplicate** (Ctrl+D) puts copies right after the selection
  - **Delete** (Del)
  - **Rotate Left / Right** (Ctrl+Shift+R / Ctrl+R)
  - **Drag PDFs from Explorer/Finder onto the panel** to merge them in: a line
    shows where they'll land, several files go in in order, and it's one undo
    step (dropping on the big page view opens the file instead)
  - **Insert from PDF…** (Ctrl+I) does the same from a file picker, after the selection
  - **Save Selected Pages As…** (Ctrl+E) extracts pages to a new file
  - right-click a page for the same menu
- **Select & copy text**: drag across text (the cursor turns into a text
  cursor over it), double-click for a word, Shift+click to extend, drag past
  the window edge to keep scrolling, works across pages. Ctrl+C or right-click
  → Copy. Selection is just for copying; nothing is saved into the PDF.
- **Find** (Ctrl+F): searches as you type (not case-sensitive), highlights every
  match, Enter / Shift+Enter or F3 / Shift+F3 to step through, Esc to close.
  Scanned PDFs that are just pictures of text have nothing to find.
- Undo / Redo (Ctrl+Z / Ctrl+Y) for every page edit
- Nothing touches the file until you Save (Ctrl+S) or Save As (Ctrl+Shift+S);
  it asks before closing with unsaved changes
- Bookmarks, links and annotations are kept where the pages still exist
- Password-protected PDFs open after you enter the password (the saved copy is
  not password-protected)
- Drag a PDF onto the window to open it

**On a Mac:** Ctrl shortcuts are Cmd (Cmd+F, Cmd+C…), next/previous match is
Cmd+G / Shift+Cmd+G, Backspace deletes pages, pinch zooms, and each PDF opens
in its own window.

## Building it yourself

Windows, with Python 3.14, from the project folder:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File build.ps1
```

That makes `dist\NousPDF\NousPDF.exe` (keep the whole `dist\NousPDF` folder
together; the exe needs the `_internal` folder next to it), plus
`installer-output\NousPDF-Setup.exe` if [Inno Setup 6](https://jrsoftware.org/isinfo.php)
is installed. Close Nous PDF before rebuilding, or the old exe can't be replaced.

Run from source instead: `.venv\Scripts\python.exe nouspdf.py [file.pdf]`

Tests: `.venv\Scripts\python.exe tests\test_pages.py` (also `test_find_merge.py`,
`test_select.py`). Each opens real windows for a few seconds and prints OK.

**Releases** are built by GitHub Actions (`.github/workflows/build.yml`) on
Windows and on Apple Silicon and Intel Macs:

1. Put the new version in the `VERSION` file (e.g. `0.2.1`) and commit.
2. `git tag v0.2.1`, then `git push` and `git push --tags`.

The build runs the tests, builds the Windows installer and checks it by
installing, launching and uninstalling it, builds both Mac apps, and publishes
a GitHub Release with all three files. You can also build without releasing
from the **Actions** tab → **Build** → **Run workflow** (files land under that
run's Artifacts).

## Built on

- [PyMuPDF](https://pymupdf.readthedocs.io/) (MuPDF): rendering and page editing. AGPL-3.0.
- [PySide6](https://doc.qt.io/qtforpython-6/) (Qt): the window. LGPL-3.0.
- [PyInstaller](https://pyinstaller.org/) and [Inno Setup](https://jrsoftware.org/isinfo.php): packaging.

## License

Nous PDF is free software under the [GNU Affero General Public License v3.0](LICENSE).
You can use, change and share it; if you share a changed version, share its
source under the same license.
