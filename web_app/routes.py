"""API 路由模块"""
import os
import signal
import threading
from flask import jsonify, send_from_directory, request
from .file_service import FileService
from .image_utils import get_cached_image_path, resize_and_cache_image


def register_routes(app, file_service):
    @app.route('/')
    def index():
        return send_from_directory('.', 'index.html')

    @app.route('/static/<path:path>')
    def serve_static(path):
        return send_from_directory('static', path)

    @app.route('/images/<path:filename>')
    def serve_image(filename):
        if not file_service.jpg_dir or not os.path.exists(file_service.jpg_dir):
            return "Image not found", 404

        file_path = os.path.join(file_service.jpg_dir, filename)
        if not os.path.exists(file_path):
            return "Image not found", 404

        width = request.args.get('w', type=int)
        height = request.args.get('h', type=int)

        if not width and not height:
            return send_from_directory(file_service.jpg_dir, filename)

        cache_path = get_cached_image_path(filename, width, height)

        if os.path.exists(cache_path):
            cache_mtime = os.path.getmtime(cache_path)
            file_mtime = os.path.getmtime(file_path)
            if cache_mtime >= file_mtime:
                return send_from_directory(os.path.dirname(cache_path), os.path.basename(cache_path))

        try:
            resize_and_cache_image(file_path, width, height, cache_path)
            return send_from_directory(os.path.dirname(cache_path), os.path.basename(cache_path))
        except Exception as e:
            print(f"Error processing image: {e}")
            return send_from_directory(file_service.jpg_dir, filename)

    @app.route('/api/browse-folder', methods=['POST'])
    def api_browse_folder():
        try:
            data = request.json
            initial_path = data.get('initial_path') if data else None
            folder_path = file_service.browse_folder(initial_path)
            if folder_path:
                return jsonify({
                    'success': True,
                    'folder_path': folder_path
                })
            else:
                return jsonify({'success': False, 'message': '未选择文件夹'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/select-jpg-dir', methods=['POST'])
    def api_select_jpg_dir():
        data = request.json
        directory = data.get('directory', '')
        if file_service.set_jpg_dir(directory):
            return jsonify({
                'success': True,
                'directory': os.path.basename(directory)
            })
        return jsonify({'success': False})

    @app.route('/api/set-raw-dir', methods=['POST'])
    def api_set_raw_dir():
        data = request.json
        directory = data.get('directory', '')
        if file_service.set_raw_dir(directory):
            return jsonify({
                'success': True,
                'directory': os.path.basename(directory),
                'raw_ext': file_service.raw_ext
            })
        return jsonify({'success': False})

    @app.route('/api/set-dest-dir', methods=['POST'])
    def api_set_dest_dir():
        data = request.json
        directory = data.get('directory', '')
        if file_service.set_dest_dir(directory):
            return jsonify({
                'success': True,
                'directory': os.path.basename(directory)
            })
        return jsonify({'success': False})

    @app.route('/api/set-raw-ext', methods=['POST'])
    def api_set_raw_ext():
        data = request.json
        file_service.raw_ext = data.get('ext', '.CR3')
        return jsonify({'success': True})

    @app.route('/api/get-images', methods=['GET'])
    def api_get_images():
        return jsonify(file_service.get_current_state())

    @app.route('/api/mark-pass', methods=['POST'])
    def api_mark_pass():
        success = file_service.mark_pass()
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx,
            'states': file_service.states,
            'done': file_service.current_idx == len(file_service.image_files) - 1
        })

    @app.route('/api/mark-reject', methods=['POST'])
    def api_mark_reject():
        success = file_service.mark_reject()
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx,
            'states': file_service.states,
            'done': file_service.current_idx == len(file_service.image_files) - 1
        })

    @app.route('/api/undo', methods=['POST'])
    def api_undo():
        success = file_service.undo()
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx,
            'states': file_service.states
        })

    @app.route('/api/go-prev', methods=['POST'])
    def api_go_prev():
        success = file_service.go_prev()
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx
        })

    @app.route('/api/go-next', methods=['POST'])
    def api_go_next():
        success = file_service.go_next()
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx,
            'done': file_service.current_idx == len(file_service.image_files) - 1
        })

    @app.route('/api/go-to', methods=['POST'])
    def api_go_to():
        data = request.json
        idx = data.get('idx', 0)
        success = file_service.go_to(idx)
        return jsonify({
            'success': success,
            'current_idx': file_service.current_idx
        })

    @app.route('/api/copy-raw', methods=['POST'])
    def api_copy_raw():
        try:
            result = file_service.copy_raw_files()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/shutdown', methods=['POST'])
    def api_shutdown():
        def shutdown_server():
            print("\n收到关闭请求，正在停止服务器...")
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=shutdown_server, daemon=True).start()
        return jsonify({'success': True, 'message': '服务器正在关闭'})
