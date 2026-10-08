"""Text selection: drag, double-click, rotated pages, across pages, Ctrl+C, hover cursor.

Run from the project folder:  .venv\Scripts\python.exe tests\test_select.py
Opens real windows briefly; prints OK at the end."""
import os, sys, tempfile, time, faulthandler
faulthandler.dump_traceback_later(60, exit=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import nouspdf as app_mod

here = tempfile.mkdtemp(prefix="nouspdf-test-")   # sample PDFs + screenshots go here
src = os.path.join(here, "sel.pdf")
d = pymupdf.open()
for i in range(3):
    pg = d.new_page()
    pg.insert_text((72, 120), f"Main page {i+1}", fontsize=36)
    pg.insert_text((72, 400), "invoice total", fontsize=20)
d[1].set_rotation(90)
d.save(src)

app = QApplication(sys.argv)
w = app_mod.MainWindow(); w.resize(1100, 900); w.show()
w.open_path(src)
def settle(t=0.5):
    end = time.time() + t
    while time.time() < end: app.processEvents()
settle()
w.activateWindow(); QTest.qWaitForWindowActive(w, 3000)
v = w.viewer; c = v.container

def word_pos(row, word, side, dy=0.5):
    """Container point at the start/end (or middle) of a word, in reading
    direction, wherever rotation puts that on screen."""
    src, pno, rot = w.refs[row]
    page = w.sources[src][pno]
    rect = page.search_for(word)[0]
    x = {"left": rect.x0 + 1, "right": rect.x1 - 1, "mid": (rect.x0 + rect.x1) / 2}[side]
    p = pymupdf.Point(x, rect.y0 + rect.height * dy)
    m = pymupdf.Matrix(v.zoom, v.zoom).prerotate(rot)
    origin = (page.rect * m).tl
    q = p * page.rotation_matrix * m
    lab = v.labels[row]
    return QPoint(int(lab.x() + q.x - origin.x), int(lab.y() + q.y - origin.y))

def mouse(kind, pos, buttons=Qt.LeftButton):
    t = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
         "release": QEvent.MouseButtonRelease, "dbl": QEvent.MouseButtonDblClick}[kind]
    btn = Qt.NoButton if kind == "move" else Qt.LeftButton
    gp = c.mapToGlobal(pos)
    ev = QMouseEvent(t, QPointF(pos), QPointF(gp), btn, buttons, Qt.NoModifier)
    QApplication.sendEvent(c, ev)

def drag(a, b):
    mouse("press", a); mouse("move", (a + b) / 2); mouse("move", b); mouse("release", b)

def scroll_into_view(row):
    v.scroll_to(row); settle(0.3)

# 1. plain drag on page 1
scroll_into_view(0)
drag(word_pos(0, "Main", "left"), word_pos(0, "1", "right"))
print(repr(v.selected_text())); assert v.selected_text() == "Main page 1"

# 2. Ctrl+C puts it on the clipboard
QApplication.clipboard().clear()
QTest.keySequence(w, "Ctrl+C"); settle(0.1)
assert QApplication.clipboard().text() == "Main page 1", QApplication.clipboard().text()

# 3. selection is drawn on the page image
settle(0.2)
lab = v.labels[0]
img = lab.pixmap().toImage()
dpr = img.devicePixelRatio()
pt = word_pos(0, "Main", "left") - lab.pos() + QPoint(2, 0)
col = QColor(img.pixel(int(pt.x() * dpr), int((pt.y() - 18) * dpr)))
print("selection pixel:", col.name()); assert col.blue() > col.red() + 40

# 4. double-click a word
mouse("dbl", word_pos(0, "invoice", "mid"))
assert v.selected_text() == "invoice", v.selected_text()

# 5. rotated page (/Rotate 90) plus a user rotation on top
w.pages.clearSelection(); w.pages.item(1).setSelected(True); w.rotate_selected(90); settle(0.3)
scroll_into_view(1)
drag(word_pos(1, "invoice", "left"), word_pos(1, "total", "right"))
print(repr(v.selected_text())); assert v.selected_text() == "invoice total"

# 6. across two pages: from "total" on page 1 to the end of "Main page 2"
scroll_into_view(0)
w.pages.clearSelection()
v.set_selection(v.caret_at(word_pos(0, "total", "left")), None)
mouse("press", word_pos(0, "total", "left"))
mouse("move", word_pos(0, "total", "right"))
v.sel_head = None
end = v.caret_at(word_pos(1, "2", "right"))
v.set_selection(v.sel_anchor, end); mouse("release", word_pos(0, "total", "right"))
print(repr(v.selected_text())); assert v.selected_text() == "total\nMain page 2"

# 7. hover cursor
mouse("move", word_pos(0, "Main", "mid"), Qt.NoButton)
assert c.cursor().shape() == Qt.IBeamCursor
lab0 = v.labels[0]
mouse("move", QPoint(lab0.x() + lab0.width() // 2, lab0.y() + lab0.height() - 30), Qt.NoButton)
assert c.cursor().shape() == Qt.ArrowCursor

# 8. click in empty paper clears the selection (click lands on nearest text -> empty selection)
mouse("press", QPoint(lab0.x() + 5, lab0.y() + lab0.height() - 5)); mouse("release", QPoint(lab0.x() + 5, lab0.y() + lab0.height() - 5))
assert v.selected_text() == ""

# 9. Delete/typing in the find box still fine and Ctrl+C in the find box copies the find text
w.show_find(); QTest.keyClicks(w.find_edit, "page"); w.find_edit.selectAll()
QTest.keySequence(w.find_edit, "Ctrl+C"); assert QApplication.clipboard().text() == "page"
w.hide_find()

# screenshot of a selection
scroll_into_view(0)
drag(word_pos(0, "page", "left"), word_pos(0, "invoice", "right")); settle(0.3)
print(repr(v.selected_text()))
w.grab().save(os.path.join(here, "select.png"))
print("OK")
