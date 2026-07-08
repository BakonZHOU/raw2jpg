"""配置模块"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'image_cache')

# 确保缓存目录存在
os.makedirs(CACHE_DIR, exist_ok=True)
