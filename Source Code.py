import sys, os, json, subprocess, webbrowser, shlex, wave, uuid, tempfile, base64
import urllib.parse
import urllib.request
import urllib.error
import socket
from functools import lru_cache

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QMenu, QFileDialog, QScrollArea, QLabel, QDialog, QLineEdit, QFrame,
    QColorDialog, QGridLayout, QSlider, QComboBox, QLayout
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QRect,
    QRectF, QUrl, QPoint, QThread, pyqtSignal, QBuffer, QIODevice, QSize
)
from PyQt6.QtGui import (
    QColor, QPainter, QCursor, QMovie, QPainterPath, QBrush, QPixmap,
    QFontMetrics, QMouseEvent, QPen, QIcon, QFont, QFontDatabase, QShortcut, QKeySequence
)
from PyQt6.QtMultimedia import (
    QMediaPlayer, QAudioOutput, QMediaDevices, QAudioSource, QAudioFormat
)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".animated_buttons_app")
CONFIG_PATH = os.path.join(CONFIG_DIR, "state.json")
MEDIA_DIR = os.path.join(CONFIG_DIR, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

TENOR_API_BASE = "https://tenor.googleapis.com/v2"
TENOR_CLIENT_KEY = "animated_buttons_app"

DEFAULT_APP_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAAXNSR0IArs4c6QAAAARnQU1BAACx"
    "jwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAADtSURBVHhe7dkxDoMwEEThlSlSpEiRIkWK"
    "FClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWK"
    "FClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWK"
    "FClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWK"
    "FClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWKFClSpEiRIkWK"
)

GLOBAL_QSS = """
QDialog, QInputDialog, QFileDialog { background: transparent; }
QLineEdit, QComboBox {
    background: #202127; color: #e6e8ee;
    border: 1px solid #2a2b33; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #5b6cff; }
QComboBox QAbstractItemView {
    background: #202127; color: #e6e8ee; border: 1px solid #2a2b33;
    selection-background-color: #5b6cff; outline: 0;
}
QPushButton {
    background: #202127; color: #e6e8ee; border: 1px solid #2a2b33;
    border-radius: 8px; padding: 8px 16px; font-size: 13px;
}
QPushButton:hover { background: #26272e; }
QScrollBar:vertical { background: transparent; width: 6px; }
QScrollBar::handle:vertical { background: #2a2b33; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: #2a2b33; border-radius: 3px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSlider::groove:horizontal { height: 4px; background: #2a2b33; border-radius: 2px; }
QSlider::handle:horizontal { background: #5b6cff; width: 14px; margin: -6px 0; border-radius: 7px; }
QSlider::sub-page:horizontal { background: #5b6cff; border-radius: 2px; }
"""

RADIUS = 18
RESIZE_MARGIN = 8
TILE_SIZE = 104
MIN_TILE_SIZE = 64
TILE_RADIUS = 18
TITLE_MAX_LEN = 20
DRAG_THRESHOLD = 8
GRID_SPACING = 14
IMAGE_FILTER = "Изображения (*.png *.jpg *.jpeg *.bmp *.webp);;Все файлы (*)"
GIF_FILTER = "Гифки (*.gif *.apng *.webp);;Все файлы (*)"
ICON_FILTER = (
    "Изображения и гифки (*.png *.jpg *.jpeg *.bmp *.webp *.ico *.gif *.apng)"
    ";;Все файлы (*)"
)
MAX_VOICE_SEC = 10

DEFAULT_THEME = {
    "bg": "#17181c", "panel": "#202127", "accent": "#5b6cff",
    "text": "#e6e8ee", "btn_bg": "#202127", "btn_text": "#e6e8ee",
    "bg_image": "",
}

DEFAULT_BUTTON_FONT = {"family": "", "size": 10, "bold": True}

ACTION_TYPES = {"sound": "Звук", "url": "Сайт", "app": "Запуск", "file": "Файл"}


# ---------- Flow Layout ----------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=10, v_spacing=10):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, index): return self._items[index] if 0 <= index < len(self._items) else None
    def takeAt(self, index): return self._items.pop(index) if 0 <= index < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._do_layout(QRect(0, 0, width, 0), True)
    def setGeometry(self, rect): super().setGeometry(rect); self._do_layout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x(); y = rect.y()
        line_height = 0
        for item in self._items:
            next_x = x + item.sizeHint().width() + self._h_spacing
            if next_x - self._h_spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self._v_spacing
                next_x = x + item.sizeHint().width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


# ---------- State ----------
def load_state():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    st.setdefault("theme", dict(DEFAULT_THEME))
    st.setdefault("buttons", [])
    st.setdefault("categories", [])
    st.setdefault("current_category", "")
    st.setdefault("pinned", False)
    st.setdefault("tenor_key", "")
    st.setdefault("app_icon", "")
    return st

def save_state(state):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save error:", e, file=sys.stderr)

def normalize_actions(spec):
    if isinstance(spec, list):
        out = []
        for a in spec:
            if isinstance(a, dict) and a.get("type") in ACTION_TYPES:
                v = str(a.get("value", "") or "").strip()
                if v: out.append({"type": a["type"], "value": v})
        return out
    if isinstance(spec, dict):
        t = spec.get("type"); v = str(spec.get("value", "") or "").strip()
        if t in ACTION_TYPES and v:
            return [{"type": t, "value": v}]
    return []

def normalize_font(spec):
    if not isinstance(spec, dict):
        return dict(DEFAULT_BUTTON_FONT)
    out = dict(DEFAULT_BUTTON_FONT)
    fam = spec.get("family", "")
    if isinstance(fam, str): out["family"] = fam
    try: out["size"] = max(6, min(28, int(spec.get("size", 10))))
    except Exception: pass
    out["bold"] = bool(spec.get("bold", True))
    return out

def _default_icon_pixmap() -> QPixmap:
    pm = QPixmap()
    try:
        pm.loadFromData(base64.b64decode(DEFAULT_APP_ICON_B64))
        if pm.isNull(): raise ValueError
    except Exception:
        pm = QPixmap(32, 32); pm.fill(QColor("#5b6cff"))
    return pm

@lru_cache(maxsize=64)
def _icon_pixmap_cached(path, mtime, size):
    pm = QPixmap(path)
    if pm.isNull(): return None
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)

def load_app_icon(path: str, size=40) -> QPixmap:
    if path and os.path.exists(path):
        try: mt = int(os.path.getmtime(path))
        except OSError: mt = 0
        pm = _icon_pixmap_cached(path, mt, size)
        if pm is not None and not pm.isNull(): return pm
    return _default_icon_pixmap()


# ---------- OS run helpers ----------
def _split_command(cmd: str):
    cmd = cmd.strip().strip('"')
    if not cmd: return "", []
    if os.path.exists(cmd): return cmd, []
    try: parts = shlex.split(cmd, posix=(os.name != "nt"))
    except ValueError: parts = cmd.split()
    return (parts[0], parts[1:]) if parts else ("", [])

def _is_special_target(target: str):
    low = target.lower()
    return "://" in low or low.startswith(("ms-settings:", "shell:", "mailto:", "tel:", "ms-"))

def _open_file_with_os(path: str):
    if not os.path.exists(path): return False, "Файл или папка не найдены."
    try:
        if sys.platform.startswith("win"): os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])
        return True, ""
    except Exception as e: return False, str(e)

def _run_program(program: str, args=None, raw_cmd: str = ""):
    args = args or []
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen([program] + args, shell=False, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        else: subprocess.Popen([program] + args)
        return True, ""
    except FileNotFoundError: pass
    except Exception as e: return False, str(e)
    try:
        subprocess.Popen(raw_cmd or (program + (" " + " ".join(args) if args else "")), shell=True)
        return True, ""
    except Exception as e: return False, str(e)

def _open_with_os(target: str, args=None):
    args = args or []
    if _is_special_target(target) and not os.path.exists(target):
        try:
            if sys.platform.startswith("win"): os.startfile(target)
            elif sys.platform == "darwin": subprocess.Popen(["open", target])
            else: subprocess.Popen(["xdg-open", target])
            return True, ""
        except Exception as e: return False, str(e)
    if os.path.exists(target):
        is_exec = os.path.isfile(target) and (
            (sys.platform.startswith("win") and target.lower().endswith((".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".lnk")))
            or (not sys.platform.startswith("win") and os.access(target, os.X_OK))
        )
        if is_exec:
            ok, err = _run_program(target, args, raw_cmd=target)
            if ok: return True, ""
            return _open_file_with_os(target)
        return _open_file_with_os(target)
    ok, err = _run_program(target, args, raw_cmd=target)
    return (True, "") if ok else (False, err or f"Не найдено: {target}")


# ---------- URL check ----------
class UrlCheckWorker(QThread):
    finished_one = pyqtSignal(int, str, bool, str)
    finished_all = pyqtSignal()
    def __init__(self, urls, parent=None):
        super().__init__(parent); self._urls = list(urls)
    def _check_one(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"): return False, "Адрес должен начинаться с http:// или https://"
            if not parsed.netloc: return False, "Некорректный адрес."
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if getattr(resp, "status", 200) >= 400: return False, f"Код {resp.status}."
                    return True, ""
            except urllib.error.HTTPError as he:
                if he.code in (403, 405, 501):
                    try:
                        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=6): return True, ""
                    except Exception: pass
                return False, f"Код {he.code}."
            except Exception as ex: return False, f"Ошибка:\n{ex}"
        except Exception as ex: return False, f"Ошибка:\n{ex}"
    def run(self):
        for i, url in enumerate(self._urls):
            ok, err = self._check_one(url)
            self.finished_one.emit(i, url, ok, err)
        self.finished_all.emit()


# ---------- Медиа ----------
class MediaAsset:
    __slots__ = ("_on_update", "path", "pixmap", "movie", "_active")
    def __init__(self, on_update):
        self._on_update = on_update; self.path = ""; self.pixmap = None; self.movie = None; self._active = False
    def set_path(self, path: str):
        if path == self.path: return
        self._stop_movie(); self.movie = None; self.pixmap = None; self.path = path or ""
        if path and os.path.exists(path):
            low = path.lower()
            if low.endswith((".gif", ".apng", ".webp")):
                m = QMovie(path)
                if m.isValid():
                    self.movie = m; m.frameChanged.connect(self._on_update)
                    if self._active: m.start()
                else: m.deleteLater()
            else:
                pm = QPixmap(path)
                if not pm.isNull(): self.pixmap = pm
        self._on_update()
    def activate(self, on: bool):
        self._active = bool(on)
        if not self.movie: return
        if on and self.movie.state() != QMovie.MovieState.Running: self.movie.start()
        elif not on and self.movie.state() == QMovie.MovieState.Running: self.movie.stop()
    def has_content(self): return bool((self.movie and self.movie.isValid()) or self.pixmap)
    def current_frame(self):
        if self.movie and self.movie.isValid(): return self.movie.currentPixmap()
        return self.pixmap
    def _stop_movie(self):
        if self.movie:
            try: self.movie.frameChanged.disconnect()
            except TypeError: pass
            self.movie.stop(); self.movie.deleteLater()
    def stop(self):
        self._stop_movie(); self.movie = None


# ---------- Логотип ----------
class AppLogoWidget(QWidget):
    clicked = pyqtSignal()
    def __init__(self, size=44, radius=10, parent=None):
        super().__init__(parent)
        self._size = size; self._radius = radius; self._movie = None; self._pixmap = None; self._hover = False
        self.setFixedSize(size, size); self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Логотип приложения (клик — сменить)")
    def set_source(self, path: str):
        self._stop_movie(); self._movie = None; self._pixmap = None
        if path and os.path.exists(path):
            low = path.lower()
            if low.endswith((".gif", ".apng", ".webp")):
                m = QMovie(path)
                if m.isValid():
                    m.setCacheMode(QMovie.CacheMode.CacheAll); m.frameChanged.connect(self.update); self._movie = m
                    if self.isVisible(): m.start()
                else: m.deleteLater()
            else:
                pm = QPixmap(path)
                if not pm.isNull(): self._pixmap = pm
        else: self._pixmap = _default_icon_pixmap()
        self.update()
    def _stop_movie(self):
        if self._movie:
            try: self._movie.frameChanged.disconnect()
            except TypeError: pass
            self._movie.stop(); self._movie.deleteLater()
    def showEvent(self, e):
        super().showEvent(e)
        if self._movie: self._movie.start()
    def hideEvent(self, e):
        super().hideEvent(e)
        if self._movie: self._movie.stop()
    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()); path = QPainterPath(); path.addRoundedRect(rect, self._radius, self._radius)
        p.setClipPath(path); p.fillPath(path, QBrush(QColor("#202127")))
        pm = None
        if self._movie and self._movie.isValid(): pm = self._movie.currentPixmap()
        elif self._pixmap: pm = self._pixmap
        if pm is not None and not pm.isNull():
            iw, ih = int(rect.width()), int(rect.height())
            scaled = pm.scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - iw) // 2; sy = (scaled.height() - ih) // 2
            p.drawPixmap(0, 0, scaled.copy(QRect(sx, sy, iw, ih)))
        if self._hover:
            p.fillPath(path, QBrush(QColor(91, 108, 255, 60))); p.setPen(QPen(QColor("#5b6cff"), 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)


# ---------- Безрамочное окно ----------
class RoundedWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(360, 400)
        self._bg_color = QColor("#17181c")
        self._bg_asset = MediaAsset(self.update); self._bg_asset.activate(True)
        self._drag_pos = None; self._resizing = False; self._resize_edges = Qt.Edge(0); self._start_geom = QRect(); self._start_pos = None
        self.setMouseTracking(True)
        self._central = QWidget(); self._central.setStyleSheet("background: transparent;"); self.setCentralWidget(self._central)
        self._is_app_active = True
    def set_theme(self, theme):
        self._bg_color = QColor(theme.get("bg", "#17181c")); self._bg_asset.set_path(theme.get("bg_image", "")); self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath(); path.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.setClipPath(path); p.fillPath(path, QBrush(self._bg_color))
        pm = self._bg_asset.current_frame()
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
    def _edge_at(self, pos):
        x, y, w, h, m = pos.x(), pos.y(), self.width(), self.height(), RESIZE_MARGIN
        e = Qt.Edge(0)
        if x <= m: e |= Qt.Edge.LeftEdge
        if x >= w - m: e |= Qt.Edge.RightEdge
        if y <= m: e |= Qt.Edge.TopEdge
        if y >= h - m: e |= Qt.Edge.BottomEdge
        return e
    def _cursor_for(self, edges):
        if edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge): return Qt.CursorShape.SizeFDiagCursor
        if edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge): return Qt.CursorShape.SizeBDiagCursor
        if edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): return Qt.CursorShape.SizeHorCursor
        if edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return super().mousePressEvent(e)
        edges = self._edge_at(e.position().toPoint())
        if edges:
            self._resizing = True; self._resize_edges = edges; self._start_geom = self.geometry(); self._start_pos = e.globalPosition().toPoint(); e.accept(); return
        if e.position().y() < 80:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft(); e.accept()
    def mouseMoveEvent(self, e):
        if self._resizing:
            d = e.globalPosition().toPoint() - self._start_pos; g = QRect(self._start_geom)
            if self._resize_edges & Qt.Edge.LeftEdge: g.setLeft(g.left() + d.x())
            if self._resize_edges & Qt.Edge.RightEdge: g.setRight(g.right() + d.x())
            if self._resize_edges & Qt.Edge.TopEdge: g.setTop(g.top() + d.y())
            if self._resize_edges & Qt.Edge.BottomEdge: g.setBottom(g.bottom() + d.y())
            if g.width() >= self.minimumWidth() and g.height() >= self.minimumHeight(): self.setGeometry(g)
            e.accept(); return
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos); e.accept(); return
        self.setCursor(self._cursor_for(self._edge_at(e.position().toPoint())))
    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._resizing = False; self.setCursor(Qt.CursorShape.ArrowCursor)


class RoundedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._bg = QColor("#17181c"); self._drag = None
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        path = QPainterPath(); path.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.fillPath(path, QBrush(self._bg))
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 40:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft(); e.accept()
    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag); e.accept()
    def mouseReleaseEvent(self, e): self._drag = None
    def showEvent(self, e):
        super().showEvent(e); self.raise_(); self.activateWindow()


# ---------- Общие диалоги ----------
def _dlg_title(parent, text):
    head = QHBoxLayout()
    t = QLabel(text); t.setStyleSheet("color:#e6e8ee;font-size:16px;font-weight:700;"); head.addWidget(t, 1)
    close = QPushButton("✕"); close.setFixedSize(28, 28); close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    close.setStyleSheet("QPushButton{background:transparent;color:#8b8f9a;border:none;border-radius:8px;font-size:14px;}QPushButton:hover{background:#202127;color:#e6e8ee;}")
    head.addWidget(close); return head, close

def _primary_btn(text):
    b = QPushButton(text); b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); b.setMinimumHeight(38)
    b.setStyleSheet("QPushButton{background:#5b6cff;color:white;border:none;border-radius:8px;padding:8px 22px;font-size:13px;font-weight:600;}QPushButton:hover{background:#4a5ae6;}")
    return b

def _ghost_btn(text):
    b = QPushButton(text); b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); b.setMinimumHeight(38)
    b.setStyleSheet("QPushButton{background:transparent;color:#b8bcc6;border:none;border-radius:8px;padding:8px 18px;font-size:13px;}QPushButton:hover{background:#202127;color:#e6e8ee;}")
    return b

def _menu_style():
    return ("QMenu{background:#202127;color:#dcdde3;border:1px solid #2a2b33;border-radius:12px;padding:6px;}"
            "QMenu::item{padding:9px 20px;border-radius:6px;font-size:13px;margin:1px 4px;}"
            "QMenu::item:selected{background:#5b6cff;color:white;}"
            "QMenu::separator{height:1px;background:#2a2b33;margin:6px 10px;}")


class MsgDialog(RoundedDialog):
    def __init__(self, parent=None, title="", text="", icon_text="⚠", confirm=False):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(400); self._confirmed = False
        v = QVBoxLayout(self); v.setContentsMargins(24, 22, 24, 22); v.setSpacing(16)
        head = QHBoxLayout(); head.setSpacing(14)
        icon = QLabel(icon_text); icon.setFixedSize(44, 44); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("QLabel{background:#2a1f22;color:#e74c3c;border-radius:12px;font-size:22px;font-weight:700;}")
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        t = QLabel(title); t.setStyleSheet("color:#e6e8ee;font-size:15px;font-weight:700;"); head.addWidget(t, 1); v.addLayout(head)
        body = QLabel(text); body.setWordWrap(True); body.setStyleSheet("color:#b8bcc6;font-size:13px;"); v.addWidget(body)
        row = QHBoxLayout(); row.setSpacing(8); row.addStretch(1)
        if confirm:
            no = _ghost_btn("Отмена"); no.clicked.connect(self.reject); row.addWidget(no)
        ok = _primary_btn("Да" if confirm else "Понятно"); ok.clicked.connect(self._accept); row.addWidget(ok); v.addLayout(row)
    def _accept(self): self._confirmed = True; self.accept()
    @staticmethod
    def show_message(parent, title, text, icon_text="⚠"): MsgDialog(parent, title, text, icon_text).exec()
    @staticmethod
    def confirm(parent, title, text, icon_text="⚠"):
        d = MsgDialog(parent, title, text, icon_text, confirm=True); d.exec(); return d._confirmed


