"""Nous PDF: a lightweight desktop PDF viewer with a page panel.

Rearrange pages by dragging, duplicate, delete, rotate, insert pages from
other PDFs (menu or drag-and-drop), find text, and save. Pages are held as (source, page number, extra rotation)
references and only written out when you save, so nothing touches the file on
disk until then.
"""

import os
import sys

import pymupdf
from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QCursor, QFont, QIcon, QImage,
                           QKeySequence, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QScrollArea, QSplitter, QToolBar,
                               QToolButton, QVBoxLayout, QWidget)

APP_NAME = "Nous PDF"
PDF_FILTER = "PDF files (*.pdf);;All files (*)"

# Thumbnail panel geometry
THUMB_BOX = QSize(130, 160)                 # where the page image fits
ICON_SIZE = QSize(THUMB_BOX.width() + 10, THUMB_BOX.height() + 26)

ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75,
              2.0, 2.5, 3.0, 4.0]
PAGE_GAP = 14


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def to_qimage(pix):
    fmt = QImage.Format_RGB888 if pix.n == 3 else QImage.Format_Grayscale8
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


# A page reference is a plain tuple: (source index, page number, extra rotation)
# Tuples are immutable, so an undo snapshot is just a copy of the list.


class PageList(QListWidget):
    """The page panel. Drag pages to reorder (emits orderChanged after a drop);
    drop PDF files from outside to insert them (emits filesDropped)."""

    orderChanged = Signal()
    filesDropped = Signal(list, int)     # paths, row to insert at

    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.ListMode)
        self.setFlow(QListWidget.TopToBottom)
        self.setIconSize(ICON_SIZE)
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(ICON_SIZE.width() + 30)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_drop_row = None        # where the insertion line is drawn

    @staticmethod
    def dropped_pdfs(event):
        md = event.mimeData()
        if event.source() is not None or not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.toLocalFile().lower().endswith(".pdf")]

    def row_at(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return self.count()
        rect = self.visualRect(idx)
        return idx.row() + (1 if pos.y() > rect.center().y() else 0)

    def set_file_drop_row(self, row):
        self.file_drop_row = row
        self.viewport().update()

    def dragEnterEvent(self, event):
        if self.dropped_pdfs(event):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.dropped_pdfs(event):
            self.set_file_drop_row(self.row_at(event.position().toPoint()))
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.set_file_drop_row(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        paths = self.dropped_pdfs(event)
        if paths:
            row = self.row_at(event.position().toPoint())
            self.set_file_drop_row(None)
            event.setDropAction(Qt.CopyAction)
            event.accept()
            # Open the files after the drag has finished, not inside it
            QTimer.singleShot(0, lambda: self.filesDropped.emit(paths, row))
            return
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)   # page drags always move, never copy
        super().dropEvent(event)
        QTimer.singleShot(0, self.orderChanged.emit)

    def paintEvent(self, event):
        super().paintEvent(event)
        row = self.file_drop_row
        if row is None:
            return
        if self.count() == 0:
            y = 4
        elif row < self.count():
            y = self.visualRect(self.indexFromItem(self.item(row))).top() - 2
        else:
            y = self.visualRect(self.indexFromItem(self.item(self.count() - 1))).bottom() + 3
        p = QPainter(self.viewport())
        p.setPen(QPen(self.palette().highlight().color(), 4))
        p.drawLine(6, y, self.viewport().width() - 6, y)
        p.end()


class PageText:
    """One page's characters in reading order, for selecting and copying text.
    Coordinates are unrotated page coordinates, like search results."""

    def __init__(self, page):
        self.chars = []      # (x0, x1, c, line index)
        self.lines = []      # (first char, end char, Rect)
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", ()):
                start = len(self.chars)
                for span in line["spans"]:
                    for ch in span["chars"]:
                        x0, _, x1, _ = ch["bbox"]
                        self.chars.append((x0, x1, ch["c"], len(self.lines)))
                if len(self.chars) > start:
                    self.lines.append((start, len(self.chars), pymupdf.Rect(line["bbox"])))

    def caret_at(self, pt):
        """Caret (a position between characters) nearest to a point."""
        if not self.lines:
            return None

        def distance(line):
            r = line[2]
            dy = 0 if r.y0 <= pt.y <= r.y1 else min(abs(pt.y - r.y0), abs(pt.y - r.y1))
            dx = 0 if r.x0 <= pt.x <= r.x1 else min(abs(pt.x - r.x0), abs(pt.x - r.x1))
            return dy, dx

        start, end, _ = min(self.lines, key=distance)
        for i in range(start, end):
            x0, x1 = self.chars[i][:2]
            if pt.x < (x0 + x1) / 2:
                return i
        return end

    def over_text(self, pt, pad=3):
        return any(r.x0 - pad <= pt.x <= r.x1 + pad and r.y0 - pad <= pt.y <= r.y1 + pad
                   for _, _, r in self.lines)

    def word_at(self, caret):
        """(start, end) of the word around a caret, within its line."""
        if not self.chars:
            return 0, 0
        i = min(caret, len(self.chars) - 1)
        line = self.chars[i][3]
        start, end = self.lines[line][:2]
        if self.chars[i][2].isspace():
            return i, i + 1
        a, b = i, i + 1
        while a > start and not self.chars[a - 1][2].isspace():
            a -= 1
        while b < end and not self.chars[b][2].isspace():
            b += 1
        return a, b

    def text(self, a, b):
        out, last_line = [], None
        for x0, x1, c, line in self.chars[a:b]:
            if last_line is not None and line != last_line:
                out.append("\n")
            out.append(c)
            last_line = line
        return "".join(out)

    def rects(self, a, b):
        """One highlight rect per line covered by chars a..b."""
        out = []
        i = a
        while i < b:
            line = self.chars[i][3]
            j = min(b, self.lines[line][1])
            r = self.lines[line][2]
            out.append(pymupdf.Rect(self.chars[i][0], r.y0, self.chars[j - 1][1], r.y1))
            i = j
        return out


class Viewer(QScrollArea):
    """Continuous vertical page view. Renders only what's near the screen.
    Drag across text to select it; the selection is (row, caret) to (row, caret)."""

    pageChanged = Signal(int)
    zoomChanged = Signal()

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.zoom = 1.0
        self.fit_width = True
        self.labels = []
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignHCenter)
        self.setStyleSheet("QScrollArea { background: #3a3d41; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: #3a3d41;")
        self.layout_ = QVBoxLayout(self.container)
        self.layout_.setSpacing(PAGE_GAP)
        self.layout_.setContentsMargins(20, 20, 20, 20)
        self.layout_.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setWidget(self.container)

        self.empty = QLabel("Open a PDF (Ctrl+O) or drop one here")
        self.empty.setStyleSheet("color: #c8c8c8; font-size: 16px;")
        self.empty.setAlignment(Qt.AlignCenter)
        self.layout_.addWidget(self.empty)

        self.render_timer = QTimer(self, singleShot=True, interval=30)
        self.render_timer.timeout.connect(self.render_visible)
        self.relayout_timer = QTimer(self, singleShot=True, interval=80)
        self.relayout_timer.timeout.connect(self.apply_sizes)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

        # text selection
        self.sel_anchor = self.sel_head = None     # (row, caret)
        self.selecting = False
        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)
        self.container.setContextMenuPolicy(Qt.CustomContextMenu)
        self.autoscroll_timer = QTimer(self, interval=30)
        self.autoscroll_timer.timeout.connect(self.autoscroll)

    # -- layout -------------------------------------------------------------

    def set_pages(self, refs, keep_page=None):
        for lab in self.labels:
            self.layout_.removeWidget(lab)
            lab.hide()
            lab.deleteLater()
        self.labels = []
        self.sel_anchor = self.sel_head = None
        self.selecting = False
        self.empty.setVisible(not refs)
        for ref in refs:
            lab = QLabel()
            lab.setStyleSheet("background: white;")
            lab.setAlignment(Qt.AlignCenter)
            lab.setAttribute(Qt.WA_TransparentForMouseEvents)   # the container handles the mouse
            lab.ref = ref
            lab.rendered_at = None
            lab.base = None          # rendered page (with search highlights), before selection
            self.layout_.addWidget(lab, 0, Qt.AlignHCenter)
            self.labels.append(lab)
        self.apply_sizes()
        if keep_page is not None and self.labels:
            QTimer.singleShot(0, lambda: self.scroll_to(min(keep_page, len(self.labels) - 1)))

    def max_page_width(self):
        return max((self.win.page_size(lab.ref)[0] for lab in self.labels), default=612)

    def apply_sizes(self):
        if not self.labels:
            return
        if self.fit_width:
            avail = self.viewport().width() - 40 - self.verticalScrollBar().sizeHint().width()
            self.zoom = max(0.1, min(6.0, avail / self.max_page_width()))
        for lab in self.labels:
            w, h = self.win.page_size(lab.ref)
            lab.setFixedSize(int(w * self.zoom), int(h * self.zoom))
            if lab.rendered_at != self.zoom:
                lab.clear()
                lab.rendered_at = None
        self.zoomChanged.emit()
        self.render_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_width:
            self.relayout_timer.start()
        self.render_timer.start()

    # -- zoom ---------------------------------------------------------------

    def set_zoom(self, z):
        page = self.current_page()
        self.fit_width = False
        self.zoom = max(0.1, min(6.0, z))
        self.apply_sizes()
        QTimer.singleShot(0, lambda: self.scroll_to(page))

    def step_zoom(self, direction):
        if direction > 0:
            nxt = next((s for s in ZOOM_STEPS if s > self.zoom + 0.001), ZOOM_STEPS[-1])
        else:
            nxt = next((s for s in reversed(ZOOM_STEPS) if s < self.zoom - 0.001), ZOOM_STEPS[0])
        self.set_zoom(nxt)

    def set_fit_width(self):
        page = self.current_page()
        self.fit_width = True
        self.apply_sizes()
        QTimer.singleShot(0, lambda: self.scroll_to(page))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.step_zoom(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)

    # -- scrolling & rendering ---------------------------------------------

    def invalidate(self, rows=None):
        """Re-render these pages (all if None), e.g. when highlights change."""
        for i, lab in enumerate(self.labels):
            if rows is None or i in rows:
                lab.rendered_at = None
        self.render_timer.start()

    def scroll_to(self, index):
        if 0 <= index < len(self.labels):
            self.verticalScrollBar().setValue(self.labels[index].y() - PAGE_GAP)

    def current_page(self):
        if not self.labels:
            return 0
        probe = self.verticalScrollBar().value() + self.viewport().height() // 3
        for i, lab in enumerate(self.labels):
            if lab.y() + lab.height() + PAGE_GAP >= probe:
                return i
        return len(self.labels) - 1

    def on_scroll(self):
        self.render_timer.start()
        if self.labels:
            self.pageChanged.emit(self.current_page())

    def render_visible(self):
        top = self.verticalScrollBar().value()
        vh = self.viewport().height()
        near_top, near_bottom = top - vh, top + 2 * vh       # render a screen ahead
        keep_top, keep_bottom = top - 4 * vh, top + 5 * vh    # free memory beyond this
        dpr = self.devicePixelRatioF()
        for row, lab in enumerate(self.labels):
            y0, y1 = lab.y(), lab.y() + lab.height()
            if y1 >= near_top and y0 <= near_bottom:
                if lab.rendered_at != self.zoom:
                    scale = self.zoom * dpr
                    img = self.win.render(lab.ref, scale).convertToFormat(QImage.Format_RGB32)
                    lab.base = self.win.paint_hits(img, row, scale)
                    lab.base_scale = scale
                    lab.rendered_at = self.zoom
                    self.show_label(row)
            elif (y1 < keep_top or y0 > keep_bottom) and lab.rendered_at is not None:
                lab.clear()
                lab.rendered_at = None
                lab.base = None

    def show_label(self, row):
        """Put a page's base image on screen, with the text selection drawn on top."""
        lab = self.labels[row]
        if lab.base is None:
            return
        img = lab.base
        rects = self.selection_rects(row)
        if rects:
            img = img.copy()
            p = QPainter(img)
            p.setCompositionMode(QPainter.CompositionMode_Multiply)
            for r in rects:
                p.fillRect(self.win.hit_rect(row, r, lab.base_scale), QColor("#9cc3ff"))
            p.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        lab.setPixmap(pm)

    # -- text selection -------------------------------------------------------

    def selection_span(self):
        """(start, end) as ordered (row, caret) pairs, or None if nothing is selected."""
        if self.sel_anchor is None or self.sel_head is None or self.sel_anchor == self.sel_head:
            return None
        return min(self.sel_anchor, self.sel_head), max(self.sel_anchor, self.sel_head)

    def row_range(self, row):
        """The (a, b) character range selected on this row, or None."""
        span = self.selection_span()
        if not span or not (span[0][0] <= row <= span[1][0]):
            return None
        text = self.win.page_text(row)
        a = span[0][1] if row == span[0][0] else 0
        b = span[1][1] if row == span[1][0] else len(text.chars)
        return (a, b) if a < b else None

    def selection_rects(self, row):
        rng = self.row_range(row)
        return self.win.page_text(row).rects(*rng) if rng else []

    def selected_text(self):
        span = self.selection_span()
        if not span:
            return ""
        parts = []
        for row in range(span[0][0], span[1][0] + 1):
            rng = self.row_range(row)
            if rng:
                parts.append(self.win.page_text(row).text(*rng))
        return "\n".join(parts)

    def sel_rows(self):
        span = self.selection_span()
        return set(range(span[0][0], span[1][0] + 1)) if span else set()

    def set_selection(self, anchor, head):
        before = self.sel_rows()
        self.sel_anchor, self.sel_head = anchor, head
        for row in before | self.sel_rows():
            self.show_label(row)

    def clear_selection(self):
        self.set_selection(None, None)

    def locate(self, pos):
        """Container point -> (row, point in unrotated page coords), using the
        nearest page when the point is in a gap or margin."""
        if not self.labels:
            return None, None

        def gap(i):
            lab = self.labels[i]
            return 0 if lab.y() <= pos.y() <= lab.y() + lab.height() else \
                min(abs(pos.y() - lab.y()), abs(pos.y() - lab.y() - lab.height()))

        row = min(range(len(self.labels)), key=gap)
        lab = self.labels[row]
        x = min(max(pos.x() - lab.x(), 0), lab.width())
        y = min(max(pos.y() - lab.y(), 0), lab.height())
        return row, self.win.to_page_point(row, x, y, self.zoom)

    def caret_at(self, pos):
        row, pt = self.locate(pos)
        if row is None:
            return None
        caret = self.win.page_text(row).caret_at(pt)
        return None if caret is None else (row, caret)

    def eventFilter(self, obj, event):
        if obj is not getattr(self, "container", None):    # QScrollArea filters too
            return super().eventFilter(obj, event)
        t = event.type()
        if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.setFocus()
            pos = event.position().toPoint()
            hit = self.caret_at(pos)
            if hit is None:
                self.clear_selection()
            elif event.modifiers() & Qt.ShiftModifier and self.sel_anchor is not None:
                self.set_selection(self.sel_anchor, hit)
            else:
                self.set_selection(hit, hit)
            self.selecting = hit is not None
            return True
        if t == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            hit = self.caret_at(event.position().toPoint())
            if hit is not None:
                a, b = self.win.page_text(hit[0]).word_at(hit[1])
                self.set_selection((hit[0], a), (hit[0], b))
            self.selecting = False
            return True
        if t == QEvent.MouseMove:
            pos = event.position().toPoint()
            if self.selecting:
                hit = self.caret_at(pos)
                if hit is not None and hit != self.sel_head:
                    self.set_selection(self.sel_anchor, hit)
                vp = self.viewport().mapFrom(self.container, pos)
                near_edge = vp.y() < 20 or vp.y() > self.viewport().height() - 20
                if near_edge and not self.autoscroll_timer.isActive():
                    self.autoscroll_timer.start()
            else:
                row, pt = self.locate(pos)
                over = row is not None and self.labels[row].geometry().contains(pos) \
                    and self.win.page_text(row).over_text(pt)
                self.container.setCursor(Qt.IBeamCursor if over else Qt.ArrowCursor)
            return False
        if t == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.selecting = False
            self.autoscroll_timer.stop()
            return True
        return super().eventFilter(obj, event)

    def autoscroll(self):
        """Keep scrolling while a selection drag is held past the top/bottom edge."""
        if not self.selecting:
            self.autoscroll_timer.stop()
            return
        vp = self.viewport().mapFromGlobal(QCursor.pos())
        h = self.viewport().height()
        if vp.y() < 20:
            step = -max(4, (20 - vp.y()) // 2)
        elif vp.y() > h - 20:
            step = max(4, (vp.y() - h + 20) // 2)
        else:
            self.autoscroll_timer.stop()
            return
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + min(80, max(-80, step)))
        hit = self.caret_at(self.container.mapFromGlobal(QCursor.pos()))
        if hit is not None and hit != self.sel_head:
            self.set_selection(self.sel_anchor, hit)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.path = None          # file currently being edited
        self.sources = []         # open pymupdf documents (index = source id)
        self.source_paths = []
        self.refs = []            # current page order
        self.saved_refs = []
        self.undo_stack, self.redo_stack = [], []
        self.thumb_cache = {}     # ref -> QImage
        self.thumb_queue = []
        self.search_text = ""
        self.hit_cache = {}       # (source, page) -> match rects (unrotated page coords)
        self.hits = []            # [(row, rect)] in reading order
        self.hits_by_row = {}     # row -> [(hit index, rect)]
        self.hit_pos = -1
        self.text_cache = {}      # (source, page) -> PageText

        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.resize(1200, 860)
        self.setAcceptDrops(True)

        self.pages = PageList()
        self.pages.orderChanged.connect(self.on_drag_reorder)
        self.pages.filesDropped.connect(self.on_files_dropped)
        self.pages.itemClicked.connect(lambda it: self.viewer.scroll_to(self.pages.row(it)))
        self.pages.customContextMenuRequested.connect(self.show_page_menu)
        self.pages.itemSelectionChanged.connect(self.update_actions)

        self.viewer = Viewer(self)
        self.viewer.pageChanged.connect(self.update_status)
        self.viewer.zoomChanged.connect(self.update_status)
        self.viewer.container.customContextMenuRequested.connect(self.show_viewer_menu)

        self.find_bar = self.build_find_bar()
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self.find_bar)
        rl.addWidget(self.viewer)

        split = QSplitter()
        split.addWidget(self.pages)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([200, 1000])
        self.setCentralWidget(split)

        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)

        self.thumb_timer = QTimer(self, interval=0)
        self.thumb_timer.timeout.connect(self.render_thumb_batch)

        self.build_actions()
        self.update_title()
        self.update_actions()

    # -- actions ------------------------------------------------------------

    def act(self, text, slot, shortcut=None, tip=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcuts(shortcut if isinstance(shortcut, list) else [shortcut])
        if tip:
            a.setToolTip(tip)
        self.addAction(a)
        return a

    def build_actions(self):
        K = QKeySequence
        self.a_open = self.act("Open…", self.open_dialog, K.Open)
        self.a_save = self.act("Save", self.save, K.Save)
        self.a_save_as = self.act("Save As…", self.save_as, K("Ctrl+Shift+S"))
        self.a_extract = self.act("Save Selected Pages As…", self.extract_selected, K("Ctrl+E"))
        self.a_close = self.act("Close", self.close, K("Ctrl+W"))
        self.a_undo = self.act("Undo", self.undo, K.Undo)
        self.a_redo = self.act("Redo", self.redo, [K("Ctrl+Y"), K("Ctrl+Shift+Z")])
        self.a_dup = self.act("Duplicate", self.duplicate_selected, K("Ctrl+D"),
                              "Duplicate selected pages (Ctrl+D)")
        self.a_del = self.act("Delete", self.delete_selected, K.Delete,
                              "Delete selected pages (Del)")
        self.a_rot_l = self.act("Rotate Left", lambda: self.rotate_selected(-90), K("Ctrl+Shift+R"),
                                "Rotate selected pages left (Ctrl+Shift+R)")
        self.a_rot_r = self.act("Rotate Right", lambda: self.rotate_selected(90), K("Ctrl+R"),
                                "Rotate selected pages right (Ctrl+R)")
        self.a_insert = self.act("Insert from PDF…", self.insert_from_pdf, K("Ctrl+I"),
                                 "Insert pages from another PDF after the selection (Ctrl+I)")
        self.a_select_all = self.act("Select All Pages", self.pages.selectAll, K.SelectAll)
        self.a_copy = self.act("Copy", self.copy_selection, K.Copy, "Copy selected text (Ctrl+C)")
        self.a_find = self.act("Find…", self.show_find, K.Find, "Find text (Ctrl+F)")
        self.a_find_next = self.act("Find Next", lambda: self.step_hit(1), K("F3"))
        self.a_find_prev = self.act("Find Previous", lambda: self.step_hit(-1), K("Shift+F3"))
        self.a_zoom_in = self.act("Zoom In", lambda: self.viewer.step_zoom(1), [K.ZoomIn, K("Ctrl+=")])
        self.a_zoom_out = self.act("Zoom Out", lambda: self.viewer.step_zoom(-1), K.ZoomOut)
        self.a_fit = self.act("Fit Width", self.viewer.set_fit_width, K("Ctrl+0"))
        self.a_actual = self.act("Actual Size", lambda: self.viewer.set_zoom(1.0), K("Ctrl+1"))

        m = self.menuBar().addMenu("&File")
        for a in (self.a_open, self.a_save, self.a_save_as, self.a_extract):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_close)
        m = self.menuBar().addMenu("&Edit")
        for a in (self.a_undo, self.a_redo, None, self.a_copy, None, self.a_dup, self.a_del, self.a_rot_l,
                  self.a_rot_r, None, self.a_insert, None, self.a_select_all, None,
                  self.a_find, self.a_find_next, self.a_find_prev):
            m.addSeparator() if a is None else m.addAction(a)
        m = self.menuBar().addMenu("&View")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_fit, self.a_actual):
            m.addAction(a)

        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        for a in (self.a_open, self.a_save, None, self.a_undo, self.a_redo, None,
                  self.a_dup, self.a_del, self.a_rot_l, self.a_rot_r, self.a_insert, None,
                  self.a_zoom_out, self.a_zoom_in, self.a_fit, None, self.a_find):
            tb.addSeparator() if a is None else tb.addAction(a)

    def show_page_menu(self, pos):
        if not self.pages.itemAt(pos):
            return
        m = QMenu(self)
        for a in (self.a_dup, self.a_del, self.a_rot_l, self.a_rot_r, None,
                  self.a_insert, self.a_extract):
            m.addSeparator() if a is None else m.addAction(a)
        m.exec(self.pages.mapToGlobal(pos))

    # -- find -----------------------------------------------------------------

    def build_find_bar(self):
        bar = QWidget()
        bar.setObjectName("findBar")
        bar.setStyleSheet("#findBar { border-bottom: 1px solid palette(mid); }")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 5, 8, 5)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find in document")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMaximumWidth(360)
        self.find_edit.installEventFilter(self)
        self.find_count = QLabel()
        self.find_count.setMinimumWidth(110)
        lay.addWidget(self.find_edit)
        lay.addWidget(self.find_count)
        for text, tip, slot in (("↑", "Previous match (Shift+Enter)", lambda: self.step_hit(-1)),
                                ("↓", "Next match (Enter)", lambda: self.step_hit(1)),
                                ("✕", "Close (Esc)", self.hide_find)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(slot)
            lay.addWidget(b)
        lay.addStretch(1)
        self.find_timer = QTimer(self, singleShot=True, interval=250)
        self.find_timer.timeout.connect(self.run_search)
        self.find_edit.textChanged.connect(lambda: self.find_timer.start())
        bar.hide()
        return bar

    def eventFilter(self, obj, event):
        if obj is self.find_edit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.find_timer.isActive():         # typed and hit Enter right away
                    self.find_timer.stop()
                    self.run_search()
                else:
                    self.step_hit(-1 if event.modifiers() & Qt.ShiftModifier else 1)
                return True
            if event.key() == Qt.Key_Escape:
                self.hide_find()
                return True
        return super().eventFilter(obj, event)

    def show_find(self):
        self.find_bar.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        if self.find_edit.text().strip() and not self.hits:
            self.run_search()

    def hide_find(self):
        self.find_bar.hide()
        self.find_timer.stop()
        self.clear_search()
        self.viewer.setFocus()

    def clear_search(self):
        had = bool(self.hits)
        self.search_text = ""
        self.hit_cache.clear()
        self.hits, self.hits_by_row, self.hit_pos = [], {}, -1
        self.find_count.setText("")
        if had:
            self.viewer.invalidate()

    def find_hits(self, keep_pos=False):
        """Recompute self.hits for the current page order (search results are
        cached per source page, so this is cheap after edits)."""
        old = self.hit_pos
        self.hits, self.hits_by_row = [], {}
        for row, (src, pno, _) in enumerate(self.refs):
            key = (src, pno)
            if key not in self.hit_cache:
                rects = self.sources[src][pno].search_for(self.search_text)
                self.hit_cache[key] = sorted(rects, key=lambda r: (round(r.y0), r.x0))
            for rect in self.hit_cache[key]:
                self.hits_by_row.setdefault(row, []).append((len(self.hits), rect))
                self.hits.append((row, rect))
        if not self.hits:
            self.hit_pos = -1
        elif keep_pos:
            self.hit_pos = max(0, min(old, len(self.hits) - 1))
        else:
            # first match at or after the page you're looking at
            here = self.viewer.current_page()
            self.hit_pos = next((i for i, (row, _) in enumerate(self.hits) if row >= here), 0)
        self.update_find_count()

    def run_search(self):
        text = self.find_edit.text().strip()
        if not text or not self.refs:
            self.clear_search()
            return
        if text != self.search_text:
            self.search_text = text
            self.hit_cache.clear()
        self.find_hits()
        self.viewer.invalidate()
        self.go_to_hit()

    def update_find_count(self):
        if not self.search_text:
            self.find_count.setText("")
        elif not self.hits:
            self.find_count.setText("No matches")
        else:
            pages = len(self.hits_by_row)
            self.find_count.setText(f"{self.hit_pos + 1} of {len(self.hits)}"
                                    f"  ({pages} page{'s' if pages != 1 else ''})")

    def step_hit(self, direction):
        if not self.find_bar.isVisible():
            self.show_find()
            return
        if not self.hits:
            return
        old_row = self.hits[self.hit_pos][0]
        self.hit_pos = (self.hit_pos + direction) % len(self.hits)
        self.viewer.invalidate({old_row, self.hits[self.hit_pos][0]})
        self.update_find_count()
        self.go_to_hit()

    def hit_rect(self, row, rect, scale):
        """Where a match rect lands in a page image rendered at this scale."""
        src, pno, rot = self.refs[row]
        page = self.sources[src][pno]
        m = pymupdf.Matrix(scale, scale).prerotate(rot)
        origin = (page.rect * m).tl
        r = rect * page.rotation_matrix * m
        return QRectF(r.x0 - origin.x, r.y0 - origin.y, r.width, r.height)

    def to_page_point(self, row, x, y, scale):
        """A point in a page image rendered at this scale -> unrotated page coords
        (the inverse of hit_rect)."""
        src, pno, rot = self.refs[row]
        page = self.sources[src][pno]
        m = pymupdf.Matrix(scale, scale).prerotate(rot)
        origin = (page.rect * m).tl
        return pymupdf.Point(x + origin.x, y + origin.y) * ~(page.rotation_matrix * m)

    def page_text(self, row):
        src, pno, _ = self.refs[row]
        key = (src, pno)
        if key not in self.text_cache:
            self.text_cache[key] = PageText(self.sources[src][pno])
        return self.text_cache[key]

    def copy_selection(self):
        text = self.viewer.selected_text()
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage(f"Copied {len(text)} characters", 3000)

    def show_viewer_menu(self, pos):
        m = QMenu(self)
        a = m.addAction("Copy", self.copy_selection)
        a.setShortcut(QKeySequence.Copy)
        a.setEnabled(bool(self.viewer.selection_span()))
        m.addSeparator()
        m.addAction(self.a_find)
        m.exec(self.viewer.container.mapToGlobal(pos))

    def paint_hits(self, img, row, scale):
        hits = self.hits_by_row.get(row)
        if not hits:
            return img
        img = img.convertToFormat(QImage.Format_RGB32)
        p = QPainter(img)
        p.setCompositionMode(QPainter.CompositionMode_Multiply)   # highlighter look
        for i, rect in hits:
            color = QColor("#ff9632") if i == self.hit_pos else QColor("#ffe94d")
            p.fillRect(self.hit_rect(row, rect, scale).adjusted(-1, -1, 1, 1), color)
        p.end()
        return img

    def go_to_hit(self):
        if not self.hits:
            return
        row, rect = self.hits[self.hit_pos]
        lab = self.viewer.labels[row]
        r = self.hit_rect(row, rect, self.viewer.zoom)
        self.viewer.ensureVisible(int(lab.x() + r.center().x()), int(lab.y() + r.center().y()),
                                  60, self.viewer.viewport().height() // 3)
        self.viewer.render_timer.start()

    # -- dropping files on the page panel -------------------------------------

    def on_files_dropped(self, paths, row):
        if not self.refs:
            self.open_path(paths[0])
            paths, row = paths[1:], len(self.refs)
            if not self.refs:
                return
        if paths:
            self.insert_paths(paths, row)

    def update_actions(self):
        has_doc = bool(self.refs)
        has_sel = bool(self.pages.selectedIndexes())
        for a in (self.a_save, self.a_save_as, self.a_insert, self.a_select_all,
                  self.a_zoom_in, self.a_zoom_out, self.a_fit, self.a_actual,
                  self.a_find, self.a_find_next, self.a_find_prev):
            a.setEnabled(has_doc)
        for a in (self.a_dup, self.a_del, self.a_rot_l, self.a_rot_r, self.a_extract):
            a.setEnabled(has_sel)
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_redo.setEnabled(bool(self.redo_stack))

    # -- documents ----------------------------------------------------------

    def load_pdf(self, path):
        """Open a PDF from memory so the file on disk is never locked."""
        with open(path, "rb") as f:
            data = f.read()
        doc = pymupdf.open(stream=data, filetype="pdf")
        while doc.needs_pass:
            pw, ok = QInputDialog.getText(self, "Password required",
                                          f"{os.path.basename(path)} is password-protected:",
                                          QLineEdit.Password)
            if not ok:
                return None
            doc.authenticate(pw)
        return doc

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", self.start_dir(), PDF_FILTER)
        if path:
            self.open_path(path)

    def open_path(self, path):
        if not self.confirm_discard():
            return
        try:
            doc = self.load_pdf(path)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Couldn't open {path}:\n\n{e}")
            return
        if doc is None:
            return
        for d in self.sources:
            d.close()
        self.path = os.path.abspath(path)
        self.sources, self.source_paths = [doc], [self.path]
        self.refs = [(0, i, 0) for i in range(doc.page_count)]
        self.saved_refs = list(self.refs)
        self.undo_stack, self.redo_stack = [], []
        self.thumb_cache.clear()
        self.text_cache.clear()
        self.hit_cache.clear()
        self.refresh(keep_page=0)

    def start_dir(self):
        return os.path.dirname(self.path) if self.path else os.path.expanduser("~")

    def page_size(self, ref):
        src, pno, rot = ref
        r = self.sources[src][pno].rect      # already accounts for the page's own /Rotate
        return (r.height, r.width) if rot % 180 else (r.width, r.height)

    def render(self, ref, scale):
        src, pno, rot = ref
        mat = pymupdf.Matrix(scale, scale).prerotate(rot)
        return to_qimage(self.sources[src][pno].get_pixmap(matrix=mat, alpha=False))

    def is_dirty(self):
        return self.refs != self.saved_refs

    # -- refresh UI ---------------------------------------------------------

    def refresh(self, keep_page=None, select=None):
        """Rebuild the page panel and viewer from self.refs."""
        if keep_page is None:
            keep_page = self.viewer.current_page()
        self.pages.blockSignals(True)
        self.pages.clear()
        for i, ref in enumerate(self.refs):
            it = QListWidgetItem()
            it.setData(Qt.UserRole, i)
            it.setSizeHint(QSize(ICON_SIZE.width() + 12, ICON_SIZE.height() + 8))
            it.setIcon(QIcon(self.compose_icon(ref, i + 1)))
            self.pages.addItem(it)
        for row in select or []:
            if 0 <= row < self.pages.count():
                self.pages.item(row).setSelected(True)
        if select:
            self.pages.scrollToItem(self.pages.item(min(select)))
        self.pages.blockSignals(False)

        self.thumb_queue = [r for r in dict.fromkeys(self.refs) if r not in self.thumb_cache]
        if self.thumb_queue:
            self.thumb_timer.start()
        if self.search_text:
            self.find_hits(keep_pos=True)
        self.viewer.set_pages(self.refs, keep_page)
        self.update_title()
        self.update_actions()
        self.update_status()

    def compose_icon(self, ref, number):
        dpr = self.devicePixelRatioF()
        canvas = QPixmap(ICON_SIZE * dpr)
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.page_size(ref)
        s = min(THUMB_BOX.width() / w, THUMB_BOX.height() / h)
        tw, th = int(w * s), int(h * s)
        box = QRect((ICON_SIZE.width() - tw) // 2, 2 + (THUMB_BOX.height() - th) // 2, tw, th)
        img = self.thumb_cache.get(ref)
        if img is None:
            p.fillRect(box, QColor("#e6e6e6"))
        else:
            p.drawImage(box, img)
        p.setPen(QPen(QColor("#9a9a9a"), 1))
        p.drawRect(box.adjusted(0, 0, -1, -1))
        p.setPen(self.palette().text().color())
        f = QFont()
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(QRect(0, THUMB_BOX.height() + 6, ICON_SIZE.width(), 18), Qt.AlignCenter, str(number))
        p.end()
        return canvas

    def render_thumb_batch(self):
        done = set()
        dpr = self.devicePixelRatioF()
        for _ in range(3):
            if not self.thumb_queue:
                break
            ref = self.thumb_queue.pop(0)
            w, h = self.page_size(ref)
            s = min(THUMB_BOX.width() / w, THUMB_BOX.height() / h) * dpr
            try:
                self.thumb_cache[ref] = self.render(ref, s)
            except Exception:
                self.thumb_cache[ref] = QImage()
            done.add(ref)
        for row in range(self.pages.count()):
            ref = self.refs[row]
            if ref in done:
                self.pages.item(row).setIcon(QIcon(self.compose_icon(ref, row + 1)))
        if not self.thumb_queue:
            self.thumb_timer.stop()

    def update_title(self):
        name = os.path.basename(self.path) if self.path else None
        star = "*" if self.is_dirty() else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}" if name else APP_NAME)

    def update_status(self, *_):
        if not self.refs:
            self.status_label.setText("")
            return
        zoom = "Fit width" if self.viewer.fit_width else ""
        self.status_label.setText(
            f"Page {self.viewer.current_page() + 1} of {len(self.refs)}    "
            f"{round(self.viewer.zoom * 100)}% {zoom}  ")

    # -- edits ----------------------------------------------------------------

    def selected_rows(self):
        return sorted({i.row() for i in self.pages.selectedIndexes()})

    def commit(self, new_refs, select=None, keep_page=None):
        self.undo_stack.append(list(self.refs))
        self.redo_stack.clear()
        self.refs = new_refs
        self.refresh(keep_page=keep_page, select=select)

    def on_drag_reorder(self):
        order = [self.pages.item(r).data(Qt.UserRole) for r in range(self.pages.count())]
        if order == list(range(len(self.refs))):
            return
        selected = {self.pages.item(r).data(Qt.UserRole) for r in self.selected_rows()}
        new_refs = [self.refs[i] for i in order]
        new_sel = [row for row, i in enumerate(order) if i in selected]
        self.commit(new_refs, select=new_sel, keep_page=new_sel[0] if new_sel else None)

    def duplicate_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        copies = [self.refs[r] for r in rows]
        at = rows[-1] + 1
        new_refs = self.refs[:at] + copies + self.refs[at:]
        self.commit(new_refs, select=list(range(at, at + len(copies))), keep_page=at)

    def delete_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        if len(rows) == len(self.refs):
            QMessageBox.information(self, APP_NAME, "A PDF needs at least one page, so the "
                                    "last page can't be deleted.")
            return
        gone = set(rows)
        new_refs = [r for i, r in enumerate(self.refs) if i not in gone]
        nxt = min(rows[0], len(new_refs) - 1)
        self.commit(new_refs, select=[nxt], keep_page=nxt)

    def rotate_selected(self, deg):
        rows = self.selected_rows()
        if not rows:
            return
        new_refs = list(self.refs)
        for r in rows:
            src, pno, rot = new_refs[r]
            new_refs[r] = (src, pno, (rot + deg) % 360)
        self.commit(new_refs, select=rows)

    def insert_from_pdf(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Insert pages from PDF", self.start_dir(), PDF_FILTER)
        if paths:
            rows = self.selected_rows()
            self.insert_paths(paths, rows[-1] + 1 if rows else len(self.refs))

    def insert_paths(self, paths, at):
        """Insert every page of each PDF at row `at`, in order, as one undo step."""
        added = []
        for path in paths:
            try:
                doc = self.load_pdf(path)
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Couldn't open {path}:\n\n{e}")
                continue
            if doc is None:
                continue
            self.sources.append(doc)
            self.source_paths.append(path)
            src = len(self.sources) - 1
            added += [(src, i, 0) for i in range(doc.page_count)]
        if not added:
            return
        at = max(0, min(at, len(self.refs)))
        new_refs = self.refs[:at] + added + self.refs[at:]
        self.commit(new_refs, select=list(range(at, at + len(added))), keep_page=at)
        n = len(paths)
        self.statusBar().showMessage(
            f"Inserted {len(added)} page(s) from {n} file{'s' if n != 1 else ''}", 4000)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.refs)
            self.refs = self.undo_stack.pop()
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.refs)
            self.refs = self.redo_stack.pop()
            self.refresh()

    # -- saving ---------------------------------------------------------------

    def build_pdf(self, refs):
        out = pymupdf.open()
        # Copy runs of consecutive pages from the same source in one call
        i = 0
        while i < len(refs):
            src, start, _ = refs[i]
            j = i
            while j + 1 < len(refs) and refs[j + 1][0] == src and refs[j + 1][1] == refs[j][1] + 1:
                j += 1
            out.insert_pdf(self.sources[src], from_page=start, to_page=refs[j][1])
            i = j + 1
        for n, (src, pno, rot) in enumerate(refs):
            if rot:
                out[n].set_rotation((self.sources[src][pno].rotation + rot) % 360)

        main = self.sources[0]
        keys = ("title", "author", "subject", "keywords", "creator", "producer", "creationDate")
        try:
            out.set_metadata({k: v for k, v in main.metadata.items() if k in keys and v})
        except Exception:
            pass
        # Keep bookmarks that still point at a page from the main file
        try:
            first_pos = {}
            for n, (src, pno, _) in enumerate(refs):
                if src == 0:
                    first_pos.setdefault(pno + 1, n + 1)
            toc = [[lvl, title, first_pos[pg]] for lvl, title, pg in main.get_toc()
                   if pg in first_pos]
            if toc:
                out.set_toc(toc)
        except Exception:
            pass
        return out

    def write_pdf(self, refs, path):
        tmp = path + ".nouspdf-tmp"
        out = self.build_pdf(refs)
        try:
            out.save(tmp, garbage=3, deflate=True)
        finally:
            out.close()
        os.replace(tmp, path)

    def save(self):
        if self.path:
            return self.save_to(self.path)
        return self.save_as()

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF As", self.path or self.start_dir(), PDF_FILTER)
        return self.save_to(path) if path else False

    def save_to(self, path):
        if not self.refs:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.write_pdf(self.refs, path)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Couldn't save to {path}:\n\n{e}\n\n"
                                 "If the file is open in another program, close it and try again.")
            return False
        page = self.viewer.current_page()
        # Reload the saved file so the in-memory state matches the disk exactly
        doc = self.load_pdf(path)
        for d in self.sources:
            d.close()
        self.path = os.path.abspath(path)
        self.sources, self.source_paths = [doc], [self.path]
        self.refs = [(0, i, 0) for i in range(doc.page_count)]
        self.saved_refs = list(self.refs)
        self.undo_stack, self.redo_stack = [], []
        self.thumb_cache.clear()
        self.text_cache.clear()
        self.hit_cache.clear()
        self.refresh(keep_page=page)
        self.statusBar().showMessage(f"Saved {path}", 4000)
        return True

    def extract_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        base = os.path.splitext(self.path or "pages")[0]
        path, _ = QFileDialog.getSaveFileName(self, "Save Selected Pages As",
                                              base + " (pages).pdf", PDF_FILTER)
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.write_pdf([self.refs[r] for r in rows], path)
            self.statusBar().showMessage(f"Saved {len(rows)} page(s) to {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Couldn't save to {path}:\n\n{e}")

    def confirm_discard(self):
        if not self.is_dirty():
            return True
        r = QMessageBox.question(
            self, APP_NAME, f"Save changes to {os.path.basename(self.path)}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    # -- window events ------------------------------------------------------

    def closeEvent(self, event):
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.open_path(u.toLocalFile())
                break


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and os.path.isfile(args[0]):
        win.open_path(args[0])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
