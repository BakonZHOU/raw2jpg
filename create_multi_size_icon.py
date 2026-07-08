#!/usr/bin/env python3
"""
创建包含多种尺寸的 Windows 标准 ico 文件
确保在所有视图模式下都能正常显示
智能处理非正方形图片，保持比例不变形
"""

from PIL import Image
import os

def create_multisize_icon(input_image_path, output_icon_path='app.ico'):
    """
    从图片创建包含多种尺寸的 ico 文件
    
    Args:
        input_image_path: 输入图片路径（可以是你已有的 app.ico 或其他图片）
        output_icon_path: 输出的 ico 文件路径
    """
    
    # Windows 标准图标尺寸 - 包含更小的尺寸避免被默认图标覆盖
    standard_sizes = [
        (16, 16),    # 详细信息视图
        (24, 24),    # 中等图标
        (32, 32),    # 普通视图
        (40, 40),
        (48, 48),    # 大图标视图
        (64, 64),
        (72, 72),
        (80, 80),
        (96, 96),
        (128, 128),
        (256, 256),
        (512, 512),  # 高 DPI 支持
    ]
    
    try:
        # 打开原始图片
        img = Image.open(input_image_path)
        print(f"原始图片尺寸: {img.width}x{img.height}")
        
        # 如果是 RGBA 模式，保留透明度
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 首先把原图处理成正方形画布（保持比例，透明背景）
        original_ratio = img.width / img.height
        
        # 创建一个足够大的正方形画布
        max_size = max(img.width, img.height)
        canvas = Image.new('RGBA', (max_size, max_size), (0, 0, 0, 0))
        
        # 计算居中位置
        paste_x = (max_size - img.width) // 2
        paste_y = (max_size - img.height) // 2
        canvas.paste(img, (paste_x, paste_y))
        
        # 现在用 Pillow 直接从正方形原图生成包含所有标准尺寸的 ico
        # Pillow 会自动处理所有尺寸的缩放
        canvas.save(
            output_icon_path,
            format='ICO',
            sizes=standard_sizes
        )
        
        # 检查文件大小
        file_size = os.path.getsize(output_icon_path)
        print(f"\n✅ 成功创建多尺寸图标: {output_icon_path}")
        print(f"文件大小: {file_size / 1024:.1f} KB")
        print(f"包含尺寸: {', '.join(f'{w}x{h}' for w, h in standard_sizes)}")
        print("\n现在重新打包 exe，图标就能在所有视图模式下正常显示了！")
        
    except FileNotFoundError:
        print(f"❌ 找不到文件: {input_image_path}")
        print("请确保你的图片文件存在！")
    except Exception as e:
        print(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 优先检查是否有原图
    input_file = None
    
    # 先找常见的原图文件
    possible_files = ['original.png', 'original.jpg', 'original.jpeg', 'original.ico']
    for f in possible_files:
        if os.path.exists(f):
            input_file = f
            break
    
    if not input_file:
        print("未找到 original.png/jpg/ico，请先把你的原图重命名为 original.png 或 original.jpg")
        print("然后再运行此脚本")
        print("\n或者你也可以直接把原图放在项目目录，然后修改脚本中的输入路径")
    else:
        print(f"发现原图: {input_file}")
        print("正在生成多尺寸图标...")
        create_multisize_icon(input_file, 'app.ico')
