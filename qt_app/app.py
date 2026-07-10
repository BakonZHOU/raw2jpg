from __future__ import annotations

import os
import sys
import time
from collections import OrderedDict
from pathlib import Path

# 确保可以找到 qt_app 模块
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    # 获取当前文件所在目录的父目录（项目根目录）
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_PATH = get_base_path()
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

from PySide6.QtCore import QFile, QObject, QEvent, Qt, QTimer, QSize, QPoint, QRect, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QPalette, QShortcut, QCursor, QPainter, QPainterPath, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtUiTools import QUiLoader

from qt_app.file_service import FileService


UI_PATH = Path(__file__).resolve().parent / "ui" / "main_window.ui"


class DropEventFilter(QObject):
    def __init__(self, owner: "PhotoCullerApp"):
        super().__init__()
        self.owner = owner
        self.dragging = False
        self.last_pos = QPoint()
        self.press_pos = QPoint()

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype in (QEvent.DragEnter, QEvent.DragMove):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.owner.set_drag_state(obj, True)
                return True
            return False
        if etype == QEvent.DragLeave:
            self.owner.set_drag_state(obj, False)
            return True
        if etype == QEvent.Drop:
            self.owner.set_drag_state(obj, False)
            self.owner.handle_drop(obj, event.mimeData())
            event.acceptProposedAction()
            return True
        if etype == QEvent.Wheel and obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.owner.zoom_main_image(1.2)
                else:
                    self.owner.zoom_main_image(1 / 1.2)
                event.accept()
                return True
            return False
        if etype == QEvent.MouseButtonDblClick and obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
            self.owner.fit_main_image()
            return True
        if etype == QEvent.MouseButtonPress and obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
            if event.button() == Qt.MouseButton.LeftButton:
                self.dragging = True
                self.last_pos = event.globalPosition().toPoint()
                self.press_pos = event.globalPosition().toPoint()
                self.owner.main_image_scroll.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return True
        if etype == QEvent.MouseMove and obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
            if self.dragging:
                pos = event.globalPosition().toPoint()
                delta = pos - self.last_pos
                self.last_pos = pos
                h_bar = self.owner.main_image_scroll.horizontalScrollBar()
                v_bar = self.owner.main_image_scroll.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                return True
        if etype == QEvent.MouseButtonRelease and obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
            if event.button() == Qt.MouseButton.LeftButton and self.dragging:
                self.dragging = False
                self.owner.main_image_scroll.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                return True
        if etype == QEvent.Resize and obj in (self.owner.main_image_scroll.viewport(), self.owner.thumbnail_scroll.viewport()):
            self.owner.schedule_viewport_refresh()
        return False


