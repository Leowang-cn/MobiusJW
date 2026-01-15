# 主导航界面
# 这里将实现四个功能按钮，分别对应四个功能模块

import tkinter as tk
from tkinter import ttk  # 新增
import sys
import os
import json
import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import font
import feature1
import feature2
import feature3
import feature4
import feature5  # 新增导入
import item_management  # 新增导入
import TF_Question_Management  # 新增导入
import item_query  # 新增题目查询功能导入
import config  # 显式导入 config，确保打包工具识别

_import_server = None
_import_token = None

def _build_import_handler(main_root, expected_token):
    class ImportHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_cors_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self):
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def do_POST(self):
            if self.path != "/import":
                self._send_json(404, {"ok": False, "message": "Not Found"})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"ok": False, "message": "Invalid JSON"})
                return

            token = data.get("token")
            if expected_token and token != expected_token:
                self._send_json(403, {"ok": False, "message": "Invalid token"})
                return

            question_id = (data.get("id") or "").strip()
            image_base64 = data.get("imageBase64") or ""
            if not question_id or not image_base64:
                self._send_json(400, {"ok": False, "message": "Missing id or image"})
                return

            if image_base64.startswith("data:"):
                try:
                    image_base64 = image_base64.split(",", 1)[1]
                except Exception:
                    self._send_json(400, {"ok": False, "message": "Invalid image data"})
                    return

            try:
                image_bytes = base64.b64decode(image_base64)
            except Exception:
                self._send_json(400, {"ok": False, "message": "Invalid base64"})
                return

            def _import_on_ui_thread():
                try:
                    feature1.import_question_from_external(question_id, image_bytes)
                except Exception:
                    pass

            try:
                main_root.after(0, _import_on_ui_thread)
            except Exception:
                self._send_json(500, {"ok": False, "message": "Client not ready"})
                return

            self._send_json(200, {"ok": True, "message": "Imported"})

        def log_message(self, format, *args):
            return

    return ImportHandler

def start_import_server(main_root):
    global _import_server, _import_token
    if _import_server is not None:
        return _import_server

    token = config.get_or_create_token()
    _import_token = token
    handler_cls = _build_import_handler(main_root, token)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 27777), handler_cls)
    except Exception as e:
        print(f"导入服务启动失败: {e}")
        return None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _import_server = server
    print("导入服务已启动: http://127.0.0.1:27777/import")
    return server
def on_item_query():
    item_query.item_query()

def on_question_entry():
    feature1.question_entry()

def on_feature2():
    print("标签管理按钮被点击")
    feature2.tag_management()

def on_feature3():
    feature3.feature3()

def on_feature4():
    feature4.create_setting_window()

def on_feature5():
    feature5.cluster_management()

def on_item_management():
    item_management.item_management()

def on_TF_question_management():
    TF_Question_Management.TF_question_management()

root = tk.Tk()
root.title("MobiusJ")
root.geometry("1000x600+100+100")  # 设置窗口位置
root.minsize(800, 500)  # 设置最小尺寸

# 设置窗口图标
try:
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)
    
    icon_path = resource_path("assets/logo.ico")
    root.iconbitmap(icon_path)
except Exception as e:
    print(f"无法加载窗口图标: {e}")

feature1.set_main_root(root)
start_import_server(root)

# 创建顶部框架用于LOGO和标题
top_frame = tk.Frame(root)
top_frame.pack(pady=20)

# 加载并显示LOGO
try:
    # 修改：使用resource_path函数加载logo
    logo_path = resource_path("assets/logo.png")
    logo = tk.PhotoImage(file=logo_path)
    
    # 按比例缩放图片，宽度固定为50px
    original_width = logo.width()
    original_height = logo.height()
    scale_factor = 100 / original_width
    new_width = 100
    new_height = int(original_height * scale_factor)
    
    # 添加保护逻辑，防止subsample参数为0
    subsample_x = max(1, int(original_width / new_width))
    subsample_y = max(1, int(original_height / new_height))
    resized_logo = logo.subsample(subsample_x, subsample_y)
    
    logo_label = tk.Label(top_frame, image=resized_logo)
    logo_label.image = resized_logo  # 保持引用，防止被垃圾回收
    logo_label.pack(pady=20)
except Exception as e:
    print(f"无法加载LOGO: {e}")

