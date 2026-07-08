#!/usr/bin/env python3
"""
简单图标生成脚本 - 使用 Pillow 生成一个基本的占位图标
你可以替换成自己喜欢的图片
"""

from PIL import Image, ImageDraw, ImageFont
import os

def generate_app_icon():
    """生成一个简单的应用图标"""
    
    # 创建一个 256x256 的图像
    size = 256
    img = Image.new('RGB', (size, size), '#4A90D9')
    draw = ImageDraw.Draw(img)
    
    # 绘制相机图标
    # 相机机身
    body_margin = 60
    body_box = [
        body_margin, body_margin + 20,
        size - body_margin, size - body_margin
    ]
    draw.rectangle(body_box, fill='#2C3E50', outline='#34495E', width=3)
    
    # 镜头
    center = (size // 2, size // 2 + 10)
    lens_radius = 50
    draw.ellipse([
        center[0] - lens_radius, center[1] - lens_radius,
        center[0] + lens_radius, center[1] + lens_radius
    ], fill='#34495E', outline='#2C3E50', width=4)
    
    draw.ellipse([
        center[0] - lens_radius + 15, center[1] - lens_radius + 15,
        center[0] + lens_radius - 15, center[1] + lens_radius - 15
    ], fill='#5DADE2')
    
    # 闪光灯
    flash_box = [
        body_margin + 30, body_margin + 30,
        body_margin + 70, body_margin + 60
    ]
    draw.rectangle(flash_box, fill='#F39C12')
    
    # 保存为多个尺寸的 ico 文件
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save('app.ico', sizes=icon_sizes)
    
    print("✅ 图标文件 app.ico 已成功生成！")
    print("你可以用自己喜欢的图片替换这个图标文件")

if __name__ == "__main__":
    try:
        generate_app_icon()
    except ImportError:
        print("需要 Pillow 库，请运行: pip install Pillow")
    except Exception as e:
        print(f"生成图标时出错: {e}")