class ThumbnailButton(QToolButton):
    def __init__(self, owner: "PhotoCullerApp", index: int, path: str, status: int):
        super().__init__()
        self.owner = owner
        self.index = index
        self.path = path
        self._hover_scale = 1.0
        self._hover_anim = None
        self._thumb_pixmap = owner.load_thumbnail_pixmap(path)
        self.setProperty("thumbnail", True)
        self.setProperty("status", self._status_name(status))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._calc_square_metrics()
        self.setFixedSize(self.thumbnail_button_size)
        self.setIconSize(self.thumbnail_icon_size)
        self.setAutoRaise(False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.clicked.connect(lambda: self.owner.go_to(index))

    def _calc_square_metrics(self):
        self.owner._calc_thumbnail_metrics()
        self.thumbnail_button_size = self.owner.thumbnail_button_size
        self.thumbnail_icon_size = self.owner.thumbnail_icon_size

    def _status_name(self, status: int) -> str:
        if status == 2:
            return "current"
        if status == 1:
            return "pass"
        if status == -1:
            return "reject"
        return "normal"

    def _set_hover_scale(self, value: float):
        self._hover_scale = value
        self.update()

    hoverScale = Property(float, lambda self: self._hover_scale, _set_hover_scale)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._animate_hover(1.07)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate_hover(1.0)

    def _animate_hover(self, target: float):
        if self._hover_anim is not None:
            self._hover_anim.stop()
        anim = QPropertyAnimation(self, b"hoverScale", self)
        anim.setDuration(140)
        anim.setStartValue(self._hover_scale)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._hover_anim = anim

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        center_x = self.rect().width() / 2
        center_y = self.rect().height() / 2
        painter.translate(center_x, center_y)
        painter.scale(self._hover_scale, self._hover_scale)
        painter.translate(-center_x, -center_y)

        max_scale = 1.07
        base_padding = int(self.rect().width() * (max_scale - 1) / 2) + 1
        top_padding = base_padding + 3
        rect = self.rect().adjusted(base_padding, top_padding, -base_padding, -base_padding)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        bg = QColor("#111111")
        if self.property("status") == "current":
            bg = QColor("#222222")
        painter.fillPath(path, bg)
        painter.setClipPath(path)

        if not self._thumb_pixmap.isNull():
            scaled = self._thumb_pixmap.scaled(
                rect.width(),
                rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) // 2
            y = rect.y() + (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        border = QColor("transparent")
        if self.property("status") == "pass":
            border = QColor("#4caf50")
        elif self.property("status") == "reject":
            border = QColor("#f44336")
        elif self.property("status") == "current":
            border = QColor("#00bcd4")
        painter.setPen(QPen(border, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)


class SummaryDialog(QDialog):
    def __init__(self, parent, title: str, message: str, details: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 420)

        root = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        root.addWidget(label)

        if details:
            edit = QPlainTextEdit()
            edit.setReadOnly(True)
            edit.setPlainText("\n".join(details))
            root.addWidget(edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


class PhotoCullerApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName("相机照片极速筛选工具")
        self.app.setQuitOnLastWindowClosed(True)
        self.app.setStyle("Fusion")
        self.apply_dark_palette()

        self.file_service = FileService()
        self.image_files: list[str] = []
        self.current_idx = 0
        self.states: dict[str, int] = {}
        self.raw_ext = ".CR2"
        self.current_image_path = ""
        self.current_main_pixmap = QPixmap()
        self.main_fit_factor = 1.0
        self.main_zoom_ratio = 1.0
        self.pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._max_cache_size = 80
        self._thumb_buttons: dict[int, ThumbnailButton] = {}
        self._viewport_refresh_timer = QTimer(self)
        self._full_preview_mode = False
        self._full_preview_container = None
        self._full_preview_left = None
        self._full_preview_center = None
        self._full_preview_right = None
        self._viewport_refresh_timer.setSingleShot(True)
        self._viewport_refresh_timer.setInterval(50)
        self._viewport_refresh_timer.timeout.connect(self.refresh_visible_views)
        self.last_browse_dir = os.path.expanduser("~")

        self.window = self.load_window()
        self.load_widgets()
        self.install_filters()
        self.bind_events()
        self.apply_styles()
        self.setup_shortcuts()
        self.refresh_state()

    def load_window(self):
        loader = QUiLoader()
        ui_file = QFile(str(UI_PATH))
        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"无法打开 UI 文件: {UI_PATH}")
        try:
            window = loader.load(ui_file)
        finally:
            ui_file.close()
        if window is None:
            raise RuntimeError("加载 UI 失败")
        return window

    def load_widgets(self):
        self.path_bar = self.window.findChild(QWidget, "pathBar")
        self.zone_jpg = self.window.findChild(QFrame, "zoneJpg")
        self.zone_raw = self.window.findChild(QFrame, "zoneRaw")
        self.zone_dest = self.window.findChild(QFrame, "zoneDest")
        self.main_drop_zone = self.window.findChild(QFrame, "mainDropZone")
        self.thumbnail_scroll = self.window.findChild(QScrollArea, "thumbnailScroll")
        self.thumbnail_content = self.window.findChild(QWidget, "thumbnailContent")
        self.thumbnail_layout = self.thumbnail_content.layout()
        self.main_splitter = self.window.findChild(QSplitter, "mainSplitter")
        self.btn_select_jpg = self.window.findChild(QPushButton, "btnSelectJpg")
        self.btn_select_raw = self.window.findChild(QPushButton, "btnSelectRaw")
        self.btn_select_dest = self.window.findChild(QPushButton, "btnSelectDest")
        self.lbl_jpg_path = self.window.findChild(QLabel, "lblJpgPath")
        self.lbl_raw_path = self.window.findChild(QLabel, "lblRawPath")
        self.lbl_dest_path = self.window.findChild(QLabel, "lblDestPath")
        self.lbl_raw_ext = self.window.findChild(QLabel, "lblRawExt")
        self.info_label = self.window.findChild(QLabel, "infoLabel")
        self.main_placeholder = self.window.findChild(QLabel, "mainPlaceholder")
        self.main_image = self.window.findChild(QLabel, "mainImage")

        self.main_image_scroll = QScrollArea(self.main_drop_zone)
        self.main_image_scroll.setObjectName("mainImageScroll")
        self.main_image_scroll.setWidgetResizable(False)
        self.main_image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_image_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_image.setParent(self.main_image_scroll)
        self.main_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_image.setScaledContents(False)
        self.main_image_scroll.setWidget(self.main_image)

        layout = self.main_drop_zone.layout()
        layout.removeWidget(self.main_image)
        layout.addWidget(self.main_image_scroll, 0, 0)
        self.main_image_scroll.hide()
        self.main_image_scroll.raise_()
        self.main_placeholder.raise_()

        self.thumbnail_scroll.setMinimumHeight(100)
        self.update_thumbnail_max_height()

        self.thumbnail_layout.setSpacing(6)
        self.thumbnail_layout.setContentsMargins(8, 12, 8, 8)


    def install_filters(self):
        self.filter = DropEventFilter(self)
        for widget in [self.zone_jpg, self.zone_raw, self.zone_dest, self.main_drop_zone, self.main_image, self.main_placeholder]:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self.filter)
        self.main_image_scroll.viewport().setAcceptDrops(True)
        self.main_image_scroll.viewport().installEventFilter(self.filter)

    def bind_events(self):
        self.btn_select_jpg.clicked.connect(self.select_jpg_dir)
        self.btn_select_raw.clicked.connect(self.select_raw_dir)
        self.btn_select_dest.clicked.connect(self.select_dest_dir)
        self.main_splitter.setSizes([760, 220])
        self.main_splitter.setHandleWidth(5)
        self.main_splitter.splitterMoved.connect(self.on_splitter_moved)

    def on_splitter_moved(self, pos, index):
        self.schedule_viewport_refresh()
        self.check_full_preview_mode()

    def setup_shortcuts(self):
        shortcuts = [
            (QKeySequence(Qt.Key.Key_Space), self.mark_pass),
            (QKeySequence(Qt.Key.Key_Return), self.mark_pass),
            (QKeySequence(Qt.Key.Key_Enter), self.mark_pass),
            (QKeySequence(Qt.Key.Key_Delete), self.mark_reject),
            (QKeySequence(Qt.Key.Key_Backspace), self.mark_reject),
            (QKeySequence(Qt.Key.Key_Left), self.go_prev),
            (QKeySequence(Qt.Key.Key_Right), self.go_next),
            (QKeySequence("Ctrl+Z"), self.undo),
        ]
        self.shortcuts = []
        for sequence, handler in shortcuts:
            shortcut = QShortcut(sequence, self.window)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)
            self.shortcuts.append(shortcut)

    def apply_dark_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 18))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(68, 68, 68))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 188, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.app.setPalette(palette)

    def apply_styles(self):
        self.window.setStyleSheet(
            """
            QMainWindow {
                background: #1e1e1e;
                color: #ffffff;
            }
            QWidget#pathBar {
                background: #2d2d2d;
            }
            QFrame[dragOver="true"] {
                border: 2px solid #00bcd4;
                background: rgba(0, 188, 212, 0.10);
                border-radius: 6px;
            }
            QFrame#mainDropZone {
                background: #000000;
            }
            QLabel#infoLabel {
                background: #333333;
                font-weight: bold;
                padding: 10px;
            }
            QLabel#lblJpgPath, QLabel#lblRawPath, QLabel#lblDestPath {
                color: #ffb300;
                min-width: 100px;
            }
            QLabel#lblRawExt {
                color: #00bcd4;
                font-weight: bold;
                min-width: 60px;
            }
            QLabel#mainPlaceholder {
                color: #666666;
                font-size: 18px;
            }
            QLabel#mainImage {
                background: transparent;
            }
            QScrollArea#thumbnailScroll {
                background: #222222;
                border: 0px;
            }
            QScrollBar:horizontal {
                height: 6px;
                background: #1a1a1a;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #444444;
                border-radius: 3px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #555555;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
            }
            QWidget#thumbnailContent {
                background: #222222;
            }
            QToolButton[thumbnail="true"] {
                background: transparent;
                border: none;
                border-radius: 0px;
                padding: 0px;
            }
            QPushButton {
                background: #444444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #555555;
            }
            QDialog {
                background: #1e1e1e;
                color: white;
            }
            QDialog QPushButton {
                padding: 8px 16px;
            }
            """
        )
        self.window.setMouseTracking(True)

    def set_drag_state(self, widget, active: bool):
        if widget is None:
            return
        widget.setProperty("dragOver", active)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def handle_drop(self, widget, mime_data):
        paths = self.extract_paths_from_mime(mime_data)
        if not paths:
            return
        if widget in (self.main_drop_zone, self.main_image, self.main_placeholder):
            self.apply_paths_in_order(paths)
            return
        path = paths[0]
        if widget is self.zone_jpg:
            self.apply_jpg_dir(path)
        elif widget is self.zone_raw:
            self.apply_raw_dir(path)
        elif widget is self.zone_dest:
            self.apply_dest_dir(path)

    def extract_paths_from_mime(self, mime_data):
        if not mime_data or not mime_data.hasUrls():
            return []
        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            local_path = url.toLocalFile()
            paths.append(local_path if os.path.isdir(local_path) else os.path.dirname(local_path))
        return paths

    def apply_paths_in_order(self, paths: list[str]):
        slots = [self.apply_jpg_dir, self.apply_raw_dir, self.apply_dest_dir]
        for index, path in enumerate(paths[:3]):
            slots[index](path)

    def choose_directory(self, title: str, initial_path: str | None = None):
        directory = QFileDialog.getExistingDirectory(
            self.window,
            title,
            initial_path or self.last_browse_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self.last_browse_dir = os.path.dirname(directory)
            self.file_service.last_browse_dir = self.last_browse_dir
            return directory
        return None

    def select_jpg_dir(self):
        directory = self.choose_directory("请选择JPG文件夹", self.file_service.jpg_dir)
        if directory:
            self.apply_jpg_dir(directory)

    def select_raw_dir(self):
        directory = self.choose_directory("请选择RAW文件夹", self.file_service.raw_dir)
        if directory:
            self.apply_raw_dir(directory)

    def select_dest_dir(self):
        directory = self.choose_directory("请选择导出文件夹", self.file_service.dest_dir)
        if directory:
            self.apply_dest_dir(directory)

    def apply_jpg_dir(self, directory: str):
        directory = directory if os.path.isdir(directory) else os.path.dirname(directory)
        if self.file_service.set_jpg_dir(directory):
            self.lbl_jpg_path.setText(os.path.basename(directory))
            self.refresh_state()
        else:
            QMessageBox.warning(self.window, "提示", "路径无效，请检查后重试")

    def apply_raw_dir(self, directory: str):
        directory = directory if os.path.isdir(directory) else os.path.dirname(directory)
        if self.file_service.set_raw_dir(directory):
            self.lbl_raw_path.setText(os.path.basename(directory))
            self.raw_ext = self.file_service.raw_ext
            self.lbl_raw_ext.setText(self.raw_ext)
        else:
            QMessageBox.warning(self.window, "提示", "路径无效，请检查后重试")

    def apply_dest_dir(self, directory: str):
        directory = directory if os.path.isdir(directory) else os.path.dirname(directory)
        if self.file_service.set_dest_dir(directory):
            self.lbl_dest_path.setText(os.path.basename(directory))
        else:
            QMessageBox.warning(self.window, "提示", "路径无效，请检查后重试")

    def refresh_state(self):
        state = self.file_service.get_current_state()
        self.image_files = state.get("files", []) or []
        self.current_idx = state.get("current_idx", 0) or 0
        self.states = state.get("states", {}) or {}
        self.raw_ext = state.get("raw_ext", ".CR2") or ".CR2"
        self.lbl_raw_ext.setText(self.raw_ext)
        self.lbl_jpg_path.setText(os.path.basename(state.get("jpg_dir", "")) or "[未选择]")
        self.lbl_raw_path.setText(os.path.basename(state.get("raw_dir", "")) or "[未选择]")
        self.lbl_dest_path.setText(os.path.basename(state.get("dest_dir", "")) or "[未选择]")

        self.window.update()
        self.window.repaint()
        QTimer.singleShot(50, self.update_view)

    def update_view(self):
        self.update_info_bar()
        if self._full_preview_mode:
            self.refresh_full_preview()
        else:
            self.refresh_main_image()
        self.refresh_thumbnails()

    def update_info_bar(self):
        if not self.image_files:
            self.info_label.setText("请先导入JPG文件夹开始筛选")
            return
        current_file = self.image_files[self.current_idx]
        total = len(self.image_files)
        pass_count = sum(1 for v in self.states.values() if v == 1)
        self.info_label.setText(f"{current_file}  |  当前第 {self.current_idx + 1} 张 / 总共 {total} 张  |  已入选：{pass_count} 张")

    def _calc_thumbnail_metrics(self):
        scroll_height = self.thumbnail_scroll.size().height()
        viewport_height = self.thumbnail_scroll.viewport().height()

        effective_height = max(scroll_height, viewport_height)

        if effective_height <= 20:
            splitter_sizes = self.main_splitter.sizes()
            if len(splitter_sizes) > 1:
                effective_height = splitter_sizes[1]

        if effective_height <= 20:
            window_height = self.window.height()
            path_bar_height = self.path_bar.height() if self.path_bar else 50
            available = window_height - path_bar_height
            effective_height = available * 0.25

        if effective_height <= 20:
            effective_height = 200

        size = max(80, min(160, effective_height - 20))
        self.thumbnail_button_size = QSize(size, size)
        self.thumbnail_icon_size = QSize(size - 6, size - 6)

    def _load_pixmap(self, path: str) -> QPixmap:
        if path in self.pixmap_cache:
            self.pixmap_cache.move_to_end(path)
            return self.pixmap_cache[path]
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.pixmap_cache[path] = pixmap
            if len(self.pixmap_cache) > self._max_cache_size:
                self.pixmap_cache.popitem(last=False)
        return pixmap if pixmap is not None else QPixmap()

    def schedule_viewport_refresh(self):
        self._viewport_refresh_timer.start()

    def refresh_visible_views(self):
        self._calc_thumbnail_metrics()
        if self.current_main_pixmap.isNull():
            self.refresh_thumbnails()
            return
        self.fit_main_image(reset_zoom=False)
        self.refresh_thumbnails()

    def _apply_main_image_transform(self):
        if self.current_main_pixmap.isNull():
            return
        scale_factor = max(0.05, self.main_fit_factor * self.main_zoom_ratio)
        scaled_width = max(1, int(self.current_main_pixmap.width() * scale_factor))
        scaled_height = max(1, int(self.current_main_pixmap.height() * scale_factor))
        scaled = self.current_main_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.main_image.setPixmap(scaled)
        self.main_image.resize(scaled.size())
        self.main_image_scroll.widget().adjustSize()

    def fit_main_image(self, reset_zoom: bool = True):
        if self.current_main_pixmap.isNull():
            return
        viewport = self.main_image_scroll.viewport().size()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        pixmap_size = self.current_main_pixmap.size()
        if pixmap_size.isEmpty():
            return
        self.main_fit_factor = min(
            viewport.width() / pixmap_size.width(),
            viewport.height() / pixmap_size.height(),
        )
        if reset_zoom:
            self.main_zoom_ratio = 1.0
        self._apply_main_image_transform()

    def zoom_main_image(self, factor: float):
        if self.current_main_pixmap.isNull():
            return
        self.main_zoom_ratio = max(0.1, min(8.0, self.main_zoom_ratio * factor))
        self._apply_main_image_transform()

    def refresh_main_image(self):
        if not self.image_files:
            self.current_image_path = ""
            self.current_main_pixmap = QPixmap()
            self.main_image.clear()
            self.main_image.setText("")
            self.main_image.setVisible(False)
            self.main_image_scroll.setVisible(False)
            self.main_placeholder.setVisible(True)
            return

        filename = self.image_files[self.current_idx]
        self.current_image_path = str(Path(self.file_service.jpg_dir) / filename)
        pixmap = self._load_pixmap(self.current_image_path)
        if pixmap.isNull():
            self.current_main_pixmap = QPixmap()
            self.main_image.clear()
            self.main_image.setText("图片加载失败")
            self.main_placeholder.setVisible(False)
            self.main_image_scroll.setVisible(True)
            self.main_image.setVisible(True)
            return

        self.current_main_pixmap = pixmap
        self.main_placeholder.setVisible(False)
        self.main_image_scroll.setVisible(True)
        self.main_image.setVisible(True)
        self.fit_main_image(reset_zoom=True)
        self.preload_thumbnails()

    def preload_thumbnails(self):
        if not self.image_files:
            return
        start_idx = max(0, self.current_idx - 3)
        end_idx = min(len(self.image_files), self.current_idx + 5)
        for i in range(start_idx, end_idx):
            _ = self.load_thumbnail_pixmap(self.image_files[i])

    def load_thumbnail_pixmap(self, filename: str) -> QPixmap:
        if not self.file_service.jpg_dir:
            return QPixmap()
        path = str(Path(self.file_service.jpg_dir) / filename)
        pixmap = self._load_pixmap(path)
        if pixmap.isNull():
            return pixmap

        size = pixmap.size()
        min_dim = min(size.width(), size.height())
        x = (size.width() - min_dim) // 2
        y = (size.height() - min_dim) // 2
        cropped = pixmap.copy(x, y, min_dim, min_dim)
        target_size = getattr(self, "thumbnail_button_size", QSize(96, 96))
        return cropped.scaled(
            target_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def refresh_thumbnails(self):
        self._calc_thumbnail_metrics()

        if not self.image_files:
            while self.thumbnail_layout.count():
                item = self.thumbnail_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._thumb_buttons.clear()
            return

        need_rebuild = len(self._thumb_buttons) != len(self.image_files)
        if need_rebuild:
            while self.thumbnail_layout.count():
                item = self.thumbnail_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._thumb_buttons.clear()

            for idx, filename in enumerate(self.image_files):
                status = 2 if idx == self.current_idx else self.states.get(filename, 0)
                button = ThumbnailButton(self, idx, filename, status)
                button.setFixedSize(self.thumbnail_button_size)
                button.setIconSize(self.thumbnail_icon_size)
                self.thumbnail_layout.addWidget(button)
                self._thumb_buttons[idx] = button

            self.thumbnail_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        else:
            for idx in range(len(self.image_files)):
                button = self._thumb_buttons.get(idx)
                if button:
                    button._calc_square_metrics()
                    button.setFixedSize(self.thumbnail_button_size)
                    button.setIconSize(self.thumbnail_icon_size)

                    filename = self.image_files[idx]
                    status = 2 if idx == self.current_idx else self.states.get(filename, 0)
                    new_status_name = button._status_name(status)
                    if button.property("status") != new_status_name:
                        button.setProperty("status", new_status_name)
                        button.style().unpolish(button)
                        button.style().polish(button)
                    button.update()

        QTimer.singleShot(0, self.scroll_current_thumbnail_into_view)

    def scroll_current_thumbnail_into_view(self):
        current_button = self._thumb_buttons.get(self.current_idx)
        if current_button is not None:
            self.thumbnail_scroll.ensureWidgetVisible(current_button)

    def mark_pass(self):
        result = self.file_service.mark_pass()
        if result:
            self.current_idx = self.file_service.current_idx
            self.states = self.file_service.states
            self.update_view()

    def mark_reject(self):
        result = self.file_service.mark_reject()
        if result:
            self.current_idx = self.file_service.current_idx
            self.states = self.file_service.states
            self.update_view()

    def undo(self):
        result = self.file_service.undo()
        if result:
            self.current_idx = self.file_service.current_idx
            self.states = self.file_service.states
            self.update_view()

    def go_prev(self):
        result = self.file_service.go_prev()
        if result:
            self.current_idx = self.file_service.current_idx
            self.update_view()

    def go_next(self):
        if not self.image_files:
            return
        if self.current_idx < len(self.image_files) - 1:
            result = self.file_service.go_next()
            if result:
                self.current_idx = self.file_service.current_idx
                self.update_view()
            self._confirm_next_press_ts = 0.0
            self._confirm_next_count = 0
            return

        now = time.monotonic()
        last_ts = getattr(self, "_confirm_next_ts", 0.0)
        last_count = getattr(self, "_confirm_next_count", 0)
        if now - last_ts <= 0.35 and last_count == 1:
            self._confirm_next_ts = 0.0
            self._confirm_next_count = 0
            self.show_confirm_dialog()
            return

        self._confirm_next_ts = now
        self._confirm_next_count = 1

    def go_to(self, idx: int):
        result = self.file_service.go_to(idx)
        if result:
            self.current_idx = self.file_service.current_idx
            self.update_view()

    def show_confirm_dialog(self):
        if not self.file_service.raw_dir or not self.file_service.dest_dir:
            QMessageBox.warning(self.window, "提示", "尚未配置【RAW目录】或【导出目录】！请在界面最上方完成选择。")
            return
        text = f"全部筛选完毕！即将匹配后辍为 [{self.raw_ext}] 的原图。是否开始批量复制到导出目录？"
        ret = QMessageBox.question(self.window, "筛选完毕", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.execute_copy()

    def execute_copy(self):
        try:
            result = self.file_service.copy_raw_files()
        except Exception as exc:
            QMessageBox.critical(self.window, "复制失败", str(exc))
            return

        if result.get("success"):
            success_count = result.get("success_count", 0)
            missing_files = result.get("missing_files", []) or []
            message = f"复制完成！成功复制 RAW 文件：{success_count} 张"
            details = []
            if missing_files:
                message += f"\n缺失/失败文件数量：{len(missing_files)} 张"
                details = missing_files
            dialog = SummaryDialog(self.window, "复制汇总", message, details)
            dialog.exec()
            self.refresh_state()
        else:
            QMessageBox.critical(self.window, "复制失败", result.get("error", "复制失败"))

    def update_thumbnail_max_height(self):
        max_thumb_size = 160
        top_margin, bottom_margin = 12, 8
        padding_for_hover = 12
        max_height = max_thumb_size + top_margin + bottom_margin + padding_for_hover
        self.thumbnail_scroll.setMaximumHeight(max_height)

    def check_full_preview_mode(self):
        if not self.image_files:
            return

        max_thumb_size = 160
        top_margin, bottom_margin = 12, 8
        padding_for_hover = 12
        normal_max_height = max_thumb_size + top_margin + bottom_margin + padding_for_hover
        full_trigger_height = normal_max_height * 2

        sizes = self.main_splitter.sizes()
        thumb_height = sizes[1] if len(sizes) > 1 else 0

        if thumb_height > full_trigger_height and not self._full_preview_mode:
            self.enter_full_preview_mode()
        elif thumb_height < normal_max_height and self._full_preview_mode:
            self.exit_full_preview_mode()

    def enter_full_preview_mode(self):
        self._full_preview_mode = True

        self.main_image_scroll.hide()
        self.main_placeholder.hide()

        self._full_preview_container = QWidget(self.main_drop_zone)
        self._full_preview_container.setObjectName("fullPreviewContainer")
        layout = QHBoxLayout(self._full_preview_container)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._full_preview_left = QLabel(self._full_preview_container)
        self._full_preview_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._full_preview_left.setStyleSheet("background: #000000;")

        self._full_preview_center = QLabel(self._full_preview_container)
        self._full_preview_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._full_preview_center.setStyleSheet("background: #000000;")

        self._full_preview_right = QLabel(self._full_preview_container)
        self._full_preview_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._full_preview_right.setStyleSheet("background: #000000;")

        layout.addWidget(self._full_preview_left)
        layout.addWidget(self._full_preview_center)
        layout.addWidget(self._full_preview_right)

        self._full_preview_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._full_preview_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._full_preview_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        drop_layout = self.main_drop_zone.layout()
        drop_layout.addWidget(self._full_preview_container, 0, 0)
        self._full_preview_container.show()

        self.thumbnail_scroll.setMaximumHeight(16777215)

        self.refresh_full_preview()

    def exit_full_preview_mode(self):
        self._full_preview_mode = False

        if self._full_preview_container:
            self._full_preview_container.deleteLater()
            self._full_preview_container = None
            self._full_preview_left = None
            self._full_preview_center = None
            self._full_preview_right = None

        self.update_thumbnail_max_height()

        if self.current_main_pixmap.isNull():
            self.main_placeholder.show()
        else:
            self.main_image_scroll.show()

    def refresh_full_preview(self):
        if not self._full_preview_mode or not self.image_files:
            return

        container_size = self._full_preview_container.size()
        if container_size.width() <= 0 or container_size.height() <= 0:
            return

        center_width = container_size.width() // 2
        side_width = (container_size.width() - center_width) // 2
        height = container_size.height()

        self._update_full_preview_label(self._full_preview_left, self.current_idx - 1, side_width, height, True)
        self._update_full_preview_label(self._full_preview_center, self.current_idx, center_width, height, False)
        self._update_full_preview_label(self._full_preview_right, self.current_idx + 1, side_width, height, False)

    def _update_full_preview_label(self, label, idx, width, height, is_left):
        if idx < 0 or idx >= len(self.image_files):
            label.clear()
            label.setText("")
            return

        filename = self.image_files[idx]
        path = str(Path(self.file_service.jpg_dir) / filename)
        pixmap = self._load_pixmap(path)

        if pixmap.isNull():
            label.clear()
            label.setText("")
            return

        scale_factor = min(width / pixmap.width(), height / pixmap.height())
        scaled_height = int(pixmap.height() * scale_factor)
        scaled_width = int(pixmap.width() * scale_factor)

        scaled = pixmap.scaled(scaled_width, scaled_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        if scaled_width > width:
            if is_left:
                source_rect = QRect(scaled_width - width, 0, width, scaled_height)
            else:
                source_rect = QRect(0, 0, width, scaled_height)
            clipped = scaled.copy(source_rect)
            label.setPixmap(clipped)
        else:
            label.setPixmap(scaled)

        status = self.states.get(filename, 0)
        border_color = "#00bcd4" if status == 2 else "#4caf50" if status == 1 else "#f44336" if status == -1 else "#333333"
        label.setStyleSheet(f"background: #000000; border: 3px solid {border_color};")

    def run(self):
        self.window.show()
        original_resize = self.window.resizeEvent
        def custom_resize(event):
            self.update_thumbnail_max_height()
            if self._full_preview_mode:
                self.refresh_full_preview()
            original_resize(event)
        self.window.resizeEvent = custom_resize
        return self.app.exec()


def run():
    app = PhotoCullerApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(run())
