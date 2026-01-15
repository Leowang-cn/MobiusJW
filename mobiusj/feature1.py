import tkinter as tk
from tkinter import messagebox, simpledialog, Toplevel, ttk
import json
import os
import sys
import subprocess
import sqlite3
import io
import config

tags_data = []
items_data = {}
modules_data = []
selected_tags = []

_main_root = None
_question_window = None
_question_id_entry = None
_img_frame = None
_query_entry = None

def set_main_root(root):
    global _main_root
    _main_root = root

def _register_question_entry_widgets(window, question_id_entry, img_frame, query_entry):
    global _question_window, _question_id_entry, _img_frame, _query_entry
    _question_window = window
    _question_id_entry = question_id_entry
    _img_frame = img_frame
    _query_entry = query_entry

    def _on_close():
        global _question_window, _question_id_entry, _img_frame, _query_entry
        _question_window = None
        _question_id_entry = None
        _img_frame = None
        _query_entry = None
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", _on_close)

def ensure_question_entry_window():
    global _question_window
    if _question_window is None:
        question_entry()
    else:
        try:
            if not _question_window.winfo_exists():
                _question_window = None
                question_entry()
            else:
                _question_window.lift()
                _question_window.focus_force()
        except Exception:
            _question_window = None
            question_entry()

def import_question_from_external(question_id, image_bytes):
    ensure_question_entry_window()
    if _question_window is None:
        return

    try:
        if _question_id_entry is not None:
            _question_id_entry.delete(0, tk.END)
            _question_id_entry.insert(0, question_id)
            _question_id_entry.icursor(tk.END)
    except Exception:
        pass

    try:
        from PIL import Image, ImageTk
        img = Image.open(io.BytesIO(image_bytes))
        if _img_frame is not None:
            max_w, max_h = 560, 800
            w, h = img.size
            scale = min(max_w / w, max_h / h, 1)
            if scale < 1:
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                img_disp = img.resize((int(w * scale), int(h * scale)), resample)
            else:
                img_disp = img
            tk_img = ImageTk.PhotoImage(img_disp)
            _img_frame.img_label.config(image=tk_img, text="")
            _img_frame.img_label.image = tk_img
            _img_frame.img_label._original_image = img.copy()
            _img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
    except Exception:
        if _img_frame is not None:
            _img_frame.img_label.config(image="", text="图片加载失败")
            _img_frame.img_label.image = None
            _img_frame.img_label._original_image = None
            _img_frame.img_size_var.set("尺寸: -")

    try:
        if _query_entry is not None:
            _query_entry.focus_set()
    except Exception:
        pass

def get_db_path():
    settings = config.load_settings()
    data_path = settings.get("data_path", "")
    if not data_path:
        messagebox.showerror("错误", "未设置数据路径，请在设置中配置数据路径")
        return None
    db_path = os.path.join(data_path, "mobius_data.sqlite3")
    if not os.path.exists(db_path):
        messagebox.showerror("错误", f"数据库文件 {db_path} 不存在")
        return None
    return db_path

