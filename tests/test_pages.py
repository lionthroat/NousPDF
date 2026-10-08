"""Page panel: open, duplicate, delete, rotate, drag-reorder, undo/redo, save (incl. over the open file).

Run from the project folder:  .venv\Scripts\python.exe tests\test_pages.py
Opens real windows briefly; prints OK at the end."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from PySide6.QtWidgets import QApplication, QMessageBox
import nouspdf as app_mod

here = tempfile.mkdtemp(prefix="nouspdf-test-")   # sample PDFs + screenshots go here
src = os.path.join(here, "sample.pdf")
d = pymupdf.open()
for i in range(6):
    pg = d.new_page()
    pg.insert_text((72, 120), f"Page {i+1}", fontsize=48)
d.set_toc([[1, "Start", 1], [1, "Four", 4]])
d.save(src)

app = QApplication(sys.argv)
w = app_mod.MainWindow(); w.resize(1100, 800); w.show()
w.open_path(src)
for _ in range(50): w.render_thumb_batch(); app.processEvents()
assert len(w.refs) == 6

def select(rows):
    w.pages.clearSelection()
    for r in rows: w.pages.item(r).setSelected(True)

select([1, 2]); w.duplicate_selected()           # 1 2 3 2 3 4 5 6
assert [r[1] for r in w.refs] == [0,1,2,1,2,3,4,5], w.refs
select([0]); w.delete_selected()                  # 2 3 2 3 4 5 6
select([0]); w.rotate_selected(90)
# simulate a drag: move last item to the front
it = w.pages.takeItem(w.pages.count() - 1); w.pages.insertItem(0, it); w.on_drag_reorder()
assert [r[1] for r in w.refs] == [5,1,2,1,2,3,4], w.refs
w.undo(); assert [r[1] for r in w.refs] == [1,2,1,2,3,4,5]
w.redo(); assert w.is_dirty()
select([0]); assert w.selected_rows() == [0]
w.delete_selected  # keep
w.refs = list(w.refs)
out = os.path.join(here, "out.pdf")
assert w.save_to(out)
o = pymupdf.open(out)
texts = [o[i].get_text().strip() for i in range(o.page_count)]
print(texts, [o[i].rotation for i in range(o.page_count)], o.get_toc())
assert texts == ["Page 6","Page 2","Page 3","Page 2","Page 3","Page 4","Page 5"]
assert o[1].rotation == 90
assert not w.is_dirty()
o.close()
# saving over the original that's open
w.open_path(src); select([5]); w.delete_selected(); assert w.save_to(src)
assert pymupdf.open(src).page_count == 5
w.open_path(out)
for _ in range(50): w.render_thumb_batch(); app.processEvents()
select([1]); w.rotate_selected(90)
import time
t=time.time()
while time.time()-t<1.5: app.processEvents()
v=w.viewer
print("zoom",v.zoom,"scroll",v.verticalScrollBar().value(),[ (l.y(),l.width(),l.height(),l.rendered_at) for l in v.labels[:3]])
w.grab().save(os.path.join(here, "shot.png"))
print("OK")
