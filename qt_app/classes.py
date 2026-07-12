from __future__ import annotations

import os
import shutil
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QFile, QObject, Qt, QTimer, QSize, QEvent, QPoint, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor, QKeySequence, QPixmap, QPalette, QShortcut, QPainter, QPainterPath, QPen, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
)
from PySide6.QtUiTools import QUiLoader

from qt_app.config import (
    APP_NAME,
    HOVER_ANIM_DURATION,
    HOVER_SCALE_FACTOR,
    MAIN_SPLITTER_HANDLE_WIDTH,
    MAIN_SPLITTER_INITIAL_SIZES,
    MAX_CACHE_SIZE,
    NEXT_CONFIRM_WINDOW,
    STYLE_SHEET,
    THUMBNAIL_BOTTOM_MARGIN,
    THUMBNAIL_HOVER_PADDING,
    THUMBNAIL_LAYOUT_MARGINS,
    THUMBNAIL_LAYOUT_SPACING,
    THUMBNAIL_MAX_SIZE,
    THUMBNAIL_MIN_SIZE,
    THUMBNAIL_SCROLL_MIN_HEIGHT,
    THUMBNAIL_TOP_MARGIN,
    UI_PATH,
    VIEWPORT_REFRESH_INTERVAL,
)


class FileService:
    RAW_EXTENSIONS = [
        '.CR3', '.CR2', '.CRW',
        '.NEF', '.NRW',
        '.ARW', '.SR2', '.SRF',
        '.RAF',
        '.RW2',
        '.ORF',
        '.PEF',
        '.DNG',
        '.X3F'
    ]
    RAW_EXTENSIONS_LOWER = {e.lower() for e in RAW_EXTENSIONS}

    def __init__(self):
        self.jpg_dir = ""
        self.raw_dir = ""
        self.dest_dir = ""
        self.raw_ext = ".CR2"
        self.image_files = []
        self.current_idx = 0
        self.states = {}
        self.pass_count = 0
        self.last_browse_dir = os.path.expanduser("~")

    def validate_folder(self, folder_path):
        if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return False
        return True

    def set_jpg_dir(self, folder_path):
        if not self.validate_folder(folder_path):
            return False
        self.jpg_dir = folder_path
        self.reload_jpg_images()
        return True

    def auto_detect_raw_ext(self):
        if not self.raw_dir or not os.path.exists(self.raw_dir):
            return None

        try:
            files = os.listdir(self.raw_dir)
            ext_count = {}
            for f in files:
                ext = os.path.splitext(f)[1].upper()
                if ext.lower() in FileService.RAW_EXTENSIONS_LOWER:
                    ext_count[ext] = ext_count.get(ext, 0) + 1

            if ext_count:
                return max(ext_count, key=ext_count.get)
            return None
        except Exception as e:
            print(f"自动识别RAW后缀失败: {e}")
            return None

    def set_raw_dir(self, folder_path):
        if not self.validate_folder(folder_path):
            return False
        self.raw_dir = folder_path
        detected = self.auto_detect_raw_ext()
        if detected:
            self.raw_ext = detected
        return True

    def set_dest_dir(self, folder_path):
        if not self.validate_folder(folder_path):
            return False
        self.dest_dir = folder_path
        return True

    def reload_jpg_images(self):
        try:
            files = os.listdir(self.jpg_dir)
            self.image_files = sorted([f for f in files if f.lower().endswith('.jpg')])
            self.current_idx = 0
            self.states = {f: 0 for f in self.image_files}
            self.pass_count = 0
        except Exception as e:
            self.image_files = []
            self.current_idx = 0
            self.states = {}
            self.pass_count = 0
            raise Exception(f"读取JPG目录失败: {e}")

    def check_match(self):
        if not self.jpg_dir or not self.raw_dir:
            return {
                "can_check": False,
                "jpg_count": len(self.image_files),
                "raw_count": 0,
                "missing_raw": [],
                "extra_raw": [],
                "match_count": 0
            }

        try:
            raw_files_in_dir = os.listdir(self.raw_dir)
            raw_files = sorted([f for f in raw_files_in_dir if os.path.splitext(f)[1].lower() in FileService.RAW_EXTENSIONS_LOWER])
        except Exception as e:
            raise Exception(f"无法读取RAW目录: {e}")

        raw_basenames_lower = {os.path.splitext(f)[0].lower(): f for f in raw_files}
        jpg_basenames_lower = {os.path.splitext(f)[0].lower(): f for f in self.image_files}

        missing_raw = []
        extra_raw = []
        match_count = 0

        for jpg_lower, jpg_name in jpg_basenames_lower.items():
            if jpg_lower in raw_basenames_lower:
                match_count += 1
            else:
                missing_raw.append(jpg_name)

        for raw_lower, raw_name in raw_basenames_lower.items():
            if raw_lower not in jpg_basenames_lower:
                extra_raw.append(raw_name)

        return {
            "can_check": True,
            "jpg_count": len(self.image_files),
            "raw_count": len(raw_files),
            "missing_raw": sorted(missing_raw),
            "extra_raw": sorted(extra_raw),
            "match_count": match_count
        }

    def write_missing_report(self, missing_files):
        if not self.raw_dir or not missing_files:
            return None
        report_path = os.path.join(self.raw_dir, "缺失RAW文件列表.txt")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("以下JPG照片在RAW目录中找不到对应的RAW文件：\n")
                f.write("=" * 50 + "\n")
                for idx, name in enumerate(missing_files, 1):
                    f.write(f"{idx}. {name}\n")
                f.write("=" * 50 + "\n")
                f.write(f"共计缺失: {len(missing_files)} 个RAW文件\n")
            return report_path
        except Exception as e:
            print(f"写入缺失报告失败: {e}")
            return None

    def copy_jpg_files(self):
        if not self.jpg_dir or not self.dest_dir:
            raise Exception("路径缺失")

        pass_list = [f for f, state in self.states.items() if state == 1]
        if not pass_list:
            raise Exception("没有选中任何合格照片")

        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)

        success_count = 0
        failed_files = []

        for jpg_name in pass_list:
            src_path = os.path.join(self.jpg_dir, jpg_name)
            dest_path = os.path.join(self.dest_dir, jpg_name)
            try:
                shutil.copy2(src_path, dest_path)
                success_count += 1
            except Exception:
                failed_files.append(jpg_name)

        return {
            "success": True,
            "success_count": success_count,
            "failed_files": failed_files,
            "mode": "jpg"
        }

    def copy_raw_files(self, strict: bool = True):
        if not self.raw_dir or not self.dest_dir:
            raise Exception("路径缺失")

        pass_list = [f for f, state in self.states.items() if state == 1]
        if not pass_list:
            raise Exception("没有选中任何合格照片")

        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)

        success_count = 0
        missing_files = []

        try:
            raw_files_in_dir = os.listdir(self.raw_dir)
            raw_map = {f.lower(): f for f in raw_files_in_dir}
        except Exception as e:
            raise Exception(f"无法读取RAW目录: {e}")

        for jpg_name in pass_list:
            base_name = os.path.splitext(jpg_name)[0]
            target_raw_lower = (base_name + self.raw_ext).lower()

            if target_raw_lower in raw_map:
                real_raw_name = raw_map[target_raw_lower]
                src_path = os.path.join(self.raw_dir, real_raw_name)
                dest_path = os.path.join(self.dest_dir, real_raw_name)
                try:
                    shutil.copy2(src_path, dest_path)
                    success_count += 1
                except Exception:
                    missing_files.append(real_raw_name)
            else:
                missing_files.append(base_name + self.raw_ext)

        if strict and missing_files:
            self.write_missing_report(missing_files)

        return {
            "success": True,
            "success_count": success_count,
            "missing_files": missing_files,
            "mode": "raw"
        }

    def get_current_state(self):
        return {
            "files": self.image_files,
            "current_idx": self.current_idx,
            "states": self.states,
            "jpg_dir": self.jpg_dir,
            "raw_dir": self.raw_dir,
            "dest_dir": self.dest_dir,
            "raw_ext": self.raw_ext
        }

    def mark_pass(self):
        if not self.image_files:
            return False
        filename = self.image_files[self.current_idx]
        prev = self.states.get(filename, 0)
        self.states[filename] = 1
        if prev != 1:
            if prev == 0:
                self.pass_count += 1
            elif prev == -1:
                self.pass_count += 1
        if self.current_idx < len(self.image_files) - 1:
            self.current_idx += 1
        return True

    def mark_pass_at(self, idx):
        if not self.image_files or idx < 0 or idx >= len(self.image_files):
            return False
        filename = self.image_files[idx]
        prev = self.states.get(filename, 0)
        self.states[filename] = 1
        if prev != 1:
            if prev == 0:
                self.pass_count += 1
            elif prev == -1:
                self.pass_count += 1
        return True

    def mark_reject(self):
        if not self.image_files:
            return False
        filename = self.image_files[self.current_idx]
        prev = self.states.get(filename, 0)
        self.states[filename] = -1
        if prev == 1:
            self.pass_count -= 1
        if self.current_idx < len(self.image_files) - 1:
            self.current_idx += 1
        return True

    def mark_reject_at(self, idx):
        if not self.image_files or idx < 0 or idx >= len(self.image_files):
            return False
        filename = self.image_files[idx]
        prev = self.states.get(filename, 0)
        self.states[filename] = -1
        if prev == 1:
            self.pass_count -= 1
        return True

    def reset_state_at(self, idx):
        if not self.image_files or idx < 0 or idx >= len(self.image_files):
            return False
        filename = self.image_files[idx]
        prev = self.states.get(filename, 0)
        self.states[filename] = 0
        if prev == 1:
            self.pass_count -= 1
        return True

    def undo(self):
        if not self.image_files:
            return False
        filename = self.image_files[self.current_idx]
        if self.states[filename] == 0 and self.current_idx > 0:
            self.current_idx -= 1
            filename = self.image_files[self.current_idx]
            prev = self.states.get(filename, 0)
            self.states[filename] = 0
            if prev == 1:
                self.pass_count -= 1
            elif prev == -1:
                pass
        else:
            prev = self.states.get(filename, 0)
            self.states[filename] = 0
            if prev == 1:
                self.pass_count -= 1
        return True

    def go_prev(self):
        if not self.image_files or self.current_idx <= 0:
            return False
        self.current_idx -= 1
        return True

    def go_next(self):
        if not self.image_files or self.current_idx >= len(self.image_files) - 1:
            return False
        self.current_idx += 1
        return True

    def go_to(self, idx):
        if 0 <= idx < len(self.image_files):
            self.current_idx = idx
            return True
        return False