class TextInputDialog(RoundedDialog):
    def __init__(self, parent=None, title="", label="", text="", max_len=20):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(380)
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(14)
        head, close = _dlg_title(self, title); close.clicked.connect(self.reject); v.addLayout(head)
        lbl = QLabel(label); lbl.setStyleSheet("color:#8b8f9a;font-size:12px;"); v.addWidget(lbl)
        self.edit = QLineEdit(text); self.edit.setMaxLength(max_len); v.addWidget(self.edit)
        self.counter = QLabel(f"{len(text)}/{max_len}"); self.counter.setStyleSheet("color:#6c707a;font-size:11px;")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight); v.addWidget(self.counter)
        self.edit.textChanged.connect(lambda s: self.counter.setText(f"{len(s)}/{max_len}"))
        btns = QHBoxLayout(); btns.setSpacing(8); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("Сохранить"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        self.edit.setFocus(); self.edit.selectAll()
    def value(self): return self.edit.text().strip()


class ColorPickerDialog(RoundedDialog):
    PRESETS = ["#5b6cff", "#7c4dff", "#e91e63", "#f44336", "#ff9800", "#ffc107", "#4caf50", "#00bcd4", "#2196f3", "#9c27b0", "#607d8b", "#202127", "#2f3136", "#3a3b45", "#17181c", "#ffffff"]
    def __init__(self, parent=None, title="Выбор цвета", current="#202127", default="#202127"):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(360)
        self._value = QColor(current); self._default = QColor(default); self._updating = False
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(14)
        head, close = _dlg_title(self, title); close.clicked.connect(self.reject); v.addLayout(head)
        self.preview = QLabel(); self.preview.setFixedHeight(52); v.addWidget(self.preview)
        grid = QGridLayout(); grid.setSpacing(8)
        for i, h in enumerate(self.PRESETS):
            r, c = divmod(i, 4); sw = QPushButton(); sw.setFixedSize(56, 34); sw.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            sw.setStyleSheet(f"QPushButton{{background:{h};border:1px solid #2a2b33;border-radius:8px;}}QPushButton:hover{{border:1px solid #5b6cff;}}")
            sw.clicked.connect(lambda _, hh=h: self._set(hh)); grid.addWidget(sw, r, c)
        v.addLayout(grid)
        row = QHBoxLayout(); row.setSpacing(8)
        self.hex_edit = QLineEdit(self._value.name()); self.hex_edit.setMaxLength(7); self.hex_edit.textChanged.connect(self._on_hex_changed)
        more = QPushButton("Другой…"); more.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); more.setMinimumHeight(34); more.clicked.connect(self._open_native)
        row.addWidget(self.hex_edit, 1); row.addWidget(more); v.addLayout(row)
        btns = QHBoxLayout(); btns.setSpacing(8)
        reset = _ghost_btn("Сбросить"); reset.clicked.connect(lambda: self._set(self._default.name())); btns.addWidget(reset); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("ОК"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        self._refresh()
    def _set(self, hex_):
        c = QColor(hex_)
        if not c.isValid(): return
        self._value = c; self._updating = True; self.hex_edit.setText(self._value.name()); self._updating = False; self._refresh()
    def _on_hex_changed(self, text):
        if self._updating: return
        t = text.strip()
        if not t.startswith("#"): t = "#" + t
        if len(t) in (4, 7):
            c = QColor(t)
            if c.isValid(): self._value = c; self._refresh(update_edit=False)
    def _refresh(self, update_edit=True):
        self.preview.setStyleSheet(f"background:{self._value.name()};border-radius:10px;border:1px solid #2a2b33;")
        if update_edit and not self._updating:
            self._updating = True; self.hex_edit.setText(self._value.name()); self._updating = False
    def _open_native(self):
        dlg = QColorDialog(self._value, self); dlg.setWindowTitle("Другой цвет"); dlg.setOptions(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if dlg.exec(): self._set(dlg.selectedColor().name())
    def color(self): return self._value.name()


class ButtonColorsDialog(RoundedDialog):
    def __init__(self, parent=None, title="Цвета кнопки", bg="#202127", text="#e6e8ee", default_bg="#202127", default_text="#e6e8ee"):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(380)
        self._bg = QColor(bg); self._text = QColor(text); self._def_bg = QColor(default_bg); self._def_text = QColor(default_text)
        self._target = "bg"; self._updating = False
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(14)
        head, close = _dlg_title(self, title); close.clicked.connect(self.reject); v.addLayout(head)
        cards = QHBoxLayout(); cards.setSpacing(10)
        self.bg_card = self._make_card("bg", "Фон"); self.text_card = self._make_card("text", "Текст")
        cards.addWidget(self.bg_card, 1); cards.addWidget(self.text_card, 1); v.addLayout(cards)
        v.addWidget(self._lbl("ПАЛИТРА"))
        grid = QGridLayout(); grid.setSpacing(8)
        for i, h in enumerate(ColorPickerDialog.PRESETS):
            r, c = divmod(i, 4); sw = QPushButton(); sw.setFixedSize(64, 32); sw.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            sw.setStyleSheet(f"QPushButton{{background:{h};border:1px solid #2a2b33;border-radius:8px;}}QPushButton:hover{{border:1px solid #5b6cff;}}")
            sw.clicked.connect(lambda _, hh=h: self._set(hh)); grid.addWidget(sw, r, c)
        v.addLayout(grid)
        row = QHBoxLayout(); row.setSpacing(8)
        self.hex_edit = QLineEdit(); self.hex_edit.setMaxLength(7); self.hex_edit.textChanged.connect(self._on_hex_changed)
        more = QPushButton("Другой…"); more.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); more.setMinimumHeight(34); more.clicked.connect(self._pick_other)
        row.addWidget(self.hex_edit, 1); row.addWidget(more); v.addLayout(row)
        btns = QHBoxLayout(); btns.setSpacing(8)
        reset = _ghost_btn("Сбросить"); reset.clicked.connect(self._reset); btns.addWidget(reset); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("ОК"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        self._refresh()
    def _lbl(self, text):
        l = QLabel(text); l.setStyleSheet("color:#8b8f9a;font-size:11px;font-weight:600;letter-spacing:1px;"); return l
    def _make_card(self, key, label):
        b = QPushButton(label); b.setFixedHeight(58); b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); b.clicked.connect(lambda _, k=key: self._select_target(k)); return b
    def _select_target(self, key): self._target = key; self._refresh()
    def _target_color(self): return self._bg if self._target == "bg" else self._text
    def _set(self, hex_):
        c = QColor(hex_)
        if not c.isValid(): return
        if self._target == "bg": self._bg = c
        else: self._text = c
        self._updating = True; self.hex_edit.setText(c.name()); self._updating = False; self._refresh()
    def _on_hex_changed(self, text):
        if self._updating: return
        t = text.strip()
        if not t.startswith("#"): t = "#" + t
        if len(t) in (4, 7):
            c = QColor(t)
            if c.isValid():
                if self._target == "bg": self._bg = c
                else: self._text = c
                self._refresh(update_edit=False)
    def _refresh(self, update_edit=True):
        active = self._target == "bg"
        self.bg_card.setStyleSheet(self._card_style("bg", active)); self.text_card.setStyleSheet(self._card_style("text", not active))
        if update_edit and not self._updating:
            self._updating = True; self.hex_edit.setText(self._target_color().name()); self._updating = False
    def _card_style(self, key, active):
        border = "#5b6cff" if active else "#2a2b33"; width = 2 if active else 1
        hover = "#7a87ff" if active else "#3a3b45"; fg = "#9aa0ad" if key == "bg" else self._text.name()
        return (f"QPushButton{{background:{self._bg.name()};color:{fg};border:{width}px solid {border};border-radius:10px;font-size:13px;font-weight:600;}}"
                f"QPushButton:hover{{border:{width}px solid {hover};}}")
    def _pick_other(self):
        dlg = QColorDialog(self._target_color(), self); dlg.setWindowTitle("Другой цвет"); dlg.setOptions(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if dlg.exec(): self._set(dlg.selectedColor().name())
    def _reset(self):
        self._bg = QColor(self._def_bg); self._text = QColor(self._def_text); self._refresh()
    def colors(self): return self._bg.name(), self._text.name()


# ---------- Шрифт кнопки ----------
class ButtonFontDialog(RoundedDialog):
    def __init__(self, parent=None, font_spec=None):
        super().__init__(parent)
        self.setModal(True); self.setFixedWidth(400)
        self._font = normalize_font(font_spec or {})
        self._selected_family = self._font["family"]
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(14)
        
        head, close = _dlg_title(self, "Шрифт текста кнопки")
        close.clicked.connect(self.reject); v.addLayout(head)
        
        self.preview = QLabel("Пример текста")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(72)
        self.preview.setStyleSheet("background:#202127;border-radius:10px;border:1px solid #2a2b33;")
        v.addWidget(self.preview)
        
        v.addWidget(self._lbl("ШРИФТ"))
        
        self.font_scroll = QScrollArea()
        self.font_scroll.setWidgetResizable(True)
        self.font_scroll.setFixedHeight(140)
        self.font_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.font_scroll.setStyleSheet("QScrollArea{background:#202127;border:1px solid #2a2b33;border-radius:8px;}"
                                       "QScrollArea > QWidget > QWidget{background:transparent;}")
        
        self.font_list_widget = QWidget()
        self.font_list_widget.setStyleSheet("background: transparent;")
        self.font_list_layout = QVBoxLayout(self.font_list_widget)
        self.font_list_layout.setContentsMargins(4, 4, 4, 4)
        self.font_list_layout.setSpacing(2)
        
        self.font_buttons = []
        families = sorted(QFontDatabase.families())
        
        for fam in families:
            btn = QPushButton(fam)
            btn.setCheckable(True)
            btn.setMinimumHeight(32)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#e6e8ee;border:none;border-radius:6px;"
                "padding:6px 10px;font-size:13px;text-align:left;}"
                "QPushButton:hover{background:#26272e;}"
                "QPushButton:checked{background:#5b6cff;color:white;font-weight:bold;}"
            )
            btn.clicked.connect(lambda checked, f=fam: self._select_font(f))
            self.font_list_layout.addWidget(btn)
            self.font_buttons.append((fam, btn))
            if fam == self._selected_family:
                btn.setChecked(True)
                
        self.font_list_layout.addStretch(1)
        self.font_scroll.setWidget(self.font_list_widget)
        v.addWidget(self.font_scroll)

        v.addWidget(self._lbl("РАЗМЕР"))
        size_row = QHBoxLayout(); size_row.setSpacing(10)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(6, 28); self.size_slider.setValue(self._font["size"])
        self.size_slider.valueChanged.connect(self._on_size)
        self.size_lbl = QLabel(f'{self._font["size"]} pt')
        self.size_lbl.setFixedWidth(44)
        self.size_lbl.setStyleSheet("color:#b8bcc6;font-size:12px;")
        size_row.addWidget(self.size_slider, 1); size_row.addWidget(self.size_lbl)
        v.addLayout(size_row)

        self.bold_btn = QPushButton("Жирный")
        self.bold_btn.setCheckable(True); self.bold_btn.setChecked(self._font["bold"])
        self.bold_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.bold_btn.setMinimumHeight(38)
        self.bold_btn.setStyleSheet(
            "QPushButton{background:#202127;color:#e6e8ee;border:1px solid #2a2b33;"
            "border-radius:8px;padding:8px 14px;font-size:13px;}"
            "QPushButton:hover{background:#26272e;}"
            "QPushButton:checked{background:#5b6cff;color:white;border:1px solid #5b6cff;}")
        self.bold_btn.toggled.connect(self._on_bold)
        v.addWidget(self.bold_btn)
        
        btns = QHBoxLayout(); btns.setSpacing(8)
        reset = _ghost_btn("Сбросить"); reset.clicked.connect(self._reset)
        btns.addWidget(reset); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("Применить"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        
        self._refresh_preview()

    def _lbl(self, text):
        l = QLabel(text); l.setStyleSheet("color:#8b8f9a;font-size:11px;font-weight:600;letter-spacing:1px;"); return l
        
    def _select_font(self, family):
        self._selected_family = family
        self._font["family"] = family
        for fam, btn in self.font_buttons:
            btn.setChecked(fam == family)
        self._refresh_preview()
        
    def _on_size(self, v):
        self._font["size"] = int(v); self.size_lbl.setText(f"{int(v)} pt")
        self._refresh_preview()
        
    def _on_bold(self, on):
        self._font["bold"] = bool(on); self._refresh_preview()
        
    def _refresh_preview(self):
        f = QFont()
        if self._font["family"]: f.setFamily(self._font["family"])
        f.setPointSize(self._font["size"]); f.setBold(self._font["bold"])
        self.preview.setFont(f); self.preview.setText("Пример текста")
        
    def _reset(self):
        self._font = dict(DEFAULT_BUTTON_FONT)
        self._select_font(self._font["family"])
        self.size_slider.setValue(self._font["size"])
        self.bold_btn.setChecked(self._font["bold"])
        self._refresh_preview()
        
    def font_spec(self): return dict(self._font)


# ---------- GIF (Tenor) ----------
class GifSearchWorker(QThread):
    done = pyqtSignal(list, str)
    def __init__(self, query, api_key, limit=24, parent=None):
        super().__init__(parent)
        self.query = query
        self.api_key = api_key
        self.limit = limit

    def run(self):
        if not self.api_key:
            self.done.emit([], "Введите ключ Tenor (кнопка внизу).")
            return
        try:
            params = urllib.parse.urlencode({
                "q": self.query or "random",
                "limit": self.limit,
                "key": self.api_key,
                "client_key": TENOR_CLIENT_KEY,
            })
            url = f"{TENOR_API_BASE}/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for r in data.get("results", []):
                mf = r.get("media_formats", {})
                tiny = mf.get("tinygif", {}).get("url", "")
                full = mf.get("gif", {}).get("url", "") or tiny
                if tiny:
                    results.append({"preview": tiny, "full": full})
            self.done.emit(results, "")
        except urllib.error.HTTPError as he:
            self.done.emit([], f"HTTP {he.code}: проверьте ключ Tenor.")
        except Exception as ex:
            self.done.emit([], f"Ошибка сети:\n{ex}")


class GifThumbWorker(QThread):
    loaded = pyqtSignal(int, bytes)
    def __init__(self, idx, url, parent=None):
        super().__init__(parent); self.idx = idx; self.url = url
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp: self.loaded.emit(self.idx, resp.read())
        except Exception: self.loaded.emit(self.idx, b"")


class GifTile(QWidget):
    picked = pyqtSignal(str)
    def __init__(self, idx, item, parent=None):
        super().__init__(parent); self.idx = idx; self.item = item
        self._movie = None; self._pixmap = None; self._loading = True; self._tmp_path = ""
        self.setFixedSize(150, 110); self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.setStyleSheet("background: transparent;")
        self._active = True
    def set_data(self, data: bytes):
        self._loading = False
        if not data: self.update(); return
        self._tmp_path = os.path.join(tempfile.gettempdir(), f"_gifprev_{self.idx}_{uuid.uuid4().hex}.gif")
        try:
            with open(self._tmp_path, "wb") as f: f.write(data)
            m = QMovie(self._tmp_path)
            if m.isValid():
                self._movie = m; m.frameChanged.connect(self._on_frame)
                if self._active: m.start()
            else:
                pm = QPixmap(); pm.loadFromData(data); self._pixmap = pm
        except Exception: pass
        self.update()
    def _on_frame(self):
        if self._active: self.update()
    def _set_active(self, on):
        self._active = on
        if self._movie:
            if on and self._movie.state() != QMovie.MovieState.Running: self._movie.start()
            elif not on and self._movie.state() == QMovie.MovieState.Running: self._movie.stop()
    def showEvent(self, e): super().showEvent(e); self._set_active(True)
    def hideEvent(self, e): super().hideEvent(e); self._set_active(False)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2); path = QPainterPath(); path.addRoundedRect(r, 12, 12)
        p.setClipPath(path); p.fillPath(path, QBrush(QColor("#202127")))
        pm = self._movie.currentPixmap() if (self._movie and self._movie.isValid()) else self._pixmap
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(r.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(r.x() + (r.width() - scaled.width()) / 2), int(r.y() + (r.height() - scaled.height()) / 2), scaled)
        elif self._loading:
            p.setPen(QColor("#8b8f9a")); p.drawText(r, Qt.AlignmentFlag.AlignCenter, "…")
        if self.underMouse():
            p.fillPath(path, QBrush(QColor(91, 108, 255, 60))); p.setPen(QPen(QColor("#5b6cff"), 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
    def enterEvent(self, e): self.update()
    def leaveEvent(self, e): self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.picked.emit(self.item.get("full") or self.item.get("preview"))


class GifPickerDialog(RoundedDialog):
    def __init__(self, parent=None, api_key=""):
        super().__init__(parent); self.setModal(True); self.setFixedSize(560, 620)
        self.api_key = api_key; self._result_url = ""; self._workers = []; self._thumbs = []
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(12)
        head, close = _dlg_title(self, "Гифка из интернета (Tenor)"); close.clicked.connect(self.reject); v.addLayout(head)
        sr = QHBoxLayout(); sr.setSpacing(8)
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("Поиск гифок (например: cat, dance, wow)")
        self.search_edit.returnPressed.connect(self.do_search)
        sb = _primary_btn("Найти"); sb.clicked.connect(self.do_search)
        sr.addWidget(self.search_edit, 1); sr.addWidget(sb); v.addLayout(sr)
        self.status = QLabel("Введите запрос и нажмите «Найти»"); self.status.setStyleSheet("color:#8b8f9a;font-size:12px;"); v.addWidget(self.status)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:1px solid #2a2b33;border-radius:10px;}QScrollArea > QWidget > QWidget{background:transparent;}")
        self.box = QWidget(); self.box.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.box); self.grid.setContentsMargins(8, 8, 8, 8); self.grid.setSpacing(8)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.box); v.addWidget(self.scroll, 1)
        low = QHBoxLayout(); low.setSpacing(8)
        self.manual_edit = QLineEdit(); self.manual_edit.setPlaceholderText("…или вставьте прямую ссылку на .gif")
        low.addWidget(self.manual_edit, 1)
        use = QPushButton("Использовать"); use.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); use.clicked.connect(self._use_manual); low.addWidget(use)
        v.addLayout(low)
        btns = QHBoxLayout(); btns.setSpacing(8)
        kb = _ghost_btn("🔑 Ключ Tenor"); kb.clicked.connect(self._set_key); btns.addWidget(kb); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject); btns.addWidget(cancel); v.addLayout(btns)
        self.search_edit.setFocus()
    def _set_key(self):
        d = TextInputDialog(self, "Ключ Tenor API",
                            "Вставьте ключ из https://developers.google.com/tenor/guides/quickstart:",
                            text=self.api_key, max_len=64)
        if d.exec():
            self.api_key = d.value(); self.status.setText("Ключ сохранён" if self.api_key else "Ключ не задан")
    def _use_manual(self):
        url = self.manual_edit.text().strip()
        if not url: return
        self._result_url = url; self.accept()
    def do_search(self):
        q = self.search_edit.text().strip(); self._clear_grid(); self.status.setText("Поиск…")
        w = GifSearchWorker(q, self.api_key, parent=self); w.done.connect(self._on_results); w.start(); self._workers.append(w)
    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0); w = item.widget()
            if w: w.setParent(None); w.deleteLater()
        self._thumbs = []
    def _on_results(self, results, err):
        if err: self.status.setText(err); return
        if not results: self.status.setText("Ничего не найдено"); return
        self.status.setText(f"Найдено: {len(results)}"); cols = 3
        for i, item in enumerate(results):
            tile = GifTile(i, item); tile.picked.connect(self._pick)
            r, c = divmod(i, cols); self.grid.addWidget(tile, r, c); self._thumbs.append(tile)
            tw = GifThumbWorker(i, item["preview"], parent=self); tw.loaded.connect(tile.set_data); tw.start(); self._workers.append(tw)
    def _pick(self, url): self._result_url = url; self.accept()
    def result_url(self): return self._result_url


