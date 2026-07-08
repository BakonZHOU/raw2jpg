"""主后端模块"""
import logging
import os
from flask import Flask
from flask_cors import CORS

from .config import CACHE_DIR
from .file_service import FileService
from .routes import register_routes

# 关闭Flask开发服务器警告
logging.getLogger('werkzeug').setLevel(logging.ERROR)


class ImageCullerBackend:
    def __init__(self):
        self.app = Flask(__name__, static_folder='static', template_folder='.')
        CORS(self.app)
        self.file_service = FileService()
        register_routes(self.app, self.file_service)

    def run(self, host='127.0.0.1', port=5000, debug=False):
        self.app.run(host=host, port=port, debug=debug)
