#!/usr/bin/env python3
"""
相机照片极速筛选工具 v2.2 (Web版)
"""
import os
import sys
import subprocess
import time
import webbrowser
import threading

if sys.platform.startswith('win'):
    import multiprocessing
    multiprocessing.freeze_support()


def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()


def kill_port_process(port=5000):
    try:
        current_pid = str(os.getpid())
        result = subprocess.run(
            ['netstat', '-ano', '-p', 'TCP'],
            capture_output=True,
            text=True,
            encoding='gbk',
            errors='ignore'
        )
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1]
                if pid and pid.isdigit() and pid != current_pid:
                    print(f"发现旧进程占用端口 {port}，正在终止 PID: {pid}")
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    time.sleep(0.5)
    except Exception as e:
        print(f"清理端口时出错: {e}")


def run_web():
    print("正在检查并清理旧进程...")
    kill_port_process(5000)

    from web_app.backend import ImageCullerBackend

    web_dir = os.path.join(BASE_PATH, 'web_app')
    os.chdir(web_dir)

    backend = ImageCullerBackend()

    def open_browser():
        time.sleep(1)
        webbrowser.open('http://127.0.0.1:5000')

    threading.Thread(target=open_browser, daemon=True).start()

    print("=" * 50)
    print("Web版本已启动！")
    print("请在浏览器中访问: http://127.0.0.1:5000")
    print("=" * 50)

    backend.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    run_web()