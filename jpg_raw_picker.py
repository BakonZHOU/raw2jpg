import os
import shutil
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk  # 引入ttk组件以使用下拉选择框
from PIL import Image, ImageTk, ImageFile

# 允许截断的图片加载
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ImageCullerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("相机照片极速筛选工具 v2.2")
        self.root.geometry("1250x850")
        self.root.minsize(900, 600)

        # 路径与格式变量
        self.jpg_dir = ""
        self.raw_dir = ""
        self.dest_dir = ""
        self.raw_ext = ".CR2"

        # 数据状态
        self.image_files = []      
        self.current_idx = 0       
        self.states = {}           
        self.thumbnails_cache = {} 

        # 核心UI设置
        self.thumb_size = 100      
        
        self.build_ui()
        self.bind_keys()
        self.update_info_bar()

    def build_ui(self):
        """UI布局：从上至下分为 路径配置栏(单行且无焦点残留)、信息与工具栏、大图、缩略图"""
        
        # ================= 1. 顶部路径配置栏 (下拉框替换输入框) =================
        self.path_frame = tk.Frame(self.root, bg="#2d2d2d", padx=10, pady=8)
        self.path_frame.pack(side=tk.TOP, fill=tk.X)

        # JPG源目录
        tk.Button(self.path_frame, text="1.导入JPG目录", command=self.select_jpg_dir, width=11, bg="#444", fg="white", bd=1).grid(row=0, column=0, padx=(2, 2))
        self.lbl_jpg_path = tk.Label(self.path_frame, text="[未选择]", anchor="w", fg="#ffb300", bg="#2d2d2d", width=15)
        self.lbl_jpg_path.grid(row=0, column=1, padx=(2, 10), sticky="w")

        # RAW源目录
        tk.Button(self.path_frame, text="2.导入RAW目录", command=self.select_raw_dir, width=11, bg="#444", fg="white", bd=1).grid(row=0, column=2, padx=(2, 2))
        self.lbl_raw_path = tk.Label(self.path_frame, text="[未选择]", anchor="w", fg="#ffb300", bg="#2d2d2d", width=15)
        self.lbl_raw_path.grid(row=0, column=3, padx=(2, 10), sticky="w")

        # 导出目录
        tk.Button(self.path_frame, text="3.确定导出目录", command=self.select_dest_dir, width=11, bg="#444", fg="white", bd=1).grid(row=0, column=4, padx=(2, 2))
        self.lbl_dest_path = tk.Label(self.path_frame, text="[未选择]", anchor="w", fg="#ffb300", bg="#2d2d2d", width=15)
        self.lbl_dest_path.grid(row=0, column=5, padx=(2, 10), sticky="w")

        # RAW格式选择 (改成只读下拉框)
        tk.Label(self.path_frame, text="RAW格式:", fg="white", bg="#2d2d2d").grid(row=0, column=6, padx=(5, 2), sticky="e")
        
        # 常见格式列表
        ext_options = [
            ".CR3 (佳能)", ".CR2 (佳能)", ".ARW (索尼)", 
            ".NEF (尼康)", ".RAF (富士)", ".RW2 (松下)", ".DNG (通用)"
        ]
        self.combo_ext = ttk.Combobox(self.path_frame, values=ext_options, width=12, state="readonly")
        self.combo_ext.current(0)  # 默认选第一个 .CR3
        self.combo_ext.grid(row=0, column=7, padx=(0, 2), sticky="w")
        
        # 当下拉框被选中时，自动剥离焦点，恢复键盘快捷键
        self.combo_ext.bind("<<ComboboxSelected>>", self.on_combo_changed)

        # 让配置栏各组件紧凑靠左
        self.path_frame.columnconfigure(8, weight=1)

        # ================= 2. 操控与信息栏 =================
        self.top_frame = tk.Frame(self.root, bg="#333", pady=10)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.info_label = tk.Label(self.top_frame, text="请先导入JPG文件夹开始筛选", fg="white", bg="#333", font=("Arial", 12, "bold"))
        self.info_label.pack(side=tk.TOP, pady=5)

        self.btn_frame = tk.Frame(self.top_frame, bg="#333")
        self.btn_frame.pack(side=tk.TOP)

        tk.Button(self.btn_frame, text="← 上一张 (Left)", command=self.go_prev, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="你过关 (Space)", command=self.mark_pass, bg="#4CAF50", fg="white", width=15, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="X 淘汰 (Del)", command=self.mark_reject, bg="#F44336", fg="white", width=15, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="撤销 (Ctrl+Z)", command=self.undo_action, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="下一张 → (Right)", command=self.go_next, width=15).pack(side=tk.LEFT, padx=5)

        # ================= 3. 中部大图预览 =================
        self.mid_frame = tk.Frame(self.root, bg="black")
        self.mid_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.img_label = tk.Label(self.mid_frame, bg="black")
        self.img_label.pack(fill=tk.BOTH, expand=True)
        self.mid_frame.bind("<Configure>", self.on_resize) 

        # ================= 4. 底部缩略图栏 =================
        self.bot_frame = tk.Frame(self.root, bg="#222", height=120)
        self.bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.bot_frame.pack_propagate(False)

        self.thumb_canvas = tk.Canvas(self.bot_frame, bg="#222", highlightthickness=0, height=120)
        self.thumb_canvas.pack(fill=tk.BOTH, expand=True)

    def bind_keys(self):
        """快捷键绑定"""
        self.root.bind('<space>', lambda e: self.mark_pass())
        self.root.bind('<Return>', lambda e: self.mark_pass())
        self.root.bind('<Delete>', lambda e: self.mark_reject())
        self.root.bind('<BackSpace>', lambda e: self.mark_reject())
        self.root.bind('<Left>', lambda e: self.go_prev())
        self.root.bind('<Right>', lambda e: self.go_next())
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-Z>', lambda e: self.undo_action())

    def on_combo_changed(self, event):
        """核心机制：选择完后缀后，强制把焦点还给大窗口，确保方向键和空格立刻可用"""
        self.root.focus_set()

    # ================= 文件夹导入与重载逻辑 =================
    def select_jpg_dir(self):
        directory = filedialog.askdirectory(title="选择 JPG 预览图文件夹")
        if directory:
            self.jpg_dir = directory
            self.lbl_jpg_path.config(text=os.path.basename(directory))
            self.reload_jpg_images()
        self.root.focus_set()

    def select_raw_dir(self):
        directory = filedialog.askdirectory(title="选择 RAW 原图文件夹")
        if directory:
            self.raw_dir = directory
            self.lbl_raw_path.config(text=os.path.basename(directory))
        self.root.focus_set()

    def select_dest_dir(self):
        directory = filedialog.askdirectory(title="选择 RAW 导出目的地文件夹")
        if directory:
            self.dest_dir = directory
            self.lbl_dest_path.config(text=os.path.basename(directory))
        self.root.focus_set()

    def reload_jpg_images(self):
        try:
            files = os.listdir(self.jpg_dir)
            self.image_files = sorted([f for f in files if f.lower().endswith('.jpg')])
            
            self.current_idx = 0
            self.states = {f: 0 for f in self.image_files}
            self.thumbnails_cache.clear() 
            
            if self.image_files:
                self.update_view()
            else:
                self.img_label.config(image='', text="该目录下没有找到JPG图片", fg="white")
                self.thumb_canvas.delete("all")
                self.update_info_bar()
                messagebox.showwarning("空目录", "选择的文件夹内没有找到任何 .jpg/.JPG 文件！")
        except Exception as e:
            messagebox.showerror("读取错误", f"读取JPG目录失败：\n{e}")

    # ================= 核心交互回调 =================
    def mark_pass(self):
        if not self.image_files: return
        self.states[self.image_files[self.current_idx]] = 1
        self.go_next()

    def mark_reject(self):
        if not self.image_files: return
        self.states[self.image_files[self.current_idx]] = -1
        self.go_next()

    def undo_action(self):
        if not self.image_files: return
        if self.states[self.image_files[self.current_idx]] == 0 and self.current_idx > 0:
            self.current_idx -= 1
            self.states[self.image_files[self.current_idx]] = 0
        else:
            self.states[self.image_files[self.current_idx]] = 0
        self.update_view()

    def go_prev(self):
        if not self.image_files: return
        if self.current_idx > 0:
            self.current_idx -= 1
            self.update_view()
        else:
            messagebox.showinfo("提示", "已经是第一张了！")

    def go_next(self):
        if not self.image_files: return
        if self.current_idx < len(self.image_files) - 1:
            self.current_idx += 1
            self.update_view()
        else:
            self.update_view() 
            self.prompt_copy_raw()

    def update_view(self):
        self.update_info_bar()
        self.show_main_image()
        self.draw_thumbnails()

    def update_info_bar(self):
        if not self.image_files:
            self.info_label.config(text="请点击上方按钮导入JPG文件夹开始筛选")
            return
        current_file = self.image_files[self.current_idx]
        total = len(self.image_files)
        pass_count = sum(1 for v in self.states.values() if v == 1)
        self.info_label.config(text=f"{current_file}  |  当前第 {self.current_idx + 1} 张 / 总共 {total} 张  |  已入选：{pass_count} 张")

    # ================= 极速看图与渲染 =================
    def on_resize(self, event):
        if hasattr(self, '_resize_job'):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(150, self.show_main_image)

    def show_main_image(self):
        if not self.image_files: return
        file_path = os.path.join(self.jpg_dir, self.image_files[self.current_idx])
        try:
            canvas_w = self.mid_frame.winfo_width()
            canvas_h = self.mid_frame.winfo_height()
            if canvas_w < 10 or canvas_h < 10: canvas_w, canvas_h = 800, 500

            img = Image.open(file_path)
            img.draft('RGB', (canvas_w, canvas_h)) 
            img.thumbnail((canvas_w, canvas_h), Image.Resampling.BILINEAR)
            
            self.main_photo = ImageTk.PhotoImage(img)
            self.img_label.config(image=self.main_photo)
        except Exception as e:
            self.img_label.config(image='', text=f"图片加载失败\n{e}", fg="red")

    def draw_thumbnails(self):
        self.thumb_canvas.delete("all")
        if not self.image_files: return
        
        canvas_w = self.bot_frame.winfo_width()
        if canvas_w < 10: canvas_w = 1200
        
        thumb_spacing = self.thumb_size + 10
        visible_count = canvas_w // thumb_spacing
        half_visible = visible_count // 2
        
        start_idx = max(0, self.current_idx - half_visible)
        end_idx = min(len(self.image_files), start_idx + visible_count)
        
        if end_idx - start_idx < visible_count and start_idx > 0:
            start_idx = max(0, end_idx - visible_count)

        x_offset = (canvas_w - (end_idx - start_idx) * thumb_spacing) // 2

        for i in range(start_idx, end_idx):
            filename = self.image_files[i]
            file_path = os.path.join(self.jpg_dir, filename)
            
            if filename not in self.thumbnails_cache:
                try:
                    t_img = Image.open(file_path)
                    t_img.draft('RGB', (self.thumb_size, self.thumb_size))
                    t_img.thumbnail((self.thumb_size, self.thumb_size), Image.Resampling.NEAREST)
                    self.thumbnails_cache[filename] = ImageTk.PhotoImage(t_img)
                except: pass
            
            if filename in self.thumbnails_cache:
                self.thumb_canvas.create_image(x_offset + self.thumb_size//2, 60, image=self.thumbnails_cache[filename])
            
            state = self.states[filename]
            if state == 1: 
                self.thumb_canvas.create_rectangle(x_offset, 10, x_offset + self.thumb_size, 15, fill="#4CAF50", outline="")
            elif state == -1: 
                self.thumb_canvas.create_rectangle(x_offset, 10, x_offset + self.thumb_size, 15, fill="#F44336", outline="")

            if i == self.current_idx:
                self.thumb_canvas.create_rectangle(x_offset-2, 10, x_offset + self.thumb_size+2, 110, outline="#00BCD4", width=3)
            x_offset += thumb_spacing

    # ================= 导出 RAW 逻辑 =================
    def prompt_copy_raw(self):
        # 从下拉选择文本中提取真正的后缀（如将 ".CR3 (佳能)" 截取为 ".CR3"）
        selected_text = self.combo_ext.get()
        self.raw_ext = selected_text.split(" ")[0].strip()

        if not self.raw_dir or not self.dest_dir:
            messagebox.showwarning("路径缺失", "尚未配置【RAW目录】或【导出目录】！请在界面最上方完成选择。")
            return

        ans = messagebox.askyesno("筛选完毕", f"全部筛选完毕！\n即将匹配后辍为 [{self.raw_ext}] 的原图。\n是否开始批量复制到导出目录？")
        if ans:
            self.execute_raw_copy()

    def execute_raw_copy(self):
        pass_list = [f for f, state in self.states.items() if state == 1]
        if not pass_list:
            messagebox.showinfo("提示", "没有选中任何合格照片。")
            return

        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)

        success_count = 0
        missing_files = []

        try:
            raw_files_in_dir = os.listdir(self.raw_dir)
            raw_map = {f.lower(): f for f in raw_files_in_dir}
        except Exception as e:
            messagebox.showerror("错误", f"无法读取RAW目录：\n{e}")
            return

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

        msg = f"🎉 复制完成！\n成功复制 RAW 文件：{success_count} 张\n"
        if missing_files:
            msg += f"缺失/失败文件数量：{len(missing_files)} 张\n（具体名单已在控制台打印输出）"
            print("--- 以下为未找到的RAW文件名单 ---")
            for m in missing_files: print(m)
        
        messagebox.showinfo("复制汇总", msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageCullerApp(root)
    root.mainloop()