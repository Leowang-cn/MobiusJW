import tkinter as tk
from tkinter import messagebox, Toplevel, ttk
import os
import json
import sqlite3
import config  # 新增：导入 config 模块
import webbrowser

# 全局变量
tags_data = []
items_data = []
modules_data = []

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
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.tag_id, t.module_id, m.module_name, t.tag_name, t.tag_intro, m.module_type
            FROM tags t
            LEFT JOIN modules m ON t.module_id = m.module_id
        """)
        tags_data = []
        for row in cursor.fetchall():
            tags_data.append({
                "tag_id": row[0],
                "module_id": row[1],
                "module_name": row[2] if row[2] else "未知模块",
                "tag_name": row[3],
                "tag_intro": row[4],
                "module_type": row[5] if len(row) > 5 and row[5] else "未知类型"
            })
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取标签数据时出错: {str(e)}")

def load_items_data():
    global items_data
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, item_level FROM items")
        items = {row[0]: {'tag_level': row[1], 'tags': []} for row in cursor.fetchall()}
        cursor.execute("SELECT item_id, tag_id FROM item_tag_relations")
        for item_id, tag_id in cursor.fetchall():
            if item_id in items:
                items[item_id]['tags'].append(tag_id)
        items_data = items
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取题目数据时出错: {str(e)}")

def load_modules_data():
    global modules_data
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT module_id, module_name, module_type FROM modules")  # 增加module_type
        modules_data = []
        for row in cursor.fetchall():
            modules_data.append({
                "module_id": row[0],
                "module_name": row[1],
                "module_type": row[2] if len(row) > 2 else "未知类型"
            })
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"读取模块数据时出错: {str(e)}")

def save_tags_data():
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for tag in tags_data:
            cursor.execute("""
                UPDATE tags SET
                    module_id = ?,
                    tag_name = ?,
                    tag_intro = ?
                WHERE tag_id = ?
            """, (tag['module_id'], tag['tag_name'], tag['tag_intro'], tag['tag_id']))
        conn.commit()
        conn.close()
    except Exception as e:
        messagebox.showerror("错误", f"保存标签数据时出错: {str(e)}")

def tag_management():
    try:
        load_tags_data()
        load_items_data()
        load_modules_data()

        # 模块类型固定值，见数据结构定义
        module_types = ["知识", "思想", "模型"]

        def filter_tags(*args):
            module_type_filter = module_type_var.get()
            module_filter = module_var.get()
            tag_name_query = tag_name_var.get().lower()

            filtered_tags = tags_data
            if module_type_filter != "所有类型":
                filtered_tags = [tag for tag in filtered_tags if tag['module_type'] == module_type_filter]
            if module_filter != "所有模块":
                filtered_tags = [tag for tag in filtered_tags if tag['module_name'] == module_filter]
            if tag_name_query:
                filtered_tags = [tag for tag in filtered_tags if tag_name_query in tag['tag_name'].lower()]

            update_tags_table(filtered_tags)

        def update_module_options(*args):
            # 联动：模块类型变化时，模块下拉框只显示该类型下的模块
            module_type_filter = module_type_var.get()
            if module_type_filter == "所有类型":
                module_names = ["所有模块"] + [m['module_name'] for m in modules_data]
            else:
                module_names = ["所有模块"] + [m['module_name'] for m in modules_data if m['module_type'] == module_type_filter]
            module_select['values'] = module_names
            module_var.set("所有模块")
            filter_tags()

        def update_tags_table(tags):
            for i in tags_table.get_children():
                tags_table.delete(i)
            db_path = get_db_path()
            if not db_path:
                return
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                for tag in tags:
                    cursor.execute("SELECT COUNT(*) FROM item_tag_relations WHERE tag_id = ?", (tag['tag_id'],))
                    item_count = cursor.fetchone()[0]
                    tags_table.insert('', 'end', values=(
                        tag['module_type'], tag['module_name'], item_count, tag['tag_name'], tag['tag_intro']
                    ))
                conn.close()
            except Exception as e:
                messagebox.showerror("错误", f"统计题量时出错: {str(e)}")

        def edit_tag(event):
            selected_item = tags_table.selection()
            if selected_item:
                item = tags_table.item(selected_item[0])
                tag_name = item['values'][3]
                tag = next((t for t in tags_data if t['tag_name'] == tag_name), None)
                if tag:
                    edit_tag_window(tag)

        def edit_tag_window(tag):
            # 查询当前标签标记的题目ID数量
            db_path = get_db_path()
            item_count = 0
            if db_path:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM item_tag_relations WHERE tag_id = ?", (tag['tag_id'],))
                    item_count = cursor.fetchone()[0]
                    conn.close()
                except Exception:
                    pass

            # 编辑弹层增加模块类型字段，并与模块下拉框联动
            def update_module_select(*args):
                selected_type = module_type_var.get()
                module_names = [m['module_name'] for m in modules_data if m['module_type'] == selected_type]
                module_select['values'] = module_names
                if module_names:
                    module_var.set(module_names[0])
                else:
                    module_var.set("")

            def save_edited_tag():
                module_type = module_type_var.get()
                module_name = module_var.get()
                tag_name = tag_name_entry.get().strip()
                tag_intro = tag_intro_text.get('1.0', tk.END).strip()

                if not module_type or not module_name or not tag_name or not tag_intro:
                    messagebox.showwarning("警告", "所有字段都是必填项")
                    return

                selected_module = next((m for m in modules_data if m['module_name'] == module_name and m['module_type'] == module_type), None)
                if not selected_module:
                    messagebox.showwarning("警告", "选择的模块或类型无效")
                    return

                module_id = selected_module['module_id']
                module_name = selected_module['module_name']
                module_type = selected_module['module_type']

                for existing_tag in tags_data:
                    if existing_tag['tag_id'] != tag['tag_id'] and existing_tag['module_id'] == module_id and existing_tag['tag_name'] == tag_name:
                        messagebox.showwarning("警告", "该标签已存在")
                        return

                tag['module_id'] = module_id
                tag['module_name'] = module_name
                tag['module_type'] = module_type
                tag['tag_name'] = tag_name
                tag['tag_intro'] = tag_intro

                save_tags_data()
                update_tags_table(tags_data)
                tag_window.destroy()

            def show_tag_items():
                db_path = get_db_path()
                if not db_path:
                    return
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT item_id FROM item_tag_relations WHERE tag_id = ?", (tag['tag_id'],)
                    )
                    item_ids = [str(row[0]) for row in cursor.fetchall()]
                    conn.close()
                except Exception as e:
                    messagebox.showerror("错误", f"读取题目ID时出错: {str(e)}")
                    return

                # 读取 subject_param
                settings_file = config.load_settings_path()
                subject_param = "physics"
                if os.path.exists(settings_file):
                    try:
                        with open(settings_file, "r", encoding="utf-8") as f:
                            settings = json.load(f)
                        subject_param = settings.get("subject_param", "physics")
                    except Exception:
                        pass

                items_window = Toplevel(tag_window)
                items_window.title(f"标签“{tag['tag_name']}”的题目ID")
                items_window.geometry("450x400")
                label = tk.Label(items_window, text=f"已标记该标签的题目ID（共{len(item_ids)}个）:")
                label.pack(pady=10)

                # 用 Listbox 支持多选
                listbox = tk.Listbox(items_window, selectmode=tk.EXTENDED, width=40, height=12)
                for iid in item_ids:
                    listbox.insert(tk.END, iid)
                listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

                def copy_all():
                    items_str = "\n".join(item_ids)
                    items_window.clipboard_clear()
                    items_window.clipboard_append(items_str)
                    items_window.update()
                    messagebox.showinfo("复制成功", "所有题目ID已复制到剪切板")

                def open_selected():
                    selected = [listbox.get(i) for i in listbox.curselection()]
                    if not selected:
                        messagebox.showwarning("未选择", "请先选择题目ID")
                        return
                    for iid in selected:
                        url = f"https://www.jyeoo.com/{subject_param}/ques/detail/{iid}"
                        webbrowser.open_new_tab(url)

                btn_frame = tk.Frame(items_window)
                btn_frame.pack(pady=10)
                copy_btn = tk.Button(btn_frame, text="复制", command=copy_all, width=10)
                copy_btn.pack(side="left", padx=10)
                open_btn = tk.Button(btn_frame, text="打开", command=open_selected, width=10)
                open_btn.pack(side="left", padx=10)
                close_btn = tk.Button(btn_frame, text="关闭", command=items_window.destroy, width=10)
                close_btn.pack(side="left", padx=10)

            def delete_tag():
                if item_count > 0:
                    messagebox.showwarning("无法删除", "有题目标注了此标签，请先处理后再删除。")
                    return
                db_path = get_db_path()
                if not db_path:
                    return
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tags WHERE tag_id = ?", (tag['tag_id'],))
                    conn.commit()
                    conn.close()
                    # 从 tags_data 中移除
                    tags_data[:] = [t for t in tags_data if t['tag_id'] != tag['tag_id']]
                    update_tags_table(tags_data)
                    messagebox.showinfo("删除成功", "标签已删除。")
                    tag_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"删除标签时出错: {str(e)}")

            tag_window = Toplevel(root)
            tag_window.title("修改标签")
            tag_window.geometry("650x300")

            # 新增：展示题目ID数量
            count_label = tk.Label(tag_window, text=f"当前标签标记题目数量：{item_count}", fg="blue")
            count_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,0), sticky="w")

            # 优化布局：模块类型、模块、名称一行
            row_frame = tk.Frame(tag_window)
            row_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="w")

            module_type_label = tk.Label(row_frame, text="模块类型：")
            module_type_label.grid(row=0, column=0, padx=(0,2), pady=5, sticky="e")
            module_type_var = tk.StringVar(value=tag['module_type'])
            module_type_select = ttk.Combobox(row_frame, textvariable=module_type_var, values=module_types, width=8)
            module_type_select.grid(row=0, column=1, padx=(2,10), pady=5, sticky="w")
            module_type_select.bind("<<ComboboxSelected>>", update_module_select)

            module_label = tk.Label(row_frame, text="模块：")
            module_label.grid(row=0, column=2, padx=(0,2), pady=5, sticky="e")
            init_modules = [m['module_name'] for m in modules_data if m['module_type'] == tag['module_type']]
            module_var = tk.StringVar(value=tag['module_name'])
            module_select = ttk.Combobox(row_frame, textvariable=module_var, values=init_modules, width=12)
            module_select.grid(row=0, column=3, padx=(2,10), pady=5, sticky="w")

            tag_name_label = tk.Label(row_frame, text="名称：")
            tag_name_label.grid(row=0, column=4, padx=(0,2), pady=5, sticky="e")
            tag_name_entry = tk.Entry(row_frame, width=24)
            tag_name_entry.grid(row=0, column=5, padx=(2,10), pady=5, sticky="w")
            tag_name_entry.insert(0, tag['tag_name'])

            # 介绍单独一行
            tag_intro_label = tk.Label(tag_window, text="介绍：")
            tag_intro_label.grid(row=2, column=0, padx=10, pady=(5,10), sticky="ne")
            tag_intro_text = tk.Text(tag_window, width=70, height=8)
            tag_intro_text.grid(row=2, column=1, padx=10, pady=(5,10), sticky="w")
            tag_intro_text.insert('1.0', tag['tag_intro'])

            # 按钮单独一行
            btn_frame = tk.Frame(tag_window)
            btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
            view_tag_items_button = tk.Button(btn_frame, text="查看", command=show_tag_items, width=10)
            view_tag_items_button.pack(side="left", padx=10)
            save_tag_button = tk.Button(btn_frame, text="保存", command=save_edited_tag, width=10)
            save_tag_button.pack(side="left", padx=10)
            # 新增：删除按钮
            delete_tag_button = tk.Button(btn_frame, text="删除", command=delete_tag, width=10)
            delete_tag_button.pack(side="left", padx=10)
            cancel_tag_button = tk.Button(btn_frame, text="取消", command=tag_window.destroy, width=10)
            cancel_tag_button.pack(side="left", padx=10)

        root = tk.Toplevel()
        root.title("标签管理")
        root.geometry("900x800")

        filter_frame = tk.Frame(root)
        filter_frame.pack(pady=10)

        # 优化布局：三项横向一行，间距紧凑
        module_type_label = tk.Label(filter_frame, text="模块类型：")
        module_type_label.grid(row=0, column=0, padx=(5,2), pady=10, sticky="e")
        module_type_var = tk.StringVar(value="所有类型")
        module_type_select = ttk.Combobox(filter_frame, textvariable=module_type_var, values=module_types, width=8)
        module_type_select.grid(row=0, column=1, padx=(2,10), pady=10, sticky="w")
        module_type_select.bind("<<ComboboxSelected>>", update_module_options)

        module_label = tk.Label(filter_frame, text="模块：")
        module_label.grid(row=0, column=2, padx=(5,2), pady=10, sticky="e")
        module_var = tk.StringVar(value="所有模块")
        module_select = ttk.Combobox(filter_frame, textvariable=module_var, values=["所有模块"] + [module['module_name'] for module in modules_data], width=10)
        module_select.grid(row=0, column=3, padx=(2,10), pady=10, sticky="w")
        module_select.bind("<<ComboboxSelected>>", filter_tags)

        tag_name_label = tk.Label(filter_frame, text="标签名称：")
        tag_name_label.grid(row=0, column=4, padx=(5,2), pady=10, sticky="e")
        tag_name_var = tk.StringVar()
        tag_name_entry = tk.Entry(filter_frame, textvariable=tag_name_var, width=20)
        tag_name_entry.grid(row=0, column=5, padx=(2,10), pady=10, sticky="w")
        tag_name_entry.bind("<KeyRelease>", filter_tags)

        # 新增：刷新按钮
        def refresh_all():
            module_type_var.set("所有类型")
            module_var.set("所有模块")
            tag_name_var.set("")
            load_tags_data()
            load_items_data()
            load_modules_data()
            update_module_options()
            filter_tags()
        refresh_btn = tk.Button(filter_frame, text="刷新", command=refresh_all, width=8)
        refresh_btn.grid(row=0, column=6, padx=(2,10), pady=10, sticky="w")

        # 表格：模块类型放在模块左侧，移除ID列
        tags_table = ttk.Treeview(root, columns=("模块类型", "模块", "题量", "名称", "介绍"), show="headings")
        tags_table.heading("模块类型", text="模块类型")
        tags_table.heading("模块", text="模块")
        tags_table.heading("题量", text="题量")
        tags_table.heading("名称", text="名称")
        tags_table.heading("介绍", text="介绍")
        tags_table.column("模块类型", width=100)
        tags_table.column("模块", width=100)
        tags_table.column("题量", width=50)
        tags_table.column("名称", width=150)
        tags_table.column("介绍", width=200)
        tags_table.pack(pady=10, fill=tk.BOTH, expand=True)

        tags_table.bind("<Double-1>", edit_tag)

        update_tags_table(tags_data)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("错误", f"标签管理界面启动时出错: {str(e)}")

if __name__ == "__main__":
    tag_management()
if __name__ == "__main__":
    tag_management()
if __name__ == "__main__":
    tag_management()
    tag_management()
if __name__ == "__main__":
    tag_management()
if __name__ == "__main__":
    tag_management()
