import argparse
import os
import sys

from PyQt5.QtCore import QEvent, QPoint, Qt, QUrl
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

import win32con
import win32gui


class OverlayWebView(QWebEngineView):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.owner.show_context_menu)


class OverlayWindow(QMainWindow):
    EDGE_MARGIN = 12
    MIN_W = 260
    MIN_H = 1

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.opacity = 1.0
        self.zoom_factor = 1.0
        self.click_through = False

        self.dragging = False
        self.resizing = False
        self.resize_edges = set()
        self.start_global = QPoint()
        self.start_geometry = self.geometry()

        self._build_window()
        self._build_tray()
        if not self._load_source(self.source):
            raise FileNotFoundError(f"Source not found or invalid: {self.source}")
        QApplication.instance().installEventFilter(self)

    def _build_window(self):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window
        self.setWindowFlags(flags)
        self.resize(800, 600)
        self.setMinimumSize(self.MIN_W, self.MIN_H)

        self.view = OverlayWebView(self)
        # Overlay usage: disable HTML input handling so move/resize stays responsive.
        self.view.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setCentralWidget(self.view)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("HTML Overlay")

        self.tray_menu = QMenu()

        open_file_action = QAction("Open HTML File...", self)
        open_file_action.triggered.connect(self.open_html_file)
        self.tray_menu.addAction(open_file_action)

        open_url_action = QAction("Open URL...", self)
        open_url_action.triggered.connect(self.open_url)
        self.tray_menu.addAction(open_url_action)
        self.tray_menu.addSeparator()

        self.tray_click_action = QAction("Click-Through", self, checkable=True)
        self.tray_click_action.triggered.connect(self.toggle_click_through)
        self.tray_menu.addAction(self.tray_click_action)

        opacity_menu = self._create_opacity_menu(self.tray_menu)
        self.tray_menu.addMenu(opacity_menu)
        zoom_menu = self._create_zoom_menu(self.tray_menu)
        self.tray_menu.addMenu(zoom_menu)
        self.tray_menu.addSeparator()

        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(quit_action)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def _create_opacity_menu(self, parent):
        menu = QMenu("Opacity", parent)
        group = QActionGroup(self)
        group.setExclusive(True)

        for value in [100, 90, 80, 70, 60, 50, 40, 30]:
            action = QAction(f"{value}%", self, checkable=True)
            action.setData(value / 100.0)
            if value == 100:
                action.setChecked(True)
            action.triggered.connect(lambda checked, a=action: self.set_overlay_opacity(a.data()))
            group.addAction(action)
            menu.addAction(action)
        return menu

    def _create_zoom_menu(self, parent):
        menu = QMenu("Scale", parent)
        group = QActionGroup(self)
        group.setExclusive(True)

        for value in [50, 75, 90, 100, 110, 125, 150, 175, 200]:
            action = QAction(f"{value}%", self, checkable=True)
            action.setData(value / 100.0)
            if value == 100:
                action.setChecked(True)
            action.triggered.connect(lambda checked, a=action: self.set_zoom_factor(a.data()))
            group.addAction(action)
            menu.addAction(action)
        return menu

    def _load_source(self, source):
        source_text = (source or "").strip()
        if not source_text:
            return False

        parsed = QUrl(source_text)
        if parsed.isValid() and parsed.scheme().lower() in ("http", "https", "file"):
            if parsed.scheme().lower() == "file":
                local = parsed.toLocalFile()
                if not os.path.exists(local):
                    return False
            self.view.load(parsed)
            self.source = source_text
            self.setWindowTitle(f"HTML Overlay - {source_text}")
            return True

        local_path = os.path.abspath(os.path.expanduser(source_text))
        if os.path.exists(local_path):
            self.view.load(QUrl.fromLocalFile(local_path))
            self.source = local_path
            self.setWindowTitle(f"HTML Overlay - {local_path}")
            return True

        return False

    def open_html_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open HTML File",
            os.getcwd(),
            "HTML Files (*.html *.htm);;All Files (*.*)",
        )
        if path and not self._load_source(path):
            QMessageBox.warning(self, "Load Failed", f"Could not load file:\n{path}")

    def open_url(self):
        url_text, ok = QInputDialog.getText(self, "Open URL", "Enter URL:")
        if not ok:
            return

        url_text = url_text.strip()
        if not url_text:
            return

        if "://" not in url_text:
            url_text = f"https://{url_text}"

        if not self._load_source(url_text):
            QMessageBox.warning(self, "Load Failed", f"Could not load URL:\n{url_text}")

    def show_context_menu(self, pos):
        if self.click_through:
            return
        self._show_context_menu_global(self.view.mapToGlobal(pos))

    def _show_context_menu_global(self, global_pos):
        if self.click_through:
            return

        menu = QMenu(self)

        open_file_action = QAction("Open HTML File...", self)
        open_file_action.triggered.connect(self.open_html_file)
        menu.addAction(open_file_action)

        open_url_action = QAction("Open URL...", self)
        open_url_action.triggered.connect(self.open_url)
        menu.addAction(open_url_action)
        menu.addSeparator()

        opacity_menu = self._create_opacity_menu(menu)
        menu.addMenu(opacity_menu)
        zoom_menu = self._create_zoom_menu(menu)
        menu.addMenu(zoom_menu)

        click_action = QAction("Click-Through", self, checkable=True)
        click_action.setChecked(self.click_through)
        click_action.triggered.connect(self.toggle_click_through)
        menu.addAction(click_action)

        menu.addSeparator()
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        menu.exec_(global_pos)

    def set_overlay_opacity(self, value):
        self.opacity = float(value)
        self.setWindowOpacity(self.opacity)

    def set_zoom_factor(self, value):
        self.zoom_factor = float(value)
        self.view.setZoomFactor(self.zoom_factor)

    def toggle_click_through(self):
        self.click_through = not self.click_through
        self.tray_click_action.setChecked(self.click_through)
        self.dragging = False
        self.resizing = False
        self.resize_edges = set()
        self._apply_click_through()

    def _apply_click_through(self):
        hwnd = int(self.winId())
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

        if self.click_through:
            style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
        else:
            style &= ~win32con.WS_EX_TRANSPARENT

        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_FRAMECHANGED,
        )

    def _hit_test_edges(self, global_pos):
        edges = set()
        g = self.geometry()

        if abs(global_pos.x() - g.left()) <= self.EDGE_MARGIN:
            edges.add("left")
        if abs(global_pos.x() - g.right()) <= self.EDGE_MARGIN:
            edges.add("right")
        if abs(global_pos.y() - g.top()) <= self.EDGE_MARGIN:
            edges.add("top")
        if abs(global_pos.y() - g.bottom()) <= self.EDGE_MARGIN:
            edges.add("bottom")
        return edges

    def _apply_cursor(self, edges):
        if edges == {"left"} or edges == {"right"}:
            self.view.setCursor(QCursor(Qt.SizeHorCursor))
        elif edges == {"top"} or edges == {"bottom"}:
            self.view.setCursor(QCursor(Qt.SizeVerCursor))
        elif edges == {"left", "top"} or edges == {"right", "bottom"}:
            self.view.setCursor(QCursor(Qt.SizeFDiagCursor))
        elif edges == {"right", "top"} or edges == {"left", "bottom"}:
            self.view.setCursor(QCursor(Qt.SizeBDiagCursor))
        else:
            self.view.setCursor(QCursor(Qt.ArrowCursor))

    def _edges_to_qt(self, edges):
        qt_edges = Qt.Edges()
        if "left" in edges:
            qt_edges |= Qt.LeftEdge
        if "right" in edges:
            qt_edges |= Qt.RightEdge
        if "top" in edges:
            qt_edges |= Qt.TopEdge
        if "bottom" in edges:
            qt_edges |= Qt.BottomEdge
        return qt_edges

    def _try_native_move_resize(self, edges):
        handle = self.windowHandle()
        if handle is None:
            return False
        try:
            if edges:
                return bool(handle.startSystemResize(self._edges_to_qt(edges)))
            return bool(handle.startSystemMove())
        except Exception:
            return False

    def eventFilter(self, obj, event):
        if self.click_through or not self.isVisible():
            return super().eventFilter(obj, event)

        popup = QApplication.activePopupWidget()
        if popup is not None:
            return super().eventFilter(obj, event)

        event_type = event.type()
        if event_type not in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            return super().eventFilter(obj, event)

        global_pos = event.globalPos()
        if not self.frameGeometry().contains(global_pos):
            return super().eventFilter(obj, event)

        target = QApplication.widgetAt(global_pos)
        if target is not None and target is not self and not self.isAncestorOf(target):
            return super().eventFilter(obj, event)

        if event_type == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            edges = self._hit_test_edges(global_pos)
            if self._try_native_move_resize(edges):
                return True

            self.start_global = global_pos
            self.start_geometry = self.geometry()

            if edges:
                self.resizing = True
                self.resize_edges = edges
            else:
                self.dragging = True
            return True

        if event_type == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self._show_context_menu_global(global_pos)
            return True

        if event_type == QEvent.MouseMove:
            if self.resizing and (event.buttons() & Qt.LeftButton):
                self._do_resize(global_pos)
                return True
            if self.dragging and (event.buttons() & Qt.LeftButton):
                delta = global_pos - self.start_global
                self.move(self.start_geometry.topLeft() + delta)
                return True
            if not (event.buttons() & Qt.LeftButton):
                self._apply_cursor(self._hit_test_edges(global_pos))

        if event_type == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self.dragging or self.resizing:
                self.dragging = False
                self.resizing = False
                self.resize_edges = set()
                return True

        return super().eventFilter(obj, event)

    def _do_resize(self, global_pos):
        delta = global_pos - self.start_global
        rect = self.start_geometry

        left = rect.left()
        top = rect.top()
        right = rect.right()
        bottom = rect.bottom()

        if "left" in self.resize_edges:
            left = min(left + delta.x(), right - self.MIN_W)
        if "right" in self.resize_edges:
            right = max(right + delta.x(), left + self.MIN_W)
        if "top" in self.resize_edges:
            top = min(top + delta.y(), bottom - self.MIN_H)
        if "bottom" in self.resize_edges:
            bottom = max(bottom + delta.y(), top + self.MIN_H)

        self.setGeometry(left, top, right - left + 1, bottom - top + 1)


def main():
    parser = argparse.ArgumentParser(description="Borderless topmost HTML overlay")
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Local HTML path or URL (e.g. C:\\overlay\\meter.html or https://example.com)",
    )
    parser.add_argument(
        "--html",
        default="2048.html",
        help="Backward-compatible local HTML path (default: 2048.html)",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("HTML Overlay")

    initial_source = args.source if args.source else args.html
    window = OverlayWindow(initial_source)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
