import os
import shutil
import json
import signal
import sys
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS


class ImageCullerBackend:
    def __init__(self):
        self.app = Flask(__name__, static_folder='static', template_folder='.')
        CORS(self.app)

        self.jpg_dir = ""
        self.raw_dir = ""
        self.dest_dir = ""
        self.raw_ext = ".CR3"

        self.image_files = []
        self.current_idx = 0
        self.states = {}

        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def index():
            return send_from_directory('.', 'index.html')

        @self.app.route('/static/<path:path>')
        def serve_static(path):
            return send_from_directory('static', path)

        @self.app.route('/images/<path:filename>')
        def serve_image(filename):
            if self.jpg_dir and os.path.exists(self.jpg_dir):
                return send_from_directory(self.jpg_dir, filename)
            return "Image not found", 404

        @self.app.route('/api/select_jpg_dir', methods=['POST'])
        def api_select_jpg_dir():
            data = request.json
            directory = data.get('directory', '')
            if directory and os.path.exists(directory):
                self.jpg_dir = directory
                self.reload_jpg_images()
                return jsonify({
                    'success': True,
                    'directory': os.path.basename(directory)
                })
            return jsonify({'success': False})

        @self.app.route('/api/set_raw_dir', methods=['POST'])
        def api_set_raw_dir():
            data = request.json
            directory = data.get('directory', '')
            if directory:
                self.raw_dir = directory
                return jsonify({
                    'success': True,
                    'directory': os.path.basename(directory)
                })
            return jsonify({'success': False})

        @self.app.route('/api/set_dest_dir', methods=['POST'])
        def api_set_dest_dir():
            data = request.json
            directory = data.get('directory', '')
            if directory:
                self.dest_dir = directory
                return jsonify({
                    'success': True,
                    'directory': os.path.basename(directory)
                })
            return jsonify({'success': False})

        @self.app.route('/api/set_raw_ext', methods=['POST'])
        def api_set_raw_ext():
            data = request.json
            self.raw_ext = data.get('ext', '.CR3')
            return jsonify({'success': True})

        @self.app.route('/api/get_images', methods=['GET'])
        def api_get_images():
            return jsonify({
                'files': self.image_files,
                'current_idx': self.current_idx,
                'states': self.states,
                'jpg_dir': self.jpg_dir,
                'raw_dir': self.raw_dir,
                'dest_dir': self.dest_dir
            })

        @self.app.route('/api/mark_pass', methods=['POST'])
        def api_mark_pass():
            if not self.image_files:
                return jsonify({'success': False})
            self.states[self.image_files[self.current_idx]] = 1
            if self.current_idx < len(self.image_files) - 1:
                self.current_idx += 1
            return jsonify({
                'success': True,
                'current_idx': self.current_idx,
                'states': self.states,
                'done': self.current_idx == len(self.image_files) - 1
            })

        @self.app.route('/api/mark_reject', methods=['POST'])
        def api_mark_reject():
            if not self.image_files:
                return jsonify({'success': False})
            self.states[self.image_files[self.current_idx]] = -1
            if self.current_idx < len(self.image_files) - 1:
                self.current_idx += 1
            return jsonify({
                'success': True,
                'current_idx': self.current_idx,
                'states': self.states,
                'done': self.current_idx == len(self.image_files) - 1
            })

        @self.app.route('/api/undo', methods=['POST'])
        def api_undo():
            if not self.image_files:
                return jsonify({'success': False})
            if self.states[self.image_files[self.current_idx]] == 0 and self.current_idx > 0:
                self.current_idx -= 1
                self.states[self.image_files[self.current_idx]] = 0
            else:
                self.states[self.image_files[self.current_idx]] = 0
            return jsonify({
                'success': True,
                'current_idx': self.current_idx,
                'states': self.states
            })

        @self.app.route('/api/go_prev', methods=['POST'])
        def api_go_prev():
            if not self.image_files or self.current_idx <= 0:
                return jsonify({'success': False})
            self.current_idx -= 1
            return jsonify({
                'success': True,
                'current_idx': self.current_idx
            })

        @self.app.route('/api/go_next', methods=['POST'])
        def api_go_next():
            if not self.image_files or self.current_idx >= len(self.image_files) - 1:
                return jsonify({'success': False})
            self.current_idx += 1
            return jsonify({
                'success': True,
                'current_idx': self.current_idx,
                'done': self.current_idx == len(self.image_files) - 1
            })

        @self.app.route('/api/go_to', methods=['POST'])
        def api_go_to():
            data = request.json
            idx = data.get('idx', 0)
            if 0 <= idx < len(self.image_files):
                self.current_idx = idx
                return jsonify({
                    'success': True,
                    'current_idx': self.current_idx
                })
            return jsonify({'success': False})

        @self.app.route('/api/copy_raw', methods=['POST'])
        def api_copy_raw():
            if not self.raw_dir or not self.dest_dir:
                return jsonify({'success': False, 'error': '路径缺失'})

            pass_list = [f for f, state in self.states.items() if state == 1]
            if not pass_list:
                return jsonify({'success': False, 'error': '没有选中任何合格照片'})

            if not os.path.exists(self.dest_dir):
                os.makedirs(self.dest_dir)

            success_count = 0
            missing_files = []

            try:
                raw_files_in_dir = os.listdir(self.raw_dir)
                raw_map = {f.lower(): f for f in raw_files_in_dir}
            except Exception as e:
                return jsonify({'success': False, 'error': f'无法读取RAW目录: {e}'})

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
                    except Exception as e:
                        missing_files.append(real_raw_name)
                else:
                    missing_files.append(base_name + self.raw_ext)

            return jsonify({
                'success': True,
                'success_count': success_count,
                'missing_files': missing_files
            })

        @self.app.route('/api/browse-folder', methods=['POST'])
        def api_browse_folder():
            """打开原生文件选择器选择文件夹"""
            try:
                # 创建隐藏的Tkinter窗口
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                
                folder_path = filedialog.askdirectory(
                    title="请选择文件夹",
                    initialdir=os.path.expanduser("~")
                )
                
                root.destroy()
                
                if folder_path:
                    return jsonify({
                        'success': True,
                        'folder_path': folder_path
                    })
                else:
                    return jsonify({'success': False, 'message': '未选择文件夹'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/shutdown', methods=['POST'])
        def api_shutdown():
            """安全关闭服务器"""
            def shutdown_server():
                print("\n收到关闭请求，正在停止服务器...")
                os.kill(os.getpid(), signal.SIGINT)
            
            import threading
            threading.Thread(target=shutdown_server, daemon=True).start()
            return jsonify({'success': True, 'message': '服务器正在关闭'})

    def reload_jpg_images(self):
        try:
            files = os.listdir(self.jpg_dir)
            self.image_files = sorted([f for f in files if f.lower().endswith('.jpg')])
            self.current_idx = 0
            self.states = {f: 0 for f in self.image_files}
        except Exception as e:
            print(f"读取JPG目录失败: {e}")

    def run(self, host='127.0.0.1', port=5000, debug=False):
        self.app.run(host=host, port=port, debug=debug)
