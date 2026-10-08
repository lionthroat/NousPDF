"""Ctrl+F search + highlight placement, and dropping PDFs from Explorer onto the page panel.

Run from the project folder:  .venv\Scripts\python.exe tests\test_find_merge.py
Opens real windows briefly; prints OK at the end."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDropEvent, QDragEnterEvent, QDragMoveEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import nouspdf as app_mod

here = tempfile.mkdtemp(prefix="nouspdf-test-")   # sample PDFs + screenshots go here

def make(path, label, n, rotate_second=False):
    d = pymupdf.open()
    for i in range(n):
        pg = d.new_page()
        pg.insert_text((72, 120), f"{label} page {i+1}", fontsize=36)
        pg.insert_text((72, 400), "invoice total", fontsize=20)
    if rotate_second:
        d[1].set_rotation(90)
    d.save(path)

main_pdf = os.path.join(here, "main.pdf"); make(main_pdf, "Main", 4, rotate_second=True)
a_pdf = os.path.join(here, "a.pdf"); make(a_pdf, "Alpha", 2)
b_pdf = os.path.join(here, "b.pdf"); make(b_pdf, "Beta", 3)

app = QApplication(sys.argv)
import threading, traceback, faulthandler
faulthandler.dump_traceback_later(40, exit=True)
from PySide6.QtCore import QTimer
def watchdog():
    m = app.activeModalWidget()
    if m is not None:
        print("MODAL:", type(m).__name__, getattr(m, "text", lambda: "")(), flush=True); m.close()
wd = QTimer(); wd.timeout.connect(watchdog); wd.start(2000)
w = app_mod.MainWindow(); w.resize(1100, 800); w.show()
w.open_path(main_pdf)
def settle(t=0.6):
    end = time.time() + t
    while time.time() < end: app.processEvents()
settle()

# --- find ---
w.activateWindow(); w.raise_(); QTest.qWaitForWindowActive(w, 3000)
print("active:", w.isActiveWindow())
QTest.keySequence(w, "Ctrl+F"); settle(0.1)
print("visible:", w.find_bar.isVisible(), "focus:", w.find_edit.hasFocus())
if not w.find_bar.isVisible(): w.show_find()
QTest.keyClicks(w.find_edit, "invoice"); settle(0.5)
assert len(w.hits) == 4, w.hits
print("count:", w.find_count.text())
QTest.keyClick(w.find_edit, Qt.Key_Return); assert w.hit_pos == 1
QTest.keyClick(w.find_edit, Qt.Key_Return, Qt.ShiftModifier); assert w.hit_pos == 0
QTest.keyClick(w.find_edit, Qt.Key_Return, Qt.ShiftModifier); assert w.hit_pos == 3  # wraps
# Delete inside the find box must not delete pages
QTest.keyClick(w.find_edit, Qt.Key_End); QTest.keyClick(w.find_edit, Qt.Key_Delete)
QTest.keyClick(w.find_edit, Qt.Key_Backspace)
assert len(w.refs) == 4, "Delete key leaked to page deletion"
QTest.keyClicks(w.find_edit, "e"); settle(0.5)

# highlight lands on the text, including on the rotated page (row 1) with an
# extra user rotation on top
w.pages.clearSelection(); w.pages.item(1).setSelected(True); w.rotate_selected(90)
assert len(w.hits) == 4
for row in range(4):
    (_, rect), = w.hits_by_row[row]
    scale = 1.5
    img = w.paint_hits(w.render(w.refs[row], scale), row, scale)
    hr = w.hit_rect(row, rect, scale)
    # sample a highlight pixel just inside the rect corner (background, not glyph)
    c = QColor(img.pixel(int(hr.left()) + 1, int(hr.top()) + 1))
    assert c.blue() < 120 and c.red() > 200, (row, c.name(), hr)
    # and the same spot without highlights is white paper
    c0 = QColor(w.render(w.refs[row], scale).pixel(int(hr.left()) + 1, int(hr.top()) + 1))
    assert c0.name() == "#ffffff", (row, c0.name())
print("highlights placed correctly on normal + rotated pages")

# duplicating a page duplicates its matches
w.pages.clearSelection(); w.pages.item(0).setSelected(True); w.duplicate_selected()
assert len(w.hits) == 5
w.undo(); w.undo(); assert len(w.hits) == 4 and len(w.refs) == 4

QTest.keyClick(w.find_edit, Qt.Key_Escape)
assert not w.find_bar.isVisible() and not w.hits

# --- drop two PDFs from "Explorer" between page 1 and page 2 ---
md = QMimeData(); md.setUrls([QUrl.fromLocalFile(a_pdf), QUrl.fromLocalFile(b_pdf)])
r1 = w.pages.visualItemRect(w.pages.item(1))
pos = QPointF(r1.center().x(), r1.top() + 5)          # upper half of row 1 -> insert at 1
vp = w.pages.viewport()
ev = QDragEnterEvent(pos.toPoint(), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev); assert ev.isAccepted()
ev = QDragMoveEvent(pos.toPoint(), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev); assert ev.isAccepted() and w.pages.file_drop_row == 1
w.grab().save(os.path.join(here, "drop_line.png"))
ev = QDropEvent(pos, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(vp, ev); settle(0.3)
labels = [w.sources[s][p].get_text().split("\n")[0] for s, p, _ in w.refs]
print(labels)
assert labels == ["Main page 1", "Alpha page 1", "Alpha page 2", "Beta page 1",
                  "Beta page 2", "Beta page 3", "Main page 2", "Main page 3", "Main page 4"]
assert w.selected_rows() == [1, 2, 3, 4, 5]
w.undo(); assert len(w.refs) == 4                     # one undo step for the whole drop

# dropping on an empty window opens the first file and appends the rest
w2 = app_mod.MainWindow(); w2.show()
w2.on_files_dropped([a_pdf, b_pdf], 0)
assert w2.path.endswith("a.pdf") and len(w2.refs) == 5

# save the merge and search the saved file
w.redo(); out = os.path.join(here, "merged.pdf"); assert w.save_to(out)
assert pymupdf.open(out).page_count == 9

# screenshot with search active
QTest.keySequence(w, "Ctrl+F"); QTest.keyClicks(w.find_edit, "total"); settle(0.6)
QTest.keyClick(w.find_edit, Qt.Key_Return); settle(0.4)
w.grab().save(os.path.join(here, "find.png"))
print("count:", w.find_count.text())
w2.close()
print("OK")