class DropEventFilter(QObject):
    def __init__(self, owner: "PhotoCullerApp"):
        super().__init__()
        self.owner = owner
        self.dragging = False
        self.last_pos = QPoint()
        self.press_pos = QPoint()
        self._hover_thumb_idx = -1
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(16)
        self._hover_timer.timeout.connect(self._check_thumb_hover)

    def start_thumb_hover_tracking(self):
        self._hover_timer.start()

    def stop_thumb_hover_tracking(self):
        self._hover_timer.stop()
        self._clear_thumb_hover()

    def _check_thumb_hover(self):
        scroll = self.owner.thumbnail_scroll
        global_pos = QCursor.pos()
        local_pos = scroll.mapFromGlobal(global_pos)
        viewport = scroll.viewport()

        if not viewport.rect().contains(local_pos):
            self._clear_thumb_hover()
            return

        content_pos = scroll.widget().mapFromGlobal(global_pos)
        content = scroll.widget()
        child = content.childAt(content_pos)
        target_idx = -1
        if child is not None:
            btn = child
            while btn is not None and not hasattr(btn, 'index'):
                btn = btn.parent()
            if btn is not None and hasattr(btn, 'index'):
                target_idx = btn.index

        if target_idx == self._hover_thumb_idx:
            return

        if self._hover_thumb_idx != -1:
            old_btn = self.owner._thumb_buttons.get(self._hover_thumb_idx)
            if old_btn is not None:
                old_btn.set_hovered(False)

        self._hover_thumb_idx = target_idx

        if target_idx != -1:
            new_btn = self.owner._thumb_buttons.get(target_idx)
            if new_btn is not None:
                new_btn.set_hovered(True)

    def _clear_thumb_hover(self):
        if self._hover_thumb_idx != -1:
            btn = self.owner._thumb_buttons.get(self._hover_thumb_idx)
            if btn is not None:
                btn.set_hovered(False)
            self._hover_thumb_idx = -1

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
        if etype == QEvent.MouseButtonPress:
            if self.owner.match_overlay.isVisible():
                click_pos = event.globalPosition().toPoint()
                overlay_pos = self.owner.match_overlay.mapToGlobal(self.owner.match_overlay.rect().topLeft())
                overlay_rect = self.owner.match_overlay.rect()
                overlay_rect.moveTopLeft(overlay_pos)
                if not overlay_rect.contains(click_pos):
                    self.owner.match_overlay.hide_overlay()
            if obj in (self.owner.main_image_scroll.viewport(), self.owner.main_image):
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
        if etype == QEvent.Resize and obj in (self.owner.main_image_scroll.viewport(), self.owner.thumbnail_scroll.viewport(), self.owner.main_drop_zone):
            self.owner.schedule_viewport_refresh()
        return False