# 显示标题和版本号
title_label = tk.Label(top_frame, 
                      text="MobiusJ",
                      font=font.Font(family="Microsoft YaHei", size=30),
                      fg="#2c3e50")
title_label.pack(pady=(0,10))  # 标题与版本号间距10px

version_label = tk.Label(top_frame,
                       text="V0.1.0",
                       font=font.Font(family="Microsoft YaHei", size=14),
                       fg="#666666")
version_label.pack(pady=(10,10))  # 版本号上下各10px间距

# 创建主功能按钮框架
frame = tk.Frame(root)
frame.pack(expand=True, pady=20)

# 美化按钮样式
style = ttk.Style()
style.theme_use('default')
style.configure(
    "TButton",
    font=("Microsoft YaHei", 13),
    foreground="#333333",
    background="#e6f0fa",
    borderwidth=0,
    focusthickness=3,
    focuscolor="#2980b9",
    padding=(12, 8),
    relief="flat"
)
style.map(
    "TButton",
    background=[("active", "#d0e6fa"), ("pressed", "#b3d1f7")],
    foreground=[("active", "#1a1a1a")]
)

def create_hover_effect(widget):
    def on_enter(e):
        widget.config(style="Hover.TButton")
    def on_leave(e):
        widget.config(style="TButton")
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)

style.configure(
    "Hover.TButton",
    font=("Microsoft YaHei", 13),
    foreground="#2980b9",
    background="#f5faff",
    borderwidth=0,
    padding=(12, 8),
    relief="flat"
)

# 按钮尺寸缩减至三分之二
button_width = int(12 * 2 / 3)
button_height = int(8 * 2 / 3)

button1 = ttk.Button(frame, text="题目录入", command=on_question_entry, style="TButton")
button1.grid(row=0, column=0, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button1)

button_item = ttk.Button(frame, text="题目管理", command=on_item_management, style="TButton")
button_item.grid(row=0, column=1, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button_item)

# 新增题目查询按钮，插入在题目管理和标签管理之间
button_query = ttk.Button(frame, text="题目查询", command=on_item_query, style="TButton")
button_query.grid(row=0, column=2, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button_query)

button2 = ttk.Button(frame, text="标签管理", command=on_feature2, style="TButton")
button2.grid(row=0, column=3, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button2)

button5 = ttk.Button(frame, text="题簇管理", command=on_feature5, style="TButton")
button5.grid(row=0, column=4, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button5)

button3 = ttk.Button(frame, text="学生管理", command=on_feature3, style="TButton")
button3.grid(row=0, column=5, padx=10, pady=10, ipadx=button_width, ipady=button_height)
create_hover_effect(button3)

# 第二行只放设置按钮
button_TF = ttk.Button(frame, text="判断题", command=on_TF_question_management, style="TButton")
button_TF.grid(row=1, column=0, padx=10, pady=10, ipadx=button_width, ipady=button_height, sticky="w")
create_hover_effect(button_TF)

button4 = ttk.Button(frame, text="设置", command=on_feature4, style="TButton")
button4.grid(row=1, column=1, padx=10, pady=10, ipadx=button_width, ipady=button_height, columnspan=4, sticky="w")
create_hover_effect(button4)

# 底部 token 展示与复制
token_frame = tk.Frame(root)
token_frame.pack(side=tk.BOTTOM, pady=(0, 10))

token_label_title = tk.Label(token_frame, text="插件Token：", font=font.Font(family="Microsoft YaHei", size=10))
token_label_title.pack(side=tk.LEFT)

token_value = _import_token or config.get_or_create_token()
token_var = tk.StringVar(value=token_value)
token_label = tk.Label(token_frame, textvariable=token_var, font=font.Font(family="Microsoft YaHei", size=10), fg="#2c3e50")
token_label.pack(side=tk.LEFT, padx=(0, 8))

def copy_token(event=None):
    try:
        root.clipboard_clear()
        root.clipboard_append(token_var.get())
        root.update()
    except Exception:
        pass

copy_token_label = tk.Label(
    token_frame,
    text="复制",
    fg="#1a73e8",
    cursor="hand2",
    font=font.Font(family="Microsoft YaHei", size=10, underline=True)
)
copy_token_label.pack(side=tk.LEFT)
copy_token_label.bind("<Button-1>", copy_token)

root.mainloop()