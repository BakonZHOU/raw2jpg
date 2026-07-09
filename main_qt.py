#!/usr/bin/env python3
"""
相机照片极速筛选工具 Qt 版启动入口
"""
import os
import sys

if sys.platform.startswith('win'):
    import multiprocessing
    multiprocessing.freeze_support()


def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)


from qt_app.app import run


if __name__ == "__main__":
    raise SystemExit(run())
