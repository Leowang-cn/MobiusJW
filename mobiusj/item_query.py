import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import config
from widgets.image_frame import ImageFrame
from widgets.view_item import open_question_url

# 获取数据库路径
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

# 查询所有标签
def load_tags():
    db_path = get_db_path()
    if not db_path:
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT tag_id, tag_name, module_id FROM tags")
        tags = cursor.fetchall()
        conn.close()
        return tags
    except Exception:
        return []

def load_modules():
    db_path = get_db_path()
    if not db_path:
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT module_id, module_name, module_type FROM modules")
        modules = cursor.fetchall()
        conn.close()
        return modules
    except Exception:
        return []

# 查询题目标签分布
# 返回：只标记该标签、标记2个标签、标记3个标签的题目数量
# 以及标记2个标签的分组统计

def query_tag_distribution(tag_id):
    db_path = get_db_path()
    if not db_path:
        return 0, 0, 0, {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 查询所有标记该标签的题目ID
        cursor.execute("SELECT item_id FROM item_tag_relations WHERE tag_id=?", (tag_id,))
        item_ids = [row[0] for row in cursor.fetchall()]
        only_one = 0
        two_tags = 0
        three_tags = 0
        two_tag_group = {}
        for item_id in item_ids:
            cursor.execute("SELECT tag_id FROM item_tag_relations WHERE item_id=?", (item_id,))
            tags = [row[0] for row in cursor.fetchall()]
            if len(tags) == 1:
                only_one += 1
            elif len(tags) == 2:
                two_tags += 1
                # 统计另一个标签
                other_tag = [t for t in tags if t != tag_id][0]
                two_tag_group.setdefault(other_tag, []).append(item_id)
            elif len(tags) == 3:
                three_tags += 1
        conn.close()
        return only_one, two_tags, three_tags, two_tag_group
    except Exception:
        return 0, 0, 0, {}

# 查询标签名称

def get_tag_name(tag_id, tags):
    for tid, tname, _ in tags:
        if tid == tag_id:
            return tname
    return ""

def item_query():
    tags = load_tags()
    modules = load_modules()
    root = tk.Toplevel()
    root.title("题目查询")
    root.geometry("1800x1000")

    # 主体区：筛选区和统计区上下排布
    main_frame = tk.Frame(root)
    main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 筛选区
    select_frame = tk.Frame(main_frame)
    select_frame.pack(fill=tk.X, pady=6)
    tk.Label(select_frame, text="模块类型:", font=("微软雅黑", 10)).grid(row=0, column=0, padx=4, sticky="w")
    module_types = list(sorted(set(m[2] for m in modules)))
    module_type_var = tk.StringVar()
    module_type_cb = ttk.Combobox(select_frame, textvariable=module_type_var, values=module_types, state="readonly", width=12)
    module_type_cb.grid(row=0, column=1, padx=4, sticky="w")

    tk.Label(select_frame, text="模块名称:", font=("微软雅黑", 10)).grid(row=0, column=2, padx=4, sticky="w")
    module_names_var = tk.StringVar()
    module_cb = ttk.Combobox(select_frame, textvariable=module_names_var, values=[], state="readonly", width=16)
    module_cb.grid(row=0, column=3, padx=4, sticky="w")

    tk.Label(select_frame, text="标签名称:", font=("微软雅黑", 10)).grid(row=0, column=4, padx=4, sticky="w")
    tag_names_var = tk.StringVar()
    tag_cb = ttk.Combobox(select_frame, textvariable=tag_names_var, values=[], state="readonly", width=18)
    tag_cb.grid(row=0, column=5, padx=4, sticky="w")

    query_btn = tk.Button(select_frame, text="查询", width=12, font=("微软雅黑", 10))
    query_btn.grid(row=0, column=6, padx=8, sticky="w")

    # 联动逻辑
    def on_module_type_change(event=None):
        mtype = module_type_var.get()
        filtered_modules = [m for m in modules if m[2] == mtype]
        module_cb['values'] = [m[1] for m in filtered_modules]
        module_names_var.set("")
        tag_cb['values'] = []
        tag_names_var.set("")
    module_type_cb.bind("<<ComboboxSelected>>", on_module_type_change)

    def on_module_change(event=None):
        mname = module_names_var.get()
        filtered_tags = [t for t in tags if any(m[0] == t[2] and m[1] == mname for m in modules)]
        tag_cb['values'] = [t[1] for t in filtered_tags]
        tag_names_var.set("")
    module_cb.bind("<<ComboboxSelected>>", on_module_change)

    # 统计结果区（分布表格+题目清单表格）
    stat_frame = tk.Frame(main_frame)
    stat_frame.pack(fill=tk.BOTH, expand=True, pady=6)

    # 统计结果一行展示（题目分布+数量分布在同一行）
    stat_frame_top = tk.Frame(stat_frame)
    stat_frame_top.pack(anchor="w", pady=6, fill=tk.X)
    stat_label = tk.Label(stat_frame_top, text="题目分布：", font=("微软雅黑", 10))
    stat_label.pack(side=tk.LEFT, padx=(0,8))
    stat_text = tk.Label(stat_frame_top, font=("微软雅黑", 10), anchor="w", justify="left")
    stat_text.pack(side=tk.LEFT, fill=tk.X)

    # 分布表格（模块+标签+数量），第一行为只有该标签的题目数量
    style = ttk.Style()
    style.configure("Treeview.Heading", font=("微软雅黑", 10))
    style.configure("Treeview", font=("微软雅黑", 10))
    table = ttk.Treeview(stat_frame, columns=("模块类型", "模块", "标签", "题目数量"), show="headings", height=10, style="Treeview")
    table.heading("模块类型", text="模块类型")
    table.heading("模块", text="模块")
    table.heading("标签", text="标签")
    table.heading("题目数量", text="题目数量")
    table.column("模块类型", width=200)
    table.column("模块", width=200)
    table.column("标签", width=200)
    table.column("题目数量", width=200)
    table.pack(anchor="w", pady=2, fill=tk.X)

    # 题目清单表格及标签展示区
    id_table_frame = tk.Frame(stat_frame)
    id_table_frame.pack(anchor="w", pady=2, fill=tk.X)
    # 文案区（题目清单+标签）
    label_row = tk.Frame(id_table_frame)
    label_row.pack(fill=tk.X)
    id_label = tk.Label(label_row, text="题目清单：", font=("微软雅黑", 10))
    id_label.pack(side=tk.LEFT, padx=(0,10))
    tag_label = tk.Label(label_row, text="标签", font=("微软雅黑", 10))
    tag_label.pack(side=tk.LEFT, padx=(750+10,0))
    # 表格区
    id_table = ttk.Treeview(id_table_frame, columns=("题目ID",), show="headings", height=12, style="Treeview")
    id_table.heading("题目ID", text="题目ID")
    id_table.column("题目ID", width=750)
    id_table.pack(side=tk.LEFT, fill=tk.Y)
    # 标签展示区
    tag_info_frame = tk.Frame(id_table_frame)
    tag_info_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)

    # 右侧图片区
    img_frame = ImageFrame(root, width=600, height=1000)
    img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    # 查询逻辑
    def do_query():
        mtype = module_type_var.get()
        mname = module_names_var.get()
        tname = tag_names_var.get()
        tag_id = None
        for t in tags:
            if t[1] == tname:
                tag_id = t[0]
                break
        if not tag_id:
            messagebox.showwarning("警告", "请选择标签")
            return
        only_one, two_tags, three_tags, two_tag_group = query_tag_distribution(tag_id)
        # 统计结果文案
        stat_text.config(text=f"1个标签：{only_one}    2个标签：{two_tags}    3个标签：{three_tags}")
        # 分布表格填充
        for i in table.get_children():
            table.delete(i)
        # 第一行：只有该标签的题目数量
        tag_obj = next((t for t in tags if t[0] == tag_id), None)
        module_obj = next((m for m in modules if m[0] == tag_obj[2]), None) if tag_obj else None
        module_name = module_obj[1] if module_obj else ""
        table.insert('', 'end', values=(module_obj[2] if module_obj else "", module_name, tag_obj[1] if tag_obj else "", only_one), tags=("only_one",))
        # 其他分布，按模块ID+标签ID排序
        group_rows = []
        for other_tag_id, item_ids in two_tag_group.items():
            other_tag_obj = next((t for t in tags if t[0] == other_tag_id), None)
            other_module_obj = next((m for m in modules if m[0] == other_tag_obj[2]), None) if other_tag_obj else None
            other_module_type = other_module_obj[2] if other_module_obj else ""
            other_module_name = other_module_obj[1] if other_module_obj else ""
            group_rows.append((other_module_obj[0] if other_module_obj else "", other_tag_obj[0] if other_tag_obj else "", other_module_type, other_module_name, other_tag_obj[1] if other_tag_obj else "", len(item_ids), other_tag_id))
        group_rows.sort(key=lambda x: (x[0], x[1]))
        for _, _, mtype, mname, tname, count, other_tag_id in group_rows:
            table.insert('', 'end', values=(mtype, mname, tname, count), tags=(other_tag_id,))
        # 新增一行：3个及以上标签
        db_path = get_db_path()
        more_ids = []
        if db_path:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT item_id FROM item_tag_relations WHERE tag_id=?", (tag_id,))
                for row in cursor.fetchall():
                    cursor.execute("SELECT COUNT(*) FROM item_tag_relations WHERE item_id=?", (row[0],))
                    cnt = cursor.fetchone()[0]
                    if cnt >= 3:
                        more_ids.append(row[0])
                conn.close()
            except Exception:
                pass
        table.insert('', 'end', values=("-", "-", "3个及以上标签", len(more_ids)), tags=("more_tags",))
        # 清空题目清单
        for i in id_table.get_children():
            id_table.delete(i)
        img_frame.img_label.config(image='', text='此处为图片粘贴区域')
        img_frame.img_label.image = None
        img_frame.img_label._original_image = None
        img_frame.img_size_var.set("尺寸: -")
    query_btn.config(command=do_query)

    # 分布表格选中事件，展示对应题目ID
    def on_table_select(event):
        sel = table.selection()
        if not sel:
            for i in id_table.get_children():
                id_table.delete(i)
            return
        tag_key = table.item(sel[0], 'tags')[0]
        mtype = module_type_var.get()
        mname = module_names_var.get()
        tname = tag_names_var.get()
        tag_id = None
        for t in tags:
            if t[1] == tname:
                tag_id = t[0]
                break
        only_one, two_tags, three_tags, two_tag_group = query_tag_distribution(tag_id)
        item_ids = []
        if tag_key == "only_one":
            db_path = get_db_path()
            if db_path:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT item_id FROM item_tag_relations WHERE tag_id=?", (tag_id,))
                    for row in cursor.fetchall():
                        cursor.execute("SELECT COUNT(*) FROM item_tag_relations WHERE item_id=?", (row[0],))
                        cnt = cursor.fetchone()[0]
                        if cnt == 1:
                            item_ids.append(row[0])
                    conn.close()
                except Exception:
                    pass
        elif tag_key == "more_tags":
            db_path = get_db_path()
            if db_path:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT item_id FROM item_tag_relations WHERE tag_id=?", (tag_id,))
                    for row in cursor.fetchall():
                        cursor.execute("SELECT COUNT(*) FROM item_tag_relations WHERE item_id=?", (row[0],))
                        cnt = cursor.fetchone()[0]
                        if cnt >= 3:
                            item_ids.append(row[0])
                    conn.close()
                except Exception:
                    pass
        else:
            item_ids = two_tag_group.get(tag_key, [])
        for i in id_table.get_children():
            id_table.delete(i)
        for iid in item_ids:
            id_table.insert('', 'end', values=(iid,), tags=(iid,))
    table.bind("<<TreeviewSelect>>", on_table_select)

    # 题目ID表格选中事件，右侧预览图片（不弹窗）
    def on_id_select(event):
        sel = id_table.selection()
        if not sel:
            # 清空标签展示区
            for widget in tag_info_frame.winfo_children():
                widget.destroy()
            return
        item_id = id_table.item(sel[0], 'values')[0]
        preview_image(item_id, show_popup=False)
        # 查询该题目标记的所有标签
        db_path = get_db_path()
        tag_rows = []
        if db_path:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT t.tag_id, t.tag_name, m.module_type, m.module_name FROM item_tag_relations r LEFT JOIN tags t ON r.tag_id = t.tag_id LEFT JOIN modules m ON t.module_id = m.module_id WHERE r.item_id=?", (item_id,))
                tag_rows = cursor.fetchall()
                conn.close()
            except Exception:
                tag_rows = []
        # 在右侧标签展示区一行一个展示
        for widget in tag_info_frame.winfo_children():
            widget.destroy()
        for row in tag_rows:
            tk.Label(tag_info_frame, text=f"{row[2]} -- {row[3]} -- {row[1]}", anchor="w", font=("微软雅黑", 10)).pack(anchor="w")
    id_table.bind("<<TreeviewSelect>>", on_id_select)

    # 双击题目ID，跳转详情（只打开网页）
    def on_id_double(event):
        sel = id_table.selection()
        if not sel:
            return
        item_id = id_table.item(sel[0], 'values')[0]
        open_question_url(item_id)
    id_table.bind("<Double-1>", on_id_double)

    # 右键题目ID，复制ID，仅短暂提示
    def on_id_right(event):
        sel = id_table.selection()
        if not sel:
            return
        item_id = id_table.item(sel[0], 'values')[0]
        root.clipboard_clear()
        root.clipboard_append(item_id)
        root.update()
        # 显示短暂提示
        tip = tk.Toplevel(root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg="#f0f0f0")
        label = tk.Label(tip, text=f"题目ID已复制：{item_id}", bg="#f0f0f0", fg="#222", font=("微软雅黑", 12))
        label.pack(ipadx=20, ipady=10)
        tip.update_idletasks()
        x = root.winfo_rootx() + (root.winfo_width() - tip.winfo_width()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - tip.winfo_height()) // 2
        tip.geometry(f"+{x}+{y}")
        tip.after(1000, tip.destroy)
    id_table.bind("<Button-3>", on_id_right)

    # 图片预览复用，show_popup参数控制是否弹窗
    def preview_image(item_id, show_popup=True):
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
            try:
                from PIL import Image, ImageTk
                img = Image.open(img_path)
                max_w, max_h = 560, 800
                w, h = img.size
                scale = min(max_w/w, max_h/h, 1)
                try:
                    if scale < 1:
                        resample = Image.Resampling.LANCZOS
                        img_disp = img.resize((int(w*scale), int(h*scale)), resample)
                    else:
                        img_disp = img
                except AttributeError:
                    resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                    img_disp = img.resize((int(w*scale), int(h*scale)), resample)
                tk_img = ImageTk.PhotoImage(img_disp)
                img_frame.img_label.config(image=tk_img, text="")
                img_frame.img_label.image = tk_img
                img_frame.img_label._original_image = img.copy()
                img_frame.img_size_var.set(f"尺寸: {img.size[0]}x{img.size[1]}")
                if show_popup:
                    img_frame.show_image_popup()
            except Exception:
                pass
        else:
            img_frame.img_label.config(image='', text='此处为图片粘贴区域')
            img_frame.img_label.image = None
            img_frame.img_label._original_image = None
            img_frame.img_size_var.set("尺寸: -")

if __name__ == "__main__":
    item_query()
