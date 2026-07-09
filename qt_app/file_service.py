"""文件服务模块 - 处理文件夹选择和文件操作"""
import os
import shutil


class FileService:
    # 常见 RAW 格式列表（优先级从高到低）
    RAW_EXTENSIONS = [
        '.CR3', '.CR2', '.CRW',
        '.NEF', '.NRW',
        '.ARW', '.SR2', '.SRF',
        '.RAF',
        '.RW2',
        '.ORF',
        '.PEF',
        '.DNG',
        '.X3F'
    ]

    def __init__(self):
        self.jpg_dir = ""
        self.raw_dir = ""
        self.dest_dir = ""
        self.raw_ext = ".CR2"
        self.image_files = []
        self.current_idx = 0
        self.states = {}
        self.last_browse_dir = os.path.expanduser("~")

    def validate_folder(self, folder_path):
        """验证文件夹路径是否有效"""
        if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return False
        return True

    def set_jpg_dir(self, folder_path):
        """设置JPG目录"""
        if not self.validate_folder(folder_path):
            return False
        self.jpg_dir = folder_path
        self.reload_jpg_images()
        return True

    def auto_detect_raw_ext(self):
        """自动检测RAW目录中的文件后缀"""
        if not self.raw_dir or not os.path.exists(self.raw_dir):
            return None

        try:
            files = os.listdir(self.raw_dir)
            ext_count = {}
            for f in files:
                ext = os.path.splitext(f)[1].upper()
                if ext in FileService.RAW_EXTENSIONS or ext.lower() in [e.lower() for e in FileService.RAW_EXTENSIONS]:
                    ext_count[ext] = ext_count.get(ext, 0) + 1

            if ext_count:
                sorted_exts = sorted(ext_count.items(), key=lambda x: x[1], reverse=True)
                return sorted_exts[0][0]
            return None
        except Exception as e:
            print(f"自动识别RAW后缀失败: {e}")
            return None

    def set_raw_dir(self, folder_path):
        """设置RAW目录并自动识别后缀"""
        if not self.validate_folder(folder_path):
            return False
        self.raw_dir = folder_path
        detected = self.auto_detect_raw_ext()
        if detected:
            self.raw_ext = detected
        return True

    def set_dest_dir(self, folder_path):
        """设置导出目录"""
        if not self.validate_folder(folder_path):
            return False
        self.dest_dir = folder_path
        return True

    def reload_jpg_images(self):
        """重新加载JPG图片"""
        try:
            files = os.listdir(self.jpg_dir)
            self.image_files = sorted([f for f in files if f.lower().endswith('.jpg')])
            self.current_idx = 0
            self.states = {f: 0 for f in self.image_files}
        except Exception as e:
            self.image_files = []
            self.current_idx = 0
            self.states = {}
            raise Exception(f"读取JPG目录失败: {e}")

    def copy_raw_files(self):
        """复制选中的RAW文件"""
        if not self.raw_dir or not self.dest_dir:
            raise Exception("路径缺失")

        pass_list = [f for f, state in self.states.items() if state == 1]
        if not pass_list:
            raise Exception("没有选中任何合格照片")

        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)

        success_count = 0
        missing_files = []

        try:
            raw_files_in_dir = os.listdir(self.raw_dir)
            raw_map = {f.lower(): f for f in raw_files_in_dir}
        except Exception as e:
            raise Exception(f"无法读取RAW目录: {e}")

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
                except Exception:
                    missing_files.append(real_raw_name)
            else:
                missing_files.append(base_name + self.raw_ext)

        return {
            "success": True,
            "success_count": success_count,
            "missing_files": missing_files
        }

    def get_current_state(self):
        """获取当前状态"""
        return {
            "files": self.image_files,
            "current_idx": self.current_idx,
            "states": self.states,
            "jpg_dir": self.jpg_dir,
            "raw_dir": self.raw_dir,
            "dest_dir": self.dest_dir,
            "raw_ext": self.raw_ext
        }

    def mark_pass(self):
        """标记当前照片为通过"""
        if not self.image_files:
            return False
        self.states[self.image_files[self.current_idx]] = 1
        if self.current_idx < len(self.image_files) - 1:
            self.current_idx += 1
        return True

    def mark_reject(self):
        """标记当前照片为淘汰"""
        if not self.image_files:
            return False
        self.states[self.image_files[self.current_idx]] = -1
        if self.current_idx < len(self.image_files) - 1:
            self.current_idx += 1
        return True

    def undo(self):
        """撤销上一个操作"""
        if not self.image_files:
            return False
        if self.states[self.image_files[self.current_idx]] == 0 and self.current_idx > 0:
            self.current_idx -= 1
            self.states[self.image_files[self.current_idx]] = 0
        else:
            self.states[self.image_files[self.current_idx]] = 0
        return True

    def go_prev(self):
        """上一张"""
        if not self.image_files or self.current_idx <= 0:
            return False
        self.current_idx -= 1
        return True

    def go_next(self):
        """下一张"""
        if not self.image_files or self.current_idx >= len(self.image_files) - 1:
            return False
        self.current_idx += 1
        return True

    def go_to(self, idx):
        """跳转到指定位置"""
        if 0 <= idx < len(self.image_files):
            self.current_idx = idx
            return True
        return False
