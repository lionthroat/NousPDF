# Nous PDF

A lightweight desktop PDF viewer with the one Acrobat feature that should never
have been paywalled: a page panel where you can rearrange, duplicate, delete
and rotate pages.

## What it does

- Opens PDFs in a scrolling view (fit width by default, Ctrl+wheel to zoom)
- **Page panel** on the left:
  - drag pages to reorder (Shift/Ctrl-click to move several at once)
  - **Duplicate** (Ctrl+D) puts copies right after the selection
  - **Delete** (Del)
  - **Rotate Left / Right** (Ctrl+Shift+R / Ctrl+R)
  - **Drag PDFs from Explorer onto the panel** to merge them in: a line shows
    where they'll land, several files go in in order, and it's one undo step
    (dropping on the big page view opens the file instead)
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

## Build the .exe

First time on a new machine (needs Python 3.14):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then, from the project folder (close Nous PDF first, or the old exe can't be replaced):

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Output: `dist\NousPDF\NousPDF.exe` (keep the whole `dist\NousPDF` folder
together; the exe needs the `_internal` folder next to it).

Run from source instead: `.venv\Scripts\python.exe nouspdf.py [file.pdf]`

Tests: `.venv\Scripts\python.exe tests\test_pages.py` (also `test_find_merge.py`,
`test_select.py`). Each opens real windows for a few seconds and prints OK.

## Make it the default PDF app

Right-click any PDF → **Open with** → **Choose another app** → scroll down to
**Choose an app on your PC** → pick `dist\NousPDF\NousPDF.exe` → **Always**.

(Or Settings → Apps → Default apps → type `.pdf` → choose the exe the same way.)

Rebuilding puts the exe back at the same path, so the association keeps working.

## Built on

- [PyMuPDF](https://pymupdf.readthedocs.io/) (MuPDF): rendering and page editing. AGPL-3.0.
- [PySide6](https://doc.qt.io/qtforpython-6/) (Qt): the window. LGPL-3.0.

Because PyMuPDF is AGPL, publishing this means licensing it AGPL-3.0 too,
which suits an open-source Acrobat replacement fine.
