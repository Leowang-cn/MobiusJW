import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import config
import os
import webbrowser
from widgets.image_frame import ImageFrame
from widgets.view_item import open_question_url

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

def table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def item_management():
    win = tk.Toplevel()
    win.title("题目管理")
    win.geometry("1800x1000")

    # 主内容区Frame
    search_frame = tk.Frame(win, width=1200, height=1000)
    search_frame.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
    search_frame.pack_propagate(False)
    # 右侧图片展示区，使用ImageFrame
    img_frame = ImageFrame(win, width=600, height=1000)
    img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    # 题目检索区
    search_top_frame = tk.Frame(search_frame)
    search_top_frame.pack(fill=tk.X, padx=10, pady=8)
    tk.Label(search_top_frame, text="题目ID检索:").pack(side=tk.LEFT, padx=4)
    search_id_var = tk.StringVar()
    search_entry = tk.Entry(search_top_frame, textvariable=search_id_var, width=36)
    search_entry.pack(side=tk.LEFT, padx=4)
    def search_by_id():
        tree.delete(*tree.get_children())
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            iid = search_id_var.get().strip()
            if not iid:
                return
            sql = """
            SELECT i.item_id, i.item_level, i.item_usage, i.item_intro,
                   m.module_type, m.module_name, t.tag_name
            FROM items i
            LEFT JOIN item_tag_relations r ON i.item_id = r.item_id
            LEFT JOIN tags t ON r.tag_id = t.tag_id
            LEFT JOIN modules m ON t.module_id = m.module_id
            WHERE i.item_id LIKE ?
            ORDER BY i.item_id DESC
            """
            cursor.execute(sql, (f"%{iid}%",))
            rows = cursor.fetchall()
            for row in rows:
                tree.insert("", "end", values=(row[4], row[5], row[6], row[0], row[1], row[2], row[3]), tags=(row[0],))
        except Exception as e:
            messagebox.showerror("错误", f"数据库查询失败: {e}", parent=win)
        finally:
            if 'conn' in locals():
                conn.close()
    tk.Button(search_top_frame, text="检索", command=search_by_id).pack(side=tk.LEFT, padx=8)

    # 筛选区
    filter_frame = tk.Frame(search_frame)
    filter_frame.pack(fill=tk.X, padx=10, pady=8)

    # 标签筛选区
    tk.Label(filter_frame, text="标签筛选:").grid(row=0, column=0, padx=4, sticky="ne")
    # Listbox展示选中标签，限制高度为4行，减少padx，避免撑大布局
    selected_tags_var = tk.Variable(value=[])
    selected_tags_listbox = tk.Listbox(
        filter_frame, listvariable=selected_tags_var, height=4, width=38,
        selectmode=tk.SINGLE, exportselection=False
    )
    # 独占一行，避免影响后续控件布局
    selected_tags_listbox.grid(row=0, column=1, columnspan=6, padx=2, pady=0, sticky="nw")
    selected_tags = []

    def refresh_selected_tags():
        tag_strs = [f"{tag['module_type']}-{tag['module_name']}-{tag['tag_name']}" for tag in selected_tags]
        selected_tags_var.set(tag_strs)

    # 双击Listbox移除标签
    def on_tag_listbox_double(event):
        selection = selected_tags_listbox.curselection()
        if selection:
            idx = selection[0]
            del selected_tags[idx]
            refresh_selected_tags()
    selected_tags_listbox.bind("<Double-Button-1>", on_tag_listbox_double)

    # 后续控件全部从row=1开始，不受Listbox影响
    tk.Label(filter_frame, text="模块类型:").grid(row=1, column=0, padx=4, sticky="e")
    module_type_var = tk.StringVar()
    module_type_cb = ttk.Combobox(filter_frame, textvariable=module_type_var, width=10, state="readonly")
    module_type_cb['values'] = ("", "知识", "思想", "模型")
    module_type_cb.grid(row=1, column=1, padx=2, sticky="w")

    tk.Label(filter_frame, text="模块名称:").grid(row=1, column=2, padx=2, sticky="e")
    module_var = tk.StringVar()
    module_cb = ttk.Combobox(filter_frame, textvariable=module_var, width=12, state="readonly")
    module_cb.grid(row=1, column=3, padx=2, sticky="w")

    tk.Label(filter_frame, text="标签名称:").grid(row=1, column=4, padx=4, sticky="e")
    tag_var = tk.StringVar()
    tag_cb = ttk.Combobox(filter_frame, textvariable=tag_var, width=14, state="readonly")
    tag_cb.grid(row=1, column=5, padx=4, sticky="w")

    # 加载所有模块和标签
    def load_modules_tags():
        db_path = get_db_path()
        if not db_path:
            return [], []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT module_id, module_name, module_type FROM modules")
            modules = cursor.fetchall()
            cursor.execute("SELECT tag_id, tag_name, module_id FROM tags")
            tags = cursor.fetchall()
            return modules, tags
        except Exception:
            return [], []
        finally:
            if 'conn' in locals():
                conn.close()
    modules, tags = load_modules_tags()

    # 联动逻辑
    def on_module_type_change(event):
        mtype = module_type_var.get()
        if mtype:
            filtered_modules = [f"{mid}:{mname}" for mid, mname, mt in modules if mt == mtype]
        else:
            filtered_modules = [f"{mid}:{mname}" for mid, mname, _ in modules]
        module_cb['values'] = [""] + filtered_modules
        module_var.set("")
        tag_cb['values'] = [""]
        tag_var.set("")
    module_type_cb.bind("<<ComboboxSelected>>", on_module_type_change)

    def on_module_change(event):
        mval = module_var.get()
        if mval:
            mid = mval.split(":")[0]
            filtered_tags = [f"{tid}:{tname}" for tid, tname, tmid in tags if tmid == mid]
        else:
            filtered_tags = [""]
        tag_cb['values'] = [""] + filtered_tags
        tag_var.set("")
    module_cb.bind("<<ComboboxSelected>>", on_module_change)

    # 添加标签到选中标签区
    def add_tag():
        tval = tag_var.get()
        mval = module_var.get()
        mtype = module_type_var.get()
        if not tval:
            return
        tid, tname = tval.split(":", 1)
        # 如果模块类型或模块名称为空，则根据标签查数据库补全
        if not (mval and mtype):
            db_path = get_db_path()
            if not db_path:
                return
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.module_id, m.module_name, m.module_type
                    FROM tags t
                    LEFT JOIN modules m ON t.module_id = m.module_id
                    WHERE t.tag_id=?
                """, (tid,))
                result = cursor.fetchone()
                if result:
                    mid, mname, mtype_db = result
                    mval = f"{mid}:{mname}"
                    mtype = mtype_db
                else:
                    return
            except Exception:
                return
            finally:
                if 'conn' in locals():
                    conn.close()
        else:
            mid, mname = mval.split(":", 1)
        # 防止重复
        for tag in selected_tags:
            if tag['tag_id'] == tid:
                return
        selected_tags.append({
            'tag_id': tid,
            'tag_name': tname,
            'module_id': mid,
            'module_name': mname,
            'module_type': mtype
        })
        refresh_selected_tags()
    tk.Button(filter_frame, text="添加标签", command=add_tag, width=10).grid(row=1, column=6, padx=8)

    # 其他筛选
    tk.Label(filter_frame, text="题目难度:").grid(row=2, column=0, padx=4, sticky="e")
    level_var = tk.StringVar()
    level_cb = ttk.Combobox(filter_frame, textvariable=level_var, width=8, state="readonly")
    level_cb['values'] = ("", "1", "2", "3", "4")
    level_cb.grid(row=2, column=1, padx=4, sticky="w")

    tk.Label(filter_frame, text="题目用途:").grid(row=2, column=2, padx=4, sticky="e")
    usage_var = tk.StringVar()
    usage_cb = ttk.Combobox(filter_frame, textvariable=usage_var, width=8, state="readonly")
    usage_cb['values'] = ("", "例", "练")
    usage_cb.grid(row=2, column=3, padx=4, sticky="w")

    # 表格区
    columns = ("module_type", "module_name", "tag_name", "item_id", "item_level", "item_usage", "item_intro")
    tree = ttk.Treeview(search_frame, columns=columns, show="headings", height=20)
    for col, txt in zip(columns, ["模块类型", "模块名称", "标签", "题目ID", "题目难度", "题目用途", "讲解思路"]):
        tree.heading(col, text=txt)
    for col in columns:
        if col == "item_id":
            tree.column(col, width=260, anchor="center")
        elif col == "item_intro":
            tree.column(col, width=260, anchor="center")
        else:
            tree.column(col, width=60, anchor="center")
    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 查询按钮逻辑
    def refresh_table():
        tree.delete(*tree.get_children())
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # 标签筛选
            tag_ids = [tag['tag_id'] for tag in selected_tags]
            if tag_ids:
                # 查询每个标签关联的题目ID
                item_sets = []
                for tid in tag_ids:
                    cursor.execute("SELECT item_id FROM item_tag_relations WHERE tag_id=?", (tid,))
                    item_ids = set(row[0] for row in cursor.fetchall())
                    item_sets.append(item_ids)
                # 取交集
                if item_sets:
                    filtered_item_ids = set.intersection(*item_sets)
                else:
                    filtered_item_ids = set()
            else:
                # 未选标签则查所有题目ID
                cursor.execute("SELECT item_id FROM items")
                filtered_item_ids = set(row[0] for row in cursor.fetchall())
            # 其他筛选
            params = []
            sql = """
            SELECT i.item_id, i.item_level, i.item_usage, i.item_intro,
                   m.module_type, m.module_name, t.tag_name
            FROM items i
            LEFT JOIN item_tag_relations r ON i.item_id = r.item_id
            LEFT JOIN tags t ON r.tag_id = t.tag_id
            LEFT JOIN modules m ON t.module_id = m.module_id
            WHERE i.item_id IN ({})
            """.format(",".join("?" for _ in filtered_item_ids) if filtered_item_ids else "'-'")
            params.extend(filtered_item_ids)
            if level_var.get():
                sql += " AND i.item_level=?"
                params.append(int(level_var.get()))
            if usage_var.get():
                sql += " AND i.item_usage=?"
                params.append(usage_var.get())
            sql += " ORDER BY i.item_id DESC"
            if filtered_item_ids:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            else:
                rows = []
            for row in rows:
                tree.insert("", "end", values=(row[4], row[5], row[6], row[0], row[1], row[2], row[3]), tags=(row[0],))
        except Exception as e:
            messagebox.showerror("错误", f"数据库查询失败: {e}", parent=win)
        finally:
            if 'conn' in locals():
                conn.close()

    tk.Button(filter_frame, text="查询", command=refresh_table).grid(row=2, column=4, padx=8)

    # 新增刷新按钮
    def reset_filters():
        # 重置所有筛选条件
        module_type_var.set("")
        module_cb['values'] = [""] + [f"{mid}:{mname}" for mid, mname, _ in modules]
        module_var.set("")
        tag_cb['values'] = [""] + [f"{tid}:{tname}" for tid, tname, _ in tags]
        tag_var.set("")
        level_var.set("")
        usage_var.set("")
        selected_tags.clear()
        refresh_selected_tags()
        search_id_var.set("")
        refresh_table()
    tk.Button(filter_frame, text="刷新", command=reset_filters).grid(row=2, column=5, padx=8)

    # 初始化下拉框
    module_cb['values'] = [""] + [f"{mid}:{mname}" for mid, mname, _ in modules]
    tag_cb['values'] = [""] + [f"{tid}:{tname}" for tid, tname, _ in tags]

    # 表格双击事件
    def on_row_double(event):
        item = tree.selection()
        if item:
            item_id = tree.item(item, "tags")[0]
            open_question_url(item_id)
    tree.bind("<Double-1>", on_row_double)

    # 表格右键事件
    def on_right_click(event):
        item = tree.identify_row(event.y)
        if not item:
            return
        item_id = tree.item(item, "tags")[0]
        # 检查图片是否存在
        settings = config.load_settings()
        data_path = settings.get("data_path", "")
        img_dir = os.path.join(data_path, "item_img_path")
        if not os.path.isdir(img_dir):
            return
        exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
        img_path = None
        for ext in exts:
            candidate = os.path.join(img_dir, f"{item_id}{ext}")
            if os.path.isfile(candidate):
                img_path = candidate
                break
        if img_path:
            # 加载图片到img_frame
            try:
                from PIL import Image
                img = Image.open(img_path)
                # 限制图片最大宽高
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
                from PIL import ImageTk
                tk_img = ImageTk.PhotoImage(img_disp)
                img_frame.img_label.config(image=tk_img, text="")
                img_frame.img_label.image = tk_img
                img_frame.img_label._original_image = img.copy()
                img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
                # 调用预览
                img_frame.show_image_popup()
            except Exception as e:
                pass

    tree.bind("<Button-3>", on_right_click)

    # 表格聚焦时显示图片
    def on_tree_select(event):
        item = tree.selection()
        if not item:
            img_frame.img_label.config(image='', text='此处为图片粘贴区域')
            img_frame.img_label.image = None
            img_frame.img_label._original_image = None
            img_frame.img_size_var.set("尺寸: -")
            return
        item_id = tree.item(item, "tags")[0]
        # 获取图片路径
        settings = config.load_settings()
        data_path = settings.get("data_path", "")
        img_dir = os.path.join(data_path, "item_img_path")
        if not os.path.isdir(img_dir):
            img_frame.img_label.config(image='', text='此处为图片粘贴区域')
            img_frame.img_label.image = None
            img_frame.img_label._original_image = None
            img_frame.img_size_var.set("尺寸: -")
            return
        exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
        img_path = None
        for ext in exts:
            candidate = os.path.join(img_dir, f"{item_id}{ext}")
            if os.path.isfile(candidate):
                img_path = candidate
                break
        if img_path:
            try:
                from PIL import Image
                img = Image.open(img_path)
                # 限制图片最大宽高
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
                from PIL import ImageTk
                tk_img = ImageTk.PhotoImage(img_disp)
                img_frame.img_label.config(image=tk_img, text="")
                img_frame.img_label.image = tk_img
                img_frame.img_label._original_image = img.copy()
                img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
            except Exception as e:
                img_frame.img_label.config(image='', text=f"图片加载失败\n{e}")
                img_frame.img_label.image = None
                img_frame.img_label._original_image = None
                img_frame.img_size_var.set("尺寸: -")
        else:
            img_frame.img_label.config(image='', text='此处为图片粘贴区域')
            img_frame.img_label.image = None
            img_frame.img_label._original_image = None
            img_frame.img_size_var.set("尺寸: -")
    tree.bind("<<TreeviewSelect>>", on_tree_select)

    # 默认刷新
    refresh_table()

def show_item_detail(parent, item_id):
    import webbrowser
    db_path = get_db_path()
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 获取题目主信息
        cursor.execute("SELECT item_id, item_level, item_usage, item_intro FROM items WHERE item_id=?", (item_id,))
        item_row = cursor.fetchone()
        if not item_row:
            messagebox.showerror("错误", "题目不存在", parent=parent)
            return
        # 获取标签及模块
        cursor.execute("""
            SELECT t.tag_id, t.tag_name, m.module_id, m.module_name, m.module_type
            FROM item_tag_relations r
            LEFT JOIN tags t ON r.tag_id = t.tag_id
            LEFT JOIN modules m ON t.module_id = m.module_id
            WHERE r.item_id=?
        """, (item_id,))
        tag_rows = cursor.fetchall()
    except Exception as e:
        messagebox.showerror("错误", f"数据库查询失败: {e}", parent=parent)
        return
    finally:
        if 'conn' in locals():
            conn.close()

    detail_win = tk.Toplevel(parent)
    detail_win.title(f"题目详情：{item_id}")
    detail_win.geometry("600x500")
    detail_win.grab_set()

    # 标签展示区（模块类型-模块名称-标签名称），带删除按钮
    tk.Label(detail_win, text="标签关联：").grid(row=0, column=0, padx=8, pady=4, sticky="ne")
    tag_info_frame = tk.Frame(detail_win)
    tag_info_frame.grid(row=0, column=1, padx=4, pady=4, sticky="w")

    # 记录当前编辑标签ID（即下方下拉框选中的标签）
    current_tag_id = None
    if tag_rows:
        current_tag_id = tag_rows[0][0]

    def refresh_tag_info():
        # 清空
        for widget in tag_info_frame.winfo_children():
            widget.destroy()
        # 重新获取标签
        db_path2 = get_db_path()
        if not db_path2:
            return
        try:
            conn2 = sqlite3.connect(db_path2)
            cursor2 = conn2.cursor()
            cursor2.execute("""
                SELECT t.tag_id, t.tag_name, m.module_id, m.module_name, m.module_type
                FROM item_tag_relations r
                LEFT JOIN tags t ON r.tag_id = t.tag_id
                LEFT JOIN modules m ON t.module_id = m.module_id
                WHERE r.item_id=?
            """, (item_id,))
            rows = cursor2.fetchall()
        except Exception:
            rows = []
        finally:
            if 'conn2' in locals():
                conn2.close()
        # 展示标签及删除按钮
        for row in rows:
            info_str = f"{row[4]}-{row[3]}-{row[1]}"
            tag_line = tk.Frame(tag_info_frame)
            tag_line.pack(fill=tk.X, pady=1)
            tk.Label(tag_line, text=info_str, anchor="w").pack(side=tk.LEFT)
            # 所有标签都显示删除按钮
            def make_delete_func(tag_id=row[0]):
                def delete_tag():
                    if not messagebox.askyesno("确认", f"确定要删除标签 {info_str} 吗？", parent=detail_win):
                        return
                    db_path3 = get_db_path()
                    if not db_path3:
                        return
                    try:
                        conn3 = sqlite3.connect(db_path3)
                        cursor3 = conn3.cursor()
                        cursor3.execute("DELETE FROM item_tag_relations WHERE item_id=? AND tag_id=?", (item_id, tag_id))
                        conn3.commit()
                    except Exception as e:
                        messagebox.showerror("错误", f"删除标签失败: {e}", parent=detail_win)
                    finally:
                        if 'conn3' in locals():
                            conn3.close()
                    # 如果删除的是当前编辑标签，则关闭详情弹层，否则刷新标签展示
                    if current_tag_id and tag_id == current_tag_id:
                        detail_win.destroy()
                    else:
                        refresh_tag_info()
                return delete_tag
            tk.Button(tag_line, text="删除标签", command=make_delete_func(), width=6).pack(side=tk.LEFT, padx=8)
    refresh_tag_info()

    # 模块类型下拉（下移一行，row=1）
    tk.Label(detail_win, text="模块类型:").grid(row=1, column=0, padx=8, pady=8, sticky="e")
    module_type_var = tk.StringVar()
    module_type_cb = ttk.Combobox(detail_win, textvariable=module_type_var, width=10, state="readonly")
    module_type_cb['values'] = ("知识", "思想", "模型")
    module_type_cb.grid(row=1, column=1, padx=4, pady=8, sticky="w")

    # 模块名称下拉
    tk.Label(detail_win, text="模块名称:").grid(row=2, column=0, padx=8, pady=8, sticky="e")
    module_name_var = tk.StringVar()
    module_cb = ttk.Combobox(detail_win, textvariable=module_name_var, width=16, state="readonly")
    module_cb.grid(row=2, column=1, padx=4, pady=8, sticky="w")

    # 标签下拉
    tk.Label(detail_win, text="标签:").grid(row=3, column=0, padx=8, pady=8, sticky="e")
    tag_var = tk.StringVar()
    tag_cb = ttk.Combobox(detail_win, textvariable=tag_var, width=18, state="readonly")
    tag_cb.grid(row=3, column=1, padx=4, pady=8, sticky="w")

    # 题目ID只读 + 查看按钮
    tk.Label(detail_win, text="题目ID:").grid(row=4, column=0, padx=8, pady=8, sticky="e")
    id_frame = tk.Frame(detail_win)
    id_frame.grid(row=4, column=1, padx=4, pady=8, sticky="w")
    tk.Label(id_frame, text=item_row[0], width=32, relief="sunken").pack(side=tk.LEFT)
    def open_jyeoo():
        settings = config.load_settings()
        subject_param = settings.get("subject_param", "")
        url = f"https://www.jyeoo.com/{subject_param}/ques/detail/{item_row[0]}"
        webbrowser.open(url)
    tk.Button(id_frame, text="查看", command=open_jyeoo, width=8).pack(side=tk.LEFT, padx=6)

    # 难度
    tk.Label(detail_win, text="题目难度:").grid(row=5, column=0, padx=8, pady=8, sticky="e")
    level_var = tk.StringVar(value=str(item_row[1]))
    level_cb = ttk.Combobox(detail_win, textvariable=level_var, width=8, state="readonly")
    level_cb['values'] = ("1", "2", "3", "4")
    level_cb.grid(row=5, column=1, padx=4, pady=8, sticky="w")

    # 用途
    tk.Label(detail_win, text="题目用途:").grid(row=6, column=0, padx=8, pady=8, sticky="e")
    usage_var = tk.StringVar(value=item_row[2] if item_row[2] else "")
    usage_cb = ttk.Combobox(detail_win, textvariable=usage_var, width=8, state="readonly")
    usage_cb['values'] = ("", "例", "练")
    usage_cb.grid(row=6, column=1, padx=4, pady=8, sticky="w")

    # 讲解思路
    tk.Label(detail_win, text="讲解思路:").grid(row=7, column=0, padx=8, pady=8, sticky="ne")
    intro_text = tk.Text(detail_win, width=40, height=6)
    intro_text.grid(row=7, column=1, padx=4, pady=8, sticky="w")
    intro_text.insert("1.0", item_row[3] if item_row[3] else "")

    # 加载所有模块和标签
    def load_all_modules_tags():
        db_path = get_db_path()
        if not db_path:
            return [], []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT module_id, module_name, module_type FROM modules")
            modules = cursor.fetchall()
            cursor.execute("SELECT tag_id, tag_name, module_id FROM tags")
            tags = cursor.fetchall()
            return modules, tags
        except Exception:
            return [], []
        finally:
            if 'conn' in locals():
                conn.close()
    modules, tags = load_all_modules_tags()

    # 联动：模块类型限制模块名称
    def on_module_type_change(event):
        mtype = module_type_var.get()
        filtered_modules = [f"{mid}:{mname}" for mid, mname, mt in modules if mt == mtype]
        module_cb['values'] = filtered_modules
        module_name_var.set("")
        tag_cb['values'] = []
        tag_var.set("")
    module_type_cb.bind("<<ComboboxSelected>>", on_module_type_change)

    # 联动：模块名称限制标签
    def on_module_change(event):
        mval = module_name_var.get()
        if mval:
            mid = mval.split(":")[0]
            filtered_tags = [f"{tid}:{tname}" for tid, tname, tmid in tags if tmid == mid]
        else:
            filtered_tags = []
        tag_cb['values'] = filtered_tags
        tag_var.set("")
        # 设置模块类型
        for m in modules:
            if m[0] == mid:
                module_type_var.set(m[2])
                break
    module_cb.bind("<<ComboboxSelected>>", on_module_change)

    # 联动：标签选择自动切换模块名称和类型
    def on_tag_change(event):
        tval = tag_var.get()
        if tval:
            tid = tval.split(":")[0]
            for t in tags:
                if t[0] == tid:
                    mid = t[2]
                    for m in modules:
                        if m[0] == mid:
                            module_name_var.set(f"{mid}:{m[1]}")
                            module_type_var.set(m[2])
                            # 联动模块名称下拉框
                            module_cb['values'] = [f"{mid}:{m[1]}" for mid, mname, mt in modules if mt == m[2]]
                            # 联动标签下拉框
                            tag_cb['values'] = [f"{tid}:{tname}" for tid, tname, tmid in tags if tmid == mid]
                            break
                    break
    tag_cb.bind("<<ComboboxSelected>>", on_tag_change)

    # 初始化下拉框
    if tag_rows:
        module_type_var.set(tag_rows[0][4])
        module_cb['values'] = [f"{mid}:{mname}" for mid, mname, mt in modules if mt == tag_rows[0][4]]
        module_name_var.set(f"{tag_rows[0][2]}:{tag_rows[0][3]}")
        tag_cb['values'] = [f"{tid}:{tname}" for tid, tname, tmid in tags if tmid == tag_rows[0][2]]
        tag_var.set(f"{tag_rows[0][0]}:{tag_rows[0][1]}")
    else:
        module_type_var.set("")
        module_cb['values'] = []
        module_name_var.set("")
        tag_cb['values'] = []
        tag_var.set("")

    # 按钮区
    btn_frame = tk.Frame(detail_win)
    btn_frame.grid(row=8, column=0, columnspan=2, pady=18)

    def save_item():
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # 用途校验：空字符串转为None
            usage_value = usage_var.get()
            if usage_value == "":
             usage_value = None
            # 更新items表
            cursor.execute("UPDATE items SET item_level=?, item_usage=?, item_intro=? WHERE item_id=?",
                           (int(level_var.get()), usage_value, intro_text.get("1.0", "end").strip(), item_id))
            # 更新标签关系
            tval = tag_var.get()
            if tval:
                tid = tval.split(":")[0]
                # 删除原有关系，插入新关系
                cursor.execute("DELETE FROM item_tag_relations WHERE item_id=? AND tag_id=?", (item_id, current_tag_id))
                cursor.execute("INSERT INTO item_tag_relations (item_id, tag_id) VALUES (?, ?)", (item_id, tid))
            conn.commit()
            messagebox.showinfo("成功", "保存成功", parent=detail_win)
            detail_win.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}", parent=detail_win)
        finally:
            if 'conn' in locals():
                conn.close()

    def delete_item():
        if not messagebox.askyesno("确认", "确定要删除该题目吗？（仅删除items和item_tag_relations表）", parent=detail_win):
            return
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE item_id=?", (item_id,))
            cursor.execute("DELETE FROM item_tag_relations WHERE item_id=?", (item_id,))
            conn.commit()
            messagebox.showinfo("成功", "题目已删除", parent=detail_win)
            detail_win.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}", parent=detail_win)
        finally:
            if 'conn' in locals():
                conn.close()

    tk.Button(btn_frame, text="保存", command=save_item, width=10).pack(side=tk.LEFT, padx=12)
    tk.Button(btn_frame, text="取消", command=detail_win.destroy, width=10).pack(side=tk.LEFT, padx=12)
    tk.Button(btn_frame, text="删除题目", command=delete_item, width=10).pack(side=tk.LEFT, padx=12)
