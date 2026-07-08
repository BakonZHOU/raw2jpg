import os
import shutil
import json
import signal
import sys
import tkinter as tk
import time
import threading
from tkinter import filedialog
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from PIL import Image, ImageOps
import io
import hashlib

def correct_image_orientation(img):
    """根据EXIF信息自动校正图像方向 - 使用PIL内置方法"""
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        pass
    return img


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
        
        # 图片缓存目录
        self.cache_dir = os.path.join(os.path.dirname(__file__), 'image_cache')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # 自动关闭功能
        self.last_access_time = time.time()
        self.auto_shutdown_timeout = 10  # 10秒无访问自动关闭
        self.shutdown_flag = False
        self._start_auto_shutdown_checker()

        self.setup_routes()
    
    def _start_auto_shutdown_checker(self):
        """启动自动关闭检查器"""
        def checker():
            while not self.shutdown_flag:
                time.sleep(5)  # 每5秒检查一次
                if time.time() - self.last_access_time > self.auto_shutdown_timeout:
                    print(f"\n{self.auto_shutdown_timeout}秒无访问，自动关闭服务器...")
                    os.kill(os.getpid(), signal.SIGINT)
                    break
        
        threading.Thread(target=checker, daemon=True).start()
    
    def _update_access_time(self):
        """更新最后访问时间"""
        self.last_access_time = time.time()

    def setup_routes(self):
        @self.app.before_request
        def before_request():
            """每次请求前更新访问时间"""
            self._update_access_time()
        
        @self.app.route('/')
        def index():
            return send_from_directory('.', 'index.html')

        @self.app.route('/static/<path:path>')
        def serve_static(path):
            return send_from_directory('static', path)

        @self.app.route('/images/<path:filename>')
        def serve_image(filename):
            if not self.jpg_dir or not os.path.exists(self.jpg_dir):
                return "Image not found", 404
            
            file_path = os.path.join(self.jpg_dir, filename)
            if not os.path.exists(file_path):
                return "Image not found", 404
            
            # 获取尺寸参数
            width = request.args.get('w', type=int)
            height = request.args.get('h', type=int)
            
            if not width and not height:
                # 没有尺寸参数，直接返回原图
                return send_from_directory(self.jpg_dir, filename)
            
            # 生成缓存文件名
            file_hash = hashlib.md5(f"{filename}_{width}_{height}".encode()).hexdigest()
            cache_path = os.path.join(self.cache_dir, f"{file_hash}.jpg")
            
            # 检查缓存是否存在且未过期
            if os.path.exists(cache_path):
                cache_mtime = os.path.getmtime(cache_path)
                file_mtime = os.path.getmtime(file_path)
                if cache_mtime >= file_mtime:
                    return send_from_directory(self.cache_dir, f"{file_hash}.jpg")
            
            # 生成调整后的图片
            try:
                img = Image.open(file_path)
                img = correct_image_orientation(img)  # 校正图像方向
                
                # 计算调整后的尺寸
                original_width, original_height = img.size
                if width and height:
                    # 同时指定宽高，保持比例
                    ratio = min(width / original_width, height / original_height)
                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
                elif width:
                    # 只指定宽度
                    ratio = width / original_width
                    new_width = width
                    new_height = int(original_height * ratio)
                else:
                    # 只指定高度
                    ratio = height / original_height
                    new_width = int(original_width * ratio)
                    new_height = height
                
                # 调整图片大小
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # 保存到缓存
                img.save(cache_path, 'JPEG', quality=85, optimize=True)
                
                return send_from_directory(self.cache_dir, f"{file_hash}.jpg")
            except Exception as e:
                print(f"Error processing image: {e}")
                # 出错时返回原图
                return send_from_directory(self.jpg_dir, filename)

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