# ---------- Голос ----------
def _write_wav_slice(src_path, dst_path, start_sec, end_sec):
    with wave.open(src_path, "rb") as w:
        params = w.getparams(); fr = params.framerate
        s = max(0.0, float(start_sec)); e = max(s, float(end_sec))
        sf = int(s * fr); ef = int(e * fr)
        w.setpos(min(sf, params.nframes)); frames = w.readframes(max(0, ef - sf))
    with wave.open(dst_path, "wb") as out: out.setparams(params); out.writeframes(frames)


class WaveformWidget(QWidget):
    __slots__ = ("_peaks", "_start", "_end", "_duration")
    def __init__(self, parent=None):
        super().__init__(parent); self.setMinimumHeight(80)
        self._peaks = []; self._start = 0.0; self._end = 1.0; self._duration = 0.0; self.setStyleSheet("background: transparent;")
    def set_wave(self, peaks, duration):
        self._peaks = peaks; self._duration = duration; self._start = 0.0; self._end = 1.0; self.update()
    def set_range(self, start, end):
        self._start = max(0.0, min(1.0, start)); self._end = max(self._start, min(1.0, end)); self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2); path = QPainterPath(); path.addRoundedRect(r, 10, 10)
        p.fillPath(path, QBrush(QColor("#202127")))
        if self._peaks:
            sx = r.x() + r.width() * self._start; ex = r.x() + r.width() * self._end
            p.fillRect(QRectF(sx, r.y(), max(0, ex - sx), r.height()), QColor(91, 108, 255, 60))
            n = len(self._peaks); mid = r.center().y(); step = r.width() / max(1, n)
            pen = QPen(QColor("#5b6cff")); pen.setWidth(1); p.setPen(pen)
            for i, peak in enumerate(self._peaks):
                x = r.x() + i * step; h = peak * (r.height() / 2 - 2)
                p.drawLine(int(x), int(mid - h), int(x), int(mid + h))
            p.setPen(QPen(QColor("#e6e8ee"), 1))
            p.drawLine(int(r.x() + r.width() * self._start), int(r.y()), int(r.x() + r.width() * self._start), int(r.bottom()))
            p.drawLine(int(r.x() + r.width() * self._end), int(r.y()), int(r.x() + r.width() * self._end), int(r.bottom()))
        else:
            p.setPen(QColor("#4b4f5a")); p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Нет записи")


class VoiceRecorderDialog(RoundedDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setModal(True); self.setFixedSize(520, 520)
        self._recording = False; self._source = None; self._buf = None; self._raw_path = ""; self._result_path = ""; self._duration = 0.0; self._elapsed = 0.0
        self._player = QMediaPlayer(self); self._audio = QAudioOutput(self); self._player.setAudioOutput(self._audio)
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(12)
        head, close = _dlg_title(self, "Запись голоса"); close.clicked.connect(self.reject); v.addLayout(head)
        hint = QLabel(f"Запись до {MAX_VOICE_SEC} секунд. Затем выберите начало и конец.")
        hint.setStyleSheet("color:#8b8f9a;font-size:12px;"); v.addWidget(hint)
        self.wave = WaveformWidget(); v.addWidget(self.wave, 1)
        self.timer_lbl = QLabel(f"0.0 / {MAX_VOICE_SEC:.1f} сек"); self.timer_lbl.setStyleSheet("color:#b8bcc6;font-size:12px;")
        self.timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.timer_lbl)
        rec_row = QHBoxLayout(); rec_row.setSpacing(8)
        self.rec_btn = QPushButton("● Записать"); self.rec_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.rec_btn.setMinimumHeight(42)
        self.rec_btn.setStyleSheet("QPushButton{background:#e74c3c;color:white;border:none;border-radius:10px;padding:10px 20px;font-weight:600;font-size:13px;}QPushButton:hover{background:#d44233;}")
        self.rec_btn.clicked.connect(self.toggle_record); rec_row.addWidget(self.rec_btn, 1)
        self.play_btn = QPushButton("▶ Прослушать"); self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setMinimumHeight(42); self.play_btn.setEnabled(False); self.play_btn.clicked.connect(self.play_result)
        rec_row.addWidget(self.play_btn, 1); v.addLayout(rec_row)
        v.addWidget(self._small_lbl("НАЧАЛО"))
        self.start_slider = QSlider(Qt.Orientation.Horizontal); self.start_slider.setRange(0, 1000)
        self.start_slider.valueChanged.connect(self._on_trim); v.addWidget(self.start_slider)
        v.addWidget(self._small_lbl("КОНЕЦ"))
        self.end_slider = QSlider(Qt.Orientation.Horizontal); self.end_slider.setRange(0, 1000); self.end_slider.setValue(1000)
        self.end_slider.valueChanged.connect(self._on_trim); v.addWidget(self.end_slider)
        btns = QHBoxLayout(); btns.setSpacing(8); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        self.save_btn = _primary_btn("Сохранить"); self.save_btn.setEnabled(False); self.save_btn.clicked.connect(self._save_final)
        btns.addWidget(cancel); btns.addWidget(self.save_btn); v.addLayout(btns)
        self._timer = QTimer(self); self._timer.setInterval(100); self._timer.timeout.connect(self._tick)
    def _small_lbl(self, text):
        l = QLabel(text); l.setStyleSheet("color:#8b8f9a;font-size:11px;font-weight:600;letter-spacing:1px;"); return l
    def toggle_record(self):
        if self._recording: self._stop_record()
        else: self._start_record()
    def _start_record(self):
        dev = QMediaDevices.defaultAudioInput()
        if dev.isNull(): MsgDialog.show_message(self, "Нет микрофона", "Микрофон не найден.", "🎙"); return
        fmt = QAudioFormat(); fmt.setSampleRate(44100); fmt.setChannelCount(1); fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._source = QAudioSource(dev, fmt, self); self._buf = QBuffer(); self._buf.open(QIODevice.OpenModeFlag.WriteOnly)
        self._source.start(self._buf); self._recording = True; self._elapsed = 0.0
        self.rec_btn.setText("■ Стоп"); self.play_btn.setEnabled(False); self.save_btn.setEnabled(False); self._timer.start()
    def _tick(self):
        if not self._recording: return
        self._elapsed += 0.1; self.timer_lbl.setText(f"{self._elapsed:.1f} / {MAX_VOICE_SEC:.1f} сек")
        if self._elapsed >= MAX_VOICE_SEC: self._stop_record()
    def _stop_record(self):
        self._timer.stop(); self._recording = False; self.rec_btn.setText("● Записать")
        if self._source: self._source.stop()
        raw = bytes(self._buf.data()) if self._buf else b""; self._buf = None
        if not raw: self.save_btn.setEnabled(False); return
        path = os.path.join(MEDIA_DIR, f"voice_raw_{uuid.uuid4().hex}.wav")
        with wave.open(path, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(raw)
        self._raw_path = path; self._load_wave(path); self.save_btn.setEnabled(True); self.play_btn.setEnabled(True)
    def _load_wave(self, path):
        try:
            with wave.open(path, "rb") as w: params = w.getparams(); data = w.readframes(w.getnframes())
        except Exception: return
        fr = params.framerate or 44100; n = params.sampwidth * params.nchannels or 2; self._duration = params.nframes / fr if fr else 0.0
        self.timer_lbl.setText(f"{self._duration:.1f} / {MAX_VOICE_SEC:.1f} сек")
        samples = []; count = len(data) // n; step = max(1, count // 300)
        for i in range(0, count, step):
            chunk = data[i * n:(i + 1) * n]
            if len(chunk) >= 2:
                v = int.from_bytes(chunk[:2], "little", signed=True); samples.append(abs(v) / 32768.0)
        self.wave.set_wave(samples, self._duration); self.start_slider.setValue(0); self.end_slider.setValue(1000)
    def _on_trim(self):
        s = self.start_slider.value() / 1000.0; e = self.end_slider.value() / 1000.0
        if e < s: self.end_slider.setValue(self.start_slider.value()); e = s
        self.wave.set_range(s, e)
    def play_result(self):
        if not self._raw_path: return
        s = (self.start_slider.value() / 1000.0) * self._duration; e = (self.end_slider.value() / 1000.0) * self._duration
        if e - s < 0.05: return
        tmp = os.path.join(tempfile.gettempdir(), f"_preview_{uuid.uuid4().hex}.wav")
        try:
            _write_wav_slice(self._raw_path, tmp, s, e); self._player.stop(); self._player.setSource(QUrl.fromLocalFile(tmp)); self._player.play()
        except Exception as ex: MsgDialog.show_message(self, "Ошибка", str(ex), "⚠")
    def _save_final(self):
        if not self._raw_path: return
        s = (self.start_slider.value() / 1000.0) * self._duration; e = (self.end_slider.value() / 1000.0) * self._duration
        if e - s < 0.05: MsgDialog.show_message(self, "Слишком коротко", "Выделите хотя бы 0.1 сек.", "✂"); return
        out = os.path.join(MEDIA_DIR, f"voice_{uuid.uuid4().hex}.wav")
        try: _write_wav_slice(self._raw_path, out, s, e)
        except Exception as ex: MsgDialog.show_message(self, "Ошибка", str(ex), "⚠"); return
        self._result_path = out; self.accept()
    def result_path(self): return self._result_path


# ---------- Тема ----------
class ThemeDialog(RoundedDialog):
    def __init__(self, parent=None, theme=None):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(480)
        self.theme = dict(theme or DEFAULT_THEME)
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(12)
        head, close = _dlg_title(self, "Настройки темы"); close.clicked.connect(self.reject); v.addLayout(head)
        v.addWidget(self._lbl("ОКНО")); self.swatches = {}
        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(8)
        for i, (k, lbl) in enumerate((("bg", "Фон"), ("panel", "Панель"), ("accent", "Акцент"), ("text", "Текст"))):
            grid.addWidget(self._lbl(lbl), i, 0); grid.addWidget(self._swatch(k), i, 1)
        v.addLayout(grid)
        v.addWidget(self._lbl("КНОПКИ"))
        grid2 = QGridLayout(); grid2.setHorizontalSpacing(10); grid2.setVerticalSpacing(8)
        for i, (k, lbl) in enumerate((("btn_bg", "Фон кнопки"), ("btn_text", "Текст кнопки"))):
            grid2.addWidget(self._lbl(lbl), i, 0); grid2.addWidget(self._swatch(k), i, 1)
        v.addLayout(grid2)
        v.addWidget(self._lbl("ФОН ОКНА (КАРТИНКА / ГИФКА)"))
        g = QHBoxLayout(); g.setSpacing(8)
        self.bg_edit = QLineEdit(self.theme.get("bg_image", "")); self.bg_edit.setPlaceholderText("путь к изображению/гифке")
        bb = QPushButton("Обзор"); bb.clicked.connect(self.pick_bg)
        bc = QPushButton("Убрать"); bc.clicked.connect(lambda: self.bg_edit.setText(""))
        for b in (bb, bc): b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        g.addWidget(self.bg_edit, 1); g.addWidget(bb); g.addWidget(bc); v.addLayout(g)
        v.addSpacing(10)
        btns = QHBoxLayout(); btns.setSpacing(8)
        reset = _ghost_btn("Сбросить тему"); reset.clicked.connect(self.reset_theme); btns.addWidget(reset); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("Применить"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        self.refresh_swatches()
    def _lbl(self, text):
        l = QLabel(text); l.setStyleSheet("color:#8b8f9a;font-size:11px;font-weight:600;letter-spacing:1px;"); return l
    def _swatch(self, key):
        sw = QPushButton(); sw.setFixedSize(38, 38); sw.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); sw.clicked.connect(lambda _, k=key: self.pick_color(k))
        self.swatches[key] = sw; return sw
    def refresh_swatches(self):
        for k, sw in self.swatches.items(): sw.setStyleSheet(f"background:{self.theme[k]};border:1px solid #3a3b45;border-radius:8px;")
    def pick_color(self, key):
        d = ColorPickerDialog(self, "Цвет", current=self.theme[key], default=DEFAULT_THEME[key])
        if d.exec(): self.theme[key] = d.color(); self.refresh_swatches()
    def pick_bg(self):
        p, _ = QFileDialog.getOpenFileName(self, "Фон окна", "", "Изображения и гифки (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.apng);;Все файлы (*)")
        if p: self.bg_edit.setText(p)
    def reset_theme(self):
        self.theme = dict(DEFAULT_THEME); self.bg_edit.setText(""); self.refresh_swatches()
    def result_theme(self):
        t = dict(self.theme); t["bg_image"] = self.bg_edit.text().strip(); t["gif"] = t["bg_image"]; return t


# ---------- Действия ----------
class ActionRow(QWidget):
    changed = pyqtSignal()
    removed = pyqtSignal(object)
    def __init__(self, action=None, parent=None):
        super().__init__(parent)
        action = dict(action or {"type": "sound", "value": ""}); self._type = action.get("type", "sound")
        if self._type not in ACTION_TYPES: self._type = "sound"
        self._value = action.get("value", ""); self.setStyleSheet("background: transparent;")
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        self.type_btn = QPushButton(ACTION_TYPES[self._type]); self.type_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.type_btn.setMinimumHeight(36); self.type_btn.setFixedWidth(110)
        self.type_btn.setStyleSheet("QPushButton{background:#202127;color:#e6e8ee;border:1px solid #2a2b33;border-radius:8px;padding:6px 10px;font-size:12px;text-align:left;}QPushButton:hover{background:#26272e;}")
        self.type_btn.clicked.connect(self._open_type_menu); h.addWidget(self.type_btn)
        self.edit = QLineEdit(self._value); self.edit.setMinimumHeight(36); self.edit.textChanged.connect(self._on_text); h.addWidget(self.edit, 1)
        self.browse = QPushButton("Обзор"); self.browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.browse.setMinimumHeight(36)
        self.browse.setStyleSheet("QPushButton{background:#202127;color:#e6e8ee;border:1px solid #2a2b33;border-radius:8px;padding:6px 10px;font-size:12px;}QPushButton:hover{background:#26272e;}")
        self.browse.clicked.connect(self._pick); h.addWidget(self.browse)
        self.rec_btn = QPushButton("🎙"); self.rec_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.rec_btn.setFixedSize(36, 36)
        self.rec_btn.setToolTip("Записать голос (до 10 сек) с обрезкой")
        self.rec_btn.setStyleSheet("QPushButton{background:#202127;color:#e6e8ee;border:1px solid #2a2b33;border-radius:8px;font-size:14px;}QPushButton:hover{background:#26272e;border-color:#5b6cff;}")
        self.rec_btn.clicked.connect(self._record_voice); h.addWidget(self.rec_btn)
        self.remove = QPushButton("✕"); self.remove.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.remove.setFixedSize(36, 36)
        self.remove.setStyleSheet("QPushButton{background:transparent;color:#8b8f9a;border:1px solid #2a2b33;border-radius:8px;font-size:14px;}QPushButton:hover{background:#2a1f22;color:#e74c3c;border-color:#5c2a2a;}")
        self.remove.clicked.connect(lambda: self.removed.emit(self)); h.addWidget(self.remove)
        self._update_type_ui()
    def _update_type_ui(self):
        self.type_btn.setText(ACTION_TYPES[self._type]); self.browse.setEnabled(self._type in ("sound", "app", "file")); self.rec_btn.setVisible(self._type == "sound")
        self.edit.setPlaceholderText({"sound": "C:/music/track.mp3", "url": "https://example.com", "app": "C:/Program Files/App/app.exe, notepad.exe, steam://run/730", "file": "C:/Pictures/photo.jpg, C:/docs/report.pdf"}.get(self._type, ""))
        self.changed.emit()
    def _open_type_menu(self):
        m = QMenu(self); m.setStyleSheet(_menu_style())
        for key, label in ACTION_TYPES.items():
            act = m.addAction(label); act.setCheckable(True); act.setChecked(key == self._type); act.triggered.connect(lambda _, k=key: self._set_type(k))
        m.exec(self.type_btn.mapToGlobal(QPoint(0, self.type_btn.height())))
    def _set_type(self, t): self._type = t; self._update_type_ui()
    def _record_voice(self):
        d = VoiceRecorderDialog(self)
        if d.exec() and d.result_path(): self.edit.setText(d.result_path())
    def _pick(self):
        if self._type == "sound":
            p, _ = QFileDialog.getOpenFileName(self, "Звук", "", "Аудио (*.wav *.mp3 *.ogg *.flac)")
            if p: self.edit.setText(p)
            return
        if self._type == "file":
            m = QMenu(self); m.setStyleSheet(_menu_style()); m.addAction("Любой файл…", self._pick_file_any); m.addAction("Картинка…", self._pick_image); m.addAction("Папка…", self._pick_folder)
            m.exec(self.browse.mapToGlobal(QPoint(0, self.browse.height()))); return
        if self._type == "app":
            m = QMenu(self); m.setStyleSheet(_menu_style()); m.addAction("Программа…", self._pick_executable); m.addAction("Любой файл…", self._pick_file_any); m.addAction("Папка…", self._pick_folder)
            m.exec(self.browse.mapToGlobal(QPoint(0, self.browse.height())))
    def _pick_executable(self):
        flt = "Программы (*.exe *.msi *.bat *.cmd *.com *.ps1 *.lnk);;Все файлы (*.*)" if sys.platform.startswith("win") else ("Приложения (*.app);;Все файлы (*.*)" if sys.platform == "darwin" else "Все файлы (*.*)")
        p, _ = QFileDialog.getOpenFileName(self, "Выберите программу", "", flt)
        if p: self.edit.setText(p)
    def _pick_file_any(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", "Все файлы (*.*)")
        if p: self.edit.setText(p)
    def _pick_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.svg *.ico);;Все файлы (*.*)")
        if p: self.edit.setText(p)
    def _pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if p: self.edit.setText(p)
    def _on_text(self, text): self._value = text.strip(); self.changed.emit()
    def get_action(self): return {"type": self._type, "value": self.edit.text().strip()}
    def is_valid(self): return bool(self.edit.text().strip())


class ActionsDialog(RoundedDialog):
    def __init__(self, parent=None, actions=None):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(660); self._rows = []
        v = QVBoxLayout(self); v.setContentsMargins(22, 20, 22, 22); v.setSpacing(12)
        head, close = _dlg_title(self, "Действия кнопки"); close.clicked.connect(self.reject); v.addLayout(head)
        hint = QLabel("Можно добавить несколько действий — они выполнятся по порядку."); hint.setWordWrap(True); hint.setStyleSheet("color:#8b8f9a;font-size:12px;"); v.addWidget(hint)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(140); self.scroll.setMaximumHeight(360)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:1px solid #2a2b33;border-radius:10px;}QScrollArea > QWidget > QWidget{background:transparent;}")
        self.box = QWidget(); self.box.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.box); self.rows_layout.setContentsMargins(8, 8, 8, 8); self.rows_layout.setSpacing(8)
        self.rows_layout.addStretch(1); self.scroll.setWidget(self.box); v.addWidget(self.scroll, 1)
        self.empty_label = QLabel("Пока нет действий"); self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty_label.setStyleSheet("color:#4b4f5a;font-size:12px;"); v.addWidget(self.empty_label)
        add_row = QHBoxLayout(); add_row.setSpacing(8)
        add_btn = QPushButton("+ Добавить действие"); add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); add_btn.setMinimumHeight(38)
        add_btn.setStyleSheet("QPushButton{background:#202127;color:#e6e8ee;border:1px dashed #3a3b45;border-radius:8px;padding:8px 14px;font-size:12px;}QPushButton:hover{background:#26272e;border-color:#5b6cff;color:#e6e8ee;}")
        add_btn.clicked.connect(self._add_row); add_row.addWidget(add_btn); add_row.addStretch(1); v.addLayout(add_row)
        btns = QHBoxLayout(); btns.setSpacing(8); btns.addStretch(1)
        cancel = _ghost_btn("Отмена"); cancel.clicked.connect(self.reject)
        ok = _primary_btn("Сохранить"); ok.setDefault(True); ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok); v.addLayout(btns)
        for a in normalize_actions(actions or []): self._add_row(a)
        self._update_empty()
    def _add_row(self, action=None):
        row = ActionRow(action); row.removed.connect(self._remove_row); row.changed.connect(self._update_empty)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row); self._rows.append(row); self._update_empty()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
    def _remove_row(self, row):
        if row in self._rows: self._rows.remove(row); row.setParent(None); row.deleteLater()
        self._update_empty()
    def _update_empty(self): self.empty_label.setVisible(not any(r.is_valid() for r in self._rows))
    def result_actions(self): return [a for r in self._rows if (a := r.get_action())["value"]]


