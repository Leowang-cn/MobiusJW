import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab

class ImageFrame(tk.Frame):
    """
    可复用的图片粘贴/显示/预览/复制 Frame。
    支持：
    - 粘贴图片（剪贴板）
    - 显示图片
    - 双击放大预览（支持缩放、拖动、右键复制）
    - 尺寸显示
    """
    def __init__(self, master=None, width=600, height=900, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.configure(width=width, height=height)
        self.pack_propagate(False)
        # 操作行
        self.img_btn_row = tk.Frame(self)
        self.img_btn_row.pack(side=tk.TOP, anchor="w", pady=(10, 0), padx=10, fill=tk.X)
        self.img_size_var = tk.StringVar(value="尺寸: -")
        self.img_size_label = tk.Label(self.img_btn_row, textvariable=self.img_size_var, anchor="e", width=18)
        self.paste_img_btn = tk.Button(self.img_btn_row, text="粘贴图片", command=self.paste_image, width=10, height=1)
        self.paste_img_btn.pack(side=tk.LEFT)
        self.img_btn_row.grid_columnconfigure(1, weight=1)
        self.img_size_label.pack(side=tk.RIGHT, padx=(0, 5))
        # 图片显示区
        self.img_label = tk.Label(self, text="此处为图片粘贴区域", bg="#f0f0f0", width=70, height=35, relief=tk.RIDGE, anchor="n", justify="center")
        self.img_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=(10,10))
        self.img_label._original_image = None
        self.img_label.bind("<Double-1>", self.show_image_popup)

    def paste_image(self):
        try:
            image = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("错误", f"ImageGrab.grabclipboard() 调用异常: {str(e)}")
            return
        if image is not None:
            try:
                # 保留原图
                self.img_label._original_image = image.copy()
                # 适应显示区宽度（如600px），高度等比缩放
                display_w = self.img_label.winfo_width() or 600
                w, h = image.size
                scale = min(display_w / w, 1.0)
                if scale < 1.0:
                    try:
                        resample = Image.Resampling.LANCZOS
                    except AttributeError:
                        resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                    disp_img = image.resize((int(w*scale), int(h*scale)), resample)
                else:
                    disp_img = image
                tk_img = ImageTk.PhotoImage(disp_img)
                self.img_label.config(image=tk_img, text="", anchor="n")
                self.img_label.image = tk_img
                self.img_size_var.set(f"尺寸: {image.size[0]}x{image.size[1]}")
            except Exception as e:
                messagebox.showerror("错误", f"图片解析失败: {str(e)}")
        else:
            self.img_size_var.set("尺寸: -")
            messagebox.showinfo("提示", "剪贴板中没有图片或格式不支持")

    def show_image_popup(self, event=None):
        if not hasattr(self.img_label, 'image') or self.img_label._original_image is None:
            return
        popup = tk.Toplevel(self)
        popup.title("图片预览")
        popup.geometry("1200x900")
        popup.resizable(True, True)
        orig_img = self.img_label._original_image
        canvas = tk.Canvas(popup, bg="#222")
        canvas.pack(fill=tk.BOTH, expand=True)
        popup._tk_img = None
        drag_data = {'x': 0, 'y': 0, 'img_x': 0, 'img_y': 0}
        canvas._img_id = None
        # 计算初始缩放比例，使图片宽度适应弹层宽度
        popup.update_idletasks()
        popup_w = canvas.winfo_width() or 1200
        img_w, img_h = orig_img.size
        init_scale = min(popup_w / img_w, 1.0)
        scale_var = [init_scale]
        def render_img():
            w, h = orig_img.size
            scale = scale_var[0]
            new_w, new_h = int(w*scale), int(h*scale)
            try:
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                img = orig_img.resize((new_w, new_h), resample)
            except Exception:
                img = orig_img
            tk_img = ImageTk.PhotoImage(img)
            canvas.delete("all")
            c_w = canvas.winfo_width()
            c_h = canvas.winfo_height()
            x = drag_data.get('img_x', max((c_w-new_w)//2, 0))
            y = drag_data.get('img_y', max((c_h-new_h)//2, 0))
            canvas._img_id = canvas.create_image(x, y, anchor="nw", image=tk_img)
            popup._tk_img = tk_img
            popup._current_pil_img = img
        # 其余代码保持不变
        def close_on_double_click(event):
            popup.destroy()
        def show_auto_tip(msg, parent=None, duration=1000):
            tip = tk.Toplevel(parent or popup)
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.configure(bg="#f0f0f0")
            label = tk.Label(tip, text=msg, bg="#f0f0f0", fg="#222", font=("微软雅黑", 12))
            label.pack(ipadx=20, ipady=10)
            tip.update_idletasks()
            x = (tip.winfo_screenwidth() - tip.winfo_width()) // 2
            y = (tip.winfo_screenheight() - tip.winfo_height()) // 2
            tip.geometry(f"+{x}+{y}")
            tip.after(duration, tip.destroy)
        # 右键拖动选区并自动复制该区域到剪贴板
        canvas.bind("<Double-1>", close_on_double_click)

        # 选区相关变量
        selection = {'start': None, 'end': None, 'rect_id': None}

        def on_right_press(event):
            selection['start'] = (event.x, event.y)
            selection['end'] = (event.x, event.y)
            if selection['rect_id']:
                canvas.delete(selection['rect_id'])
            selection['rect_id'] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=2)

        def on_right_drag(event):
            if selection['rect_id']:
                selection['end'] = (event.x, event.y)
                canvas.coords(selection['rect_id'], selection['start'][0], selection['start'][1], event.x, event.y)

        def on_right_release(event):
            if not selection['rect_id']:
                return
            x0, y0 = selection['start']
            x1, y1 = selection['end']
            # 计算选区左上和右下
            x_min, y_min = min(x0, x1), min(y0, y1)
            x_max, y_max = max(x0, x1), max(y0, y1)
            # 获取当前图片在画布上的位置和缩放
            coords = canvas.coords(canvas._img_id)
            img_x, img_y = int(coords[0]), int(coords[1])
            scale = scale_var[0]
            # 计算选区在原图上的像素坐标
            sel_left = int((x_min - img_x) / scale)
            sel_top = int((y_min - img_y) / scale)
            sel_right = int((x_max - img_x) / scale)
            sel_bottom = int((y_max - img_y) / scale)
            # 裁剪区域合法性
            sel_left = max(0, sel_left)
            sel_top = max(0, sel_top)
            sel_right = min(orig_img.size[0], sel_right)
            sel_bottom = min(orig_img.size[1], sel_bottom)
            if sel_right > sel_left and sel_bottom > sel_top:
                region = orig_img.crop((sel_left, sel_top, sel_right, sel_bottom))
                # 复制到剪贴板（仅macOS）
                try:
                    import platform
                    if platform.system() != 'Darwin':
                        messagebox.showinfo("提示", "当前仅支持macOS图片复制")
                        return
                    from AppKit import NSPasteboard, NSPasteboardTypePNG, NSImage
                    from Foundation import NSData
                    import io
                    output = io.BytesIO()
                    region.save(output, format='PNG')
                    data = output.getvalue()
                    nsdata = NSData.dataWithBytes_length_(data, len(data))
                    image = NSImage.alloc().initWithData_(nsdata)
                    pb = NSPasteboard.generalPasteboard()
                    pb.clearContents()
                    pb.writeObjects_([image])
                    show_auto_tip("选区已复制到剪贴板！", parent=popup, duration=1200)
                except Exception as e:
                    messagebox.showerror("错误", f"复制图片到剪贴板失败: {str(e)}")
            # 删除选区框
            canvas.delete(selection['rect_id'])
            selection['rect_id'] = None

        # 绑定右键拖动事件
        canvas.bind('<ButtonPress-3>', on_right_press)
        canvas.bind('<B3-Motion>', on_right_drag)
        canvas.bind('<ButtonRelease-3>', on_right_release)
        def on_mousewheel(event):
            delta = event.delta
            if abs(delta) < 10:
                delta = delta * 120
            if delta > 0:
                scale_var[0] = min(scale_var[0]*1.15, 10.0)
            else:
                scale_var[0] = max(scale_var[0]/1.15, 0.1)
            drag_data['img_x'] = max((canvas.winfo_width()-int(orig_img.size[0]*scale_var[0]))//2, 0)
            drag_data['img_y'] = max((canvas.winfo_height()-int(orig_img.size[1]*scale_var[0]))//2, 0)
            render_img()
        def on_resize(event):
            render_img()
        def on_press(event):
            drag_data['x'] = event.x
            drag_data['y'] = event.y
        def on_drag(event):
            dx = event.x - drag_data['x']
            dy = event.y - drag_data['y']
            drag_data['x'] = event.x
            drag_data['y'] = event.y
            if canvas._img_id is not None:
                coords = canvas.coords(canvas._img_id)
                new_x = coords[0] + dx
                new_y = coords[1] + dy
                canvas.coords(canvas._img_id, new_x, new_y)
                drag_data['img_x'] = new_x
                drag_data['img_y'] = new_y
        canvas.bind("<Configure>", on_resize)
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: (scale_var.__setitem__(0, min(scale_var[0]*1.15, 10.0)), render_img()))
        canvas.bind_all("<Button-5>", lambda e: (scale_var.__setitem__(0, max(scale_var[0]/1.15, 0.1)), render_img()))
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        render_img()
