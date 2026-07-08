"""图片处理工具模块"""
import os
import hashlib
from PIL import Image, ImageOps
from .config import CACHE_DIR


def correct_image_orientation(img):
    """根据EXIF信息自动校正图像方向 - 使用PIL内置方法"""
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        pass
    return img


def get_cached_image_path(filename, width, height):
    """生成缓存图片路径"""
    file_hash = hashlib.md5(f"{filename}_{width}_{height}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{file_hash}.jpg")


def resize_and_cache_image(file_path, width, height, cache_path):
    """调整图片大小并缓存"""
    img = Image.open(file_path)
    img = correct_image_orientation(img)

    original_width, original_height = img.size
    if width and height:
        ratio = min(width / original_width, height / original_height)
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)
    elif width:
        ratio = width / original_width
        new_width = width
        new_height = int(original_height * ratio)
    else:
        ratio = height / original_height
        new_width = int(original_width * ratio)
        new_height = height

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    img.save(cache_path, 'JPEG', quality=85, optimize=True)
