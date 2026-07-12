from __future__ import annotations

import os
import sys
from pathlib import Path


def get_base_path() -> str:
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_PATH = get_base_path()
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

UI_PATH = Path(__file__).resolve().parent / "ui" / "main_window.ui"

MAX_CACHE_SIZE = 80
THUMBNAIL_MAX_SIZE = 160
THUMBNAIL_TOP_MARGIN = 12
THUMBNAIL_BOTTOM_MARGIN = 8
THUMBNAIL_HOVER_PADDING = 12
THUMBNAIL_MIN_SIZE = 80
THUMBNAIL_LAYOUT_SPACING = 6
THUMBNAIL_LAYOUT_MARGINS = (8, 12, 8, 8)
THUMBNAIL_SCROLL_MIN_HEIGHT = 100

HOVER_SCALE_FACTOR = 1.07
HOVER_ANIM_DURATION = 140

VIEWPORT_REFRESH_INTERVAL = 50

NEXT_CONFIRM_WINDOW = 0.35

MAIN_SPLITTER_INITIAL_SIZES = [760, 220]
MAIN_SPLITTER_HANDLE_WIDTH = 5

APP_NAME = "相机照片极速筛选工具"

STYLE_SHEET = """
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
