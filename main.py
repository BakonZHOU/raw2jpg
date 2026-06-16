#!/usr/bin/env python3
"""
相机照片极速筛选工具 v2.2
支持两种启动模式：
- tkinter GUI 和 Web（网页版
修改 MODE 变量选择启动模式：
- 'tkinter' - 使用传统桌面应用
- 'web' - 使用Web网页版
"""
import os
import sys
import subprocess
import time

# ================== 配置启动模式 ==================
# 修改这里切换模式：'tkinter' 或 'web'
MODE = 'web'  # 默认使用Web模式，更美观


def run_tkinter():
    """运行tkinter版本"""
    import tkinter as tk
    from tkinter_app.app import ImageCullerApp

    root = tk.Tk()
    app = ImageCullerApp(root)
    root.mainloop()


def kill_port_process(port=5000):
    """杀死占用指定端口的进程（Windows）"""
    try:
        # 获取占用端口的进程PID
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
                if pid and pid.isdigit():
                    print(f"发现旧进程占用端口 {port}，正在终止 PID: {pid}")
                    subprocess.run(['taskkill', '/F', '/PID', pid], 
                                 capture_output=True)
                    time.sleep(0.5)  # 等待进程完全终止
    except Exception as e:
        print(f"清理端口时出错: {e}")

def run_web():
    """运行Web版本"""
    # 先清理占用5000端口的旧进程
    print("正在检查并清理旧进程...")
    kill_port_process(5000)
    
    # 确保Flask需要的依赖
    try:
        from flask import Flask
        from flask_cors import CORS
    except ImportError:
        print("正在安装Web版本需要的依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors"])
    
    from web_app.backend import ImageCullerBackend
    import webbrowser
    import threading

    # 切换到web_app目录
    web_dir = os.path.join(os.path.dirname(__file__), 'web_app')
    os.chdir(web_dir)

    # 启动Flask后端
    backend = ImageCullerBackend()
    
    # 在新线程中打开浏览器
    def open_browser():
        time.sleep(1)  # 等待服务器启动
        webbrowser.open('http://127.0.0.1:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("=" * 50)
    print("Web版本已启动！")
    print("请在浏览器中访问: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    try:
        backend.run(host='127.0.0.1', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    print(f"正在启动 {MODE} 版本...")
    if MODE == 'tkinter':
        run_tkinter()
    elif MODE == 'web':
        run_web()
    else:
        print(f"未知的模式: {MODE}，请选择 'tkinter' 或 'web'")
        sys.exit(1)
