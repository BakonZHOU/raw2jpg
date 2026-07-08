#!/usr/bin/env python3
"""
相机照片极速筛选工具 v2.2 (稳定版)
默认使用 Tkinter 模式，更稳定可靠
"""
import os
import sys
import subprocess
import time

# ========== 关键：PyInstaller 多进程修复 ==========
if sys.platform.startswith('win'):
    import multiprocessing
    multiprocessing.freeze_support()

# ========== 路径处理 ==========
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()

# ========== 配置 ==========
MODE = 'tkinter'  # 稳定版默认使用 Tkinter

def run_tkinter():
    """运行 Tkinter 版本（稳定）"""
    import tkinter as tk
    from tkinter_app.app import ImageCullerApp
    root = tk.Tk()
    app = ImageCullerApp(root)
    root.mainloop()

def kill_port_process_safe(port=5000):
    """安全清理端口（避免无限循环）"""
    try:
        result = subprocess.run(
            ['netstat', '-ano', '-p', 'TCP'],
            capture_output=True,
            text=True,
            encoding='gbk',
            errors='ignore'
        )
        current_pid = str(os.getpid())
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1]
                if pid and pid.isdigit() and pid != current_pid:
                    print(f"清理端口 {port}，PID: {pid}")
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    time.sleep(0.5)
    except Exception as e:
        print(f"清理端口时忽略错误: {e}")

def run_web():
    """运行 Web 版本"""
    kill_port_process_safe(5000)
    from web_app.backend import ImageCullerBackend
    import webbrowser
    import threading
    web_dir = os.path.join(BASE_PATH, 'web_app')
    os.chdir(web_dir)
    backend = ImageCullerBackend()
    
    def open_browser():
        time.sleep(1)
        webbrowser.open('http://127.0.0.1:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    print("Web 版本启动！")
    backend.run(host='127.0.0.1', port=5000, debug=False)

if __name__ == "__main__":
    print(f"启动 {MODE} 版本...")
    if MODE == 'tkinter':
        run_tkinter()
    elif MODE == 'web':
        run_web()