# ---------- Плитка ----------
class AppTile(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent); self._opacity = 0.0; self._lift = 0.0; self.actions = []
        self.btn_bg = QColor("#202127"); self.btn_text = QColor("#e6e8ee"); self.font_spec = dict(DEFAULT_BUTTON_FONT)
        self._media = MediaAsset(self.update); self._player = None; self._audio = None
        self._select_mode = False; self._selected = False; self._main = None; self._url_worker = None
        self._press_pos = None; self._press_active = False; self._dragging_tile = False
        self.setFixedSize(TILE_SIZE, TILE_SIZE); self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.customContextMenuRequested.connect(self.show_menu)
        self._fade = QPropertyAnimation(self, b"opacity", self); self._fade.setDuration(380); self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press = QPropertyAnimation(self, b"geometry", self); self._press.setDuration(110); self._press.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.clicked.connect(self.run)

    def set_tile_size(self, size: int):
        if size == self.width() == self.height(): return
        self.setFixedSize(size, size); self.update()

    def set_active_visual(self, active: bool):
        """Включает/выключает анимацию гифки на кнопке в зависимости от активности приложения."""
        self._media.activate(active and self.isVisible())

    def get_opacity(self): return self._opacity
    def set_opacity(self, v): self._opacity = v; self.update()
    opacity = pyqtProperty(float, fget=get_opacity, fset=set_opacity)

    def get_lift(self): return self._lift
    def set_lift(self, v): self._lift = v; self.update()
    lift = pyqtProperty(float, fget=get_lift, fset=set_lift)

    def set_colors(self, bg_hex, text_hex): self.btn_bg = QColor(bg_hex); self.btn_text = QColor(text_hex); self.update()
    def set_font_spec(self, spec): self.font_spec = normalize_font(spec); self.update()
    def set_image(self, path: str): self._media.set_path(path); self._media.activate(self.isVisible() and getattr(self._main, '_is_app_active', True)); self.update()
    def image_path(self): return self._media.path

    def set_select_mode(self, on: bool):
        self._select_mode = on
        if not on: self._selected = False
        self.update()

    def is_selected(self): return self._selected
    def set_selected(self, on: bool): self._selected = on; self.update()

    def showEvent(self, e): super().showEvent(e); self._media.activate(getattr(self._main, '_is_app_active', True))
    def hideEvent(self, e): super().hideEvent(e); self._media.activate(False)

    def _qfont(self, point_size):
        f = QFont()
        if self.font_spec["family"]: f.setFamily(self.font_spec["family"])
        f.setPointSize(point_size); f.setBold(self.font_spec["bold"]); return f

    def _draw_text_block(self, p, text, rect, base_font_size):
        if not text: return
        scale = max(0.55, min(1.0, self.width() / TILE_SIZE)); pt = max(6, int(round(base_font_size * self.font_spec["size"] / 10 * scale)))
        f = self._qfont(pt); p.setFont(f); fm = QFontMetrics(f); max_w = int(rect.width()) - 4
        one = fm.elidedText(text, Qt.TextElideMode.ElideRight, max_w)
        if fm.horizontalAdvance(one) <= max_w and one == text: p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text); return
        words = text.split(); lines = []; cur = ""
        for w in words:
            candidate = (cur + " " + w).strip()
            if fm.horizontalAdvance(candidate) <= max_w: cur = candidate
            else:
                if cur: lines.append(cur)
                cur = w
                if len(lines) >= 3: break
        if cur and len(lines) < 3: lines.append(cur)
        if " ".join(lines) != text and lines:
            last = lines[-1]
            while last and fm.horizontalAdvance(last + "…") > max_w: last = last[:-1]
            lines[-1] = (last + "…") if last else "…"
        line_h = fm.height(); total_h = line_h * len(lines); start_y = rect.y() + rect.height() - total_h - 2
        for i, ln in enumerate(lines):
            p.drawText(QRectF(rect.x(), start_y + i * line_h, rect.width(), line_h), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, ln)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        RING = 3; lift = self._lift; scale = 1.0 + 0.06 * lift
        p.translate(self.width() / 2, self.height() / 2); p.scale(scale, scale); p.translate(-self.width() / 2, -self.height() / 2)
        outer = QRectF(0, 0, self.width(), self.height()); inner = outer.adjusted(RING, RING, -RING, -RING)
        po = QPainterPath(); po.addRoundedRect(outer, TILE_RADIUS, TILE_RADIUS); pi = QPainterPath(); pi.addRoundedRect(inner, TILE_RADIUS - RING, TILE_RADIUS - RING)
        if lift > 0.01: p.fillPath(po.translated(0, 6 * lift), QBrush(QColor(0, 0, 0, int(90 * lift))))
        rc = QColor(self.btn_bg); rc.setAlpha(int(255 * (0.55 + 0.45 * self._opacity))); p.fillPath(po, QBrush(rc))
        bg = QColor(self.btn_bg); bg.setAlpha(int(255 * (0.45 + 0.55 * self._opacity))); p.setClipPath(pi); p.fillPath(pi, QBrush(bg))
        if self.underMouse() and not self._select_mode: hov = QColor(255, 255, 255); hov.setAlpha(18); p.fillPath(pi, QBrush(hov))
        pm = self._media.current_frame()
        if pm is not None and not pm.isNull():
            iw, ih = int(inner.width()), int(inner.height()); scaled = pm.scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            src = QRectF((scaled.width() - iw) / 2, (scaled.height() - ih) / 2, iw, ih); p.drawPixmap(int(inner.x()), int(inner.y()), scaled.copy(src.toRect()))
            txt = self.text()
            if txt:
                oh = 32; o = QPainterPath(); o.addRoundedRect(QRectF(inner.x() + 4, inner.bottom() - oh - 4, inner.width() - 8, oh), 8, 8)
                p.fillPath(o, QBrush(QColor(0, 0, 0, int(170 * self._opacity)))); tx = QColor(self.btn_text); tx.setAlpha(int(255 * (0.55 + 0.45 * self._opacity))); p.setPen(tx)
                self._draw_text_block(p, txt, QRectF(inner.x() + 6, inner.bottom() - oh - 4, inner.width() - 12, oh - 4), base_font_size=9)
        else:
            tx = QColor(self.btn_text); tx.setAlpha(int(255 * (0.55 + 0.45 * self._opacity))); p.setPen(tx)
            self._draw_text_block(p, self.text(), QRectF(inner.x() + 6, inner.y() + 6, inner.width() - 12, inner.height() - 12), base_font_size=10)
        n = len(self.actions)
        if n > 1:
            r = 9; cx = inner.left() + 10; cy = inner.top() + 10; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#5b6cff"))
            p.drawEllipse(QPoint(int(cx), int(cy)), r, r); p.setPen(QColor("white")); f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)
            p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2), Qt.AlignmentFlag.AlignCenter, str(n))
        border = self.btn_bg.lighter(150); border.setAlpha(int(60 + 100 * self._opacity)); p.setPen(border); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(pi)
        if self._select_mode:
            if not self._selected: p.fillPath(pi, QBrush(QColor(0, 0, 0, 100)))
            pen = p.pen(); pen.setColor(QColor("#5b6cff")); pen.setWidth(3); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(pi)
            box = 22; circle = QPainterPath(); circle.addEllipse(QRectF(inner.right() - box - 4, inner.top() + 4, box, box))
            p.fillPath(circle, QBrush(QColor("#5b6cff") if self._selected else QColor(0, 0, 0, 140)))
            p.setPen(QColor("white")); f = p.font(); f.setPointSize(11); f.setBold(True); p.setFont(f)
            p.drawText(QRectF(inner.right() - box - 4, inner.top() + 4, box, box), Qt.AlignmentFlag.AlignCenter, "✓" if self._selected else "")

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return super().mousePressEvent(e)
        if self._select_mode:
            shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if self._main:
                self._main.handle_tile_select_click(self, shift)
            e.accept(); return
        self._press_pos = e.globalPosition().toPoint(); self._press_active = True; self._dragging_tile = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._press_active or self._select_mode: return super().mouseMoveEvent(e)
        if not (e.buttons() & Qt.MouseButton.LeftButton): return super().mouseMoveEvent(e)
        if not self._dragging_tile:
            if (e.globalPosition().toPoint() - self._press_pos).manhattanLength() < DRAG_THRESHOLD: return super().mouseMoveEvent(e)
            self._dragging_tile = True
            QPushButton.mouseReleaseEvent(self, QMouseEvent(QMouseEvent.Type.MouseButtonRelease, e.position(), e.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            if self._main: self._main.start_tile_drag(self, self._press_pos)
            e.accept(); return
        if self._dragging_tile and self._main: self._main._on_global_move(e.globalPosition().toPoint()); e.accept(); return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return super().mouseReleaseEvent(e)
        was = self._dragging_tile; self._press_active = False; self._dragging_tile = False; self._press_pos = None
        if was: return
        super().mouseReleaseEvent(e)

    def appear(self):
        self._fade.stop(); self._fade.setStartValue(0.0); self._fade.setEndValue(1.0); self._fade.start()

    def _play_sound(self, path):
        if not os.path.exists(path): MsgDialog.show_message(self, "Файл не найден", f"Аудиофайл не найден:\n{path}", "⚠"); return
        if not self._player:
            self._player = QMediaPlayer(self); self._audio = QAudioOutput(self); self._player.setAudioOutput(self._audio)
        self._player.stop(); self._player.setSource(QUrl.fromLocalFile(path)); self._player.play()

    def _run_urls(self, urls):
        if not urls: return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        worker = UrlCheckWorker(urls, self); self._url_worker = worker; results = {}
        def _one(i, url, ok, err): results[i] = (url, ok, err)
        def _all():
            QApplication.restoreOverrideCursor(); failed = []
            for i in range(len(urls)):
                url, ok, err = results.get(i, (urls[i], False, "Неизвестная ошибка"))
                if not ok: failed.append((url, err)); continue
                if not webbrowser.open(url): failed.append((url, "Браузер не смог открыть."))
            self._url_worker = None
            if failed: MsgDialog.show_message(self, "Не удалось открыть сайт", "Часть сайтов недоступна:\n\n" + "\n\n".join(f"• {u}\n  {e}" for u, e in failed), "🌐")
        worker.finished_one.connect(_one); worker.finished_all.connect(_all); worker.start()

    def _run_file_action(self, value):
        raw = value.strip().strip('"')
        if not raw: return False, "Пустой путь."
        expanded = os.path.expandvars(os.path.expanduser(raw))
        if not os.path.exists(expanded): return False, f"Файл или папка не найдены:\n{expanded}"
        return _open_file_with_os(expanded)

    def run(self):
        if self._select_mode: return
        r = self.geometry(); self._press.stop(); self._press.setStartValue(r)
        small = QRect(r.x() + 3, r.y() + 3, r.width() - 6, r.height() - 6); self._press.setKeyValueAt(0.5, small); self._press.setEndValue(r); self._press.start()
        actions = normalize_actions(self.actions)
        if not actions: return
        url_actions = []; errors = []
        for a in actions:
            t, v = a["type"], a["value"]
            try:
                if t == "sound":
                    if not os.path.exists(v): errors.append(f"• Звук: файл не найден\n  {v}"); continue
                    self._play_sound(v)
                elif t == "url":
                    url = v
                    if not url.lower().startswith(("http://", "https://")): url = "https://" + url.lstrip("/")
                    url_actions.append(url)
                elif t == "file":
                    ok, err = self._run_file_action(v)
                    if not ok: errors.append(f"• Файл: {err}")
                elif t == "app":
                    raw = v.strip().strip('"')
                    if not raw: errors.append("• Запуск: пустая команда"); continue
                    raw = os.path.expandvars(os.path.expanduser(raw)); program, args = _split_command(raw)
                    is_special = _is_special_target(raw); is_path = bool(program) and os.path.exists(program)
                    if not is_special and not is_path and not program: errors.append("• Запуск: пустая команда"); continue
                    ok, err = _open_with_os(raw if (is_special or not args) else program, args if not is_special else [])
                    if not ok: errors.append(f"• Запуск: не удалось\n  {raw}\n  {err}")
            except Exception as ex: errors.append(f"• {ACTION_TYPES.get(t, t)}: {ex}")
        if url_actions: self._run_urls(url_actions)
        if errors: MsgDialog.show_message(self, "Ошибки при выполнении", "Не удалось выполнить:\n\n" + "\n\n".join(errors), "⚠")

    def show_menu(self, pos):
        m = QMenu(self); m.setStyleSheet(_menu_style())
        n = len(normalize_actions(self.actions))
        label = (f"Действия ({n})…" if n > 1 else ("Действие…" if n == 1 else "Добавить действие…"))
        m.addAction(label, self.edit_actions)
        m.addAction("Дублировать (Ctrl+D)", self.duplicate)
        m.addAction("Переименовать", self.rename)
        m.addAction("Цвет кнопки", self.pick_colors)
        m.addAction("Шрифт текста…", self.pick_font)
        m.addAction("Картинка", self.pick_image)
        m.addAction("Гифка (файл)", self.pick_gif)
        m.addAction("Гифка из интернета…", self.pick_gif_online)
        if self._media.has_content() or self._media.path: m.addAction("Убрать картинку", self.clear_image)
        m.addSeparator(); m.addAction("Удалить", self.delete)
        m.exec(self.mapToGlobal(pos))

    def edit_actions(self):
        d = ActionsDialog(self, self.actions)
        if d.exec(): self.actions = d.result_actions(); self.update(); self._on_change()

    def duplicate(self):
        if self._main: self._main.duplicate_tile(self)

    def rename(self):
        cur = self.text()[:TITLE_MAX_LEN]; d = TextInputDialog(self, "Переименовать", f"Название (до {TITLE_MAX_LEN} символов):", text=cur, max_len=TITLE_MAX_LEN)
        if not d.exec(): return
        t = d.value()
        if t: self.setText(t); self._on_change()

    def pick_colors(self):
        d = ButtonColorsDialog(self, "Цвета кнопки", bg=self.btn_bg.name(), text=self.btn_text.name(), default_bg=DEFAULT_THEME["btn_bg"], default_text=DEFAULT_THEME["btn_text"])
        if d.exec(): bg, tx = d.colors(); self.set_colors(bg, tx); self._on_change()

    def pick_font(self):
        d = ButtonFontDialog(self, self.font_spec)
        if d.exec(): self.set_font_spec(d.font_spec()); self._on_change()

    def pick_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Картинка", "", IMAGE_FILTER)
        if p: self.set_image(p); self._on_change()

    def pick_gif(self):
        p, _ = QFileDialog.getOpenFileName(self, "Гифка", "", GIF_FILTER)
        if p: self.set_image(p); self._on_change()

    def pick_gif_online(self):
        key = self._main._state.get("tenor_key", "") if self._main else ""; d = GifPickerDialog(self, api_key=key)
        if d.exec() and d.result_url(): self._download_and_set(d.result_url())
        if self._main: self._main._state["tenor_key"] = d.api_key; self._main.schedule_save()

    def _download_and_set(self, url):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp: data = resp.read()
            low = url.lower().split("?")[0]; ext = ".gif"
            for c in (".gif", ".webp", ".png", ".jpg", ".jpeg", ".apng"):
                if low.endswith(c): ext = c; break
            path = os.path.join(MEDIA_DIR, f"gif_{uuid.uuid4().hex}{ext}")
            with open(path, "wb") as f: f.write(data)
            self.set_image(path); self._on_change()
        except Exception as ex: MsgDialog.show_message(self, "Не удалось скачать", f"Ошибка загрузки:\n{ex}", "🌐")
        finally: QApplication.restoreOverrideCursor()

    def clear_image(self): self.set_image(""); self._on_change()

    def _on_change(self):
        if self._main: self._main.schedule_save()

    def delete(self):
        self._media.stop()
        if self._main: self._main.remove_tile(self)


# ---------- Главное окно ----------
class MainWindow(RoundedWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Кнопки"); self.resize(580, 720)
        self._state = load_state()
        self.theme = dict(DEFAULT_THEME); self.theme.update(self._state.get("theme", {}))
        if not self.theme.get("bg_image") and self.theme.get("gif"): self.theme["bg_image"] = self.theme["gif"]
        self._pinned = bool(self._state.get("pinned", False)); self._app_icon_path = self._state.get("app_icon", "")
        self._categories = self._state.setdefault("categories", []); self._current_cat = ""
        self.tiles = []; self._select_mode = False; self._drag_tile = None; self._drag_offset = QPoint(0, 0); self._drag_start_index = -1
        self._current_tile_sz = TILE_SIZE
        self._last_clicked_tile = None
        self._is_app_active = True

        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.setInterval(300); self._save_timer.timeout.connect(self._save_now)
        self._resize_timer = QTimer(self); self._resize_timer.setSingleShot(True); self._resize_timer.setInterval(60); self._resize_timer.timeout.connect(self._on_resize)

        v = QVBoxLayout(self._central); v.setContentsMargins(24, 18, 24, 22); v.setSpacing(14)
        head_row = QHBoxLayout(); head_row.setSpacing(12)
        self.app_icon_btn = AppLogoWidget(size=44, radius=10); self.app_icon_btn.clicked.connect(self.change_app_icon)
        head_row.addWidget(self.app_icon_btn, 0, Qt.AlignmentFlag.AlignTop)
        head = QVBoxLayout(); head.setSpacing(4)
        self.title = QLabel("Кнопки"); self.title.setObjectName("title")
        self.sub = QLabel("ПКМ — настройка · ЛКМ — запуск · зажим — поменять местами"); self.sub.setObjectName("subtitle")
        head.addWidget(self.title); head.addWidget(self.sub); head_row.addLayout(head, 1)

        self.pin_btn = QPushButton("📌"); self.pin_btn.setFixedSize(40, 40); self.pin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.pin_btn.setToolTip("Поверх других окон")
        self.pin_btn.setCheckable(True); self.pin_btn.setChecked(self._pinned); self.pin_btn.clicked.connect(self.toggle_pin); head_row.addWidget(self.pin_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.cat_btn = QPushButton("📁"); self.cat_btn.setFixedSize(40, 40); self.cat_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.cat_btn.setToolTip("Категории")
        self.cat_btn.clicked.connect(self.open_categories_menu); head_row.addWidget(self.cat_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.settings_btn = QPushButton("⚙"); self.settings_btn.setFixedSize(40, 40); self.settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings_menu); head_row.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignTop)
        
        self.min_btn = QPushButton("—"); self.min_btn.setFixedSize(40, 40); self.min_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.min_btn.setToolTip("Свернуть")
        self.min_btn.clicked.connect(self.showMinimized); head_row.addWidget(self.min_btn, 0, Qt.AlignmentFlag.AlignTop)
        
        self.close_btn = QPushButton("✕"); self.close_btn.setFixedSize(40, 40); self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.clicked.connect(self.close); head_row.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(head_row)

        self.breadcrumb = QLabel("Кнопки"); self.breadcrumb.setStyleSheet("color:#6c707a;font-size:12px;padding:0 2px;")
        self.breadcrumb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.breadcrumb.mousePressEvent = self._on_breadcrumb_click
        v.addWidget(self.breadcrumb)

        self.line = QFrame(); self.line.setFixedHeight(1); v.addWidget(self.line)

        self.bulk = QWidget(); self.bulk.setStyleSheet("background: transparent;")
        bulk_outer = QHBoxLayout(self.bulk); bulk_outer.setContentsMargins(0, 0, 0, 0); bulk_outer.setSpacing(0)
        self.bulk_scroll = QScrollArea(); self.bulk_scroll.setWidgetResizable(True); self.bulk_scroll.setFixedHeight(42)
        self.bulk_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.bulk_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bulk_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollArea > QWidget > QWidget{background:transparent;}")
        bulk_inner = QWidget(); bulk_inner.setStyleSheet("background: transparent;")
        bl = QHBoxLayout(bulk_inner); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(8)
        self.bulk_count = QLabel("Выбрано: 0"); self.bulk_count.setStyleSheet("color:#b8bcc6;font-size:12px; min-width: 80px;"); bl.addWidget(self.bulk_count)
        bulk_btn_style = ("QPushButton{background:#202127;color:#e6e8ee;border:1px solid #2a2b33;border-radius:8px;padding:6px 12px;font-size:12px;}"
                          "QPushButton:hover{background:#26272e;}QPushButton:checked{background:#5b6cff;color:white;border:1px solid #5b6cff;}")
        self.sel_all_btn = QPushButton("Все"); self.sel_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.sel_all_btn.setMinimumHeight(34)
        self.sel_all_btn.setStyleSheet(bulk_btn_style); self.sel_all_btn.setCheckable(True); self.sel_all_btn.clicked.connect(self.select_all_tiles); bl.addWidget(self.sel_all_btn)
        self.sel_half_btn = QPushButton("Половина"); self.sel_half_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.sel_half_btn.setMinimumHeight(34)
        self.sel_half_btn.setStyleSheet(bulk_btn_style); self.sel_half_btn.setCheckable(True); self.sel_half_btn.clicked.connect(self.select_half_tiles); bl.addWidget(self.sel_half_btn)
        for label, fn in (("Цвет", self.bulk_color), ("Шрифт", self.bulk_font), ("Картинка", self.bulk_image), ("Гифка", self.bulk_gif), ("Убрать", self.bulk_clear_menu), ("Удалить", self.bulk_delete)):
            b = QPushButton(label); b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); b.setMinimumHeight(34); b.setStyleSheet(bulk_btn_style)
            b.clicked.connect(fn)
            if label == "Убрать": self.bulk_clear_btn = b
            bl.addWidget(b)
        bl.addStretch(1); self.bulk_scroll.setWidget(bulk_inner); bulk_outer.addWidget(self.bulk_scroll)
        self.bulk.setVisible(False); v.addWidget(self.bulk)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.box = QWidget(); self.box.setStyleSheet("background: transparent;")
        self.grid = FlowLayout(self.box, margin=0, h_spacing=GRID_SPACING, v_spacing=GRID_SPACING)
        self.scroll.setWidget(self.box); v.addWidget(self.scroll, 1)

        self.empty = QLabel("Пока нет кнопок\nНажмите «Добавить»"); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.empty)

        bottom = QHBoxLayout(); bottom.setSpacing(10)
        self.add_btn = QPushButton("Добавить кнопку"); self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.add_btn.setMinimumHeight(46)
        self.add_btn.clicked.connect(self.add_tile); bottom.addWidget(self.add_btn, 1)
        self.select_btn = QPushButton("Выбрать"); self.select_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); self.select_btn.setMinimumHeight(46)
        self.select_btn.setCheckable(True); self.select_btn.clicked.connect(self.toggle_select_mode)
        bottom.addWidget(self.select_btn); v.addLayout(bottom)

        self._shortcut_dup = QShortcut(QKeySequence("Ctrl+D"), self)
        self._shortcut_dup.activated.connect(self._duplicate_selected_or_last)

        self.apply_theme(); self._refresh_app_icon(); self._restore_tiles(); self._update_breadcrumb(); self._relayout_grid()
        if self._pinned: self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        QApplication.instance().installEventFilter(self)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange:
            self._is_app_active = self.isActiveWindow()
            for t in self.tiles:
                t.set_active_visual(self._is_app_active)
        super().changeEvent(event)

    def _duplicate_selected_or_last(self):
        if self._select_mode:
            sel = self._selected_tiles()
            if sel:
                self.duplicate_tile(sel[0])
                return
        if self._last_clicked_tile:
            self.duplicate_tile(self._last_clicked_tile)

    def duplicate_tile(self, tile):
        if tile not in self.tiles: return
        idx = self.tiles.index(tile)
        text = tile.text()
        if len(text) > TITLE_MAX_LEN - 3: text = text[:TITLE_MAX_LEN - 3] + "..."
        new_tile = self._create_tile(
            text=text + " (копия)" if len(text) <= TITLE_MAX_LEN - 7 else text,
            actions=[dict(a) for a in normalize_actions(tile.actions)],
            btn_bg=tile.btn_bg.name(),
            btn_text=tile.btn_text.name(),
            font_spec=dict(tile.font_spec),
            image=tile.image_path(),
            animate=True
        )
        self.tiles.remove(new_tile)
        self.tiles.insert(idx + 1, new_tile)
        self._relayout_grid()
        self.schedule_save()

    def handle_tile_select_click(self, tile, shift):
        if shift and self._last_clicked_tile and self._last_clicked_tile in self.tiles:
            i1 = self.tiles.index(self._last_clicked_tile)
            i2 = self.tiles.index(tile)
            start, end = min(i1, i2), max(i1, i2)
            select_state = not self._last_clicked_tile.is_selected()
            for i in range(start, end + 1):
                self.tiles[i].set_selected(select_state)
        else:
            tile.set_selected(not tile.is_selected())
        self._last_clicked_tile = tile
        self._update_bulk_count()

    def _cat_by_id(self, cid):
        if not cid: return None
        return next((c for c in self._categories if c["id"] == cid), None)
    def _active_container(self):
        if self._current_cat:
            c = self._cat_by_id(self._current_cat)
            if c is not None:
                c.setdefault("buttons", []); return c["buttons"]
        self._state.setdefault("buttons", []); return self._state["buttons"]
    def _snapshot_tiles(self):
        return [{"text": t.text(), "actions": normalize_actions(t.actions), "btn_bg": t.btn_bg.name(), "btn_text": t.btn_text.name(), "font": normalize_font(t.font_spec), "image": t.image_path()} for t in self.tiles]
    def _restore_from_snapshot(self, specs):
        for spec in specs:
            text = spec.get("text", "Кнопка")[:TITLE_MAX_LEN]
            self._create_tile(text=text, actions=normalize_actions(spec.get("actions", [])), btn_bg=spec.get("btn_bg", self.theme["btn_bg"]),
                              btn_text=spec.get("btn_text", self.theme["btn_text"]), font_spec=normalize_font(spec.get("font", {})), image=spec.get("image", ""), animate=False)
    def _clear_tiles(self):
        for t in list(self.tiles): self.grid.removeWidget(t); t.setParent(None); t.deleteLater()
        self.tiles.clear()
    def _switch_category(self, cid):
        if cid == self._current_cat: return
        self._active_container()[:] = self._snapshot_tiles(); self._current_cat = cid or ""
        self._clear_tiles(); self._restore_from_snapshot(list(self._active_container())); self._update_breadcrumb()
        self.empty.setVisible(not self.tiles); self._relayout_grid(); self.schedule_save()
    def _update_breadcrumb(self):
        if self._current_cat:
            c = self._cat_by_id(self._current_cat); name = c["name"] if c else "?"
            self.breadcrumb.setText(f"Кнопки  /  {name}   ← вернуться в корень")
        else: self.breadcrumb.setText("Кнопки")
    def _on_breadcrumb_click(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._current_cat: self._switch_category("")
    def open_categories_menu(self):
        m = QMenu(self); m.setStyleSheet(_menu_style())
        if self._current_cat: m.addAction("← В корень", lambda: self._switch_category("")); m.addSeparator()
        if self._categories:
            for c in self._categories:
                act = m.addAction(f"📁 {c['name']}", lambda cid=c['id']: self._switch_category(cid))
                if c["id"] == self._current_cat: act.setCheckable(True); act.setChecked(True)
            m.addSeparator()
        else: m.addAction("Нет категорий").setEnabled(False); m.addSeparator()
        m.addAction("➕ Новая категория…", self._new_category)
        if self._current_cat:
            m.addAction("✏ Переименовать…", lambda: self._rename_category(self._current_cat))
            m.addAction("🗑 Удалить категорию", lambda: self._delete_category(self._current_cat))
        m.exec(self.cat_btn.mapToGlobal(QPoint(0, self.cat_btn.height())))
    def _new_category(self):
        d = TextInputDialog(self, "Новая категория", "Название:", text="", max_len=30)
        if not d.exec() or not d.value(): return
        cid = uuid.uuid4().hex; self._categories.append({"id": cid, "name": d.value(), "buttons": []})
        self.schedule_save(); self._switch_category(cid)
    def _rename_category(self, cid):
        c = self._cat_by_id(cid)
        if not c: return
        d = TextInputDialog(self, "Переименовать", "Название:", text=c["name"], max_len=30)
        if d.exec() and d.value(): c["name"] = d.value(); self._update_breadcrumb(); self.schedule_save()
    def _delete_category(self, cid):
        c = self._cat_by_id(cid)
        if not c: return
        if not MsgDialog.confirm(self, "Удалить категорию", f"Удалить «{c['name']}» со всеми кнопками?", "🗑"): return
        self._categories = [x for x in self._categories if x["id"] != cid]; self._state["categories"] = self._categories; self._switch_category("")
    def _refresh_app_icon(self):
        self.app_icon_btn.set_source(self._app_icon_path); pm = load_app_icon(self._app_icon_path, 64)
        if not pm.isNull(): self.setWindowIcon(QIcon(pm))
    def change_app_icon(self):
        m = QMenu(self); m.setStyleSheet(_menu_style())
        m.addAction("Выбрать файл (картинка или GIF)…", self._pick_app_icon)
        m.addAction("GIF из интернета…", self._pick_app_gif_online)
        m.addAction("Сбросить на стандартную", self._reset_app_icon)
        m.exec(self.app_icon_btn.mapToGlobal(QPoint(0, self.app_icon_btn.height())))
    def _pick_app_icon(self):
        p, _ = QFileDialog.getOpenFileName(self, "Логотип приложения (картинка/GIF)", "", ICON_FILTER)
        if p: self._app_icon_path = p; self._state["app_icon"] = p; self._refresh_app_icon(); self.schedule_save()
    def _pick_app_gif_online(self):
        key = self._state.get("tenor_key", ""); d = GifPickerDialog(self, api_key=key)
        if d.exec() and d.result_url(): self._download_app_icon(d.result_url())
        self._state["tenor_key"] = d.api_key; self.schedule_save()
    def _download_app_icon(self, url):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp: data = resp.read()
            low = url.lower().split("?")[0]; ext = ".gif"
            for c in (".gif", ".webp", ".png", ".jpg", ".jpeg", ".apng"):
                if low.endswith(c): ext = c; break
            path = os.path.join(MEDIA_DIR, f"logo_{uuid.uuid4().hex}{ext}")
            with open(path, "wb") as f: f.write(data)
            self._app_icon_path = path; self._state["app_icon"] = path; self._refresh_app_icon(); self.schedule_save()
        except Exception as ex: MsgDialog.show_message(self, "Не удалось скачать", f"Ошибка загрузки:\n{ex}", "🌐")
        finally: QApplication.restoreOverrideCursor()
    def _reset_app_icon(self):
        self._app_icon_path = ""; self._state["app_icon"] = ""; self._refresh_app_icon(); self.schedule_save()
    def toggle_pin(self, checked=None):
        if checked is None: checked = self.pin_btn.isChecked()
        self._pinned = bool(checked); self.pin_btn.setChecked(self._pinned)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._pinned)
        self.show(); self._apply_pin_style(); self.schedule_save()
    def _apply_pin_style(self):
        t = self.theme; on = self._pinned; bg = t['accent'] if on else t['panel']; fg = "white" if on else t['text']
        self.pin_btn.setStyleSheet(f"QPushButton{{background:{bg};color:{fg};border:1px solid #2a2b33;border-radius:10px;font-size:15px;}}QPushButton:hover{{background:#26272e;}}")
    def open_settings_menu(self):
        m = QMenu(self); m.setStyleSheet(_menu_style())
        m.addAction("Настройки темы", self.open_theme); m.addAction("Сбросить тему", self.reset_theme)
        m.addSeparator(); m.addAction("Сменить логотип", self.change_app_icon)
        m.addSeparator(); m.addAction("Сбросить все кнопки здесь", self.reset_buttons)
        m.exec(self.settings_btn.mapToGlobal(QPoint(0, self.settings_btn.height())))
    def eventFilter(self, obj, ev):
        if not self._drag_tile: return super().eventFilter(obj, ev)
        t = ev.type()
        if t == ev.Type.MouseMove: self._on_global_move(ev.globalPosition().toPoint()); return True
        if t == ev.Type.MouseButtonRelease: self._on_global_release(ev.globalPosition().toPoint()); return True
        return super().eventFilter(obj, ev)
    def _compute_tile_size(self):
        avail = self.scroll.viewport().width() - 24
        if avail <= 0: return TILE_SIZE
        cols = max(1, (avail + GRID_SPACING) // (TILE_SIZE + GRID_SPACING))
        size = (avail - (cols - 1) * GRID_SPACING) // cols
        return max(MIN_TILE_SIZE, min(TILE_SIZE, size))
    def _apply_tile_size(self):
        size = self._compute_tile_size()
        if size == self._current_tile_sz: return
        self._current_tile_sz = size
        for t in self.tiles: t.set_tile_size(size)
    def _relayout_grid(self):
        self.grid.invalidate()
        if self.box.layout(): self.box.layout().activate(); self.box.updateGeometry()
    def resizeEvent(self, e): super().resizeEvent(e); self._resize_timer.start()
    def _on_resize(self): self._apply_tile_size(); self._relayout_grid()
    def start_tile_drag(self, tile, press_global_pos):
        if self._select_mode: return
        self._drag_tile = tile; self._drag_start_index = self.tiles.index(tile); gp = tile.mapToGlobal(QPoint(0, 0)); self._drag_offset = press_global_pos - gp
        a = QPropertyAnimation(tile, b"lift", self); a.setDuration(150); a.setEasingCurve(QEasingCurve.Type.OutCubic); a.setStartValue(tile._lift); a.setEndValue(1.0); a.start(); tile._lift_anim = a
        tile.raise_(); vp = self.scroll.viewport(); local = vp.mapFromGlobal(tile.mapToGlobal(QPoint(0, 0))); tile.setParent(vp); tile.move(local); tile.show(); tile.raise_()
    def _on_global_move(self, global_pos):
        if not self._drag_tile: return
        vp = self.scroll.viewport(); self._drag_tile.move(vp.mapFromGlobal(global_pos) - self._drag_offset)
    def _on_global_release(self, global_pos):
        tile = self._drag_tile
        if not tile: return
        self._drag_tile = None; target = self._index_at_global(global_pos)
        if target is None: target = self._drag_start_index
        tile.setParent(self.box); tile.show(); cur = self.tiles.index(tile)
        if target != cur:
            other = self.tiles[target]; self.tiles[cur], self.tiles[target] = other, tile
            self._relayout_grid(); self._animate_swap(tile, other)
        self._reset_lift(tile); self.schedule_save()
    def _animate_swap(self, a_tile, b_tile):
        for t in (a_tile, b_tile):
            anim = QPropertyAnimation(t, b"lift", self); anim.setDuration(220); anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.0); anim.setKeyValueAt(0.5, 0.6); anim.setEndValue(0.0); anim.start(); t._swap_anim = anim
    def _reset_lift(self, tile):
        a = QPropertyAnimation(tile, b"lift", self); a.setDuration(180); a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.setStartValue(tile._lift); a.setEndValue(0.0); a.start(); tile._lift_anim = a
    def _index_at_global(self, global_pos):
        vp = self.scroll.viewport(); pos = vp.mapFromGlobal(global_pos); sz = self._current_tile_sz
        cw = sz + GRID_SPACING; ch = sz + GRID_SPACING; x = pos.x() - 6; y = pos.y() - 8
        if x < 0 or y < 0: return 0 if y < 0 else None
        avail = vp.width() - 24; cols = max(1, (avail + GRID_SPACING) // (sz + GRID_SPACING))
        c = x // cw; r = y // ch
        if c >= cols: c = cols - 1
        idx = int(r) * cols + int(c)
        if idx < 0: idx = 0
        if idx >= len(self.tiles): idx = len(self.tiles) - 1
        return idx
    def schedule_save(self): self._save_timer.start()
    def _save_now(self):
        self._active_container()[:] = self._snapshot_tiles()
        self._state["theme"] = self.theme; self._state["categories"] = self._categories
        self._state["pinned"] = self._pinned; self._state["app_icon"] = self._app_icon_path; save_state(self._state)
    def closeEvent(self, e):
        self._save_now()
        try: QApplication.instance().removeEventFilter(self)
        except Exception: pass
        super().closeEvent(e)
    def _restore_tiles(self):
        self._restore_from_snapshot(list(self._state.get("buttons", [])))
        if self.tiles: self.empty.hide()
    def apply_theme(self):
        t = self.theme; self.set_theme(t); self._central.setStyleSheet("background: transparent;")
        self.setStyleSheet(f"QMainWindow{{background:transparent;}}QLabel#title{{color:{t['text']};font-size:22px;font-weight:700;}}QLabel#subtitle{{color:#6c707a;font-size:12px;}}QScrollArea{{background:transparent;border:none;}}")
        self.line.setStyleSheet(f"background:{t['panel']};border:none;")
        self.empty.setStyleSheet("color:#4b4f5a;font-size:13px;background:transparent;")
        icon_style = (f"QPushButton{{background:{t['panel']};color:{t['text']};border:1px solid #2a2b33;border-radius:10px;font-size:16px;}}QPushButton:hover{{background:#26272e;}}")
        self.settings_btn.setStyleSheet(icon_style); self.cat_btn.setStyleSheet(icon_style.replace("16px", "15px")); self.close_btn.setStyleSheet(icon_style.replace("16px", "14px"))
        self.min_btn.setStyleSheet(icon_style.replace("16px", "14px"))
        self.add_btn.setStyleSheet(f"QPushButton{{background:{t['accent']};color:white;border:none;border-radius:12px;padding:12px 20px;font-size:14px;font-weight:600;}}QPushButton:hover{{background:{QColor(t['accent']).darker(115).name()};}}")
        neutral = (f"QPushButton{{background:{t['panel']};color:{t['text']};border:1px solid #2a2b33;border-radius:12px;padding:12px 18px;font-size:14px;}}QPushButton:hover{{background:#26272e;}}QPushButton:checked{{background:{t['accent']};color:white;border:1px solid {t['accent']};}}")
        self.select_btn.setStyleSheet(neutral); self._apply_pin_style()
        for tile in self.tiles: tile.set_colors(t["btn_bg"], t["btn_text"])
    def open_theme(self):
        d = ThemeDialog(self, self.theme)
        if d.exec(): self.theme = d.result_theme(); self.apply_theme(); self.schedule_save()
    def _create_tile(self, text, actions, btn_bg, btn_text, font_spec, image, animate):
        tile = AppTile(text); tile.set_tile_size(self._current_tile_sz); tile.actions = normalize_actions(actions); tile.set_colors(btn_bg, btn_text); tile.set_font_spec(font_spec)
        if image: tile.set_image(image)
        tile.set_select_mode(self._select_mode); tile._main = self; self.tiles.append(tile); self.grid.addWidget(tile)
        if animate: tile.appear()
        else: tile._opacity = 1.0; tile.update()
        return tile
    def add_tile(self):
        self.empty.hide()
        self._create_tile(text=f"Кнопка {len(self.tiles) + 1}"[:TITLE_MAX_LEN], actions=[], btn_bg=self.theme["btn_bg"], btn_text=self.theme["btn_text"], font_spec=dict(DEFAULT_BUTTON_FONT), image="", animate=True)
        self._relayout_grid(); self.schedule_save(); QTimer.singleShot(60, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
    def remove_tile(self, tile):
        if tile in self.tiles: self.tiles.remove(tile)
        if self._last_clicked_tile is tile: self._last_clicked_tile = None
        self.grid.removeWidget(tile); tile.setParent(None); tile.deleteLater()
        if not self.tiles: self.empty.show()
        self._relayout_grid(); self._update_bulk_count(); self.schedule_save()
    def toggle_select_mode(self, on):
        self._select_mode = on; self.bulk.setVisible(on)
        for t in self.tiles: t.set_select_mode(on)
        if not on: self.sel_all_btn.setChecked(False); self.sel_half_btn.setChecked(False)
        self._last_clicked_tile = None
        self._update_bulk_count()
    def _selected_tiles(self): return [t for t in self.tiles if t.is_selected()]
    def _update_bulk_count(self):
        sel = self._selected_tiles(); self.bulk_count.setText(f"Выбрано: {len(sel)}")
        if hasattr(self, "sel_all_btn"): self.sel_all_btn.setChecked(bool(self.tiles) and len(sel) == len(self.tiles))
    def select_all_tiles(self):
        if not self.tiles: return
        all_selected = all(t.is_selected() for t in self.tiles); target = not all_selected
        for t in self.tiles: t.set_selected(target)
        self.sel_all_btn.setChecked(target); self.sel_half_btn.setChecked(False); self._update_bulk_count()
    def select_half_tiles(self):
        if not self.tiles: return
        n = len(self.tiles); half = (n + 1) // 2; selected = {i for i, t in enumerate(self.tiles) if t.is_selected()}
        first = set(range(0, half)); second = set(range(half, n))
        if not selected: target_set = first; self.sel_half_btn.setChecked(True)
        elif selected == first: target_set = second; self.sel_half_btn.setChecked(True)
        else: target_set = set(); self.sel_half_btn.setChecked(False)
        for i, t in enumerate(self.tiles): t.set_selected(i in target_set)
        self.sel_all_btn.setChecked(False); self._update_bulk_count()
    def reset_theme(self):
        if not MsgDialog.confirm(self, "Сбросить тему", "Вернуть все настройки темы по умолчанию?", "🔄"): return
        self.theme = dict(DEFAULT_THEME); self.apply_theme(); self.schedule_save()
    def reset_buttons(self):
        if not self.tiles: MsgDialog.show_message(self, "Нет кнопок", "Список уже пуст.", "i"); return
        if not MsgDialog.confirm(self, "Сбросить кнопки", "Удалить все кнопки в текущем месте без возможности отмены?", "🗑"): return
        for t in list(self.tiles): self.grid.removeWidget(t); t.setParent(None); t.deleteLater()
        self.tiles.clear(); self.empty.show(); self._relayout_grid(); self._update_bulk_count(); self.schedule_save()
    def bulk_color(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        d = ButtonColorsDialog(self, "Цвета выбранных кнопок", bg=sel[0].btn_bg.name(), text=sel[0].btn_text.name(), default_bg=DEFAULT_THEME["btn_bg"], default_text=DEFAULT_THEME["btn_text"])
        if d.exec():
            bg, tx = d.colors()
            for t in sel: t.set_colors(bg, tx)
            self.schedule_save()
    def bulk_font(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        d = ButtonFontDialog(self, sel[0].font_spec)
        if d.exec():
            spec = d.font_spec()
            for t in sel: t.set_font_spec(spec)
            self.schedule_save()
    def bulk_image(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        p, _ = QFileDialog.getOpenFileName(self, "Картинка для выбранных", "", IMAGE_FILTER)
        if not p: return
        for t in sel: t.set_image(p)
        self.schedule_save()
    def bulk_gif(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        p, _ = QFileDialog.getOpenFileName(self, "Гифка для выбранных", "", GIF_FILTER)
        if not p: return
        for t in sel: t.set_image(p)
        self.schedule_save()
    def bulk_clear_menu(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        m = QMenu(self); m.setStyleSheet(_menu_style())
        m.addAction("🎨  Цвет", lambda: self._bulk_remove_color(sel))
        m.addAction("🔤  Шрифт", lambda: self._bulk_remove_font(sel))
        m.addSeparator(); m.addAction("🖼  Картинку / гифку", lambda: self._bulk_remove_image(sel))
        m.exec(self.bulk_clear_btn.mapToGlobal(QPoint(0, -m.sizeHint().height())))
    def _bulk_remove_color(self, sel):
        for t in sel: t.set_colors(self.theme["btn_bg"], self.theme["btn_text"])
        self.schedule_save()
    def _bulk_remove_font(self, sel):
        for t in sel: t.set_font_spec(dict(DEFAULT_BUTTON_FONT))
        self.schedule_save()
    def _bulk_remove_image(self, sel):
        for t in sel: t.set_image("")
        self.schedule_save()
    def bulk_delete(self):
        sel = self._selected_tiles()
        if not sel:
            MsgDialog.show_message(self, "Ничего не выбрано", "Сначала выберите кнопки (режим «Выбрать»).", "i")
            return
        for t in list(sel): self.remove_tile(t)
        self._update_bulk_count()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())