def load_tags_data():
    global tags_data
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            SELECT tag_id, module_id, tag_name, tag_intro
            FROM tags
        """)
        tags_data = []
        for row in c.fetchall():
            tag_id, module_id, tag_name, tag_intro = row
            # 查询题量
            c.execute("SELECT COUNT(*) FROM item_tag_relations WHERE tag_id=?", (tag_id,))
            item_count = c.fetchone()[0]
            tags_data.append({
                "tag_id": tag_id,
                "module_id": module_id,
                "tag_name": tag_name,
                "tag_intro": tag_intro,
                "item_count": item_count,
                "tag_level": 1
            })
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取标签数据时出错: {str(e)}")

def save_tags_data():
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 清空 tags 表并重新插入
        c.execute("DELETE FROM tags")
        for tag in tags_data:
            c.execute("""
                INSERT INTO tags (tag_id, module_id, tag_name, tag_intro)
                VALUES (?, ?, ?, ?)
            """, (tag['tag_id'], tag['module_id'], tag['tag_name'], tag['tag_intro']))
        conn.commit()
        conn.close()
        messagebox.showinfo("成功", "标签数据已保存")
    except Exception as e:
        messagebox.showerror("错误", f"保存标签数据时出错: {str(e)}")

def load_items_data():
    global items_data
    db_path = get_db_path()
    if not db_path:
        return
    print(f"[调试] 数据库文件路径: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items")
        items_count = c.fetchone()[0]
        print(f"[调试] items表数据数量: {items_count}")
        items_data = {}
        c.execute("SELECT item_id, item_level FROM items")
        rows = c.fetchall()
        print(f"[调试] 读取表: items, 数据: {rows}")
        for item_id, tag_level in rows:
            c.execute("SELECT tag_id FROM item_tag_relations WHERE item_id=?", (item_id,))
            tag_ids = [row[0] for row in c.fetchall()]
            items_data[item_id] = {
                'tags': tag_ids,
                'tag_level': tag_level
            }
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取题目数据时出错: {str(e)}")

def save_items_data():
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 清空 items 和 item_tag_relations 表并重新插入
        c.execute("DELETE FROM items")
        c.execute("DELETE FROM item_tag_relations")
        for question_id, data in items_data.items():
            c.execute("""
                INSERT INTO items (item_id, item_level)
                VALUES (?, ?)
            """, (question_id, data['tag_level']))
            for tag_id in data['tags']:
                c.execute("""
                    INSERT INTO item_tag_relations (item_id, tag_id)
                    VALUES (?, ?)
                """, (question_id, tag_id))
        conn.commit()
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"保存题目数据时出错: {str(e)}")

def load_modules_data():
    global modules_data
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 修改：查询 module_type
        c.execute("SELECT module_id, module_name, module_type FROM modules")
        modules_data = []
        for module_id, module_name, module_type in c.fetchall():
            modules_data.append({
                "module_id": module_id,
                "module_name": module_name,
                "module_type": module_type
            })
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取模块数据时出错: {str(e)}")

def question_entry():
    load_tags_data()
    load_items_data()
    load_modules_data()

    root = tk.Toplevel()
    root.title("题目录入")
    root.geometry("1800x930")  # 总宽度变为1800
    root.resizable(width=False, height=False)

    # 难度下拉固定为1-5
    difficulty_options = ["1", "2", "3", "4", "5"]
    difficulty_var = tk.StringVar(master=root, value=difficulty_options[0])
    difficulty_select = None

    def validate_question_id():
        question_id = question_id_entry.get().strip()
        if not question_id:
            messagebox.showwarning("警告", "题目ID不能为空")
            return False

        if not all(c.isalnum() or c == '-' for c in question_id):
            messagebox.showwarning("警告", "题目ID格式不正确，请检查。")
            return False

        return True

    def set_difficulty_value(value):
        if value is None:
            return
        value = str(value)
        if difficulty_select is not None:
            existing_values = list(difficulty_select['values'])
            if value not in existing_values:
                existing_values.append(value)
                difficulty_select['values'] = tuple(existing_values)
        difficulty_var.set(value)

    def handle_paste():
        try:
            question_id_entry.delete(0, tk.END)
            question_id_entry.insert(0, root.clipboard_get())
            question_id_entry.icursor(tk.END)
            question_id_entry.focus_set()
        except tk.TclError:
            messagebox.showerror("错误", "无法从剪贴板获取内容")

    def handle_question_id_enter():
        question_id = question_id_entry.get().strip()
        print("输入题目ID:", question_id)
        print("items_data keys:", list(items_data.keys()))
        if not question_id:
            messagebox.showwarning("警告", "题目ID不能为空")
            return

        if not all(c.isalnum() or c == '-' for c in question_id):
            messagebox.showwarning("警告", "题目ID格式不正确，请检查。")
            return

        if question_id in items_data:
            # 1. 自动消失弹窗
            def auto_close_tip():
                tip = tk.Toplevel(root)
                tip.overrideredirect(True)
                tip.attributes("-topmost", True)
                tip.configure(bg="#f0f0f0")
                label = tk.Label(tip, text="该题目已存在", bg="#f0f0f0", fg="#222", font=("微软雅黑", 12))
                label.pack(ipadx=20, ipady=10)
                tip.update_idletasks()
                x = (tip.winfo_screenwidth() - tip.winfo_width()) // 2
                y = (tip.winfo_screenheight() - tip.winfo_height()) // 2
                tip.geometry(f"+{x}+{y}")
                tip.after(1000, tip.destroy)
            auto_close_tip()
            # 2. 自动填充标签、难度
            selected_tags[:] = [tag['tag_name'] for tag_id in items_data[question_id]['tags'] for tag in tags_data if tag['tag_id'] == tag_id]
            set_difficulty_value(items_data[question_id]['tag_level'])
            update_selected_tags_display()
            update_tags_table(tags_data)
            # 3. 自动加载图片
            settings = config.load_settings()
            data_path = settings.get("data_path", "")
            img_dir = os.path.join(data_path, "item_img_path") if data_path else ""
            img_path = os.path.join(img_dir, f"{question_id}.png") if img_dir else ""
            if img_path and os.path.exists(img_path):
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(img_path)
                    # 触发 ImageFrame 的图片显示
                    max_w, max_h = 560, 800
                    w, h = img.size
                    scale = min(max_w/w, max_h/h, 1)
                    if scale < 1:
                        try:
                            resample = Image.Resampling.LANCZOS
                        except AttributeError:
                            resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                        img_disp = img.resize((int(w*scale), int(h*scale)), resample)
                    else:
                        img_disp = img
                    tk_img = ImageTk.PhotoImage(img_disp)
                    img_frame.img_label.config(image=tk_img, text="")
                    img_frame.img_label.image = tk_img
                    img_frame.img_label._original_image = img.copy()
                    img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
                except Exception as e:
                    img_frame.img_label.config(image="", text="图片加载失败")
                    img_frame.img_label.image = None
                    img_frame.img_label._original_image = None
                    img_frame.img_size_var.set("尺寸: -")
            else:
                # 没有图片则清空
                img_frame.img_label.config(image="", text="此处为图片粘贴区域")
                img_frame.img_label.image = None
                img_frame.img_label._original_image = None
                img_frame.img_size_var.set("尺寸: -")
            query_entry.focus_set()
        else:
            query_entry.focus_set()

    def handle_tag_query_enter():
        filtered_tags = [tag for tag in tags_data if query_var.get().lower() in tag['tag_name'].lower()]
        if len(filtered_tags) == 1:
            tag = filtered_tags[0]
            toggle_selected_tag(tag)
        elif len(filtered_tags) == 0:
            # 无匹配时自动弹出添加标签弹窗，并填入名称
            create_tag(query_var.get())
        # 多于1个匹配时不做处理

    def toggle_selected_tag(tag):
        tag_name = tag['tag_name']
        if tag_name in selected_tags:
            selected_tags.remove(tag_name)
        else:
            selected_tags.append(tag_name)
        update_selected_tags_display()

    def update_selected_tags_display():
        for widget in selected_tags_frame.winfo_children():
            widget.destroy()
        for tag_name in selected_tags:
            tag_button = tk.Button(selected_tags_frame, text=tag_name, width=15, height=1)
            tag_button.pack(side=tk.LEFT, padx=5, pady=5)
            tag_button.bind("<Double-1>", lambda event, tn=tag_name: toggle_selected_tag(next((tag for tag in tags_data if tag['tag_name'] == tn), None)))

    def filter_tags(*args):
        query = query_var.get().lower()
        print(f"filter_tags called, query: {query}")
        filtered_tags = [tag for tag in tags_data if query in tag['tag_name'].lower()]
        print(f"filtered_tags: {[tag['tag_name'] for tag in filtered_tags]}")
        update_tags_table(filtered_tags)

    def update_tags_table(tags, preferred_tag_id=None):
        print(f"[调试] 数据库文件路径: {get_db_path()}")
        print(f"[调试] 读取表: tags, 数据: {[tag['tag_name'] for tag in tags]}")
        print(f"update_tags_table called, tags: {[tag['tag_name'] for tag in tags]}")
        print("表格插入前行数：", len(tags_table.get_children()))
        current_selection = preferred_tag_id
        if current_selection is None:
            existing_selection = tags_table.selection()
            if existing_selection:
                current_selection = existing_selection[0]
        for item in tags_table.get_children():
            tags_table.delete(item)
        available_ids = []
        # 按照 module_id → tag_id 从小到大排序
        sorted_tags = sorted(tags, key=lambda x: (int(x['module_id']) if x['module_id'].isdigit() else 999999, int(x['tag_id']) if x['tag_id'].isdigit() else 999999))
        for tag in sorted_tags:
            module_obj = next((module for module in modules_data if module['module_id'] == tag['module_id']), None)
            module_name = module_obj['module_name'] if module_obj else "未知模块"
            module_type = module_obj['module_type'] if module_obj else "未知类型"
            tags_table.insert('', 'end', iid=tag['tag_id'], values=(module_type, module_name, tag['item_count'], tag['tag_name'], tag['tag_intro']))
            available_ids.append(tag['tag_id'])
        print("表格插入后行数：", len(tags_table.get_children()))
        tags_table.update_idletasks()  # 强制刷新表格

        target_id = None
        if current_selection in available_ids:
            target_id = current_selection
        elif available_ids:
            target_id = available_ids[0]

        if target_id:
            tags_table.selection_set(target_id)
            tags_table.focus(target_id)
            update_tag_frame(next((tag for tag in tags_data if tag['tag_id'] == target_id), None))
        else:
            tags_table.selection_remove(tags_table.selection())
            update_tag_frame(None)
    def save_item():
        question_id = question_id_entry.get().strip()
        if not question_id:
            messagebox.showwarning("警告", "题目ID不能为空")
            return

        if not selected_tags:
            messagebox.showwarning("警告", "至少需要一个标签")
            return

        if not difficulty_var.get():
            messagebox.showwarning("警告", "请选择题目难度")
            return

        # 新增：保存图片（如有）
        # 图片保存目录自动为 data_path/item_img_path
        settings = config.load_settings()
        data_path = settings.get("data_path", "")
        img_dir = os.path.join(data_path, "item_img_path") if data_path else ""
        if img_dir:
            try:
                if not os.path.exists(img_dir):
                    os.makedirs(img_dir)
            except Exception as e:
                messagebox.showerror("错误", f"创建图片保存目录失败: {str(e)}")
                return
        # 检查 ImageFrame 是否有图片
        img_obj = getattr(img_frame.img_label, '_original_image', None)
        if img_obj and img_dir:
            try:
                img_path = os.path.join(img_dir, f"{question_id}.png")
                # 直接保存（自动覆盖同名图片）
                img_obj.save(img_path, format="PNG")
            except Exception as e:
                messagebox.showerror("错误", f"图片保存失败: {str(e)}")
                return

        items_data[question_id] = {
            'tags': [tag['tag_id'] for tag in tags_data if tag['tag_name'] in selected_tags],
            'tag_level': int(difficulty_var.get())
        }
        save_items_data()
        load_tags_data()
        messagebox.showinfo("成功", "题目已保存")
        clear_fields()

    def clear_fields():
        question_id_entry.delete(0, tk.END)
        selected_tags[:] = []
        if difficulty_select is not None and difficulty_select['values']:
            set_difficulty_value(difficulty_select['values'][0])
        else:
            difficulty_var.set("")
        query_entry.delete(0, tk.END)
        # 清空图片预览区域
        img_frame.img_label.config(image="", text="此处为图片粘贴区域")
        img_frame.img_label.image = None
        img_frame.img_label._original_image = None
        img_frame.img_size_var.set("尺寸: -")
        update_selected_tags_display()
        update_tags_table(tags_data)

    def create_tag(default_tag_name=None):
        def save_new_tag():
            try:
                module_name = module_var.get()
                tag_name = tag_name_entry.get().strip()
                tag_intro = tag_intro_text.get('1.0', tk.END).strip()

                print(f"module_name: '{module_name}', tag_name: '{tag_name}', tag_intro: '{tag_intro}'")
                
                if not module_name or not tag_name or not tag_intro:
                    messagebox.showwarning("警告", "所有字段都是必填项")
                    return

                selected_module = next((m for m in modules_data if m['module_name'] == module_name), None)
                if not selected_module:
                    messagebox.showerror("错误", "未找到模块")
                    return
                module_id = selected_module['module_id']

                for tag in tags_data:
                    if tag['module_id'] == module_id and tag['tag_name'] == tag_name:
                        messagebox.showwarning("警告", "该标签已存在")
                        return

                # 修改生成新标签ID逻辑
                if tags_data:
                    new_tag_id = str(max(int(tag['tag_id']) for tag in tags_data) + 1).zfill(5)
                else:
                    new_tag_id = "00001"
                new_tag = {
                    "module_id": module_id,
                    "module_name": module_name,
                    "tag_id": new_tag_id,
                    "tag_name": tag_name,
                    "tag_intro": tag_intro,
                    "item_count": 0,
                    "tag_level": 1
                }

                tags_data.append(new_tag)
                save_tags_data()
                update_tags_table(tags_data)
                tag_window.destroy()
                messagebox.showinfo("成功", "标签已保存")
            except Exception as e:
                messagebox.showerror("错误", f"保存标签时出错: {str(e)}")

        tag_window = Toplevel(root)
        tag_window.title("创建标签")
        tag_window.geometry("600x400")

        # 模块选择行
        module_row = tk.Frame(tag_window)
        module_row.grid(row=0, column=0, columnspan=2, padx=0, pady=10, sticky="w")  # sticky改为w，padx=0
        
        module_label = tk.Label(module_row, text="模块：", anchor="w", width=6)
        module_label.pack(side=tk.LEFT, padx=(10, 0))  # 距左10px
        
        module_var = tk.StringVar()
        module_select = ttk.Combobox(module_row, textvariable=module_var, values=[module['module_name'] for module in modules_data], width=25)
        module_select.pack(side=tk.LEFT, padx=(0, 0))  # 左侧对齐
        if module_select['values']:
            module_select.current(0)
            module_var.set(module_select['values'][0])  # 修复：同步设置默认值

        # 重构添加模块按钮逻辑
        def add_module():
            dialog = Toplevel(tag_window)
            dialog.title("批量添加模块")
            dialog.geometry("400x340")  # 高度略增
            # 新增模块类型下拉框
            type_row = tk.Frame(dialog)
            type_row.pack(pady=(10, 0))
            tk.Label(type_row, text="模块类型：").pack(side=tk.LEFT, padx=(0, 5))
            module_type_var = tk.StringVar()
            # 修改为数据库定义的类型
            module_type_select = ttk.Combobox(type_row, textvariable=module_type_var, values=["知识", "思想", "模型"], width=20)
            module_type_select.pack(side=tk.LEFT)
            if module_type_select['values']:
                module_type_select.current(0)
                module_type_var.set(module_type_select['values'][0])

            tk.Label(dialog, text="每行输入一个模块名称：").pack(pady=10)
            text = tk.Text(dialog, width=40, height=10)
            text.pack(padx=10, pady=5)
            def do_add():
                module_type = module_type_var.get().strip()
                if not module_type:
                    messagebox.showwarning("警告", "请选择模块类型", parent=dialog)
                    return
                names = [line.strip() for line in text.get("1.0", tk.END).splitlines() if line.strip()]
                if not names:
                    messagebox.showwarning("警告", "请输入至少一个模块名称", parent=dialog)
                    return
                db_path = get_db_path()
                if not db_path:
                    return
                try:
                    conn = sqlite3.connect(db_path)
                    c = conn.cursor()
                    # 获取当前最大 module_id
                    c.execute("SELECT MAX(module_id) FROM modules")
                    max_id = c.fetchone()[0]
                    next_id = int(max_id) if max_id and max_id.isdigit() else 0
                    added = []
                    for module_name in names:
                        # 检查是否已存在
                        c.execute("SELECT 1 FROM modules WHERE module_name=?", (module_name,))
                        if c.fetchone():
                            continue
                        next_id += 1
                        new_id = str(next_id).zfill(4)
                        # 修改插入语句，增加 module_type
                        c.execute("INSERT INTO modules (module_id, module_name, module_type) VALUES (?, ?, ?)", (new_id, module_name, module_type))
                        added.append(module_name)
                    conn.commit()
                    conn.close()
                    load_modules_data()
                    module_select['values'] = [module['module_name'] for module in modules_data]
                    if module_select['values']:
                        module_select.current(0)
                        module_var.set(module_select['values'][0])  # 修复：同步设置默认值
                    if added:
                        messagebox.showinfo("成功", f"已添加模块：\n" + "\n".join(added), parent=dialog)
                    else:
                        messagebox.showinfo("提示", "没有新模块被添加", parent=dialog)
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"添加模块失败: {str(e)}", parent=dialog)
            tk.Button(dialog, text="添加", command=do_add, width=10).pack(pady=10)
            tk.Button(dialog, text="取消", command=dialog.destroy, width=10).pack()
        add_module_btn = tk.Button(module_row, text="添加模块", command=add_module, width=10)
        add_module_btn.pack(side=tk.LEFT, padx=5)

        # 新增删除模块按钮
        def delete_module():
            dialog = Toplevel(tag_window)
            dialog.title("删除模块")
            dialog.geometry("400x267")  # 原为"400x200"，高度增加三分之一
            tk.Label(dialog, text="请选择要删除的模块：").pack(pady=10)
            # 列表显示所有模块，展示类型和名称
            module_listbox = tk.Listbox(dialog, width=30, height=8)
            for module in modules_data:
                # 展示｜模块类型｜模块名称｜
                display_name = f"｜{module['module_type']}｜{module['module_name']}｜"
                module_listbox.insert(tk.END, display_name)
            module_listbox.pack(padx=10, pady=5)
            def do_delete():
                sel = module_listbox.curselection()
                if not sel:
                    messagebox.showwarning("警告", "请选择一个模块", parent=dialog)
                    return
                # 解析选中的模块类型和名称
                display_name = module_listbox.get(sel[0])
                # 反向查找模块对象
                module_obj = next((m for m in modules_data if f"｜{m['module_type']}｜{m['module_name']}｜" == display_name), None)
                if not module_obj:
                    messagebox.showerror("错误", "未找到模块", parent=dialog)
                    return
                module_id = module_obj['module_id']
                db_path = get_db_path()
                if not db_path:
                    return
                try:
                    conn = sqlite3.connect(db_path)
                    c = conn.cursor()
                    # 校验是否有关联
                    c.execute("SELECT COUNT(*) FROM tags WHERE module_id=?", (module_id,))
                    tag_count = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM clusters WHERE module_id=?", (module_id,))
                    cluster_count = c.fetchone()[0]
                    if tag_count > 0 or cluster_count > 0:
                        msg = "无法删除：该模块仍有关联的"
                        if tag_count > 0:
                            msg += f"标签({tag_count})"
                        if tag_count > 0 and cluster_count > 0:
                            msg += "和"
                        if cluster_count > 0:
                            msg += f"题簇({cluster_count})"
                        messagebox.showerror("错误", msg, parent=dialog)
                        conn.close()
                        return
                    # 删除模块
                    c.execute("DELETE FROM modules WHERE module_id=?", (module_id,))
                    conn.commit()
                    conn.close()
                    load_modules_data()
                    module_select['values'] = [module['module_name'] for module in modules_data]
                    if module_select['values']:
                        module_select.current(0)
                        module_var.set(module_select['values'][0])  # 修复：同步设置默认值
                    messagebox.showinfo("成功", f"模块已删除：｜{module_obj['module_type']}｜{module_obj['module_name']}｜", parent=dialog)
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"删除模块失败: {str(e)}", parent=dialog)
            tk.Button(dialog, text="删除", command=do_delete, width=10).pack(pady=10)
            tk.Button(dialog, text="取消", command=dialog.destroy, width=10).pack()
        delete_module_btn = tk.Button(module_row, text="删除模块", command=delete_module, width=10)
        delete_module_btn.pack(side=tk.LEFT, padx=5)

        # 名称行

        name_row = tk.Frame(tag_window)
        name_row.grid(row=1, column=0, columnspan=2, sticky="w")  # sticky改为w

        tag_name_label = tk.Label(name_row, text="名称：", anchor="w", width=6)
        tag_name_label.pack(side=tk.LEFT, padx=(10, 0))  # 距左10px

        tag_name_entry = tk.Entry(name_row, width=50)  # 修改为width=50
        tag_name_entry.pack(side=tk.LEFT, padx=(0, 0))  # 左侧对齐
        # 如果有默认标签名，自动填入
        if default_tag_name:
            tag_name_entry.insert(0, default_tag_name)

        # 介绍行
        intro_row = tk.Frame(tag_window)
        intro_row.grid(row=2, column=0, columnspan=2, sticky="w")  # sticky改为w

        tag_intro_label = tk.Label(intro_row, text="介绍：", anchor="w", width=6)
        tag_intro_label.pack(side=tk.LEFT, padx=(10, 0))  # 距左10px

        tag_intro_text = tk.Text(intro_row, width=50, height=5)
        tag_intro_text.pack(side=tk.LEFT, padx=(0, 0))  # 左侧对齐
        # 如果有默认标签名，自动将焦点设置到介绍输入框
        if default_tag_name:
            tag_intro_text.focus_set()

        # 保存/取消按钮
        save_tag_button = tk.Button(tag_window, text="保存", command=save_new_tag)
        save_tag_button.grid(row=3, column=0, padx=10, pady=10)

        cancel_tag_button = tk.Button(tag_window, text="取消", command=tag_window.destroy)
        cancel_tag_button.grid(row=3, column=1, padx=10, pady=10)

    # 修改这里，原来是 root = tk.Tk()

    # 新增tag_frame（最左侧）
    tag_frame = tk.Frame(root, width=600, height=900, bd=1, relief=tk.SOLID)
    tag_frame.place(x=0, y=0, width=600, height=900)

    # type_frame右移
    type_frame = tk.Frame(root, width=600, height=900, bd=1, relief=tk.SOLID)
    type_frame.place(x=600, y=0, width=600, height=900)

    # img_frame右移
    from widgets.image_frame import ImageFrame
    img_frame = ImageFrame(root, width=600, height=900, bd=1, relief=tk.SOLID)
    img_frame.place(x=1200, y=0, width=600, height=900)

    stance_frame = tk.Frame(root, width=1800, height=30, bd=1, relief=tk.SOLID)
    stance_frame.place(x=0, y=900, width=1800, height=30)
    # --- tag_frame内容 ---
    tag_info_vars = {
        'module_type': tk.StringVar(),
        'module_name': tk.StringVar(),
        'tag_name': tk.StringVar(),
    }
    tag_current = {'tag_id': None}

    def update_tag_frame(tag):
        # 清空frame
        for widget in tag_frame.winfo_children():
            widget.destroy()
        if not tag:
            tag_current['tag_id'] = None
            return
        tag_current['tag_id'] = tag['tag_id']
        # 第一行：模块类型、模块名称
        row1 = tk.Frame(tag_frame)
        row1.pack(pady=10, anchor="w")
        tk.Label(row1, text="模块类型：").pack(side=tk.LEFT, padx=(10,0))
        module_types = list(sorted(set(m['module_type'] for m in modules_data)))
        tag_info_vars['module_type'].set(next((m['module_type'] for m in modules_data if m['module_id']==tag['module_id']), module_types[0] if module_types else ""))
        module_type_cb = ttk.Combobox(row1, textvariable=tag_info_vars['module_type'], values=module_types, width=10)
        module_type_cb.pack(side=tk.LEFT, padx=(0,10))
        tk.Label(row1, text="模块名称：").pack(side=tk.LEFT)
        module_names = [m['module_name'] for m in modules_data if m['module_type']==tag_info_vars['module_type'].get()]
        tag_info_vars['module_name'].set(next((m['module_name'] for m in modules_data if m['module_id']==tag['module_id']), module_names[0] if module_names else ""))
        module_name_cb = ttk.Combobox(row1, textvariable=tag_info_vars['module_name'], values=module_names, width=18)
        module_name_cb.pack(side=tk.LEFT)

        def on_module_type_change(*args):
            # 切换类型时，模块名称下拉框内容联动
            names = [m['module_name'] for m in modules_data if m['module_type']==tag_info_vars['module_type'].get()]
            module_name_cb['values'] = names
            if names:
                tag_info_vars['module_name'].set(names[0])
        tag_info_vars['module_type'].trace_add('write', on_module_type_change)


        # 第二行：标签名称
        row2 = tk.Frame(tag_frame)
        row2.pack(pady=10, anchor="w")
        tk.Label(row2, text="标签名称：").pack(side=tk.LEFT, padx=(10,0))
        tag_info_vars['tag_name'].set(tag['tag_name'])
        tag_name_entry = tk.Entry(row2, textvariable=tag_info_vars['tag_name'], width=30)
        tag_name_entry.pack(side=tk.LEFT)

        # 新增：简介行（多行输入框）
        row_intro = tk.Frame(tag_frame)
        row_intro.pack(pady=5, anchor="w", fill=tk.X)
        tk.Label(row_intro, text="标签简介：").pack(side=tk.LEFT, padx=(10,0), anchor="n")
        intro_text = tk.Text(row_intro, width=45, height=3)
        intro_text.pack(side=tk.LEFT, padx=(0,0), pady=(0,0), fill=tk.X, expand=True)
        intro_text.delete('1.0', tk.END)
        intro_text.insert('1.0', tag.get('tag_intro', ''))

        # 第三行：题目表格
        row3 = tk.Frame(tag_frame)
        row3.pack(pady=10, fill=tk.BOTH, expand=True)
        tk.Label(row3, text="该标签下题目：").pack(anchor="w", padx=10)
        table = ttk.Treeview(row3, columns=("题目ID", "图片"), show="headings", height=20)
        table.heading("题目ID", text="题目ID")
        table.heading("图片", text="图片")
        table.column("题目ID", width=215)
        table.column("图片", width=5)
        # 获取该标签下所有题目ID
        tag_id = tag['tag_id']
        item_ids = [item_id for item_id, data in items_data.items() if tag_id in data['tags']]
        # 获取图片目录
        settings = config.load_settings()
        data_path = settings.get("data_path", "")
        img_dir = os.path.join(data_path, "item_img_path") if data_path else ""
        for item_id in item_ids:
            img_path = os.path.join(img_dir, f"{item_id}.png") if img_dir else ""
            has_img = "有" if img_path and os.path.exists(img_path) else "无"
            table.insert('', 'end', values=(item_id, has_img))
        table.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # 添加双击事件：打开题目网页
        def on_double_click(event):
            selected = table.selection()
            if selected:
                item_id = table.item(selected[0], 'values')[0]
                from widgets.view_item import open_question_url
                open_question_url(item_id)

        # 添加右键事件：显示菜单
        def on_right_click(event):
            selected = table.selection()
            if selected:
                item_id = table.item(selected[0], 'values')[0]
                # 创建右键菜单
                menu = tk.Menu(table, tearoff=0)
                menu.add_command(label="复制", command=lambda: copy_item_id(item_id))
                menu.add_command(label="预览", command=lambda: preview_image(item_id))
                menu.post(event.x_root, event.y_root)

        def copy_item_id(item_id):
            root.clipboard_clear()
            root.clipboard_append(item_id)
            root.update()  # 确保剪切板更新

        def preview_image(item_id):
            # 检查图片是否存在
            settings = config.load_settings()
            data_path = settings.get("data_path", "")
            img_dir = os.path.join(data_path, "item_img_path") if data_path else ""
            if not img_dir:
                return
            exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
            img_path = None
            for ext in exts:
                candidate = os.path.join(img_dir, f"{item_id}{ext}")
                if os.path.isfile(candidate):
                    img_path = candidate
                    break
            if img_path:
                # 加载到img_frame并预览
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(img_path)
                    max_w, max_h = 560, 800
                    w, h = img.size
                    scale = min(max_w/w, max_h/h, 1)
                    if scale < 1:
                        try:
                            resample = Image.Resampling.LANCZOS
                        except AttributeError:
                            resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                        img_disp = img.resize((int(w*scale), int(h*scale)), resample)
                    else:
                        img_disp = img
                    tk_img = ImageTk.PhotoImage(img_disp)
                    img_frame.img_label.config(image=tk_img, text="")
                    img_frame.img_label.image = tk_img
                    img_frame.img_label._original_image = img.copy()
                    img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
                    # 调用预览
                    img_frame.show_image_popup()
                except Exception as e:
                    pass
            else:
                # 提示暂无图片
                tip = tk.Toplevel(root)
                tip.overrideredirect(True)
                tip.attributes("-topmost", True)
                tip.configure(bg="#f0f0f0")
                label = tk.Label(tip, text="暂无图片", bg="#f0f0f0", fg="#222", font=("微软雅黑", 12))
                label.pack(ipadx=20, ipady=10)
                tip.update_idletasks()
                x = (tip.winfo_screenwidth() - tip.winfo_width()) // 2
                y = (tip.winfo_screenheight() - tip.winfo_height()) // 2
                tip.geometry(f"+{x}+{y}")
                tip.after(1000, tip.destroy)

        # 添加选中事件：自动预览图片
        def on_select(event):
            selected = table.selection()
            if selected:
                item_id = table.item(selected[0], 'values')[0]
                # 检查图片是否存在并自动预览
                settings = config.load_settings()
                data_path = settings.get("data_path", "")
                img_dir = os.path.join(data_path, "item_img_path") if data_path else ""
                if not img_dir:
                    return
                exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
                img_path = None
                for ext in exts:
                    candidate = os.path.join(img_dir, f"{item_id}{ext}")
                    if os.path.isfile(candidate):
                        img_path = candidate
                        break
                if img_path:
                    # 自动加载到img_frame预览
                    try:
                        from PIL import Image, ImageTk
                        img = Image.open(img_path)
                        max_w, max_h = 560, 800
                        w, h = img.size
                        scale = min(max_w/w, max_h/h, 1)
                        if scale < 1:
                            try:
                                resample = Image.Resampling.LANCZOS
                            except AttributeError:
                                resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                            img_disp = img.resize((int(w*scale), int(h*scale)), resample)
                        else:
                            img_disp = img
                        tk_img = ImageTk.PhotoImage(img_disp)
                        img_frame.img_label.config(image=tk_img, text="")
                        img_frame.img_label.image = tk_img
                        img_frame.img_label._original_image = img.copy()
                        img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
                    except Exception as e:
                        pass
                else:
                    # 没有图片则清空预览区域
                    img_frame.img_label.config(image="", text="此处为图片粘贴区域")
                    img_frame.img_label.image = None
                    img_frame.img_label._original_image = None
                    img_frame.img_size_var.set("尺寸: -")

        table.bind("<<TreeviewSelect>>", on_select)
        table.bind("<Double-1>", on_double_click)
        table.bind("<Button-3>", on_right_click)

        # 第四行：保存按钮
        row4 = tk.Frame(tag_frame)
        row4.pack(pady=10)
        def save_tag_info():
            # 允许修改模块类型、模块名称、标签名称、简介
            new_type = tag_info_vars['module_type'].get()
            new_name = tag_info_vars['module_name'].get()
            new_tag_name = tag_info_vars['tag_name'].get().strip()
            new_intro = intro_text.get('1.0', tk.END).strip()
            if not new_type or not new_name or not new_tag_name:
                messagebox.showwarning("警告", "所有字段不能为空", parent=root)
                return
            # 找到对应module_id
            module_obj = next((m for m in modules_data if m['module_type']==new_type and m['module_name']==new_name), None)
            if not module_obj:
                messagebox.showerror("错误", "未找到对应模块", parent=root)
                return
            # 检查标签名是否重复（同模块下）
            for t in tags_data:
                if t['tag_id'] != tag['tag_id'] and t['module_id']==module_obj['module_id'] and t['tag_name']==new_tag_name:
                    messagebox.showwarning("警告", "该模块下标签名已存在", parent=root)
                    return
            # 修改tag对象
            tag['module_id'] = module_obj['module_id']
            tag['tag_name'] = new_tag_name
            tag['tag_intro'] = new_intro
            save_tags_data()
            load_tags_data()
            update_tags_table(tags_data, preferred_tag_id=tag['tag_id'])
            messagebox.showinfo("成功", "标签信息已保存", parent=root)
        save_btn = tk.Button(row4, text="保存", width=15, command=save_tag_info)
        save_btn.pack()

    # --- type_frame内容 ---

    # --- type_frame内容 ---
    # 题目ID行
    question_id_frame = tk.Frame(type_frame)
    question_id_frame.pack(pady=10)
    question_id_label = tk.Label(question_id_frame, text="题目ID：")
    question_id_label.pack(side=tk.LEFT, padx=5)
    question_id_entry = tk.Entry(question_id_frame, width=48)
    question_id_entry.pack(side=tk.LEFT, padx=5)
    question_id_entry.bind("<Return>", lambda event: handle_question_id_enter())
    question_id_entry.bind("<KP_Enter>", lambda event: handle_question_id_enter())
    paste_button = tk.Button(question_id_frame, text="粘贴", width=10, height=1, command=handle_paste)
    paste_button.pack(side=tk.LEFT, padx=5)

    # 难度选择行
    difficulty_frame = tk.Frame(type_frame)
    difficulty_frame.pack(pady=(0, 10), anchor='w')
    tk.Label(difficulty_frame, text="题目难度：").pack(side=tk.LEFT, padx=5)
    difficulty_select = ttk.Combobox(
        difficulty_frame,
        textvariable=difficulty_var,
        values=tuple(difficulty_options),
        state="readonly",
        width=10
    )
    difficulty_select.pack(side=tk.LEFT, padx=5)
    if difficulty_select['values']:
        difficulty_select.current(0)

    # 模块选中区域
    selected_tags_frame = tk.Frame(type_frame)
    selected_tags_frame.pack(pady=10)

    # 标签输入、创建、刷新
    tags_frame = tk.Frame(type_frame)
    tags_frame.pack(pady=10)
    query_var = tk.StringVar()
    query_entry = tk.Entry(tags_frame, textvariable=query_var, width=30)
    query_entry.grid(row=0, column=1, padx=10, pady=10)
    query_var.trace_add('write', lambda *args: filter_tags())
    query_entry.bind("<Return>", lambda event: handle_tag_query_enter())
    query_entry.bind("<KP_Enter>", lambda event: handle_tag_query_enter())
    create_tag_button = tk.Button(tags_frame, text="创建标签", width=10, height=1, command=create_tag)
    create_tag_button.grid(row=0, column=2, padx=10, pady=10)
    def refresh_tags():
        load_tags_data()
        update_tags_table(tags_data, preferred_tag_id=tag_current['tag_id'])
    refresh_button = tk.Button(tags_frame, text="刷新", width=10, height=1, command=refresh_tags)
    refresh_button.grid(row=0, column=3, padx=10, pady=10)

    # 动态表格
    tags_table = ttk.Treeview(type_frame, columns=("类型", "模块", "题量", "名称", "介绍"), show="headings")
    tags_table.heading("类型", text="类型")
    tags_table.heading("模块", text="模块")
    tags_table.heading("题量", text="题量")
    tags_table.heading("名称", text="名称")
    tags_table.heading("介绍", text="介绍")
    tags_table.column("类型", width=70)
    tags_table.column("模块", width=100)
    tags_table.column("题量", width=50)
    tags_table.column("名称", width=150)
    tags_table.column("介绍", width=200)
    tags_table.pack(pady=10, fill=tk.BOTH, expand=True)
    tags_table.bind("<<TreeviewSelect>>", lambda event: update_tag_frame(get_selected_tag()))
    tags_table.bind("<Double-1>", lambda event: toggle_selected_tag(get_selected_tag()))
    def get_selected_tag(event=None):
        selected_item = tags_table.selection()
        if not selected_item:
            return None
        tag_id = selected_item[0]
        return next((tag for tag in tags_data if tag['tag_id'] == tag_id), None)


    # --- img_frame内容已由 ImageFrame 封装，无需手写 ---
    # --- stance_frame内容 ---
    buttons_frame = tk.Frame(stance_frame)
    buttons_frame.pack(expand=True)
    save_button = tk.Button(buttons_frame, text="保存", width=20, height=1, command=save_item)
    save_button.pack(side=tk.LEFT, padx=5)
    save_button.bind("<Return>", lambda event: save_item())
    clear_button = tk.Button(buttons_frame, text="清空", width=20, height=1, command=clear_fields)
    clear_button.pack(side=tk.LEFT, padx=5)

    _register_question_entry_widgets(root, question_id_entry, img_frame, query_entry)
    update_tags_table(tags_data)
    update_selected_tags_display()

if __name__ == "__main__":
    question_entry()