class ThumbnailButton(QToolButton):
    def __init__(self, owner: "PhotoCullerApp", index: int, path: str, status: int, is_current: bool = False):
        super().__init__()
        self.owner = owner
        self.index = index
        self.path = path
        self._scale = HOVER_SCALE_FACTOR if is_current else 1.0
        self._scale_anim = None
        self._is_hovered = False
        self._is_current = is_current
        self._thumb_pixmap = owner.load_thumbnail_pixmap(path)
        self._is_pressed = False
        self.setProperty("thumbnail", True)
        self.setProperty("status", self._status_name(status))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._calc_square_metrics()
        self.setFixedSize(self.thumbnail_button_size)
        self.setIconSize(self.thumbnail_icon_size)
        self.setAutoRaise(False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def _calc_square_metrics(self):
        self.owner._calc_thumbnail_metrics()
        self.thumbnail_button_size = self.owner.thumbnail_button_size
        self.thumbnail_icon_size = self.owner.thumbnail_icon_size

    def _status_name(self, status: int) -> str:
        if status == 1:
            return "pass"
        if status == -1:
            return "reject"
        return "normal"

    def _set_scale(self, value: float):
        self._scale = value
        self.update()

    scale = Property(float, lambda self: self._scale, _set_scale)

    def _target_scale(self) -> float:
        if self._is_current or self._is_hovered:
            return HOVER_SCALE_FACTOR
        return 1.0

    def _animate_to_target(self):
        target = self._target_scale()
        if abs(self._scale - target) < 0.001:
            return
        if self._scale_anim is not None:
            self._scale_anim.stop()
        anim = QPropertyAnimation(self, b"scale", self)
        anim.setDuration(HOVER_ANIM_DURATION)
        anim.setStartValue(self._scale)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._scale_anim = anim

    def set_current(self, is_current: bool):
        if self._is_current == is_current:
            return
        self._is_current = is_current
        if self._scale_anim is not None:
            self._scale_anim.stop()
        self._set_scale(self._target_scale())

    def set_hovered(self, is_hovered: bool):
        if self._is_hovered == is_hovered:
            return
        self._is_hovered = is_hovered
        self._animate_to_target()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            if self.rect().contains(event.position().toPoint()):
                self._on_click()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.owner.mark_reject_at(self.index)
        event.accept()

    def _on_click(self):
        is_current = self.index == self.owner.current_idx
        if is_current:
            self.owner.mark_pass_at(self.index)
        else:
            self.owner.go_to(self.index)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        center_x = self.rect().width() / 2
        center_y = self.rect().height() / 2
        painter.translate(center_x, center_y)
        painter.scale(self._scale, self._scale)
        painter.translate(-center_x, -center_y)

        max_scale = HOVER_SCALE_FACTOR
        base_padding = int(self.rect().width() * (max_scale - 1) / 2) + 1
        top_padding = base_padding + 3
        outer_rect = self.rect().adjusted(base_padding, top_padding, -base_padding, -base_padding)

        inner_border_width = 2
        status = self.property("status")
        radius = 8

        bg = QColor("#111111")

        inner_border_color = QColor("transparent")
        if status == "pass":
            inner_border_color = QColor("#4caf50")
        elif status == "reject":
            inner_border_color = QColor("#f44336")

        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer_rect, radius, radius)
        painter.fillPath(outer_path, bg)

        if inner_border_color.alpha() > 0:
            content_path = QPainterPath()
            content_path.addRoundedRect(outer_rect, radius, radius)
            painter.fillPath(content_path, inner_border_color)

            image_rect = outer_rect.adjusted(
                inner_border_width,
                inner_border_width,
                -inner_border_width,
                -inner_border_width,
            )
            image_radius = max(0, radius - inner_border_width)
            image_path = QPainterPath()
            image_path.addRoundedRect(image_rect, image_radius, image_radius)
            painter.fillPath(image_path, bg)
        else:
            image_rect = outer_rect
            image_radius = radius
            image_path = QPainterPath()
            image_path.addRoundedRect(image_rect, image_radius, image_radius)

        painter.setClipPath(image_path)

        if not self._thumb_pixmap.isNull():
            scaled = self._thumb_pixmap.scaled(
                image_rect.width(),
                image_rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = image_rect.x() + (image_rect.width() - scaled.width()) // 2
            y = image_rect.y() + (image_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)


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


class MatchOverlay(QWidget):
    COLOR_MATCH = "#4caf50"
    COLOR_MISSING_RAW = "#f44336"
    COLOR_EXTRA_RAW = "#ff9800"
    ROW_HEIGHT = 24
    HORIZONTAL_GAP = 20
    AUTO_HIDE_MS = 3000
    WIDTH_RATIO = 0.22

    def __init__(self, parent: QWidget, anchor_widget: QWidget | None = None):
        super().__init__(parent)
        self._anchor = anchor_widget
        self._is_hovered = False
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        self.bg_frame = QFrame(self)
        self.bg_frame.setObjectName("matchOverlayBg")
        self.bg_frame.setStyleSheet("""
            QFrame#matchOverlayBg {
                background: rgba(30, 30, 30, 215);
                border: 1px solid #444444;
                border-radius: 8px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 6px;
                background: #1a1a1a;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #444444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(14, 10, 14, 10)
        bg_layout.setSpacing(6)

        self.header_label = QLabel("文件匹配对照")
        self.header_label.setStyleSheet("color: #ffb300; font-size: 13px; font-weight: bold;")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_layout.addWidget(self.header_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.content)
        self.list_layout.setContentsMargins(2, 2, 2, 2)
        self.list_layout.setSpacing(1)

        self.scroll.setWidget(self.content)
        bg_layout.addWidget(self.scroll, 1)

        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.bg_frame)

        self.setMouseTracking(True)
        self.bg_frame.setMouseTracking(True)
        self.content.setMouseTracking(True)
        self.scroll.viewport().setMouseTracking(True)

    def set_data(self, jpg_files: list[str], raw_files: list[str]):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        jpg_map = {os.path.splitext(f)[0].lower(): f for f in sorted(jpg_files)}
        raw_map = {os.path.splitext(f)[0].lower(): f for f in sorted(raw_files)}

        all_basenames = sorted(set(list(jpg_map.keys()) + list(raw_map.keys())))

        for base in all_basenames:
            jpg_name = jpg_map.get(base, "")
            raw_name = raw_map.get(base, "")

            row = QWidget()
            row.setMouseTracking(True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self.HORIZONTAL_GAP)
            row.setFixedHeight(self.ROW_HEIGHT)

            left_label = QLabel(jpg_name if jpg_name else "")
            left_label.setFixedHeight(self.ROW_HEIGHT)
            left_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            if not jpg_name:
                left_color = "transparent"
            elif raw_name:
                left_color = self.COLOR_MATCH
            else:
                left_color = self.COLOR_MISSING_RAW
            left_label.setStyleSheet(f"color: {left_color}; font-size: 12px; background: transparent;")

            arrow = QLabel("→")
            arrow.setFixedHeight(self.ROW_HEIGHT)
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow_color = self.COLOR_MATCH if (jpg_name and raw_name) else "#555555"
            arrow.setStyleSheet(f"color: {arrow_color}; font-size: 13px; font-weight: bold; background: transparent;")

            right_label = QLabel(raw_name if raw_name else "")
            right_label.setFixedHeight(self.ROW_HEIGHT)
            right_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            if not raw_name:
                right_color = "transparent"
            elif jpg_name:
                right_color = self.COLOR_MATCH
            else:
                right_color = self.COLOR_EXTRA_RAW
            right_label.setStyleSheet(f"color: {right_color}; font-size: 12px; background: transparent;")

            row_layout.addWidget(left_label, 1)
            row_layout.addWidget(arrow, 0)
            row_layout.addWidget(right_label, 1)

            self.list_layout.addWidget(row)

        self.list_layout.addStretch(1)

    def show_overlay(self, duration_ms: int | None = None):
        self.show()
        self.raise_()
        self._update_position()
        if duration_ms is not None:
            self._auto_hide_timer.start(duration_ms)
        else:
            self._auto_hide_timer.stop()

    def hide_overlay(self):
        self._auto_hide_timer.stop()
        self.hide()

    def toggle_overlay(self):
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay(duration_ms=None)

    def _on_auto_hide_timeout(self):
        if not self._is_hovered:
            self.hide_overlay()

    def enterEvent(self, event):
        self._is_hovered = True
        self._auto_hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        if self._auto_hide_timer.isActive():
            pass
        elif not self._pinned:
            self._auto_hide_timer.start(500)
        super().leaveEvent(event)

    @property
    def _pinned(self) -> bool:
        return not self._auto_hide_timer.isActive() and self.isVisible()

    def _update_position(self):
        parent = self.parentWidget()
        if parent is None:
            return

        border_radius = 8

        if self._anchor is not None:
            anchor_rect = self._anchor.geometry()
            anchor_pos = self._anchor.mapTo(parent, anchor_rect.topLeft())
            area_x = anchor_pos.x()
            area_top = anchor_pos.y()
            area_w = anchor_rect.width()
            area_bottom = anchor_pos.y() + anchor_rect.height()
        else:
            area_x = 0
            area_top = 0
            area_w = parent.width()
            area_bottom = parent.height()

        top_y = area_top + border_radius

        w = max(320, int(area_w * self.WIDTH_RATIO))

        max_h = max(120, area_bottom - top_y - border_radius)
        h = max_h

        x = area_x + area_w - w - border_radius
        y = top_y

        self.setGeometry(x, y, w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg_frame.setGeometry(0, 0, self.width(), self.height())


class PhotoCullerApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance() or QApplication([])
        self.app.setApplicationName(APP_NAME)
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
        self._max_cache_size = MAX_CACHE_SIZE
        self._thumb_buttons: dict[int, ThumbnailButton] = {}
        self._viewport_refresh_timer = QTimer(self)
        self._viewport_refresh_timer.setSingleShot(True)
        self._viewport_refresh_timer.setInterval(VIEWPORT_REFRESH_INTERVAL)
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
        self.info_label.setMinimumHeight(24)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.info_label.setStyleSheet("""
            QLabel#infoLabel {
                background: #333333;
                color: #ffffff;
                font-size: 12px;
                padding: 4px 10px;
                border: none;
            }
        """)
        status_bar = self.window.statusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.setStyleSheet("QStatusBar { background: #333333; }")
        status_bar.addWidget(self.info_label, 1)
        central = self.window.findChild(QWidget, "centralwidget")
        root_layout = central.layout()
        root_layout.removeWidget(self.info_label)
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

        self.thumbnail_scroll.setMinimumHeight(THUMBNAIL_SCROLL_MIN_HEIGHT)
        self.thumbnail_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_thumbnail_max_height()

        self.thumbnail_layout.setSpacing(THUMBNAIL_LAYOUT_SPACING)
        self.thumbnail_layout.setContentsMargins(*THUMBNAIL_LAYOUT_MARGINS)

        self.match_overlay = MatchOverlay(
            self.window.findChild(QWidget, "centralwidget"),
            anchor_widget=self.main_drop_zone
        )
        self.match_overlay.hide()

    def install_filters(self):
        self.filter = DropEventFilter(self)
        for widget in [self.zone_jpg, self.zone_raw, self.zone_dest, self.main_drop_zone, self.main_image, self.main_placeholder, self.info_label, self.path_bar, self.thumbnail_scroll.viewport()]:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self.filter)
        self.main_image_scroll.viewport().setAcceptDrops(True)
        self.main_image_scroll.viewport().installEventFilter(self.filter)
        self.filter.start_thumb_hover_tracking()

    def bind_events(self):
        self.btn_select_jpg.clicked.connect(self.select_jpg_dir)
        self.btn_select_raw.clicked.connect(self.select_raw_dir)
        self.btn_select_dest.clicked.connect(self.select_dest_dir)
        self.main_splitter.setSizes(MAIN_SPLITTER_INITIAL_SIZES)
        self.main_splitter.setHandleWidth(MAIN_SPLITTER_HANDLE_WIDTH)
        self.main_splitter.splitterMoved.connect(self.on_splitter_moved)

    def on_splitter_moved(self, pos, index):
        self.schedule_viewport_refresh()
        if self.match_overlay.isVisible():
            self.match_overlay._update_position()

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
            (QKeySequence(Qt.Key.Key_Tab), self.toggle_match_overlay),
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
        self.window.setStyleSheet(STYLE_SHEET)
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
        had_raw_before = bool(self.file_service.raw_dir)
        if self.file_service.set_jpg_dir(directory):
            self.lbl_jpg_path.setText(os.path.basename(directory))
            self.refresh_state()
            if had_raw_before:
                QTimer.singleShot(100, self.show_match_info)
        else:
            QMessageBox.warning(self.window, "提示", "路径无效，请检查后重试")

    def apply_raw_dir(self, directory: str):
        directory = directory if os.path.isdir(directory) else os.path.dirname(directory)
        had_jpg_before = bool(self.file_service.jpg_dir)
        if self.file_service.set_raw_dir(directory):
            self.lbl_raw_path.setText(os.path.basename(directory))
            self.raw_ext = self.file_service.raw_ext
            self.lbl_raw_ext.setText(self.raw_ext)
            if had_jpg_before:
                QTimer.singleShot(100, self.show_match_info)
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
        self.refresh_main_image()
        self.refresh_thumbnails()

    def update_info_bar(self):
        if not self.image_files:
            self.info_label.setText("请先导入JPG文件夹开始筛选")
            return
        current_file = self.image_files[self.current_idx]
        total = len(self.image_files)
        pass_count = self.file_service.pass_count
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

        size = max(THUMBNAIL_MIN_SIZE, min(THUMBNAIL_MAX_SIZE, effective_height - 20))
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
        if self.match_overlay.isVisible():
            self.match_overlay._update_position()
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
                is_current = idx == self.current_idx
                status = self.states.get(filename, 0)
                button = ThumbnailButton(self, idx, filename, status, is_current)
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
                    is_current = idx == self.current_idx
                    status = self.states.get(filename, 0)
                    new_status_name = button._status_name(status)
                    if button.property("status") != new_status_name:
                        button.setProperty("status", new_status_name)
                    button.set_current(is_current)
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

    def mark_pass_at(self, idx):
        result = self.file_service.mark_pass_at(idx)
        if result:
            self.states = self.file_service.states
            self.update_info_bar()
            self.refresh_thumbnails()

    def mark_reject(self):
        result = self.file_service.mark_reject()
        if result:
            self.current_idx = self.file_service.current_idx
            self.states = self.file_service.states
            self.update_view()

    def mark_reject_at(self, idx):
        result = self.file_service.mark_reject_at(idx)
        if result:
            self.states = self.file_service.states
            self.update_info_bar()
            self.refresh_thumbnails()

    def reset_state_at(self, idx):
        result = self.file_service.reset_state_at(idx)
        if result:
            self.states = self.file_service.states
            self.update_info_bar()
            self.refresh_thumbnails()

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
        if now - last_ts <= NEXT_CONFIRM_WINDOW and last_count == 1:
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

    def show_match_info(self):
        if not self.file_service.jpg_dir or not self.file_service.raw_dir:
            return
        try:
            match_info = self.file_service.check_match()
        except Exception as e:
            QMessageBox.warning(self.window, "匹配检查失败", str(e))
            return

        if not match_info.get("can_check"):
            return

        missing_raw = match_info["missing_raw"]
        if missing_raw:
            self.file_service.write_missing_report(missing_raw)

        try:
            raw_files_in_dir = os.listdir(self.file_service.raw_dir)
            raw_files = sorted([f for f in raw_files_in_dir if os.path.splitext(f)[1].lower() in FileService.RAW_EXTENSIONS_LOWER])
        except Exception:
            raw_files = []

        self.match_overlay.set_data(self.image_files, raw_files)
        self.match_overlay.show_overlay(duration_ms=3000)

    def toggle_match_overlay(self):
        if not self.file_service.jpg_dir or not self.file_service.raw_dir:
            return
        if self.match_overlay.isVisible():
            self.match_overlay.hide_overlay()
        else:
            try:
                raw_files_in_dir = os.listdir(self.file_service.raw_dir)
                raw_files = sorted([f for f in raw_files_in_dir if os.path.splitext(f)[1].lower() in FileService.RAW_EXTENSIONS_LOWER])
            except Exception:
                raw_files = []
            self.match_overlay.set_data(self.image_files, raw_files)
            self.match_overlay.show_overlay(duration_ms=None)

    def show_confirm_dialog(self):
        if not self.file_service.dest_dir:
            QMessageBox.warning(self.window, "提示", "尚未配置【导出目录】！请在界面最上方完成选择。")
            return
        if not self.file_service.jpg_dir:
            QMessageBox.warning(self.window, "提示", "尚未配置【JPG目录】！请在界面最上方完成选择。")
            return

        has_raw = bool(self.file_service.raw_dir)

        if has_raw:
            match_info = self.file_service.check_match()
            missing_raw = match_info.get("missing_raw", [])
            if missing_raw:
                ret = QMessageBox.warning(
                    self.window,
                    "存在缺失RAW文件",
                    f"检测到有 {len(missing_raw)} 张JPG在RAW目录中找不到对应的RAW文件！\n\n"
                    f"这些照片将无法导出对应的RAW文件。\n"
                    f"已在RAW目录生成【缺失RAW文件列表.txt】。\n\n"
                    f"是否继续导出？（仅导出能匹配到的RAW文件）",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return

            text = f"全部筛选完毕！即将匹配后缀为 [{self.raw_ext}] 的RAW原图。是否开始批量复制到导出目录？"
        else:
            text = "全部筛选完毕！即将导出选中的JPG照片到导出目录。是否开始复制？"

        ret = QMessageBox.question(self.window, "筛选完毕", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.execute_copy()

    def execute_copy(self):
        has_raw = bool(self.file_service.raw_dir)
        try:
            if has_raw:
                result = self.file_service.copy_raw_files(strict=True)
            else:
                result = self.file_service.copy_jpg_files()
        except Exception as exc:
            QMessageBox.critical(self.window, "复制失败", str(exc))
            return

        if result.get("success"):
            success_count = result.get("success_count", 0)
            mode = result.get("mode", "raw")

            if mode == "raw":
                missing_files = result.get("missing_files", []) or []
                message = f"复制完成！成功复制 RAW 文件：{success_count} 张"
                details = []
                if missing_files:
                    message += f"\n缺失/失败文件数量：{len(missing_files)} 张"
                    message += "\n已在RAW目录生成【缺失RAW文件列表.txt】"
                    details = missing_files
            else:
                failed_files = result.get("failed_files", []) or []
                message = f"导出完成！成功复制 JPG 文件：{success_count} 张"
                details = []
                if failed_files:
                    message += f"\n失败文件数量：{len(failed_files)} 张"
                    details = failed_files

            dialog = SummaryDialog(self.window, "导出汇总", message, details if details else None)
            dialog.exec()
            self.refresh_state()
        else:
            QMessageBox.critical(self.window, "复制失败", result.get("error", "复制失败"))

    def update_thumbnail_max_height(self):
        max_height = THUMBNAIL_MAX_SIZE + THUMBNAIL_TOP_MARGIN + THUMBNAIL_BOTTOM_MARGIN + THUMBNAIL_HOVER_PADDING
        self.thumbnail_scroll.setMaximumHeight(max_height)

    def run(self):
        self.window.show()
        original_resize = self.window.resizeEvent
        def custom_resize(event):
            self.update_thumbnail_max_height()
            if self.match_overlay.isVisible():
                self.match_overlay._update_position()
            original_resize(event)
        self.window.resizeEvent = custom_resize
        return self.app.exec()


def run():
    app = PhotoCullerApp()
    return app.run()
