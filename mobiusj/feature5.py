import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import config
import os
import uuid
import random
import json
import webbrowser

def get_db_path():
    settings = config.load_settings()
    data_path = settings.get("data_path", "")
    db_path = os.path.join(data_path, "mobius_data.sqlite3")
    return db_path

def get_modules():
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT module_id, module_name, module_type FROM modules")
            modules = cur.fetchall()
            return modules
    except Exception as e:
        print("获取模块异常:", e)
        return []

def get_tags_by_module(module_id):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT tag_id, tag_name FROM tags WHERE module_id=?", (module_id,))
            tags = cur.fetchall()
            return tags
    except Exception as e:
        print("获取标签异常:", e)
        return []

def get_clusters(module_id=None, tag_id=None, cluster_name=None):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            sql = """
                SELECT c.cluster_id, m.module_type, m.module_name, t.tag_name, c.cluster_name, c.cluster_intro
                FROM clusters c
                LEFT JOIN modules m ON c.module_id = m.module_id
                LEFT JOIN tags t ON c.tag_id = t.tag_id
                WHERE 1=1
            """
            params = []
            if module_id:
                sql += " AND c.module_id=?"
                params.append(module_id)
            if tag_id:
                sql += " AND c.tag_id=?"
                params.append(tag_id)
            if cluster_name:
                sql += " AND c.cluster_name LIKE ?"
                params.append(f"%{cluster_name}%")
            cur.execute(sql, params)
            clusters = cur.fetchall()
            return clusters
    except Exception as e:
        print("获取题簇异常:", e)
        return []

def get_group_counts(cluster_id):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), group_level FROM groups WHERE cluster_id=? GROUP BY group_level", (cluster_id,))
            data = cur.fetchall()
            total = sum([x[0] for x in data])
            # 修正统计逻辑，key为level，value为count
            level_counts = {level: count for count, level in data}
            return total, level_counts
    except Exception as e:
        print("统计题组数量异常:", e)
        return 0, {}

def generate_group_id():
    # 生成6位数字字符串
    return "{:06d}".format(random.randint(0, 999999))

def generate_cluster_id():
    # 生成6位数字字符串
    return "{:06d}".format(random.randint(0, 999999))

def insert_cluster(module_id, tag_id, cluster_name, cluster_intro, groups):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # 使用6位数字生成唯一cluster_id
            next_id = generate_cluster_id()
            cur.execute("INSERT INTO clusters (cluster_id, module_id, tag_id, cluster_name, cluster_intro) VALUES (?, ?, ?, ?, ?)",
                        (next_id, module_id, tag_id, cluster_name, cluster_intro))
            for g in groups:
                next_gid = generate_group_id()
                cur.execute("INSERT INTO groups (group_id, group_name, group_level, cluster_id, group_intro) VALUES (?, ?, ?, ?, ?)",
                            (next_gid, g['group_name'], g['group_level'], next_id, g['group_intro']))
                for item_id in g['examples']:
                    cur.execute("INSERT INTO group_examples (group_id, item_id) VALUES (?, ?)", (next_gid, item_id))
                for item_id in g['exercises']:
                    cur.execute("INSERT INTO group_exercises (group_id, item_id) VALUES (?, ?)", (next_gid, item_id))
            conn.commit()
    except Exception as e:
        print("插入题簇异常:", e)
        messagebox.showerror("错误", f"插入题簇异常: {e}")

def get_cluster_detail(cluster_name):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT cluster_id, module_id, tag_id, cluster_name, cluster_intro
                FROM clusters WHERE cluster_name=?
            """, (cluster_name,))
            cluster = cur.fetchone()
            return cluster
    except Exception as e:
        print("获取题簇详情异常:", e)
        return None

def get_groups_by_cluster(cluster_id):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT group_id, group_name, group_level, group_intro
                FROM groups WHERE cluster_id=?
            """, (cluster_id,))
            groups = []
            for gid, gname, glevel, gintro in cur.fetchall():
                # 获取例题
                cur.execute("SELECT item_id FROM group_examples WHERE group_id=?", (gid,))
                examples = [row[0] for row in cur.fetchall()]
                # 获取练习
                cur.execute("SELECT item_id FROM group_exercises WHERE group_id=?", (gid,))
                exercises = [row[0] for row in cur.fetchall()]
                groups.append({
                    "group_id": gid,
                    "group_name": gname,
                    "group_level": glevel,
                    "group_intro": gintro,
                    "examples": examples,
                    "exercises": exercises
                })
            return groups
    except Exception as e:
        print("获取题组详情异常:", e)
        return []

def update_cluster(cluster_id, module_id, tag_id, cluster_name, cluster_intro, groups):
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE clusters SET module_id=?, tag_id=?, cluster_name=?, cluster_intro=? WHERE cluster_id=?",
                        (module_id, tag_id, cluster_name, cluster_intro, cluster_id))
            # 删除原有题组及关联
            cur.execute("SELECT group_id FROM groups WHERE cluster_id=?", (cluster_id,))
            old_gids = [row[0] for row in cur.fetchall()]
            for gid in old_gids:
                cur.execute("DELETE FROM group_examples WHERE group_id=?", (gid,))
                cur.execute("DELETE FROM group_exercises WHERE group_id=?", (gid,))
            cur.execute("DELETE FROM groups WHERE cluster_id=?", (cluster_id,))
            # 重新插入题组及关联
            for g in groups:
                next_gid = generate_group_id()
                cur.execute("INSERT INTO groups (group_id, group_name, group_level, cluster_id, group_intro) VALUES (?, ?, ?, ?, ?)",
                            (next_gid, g['group_name'], g['group_level'], cluster_id, g['group_intro']))
                for item_id in g['examples']:
                    cur.execute("INSERT INTO group_examples (group_id, item_id) VALUES (?, ?)", (next_gid, item_id))
                for item_id in g['exercises']:
                    cur.execute("INSERT INTO group_exercises (group_id, item_id) VALUES (?, ?)", (next_gid, item_id))
            conn.commit()
    except Exception as e:
        print("更新题簇异常:", e)
        messagebox.showerror("错误", f"更新题簇异常: {e}")

def load_subject_param():
    # 读取settings.json中的subject_param
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            return settings.get("subject_param", "physics")
    except Exception:
        return "physics"

def get_students():
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT student_id, student_name FROM students")
            return cur.fetchall()
    except Exception as e:
        print("获取学生名单异常:", e)
        return []

def mark_student_item(student_id, item_id):
    db_path = get_db_path()
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO student_item_relations (student_id, item_id, date_created) VALUES (?, ?, ?)",
                (student_id, item_id, now)
            )
            conn.commit()
    except Exception as e:
        print("标记学生题目关系异常:", e)
        messagebox.showerror("错误", f"标记失败: {e}")

def show_items_popup(parent, title, items, subject_param):
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.geometry("650x420")  # 宽度略增
    frame = tk.Frame(popup)
    frame.pack(fill="both", expand=True, padx=15, pady=15)
    for idx, item_id in enumerate(items):
        row = tk.Frame(frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=item_id, width=50, anchor="w").pack(side="left")
        # 按钮组合区，右对齐，距离右边界5px
        btn_group = tk.Frame(row)
        btn_group.pack(side="right", padx=(0,5))
        def make_open_url(item_id):
            def open_url():
                url = f"https://www.jyeoo.com/{subject_param}/ques/detail/{item_id}"
                webbrowser.open(url)
            return open_url
        tk.Button(btn_group, text="查看", command=make_open_url(item_id), width=4).pack(side="left")
        def make_mark(item_id):
            def mark():
                students = get_students()
                if not students:
                    messagebox.showerror("错误", "未找到学生名单")
                    return
                sel_win = tk.Toplevel(popup)
                sel_win.title("选择学生")
                sel_win.geometry("320x220")
                tk.Label(sel_win, text="请选择学生进行标记：").pack(pady=10)
                student_var = tk.StringVar()
                names = [s[1] for s in students]
                cb = ttk.Combobox(sel_win, values=names, textvariable=student_var, state="readonly", width=18)
                cb.pack(pady=10)
                def do_mark():
                    name = student_var.get()
                    if not name:
                        messagebox.showerror("错误", "请选择学生")
                        return
                    student_id = next((s[0] for s in students if s[1] == name), None)
                    if not student_id:
                        messagebox.showerror("错误", "学生ID未找到")
                        return
                    mark_student_item(student_id, item_id)
                    messagebox.showinfo("成功", f"已标记学生【{name}】与题目ID【{item_id}】")
                    sel_win.destroy()
                tk.Button(sel_win, text="标记", command=do_mark, width=10).pack(pady=10)
            return mark
        tk.Button(btn_group, text="标记", command=make_mark(item_id), width=4).pack(side="left", padx=(2,0))
    def on_close():
        popup.destroy()
    popup.protocol("WM_DELETE_WINDOW", on_close)

def cluster_management():
    try:
        win = tk.Toplevel()
        win.title("题簇管理")
        win.geometry("1100x600")
        win.lift()
        win.focus_force()

        def on_close():
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        # 查询区
        query_frame = tk.LabelFrame(win, text="查询题簇")
        query_frame.pack(fill="x", padx=10, pady=5)

        modules = get_modules()
        if not modules:
            messagebox.showerror("错误", "未获取到模块，请检查数据库内容。")
            win.destroy()
            return

        module_choices = [""] + [f"{m[1]}（{m[2]}）" for m in modules]
        module_id_map = {f"{m[1]}（{m[2]}）": m[0] for m in modules}

        module_var = tk.StringVar()
        tag_var = tk.StringVar()
        cluster_name_var = tk.StringVar()

        ttk.Label(query_frame, text="模块:").grid(row=0, column=0, padx=5, pady=5)
        module_cb = ttk.Combobox(query_frame, values=module_choices, textvariable=module_var, state="readonly", width=18)
        module_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(query_frame, text="标签:").grid(row=0, column=2, padx=5, pady=5)
        tag_cb = ttk.Combobox(query_frame, values=[""], textvariable=tag_var, state="readonly", width=18)
        tag_cb.grid(row=0, column=3, padx=5, pady=5)

        def update_tags(*_):
            sel = module_var.get()
            if sel and sel in module_id_map:
                tags = get_tags_by_module(module_id_map[sel])
                tag_cb["values"] = [""] + [t[1] for t in tags]
            else:
                tag_cb["values"] = [""]
            tag_var.set("")
        module_cb.bind("<<ComboboxSelected>>", update_tags)

        ttk.Label(query_frame, text="题簇名称:").grid(row=0, column=4, padx=5, pady=5)
        cluster_entry = ttk.Entry(query_frame, textvariable=cluster_name_var, width=18)
        cluster_entry.grid(row=0, column=5, padx=5, pady=5)

        def do_query():
            module_id = module_id_map.get(module_var.get(), None)
            tag_id = None
            if tag_var.get():
                tags = get_tags_by_module(module_id) if module_id else []
                tag_id = next((str(t[0]) for t in tags if t[1] == tag_var.get()), None)
            cname = cluster_name_var.get()
            clusters = get_clusters(module_id, tag_id, cname)
            for i in tree.get_children():
                tree.delete(i)
            for c in clusters:
                total, level_counts = get_group_counts(c[0])
                levels = ["基础", "进阶", "疯狂", "暴躁"]
                # 新增：各层次数量分别展示
                level_nums = [level_counts.get(l, 0) for l in levels]
                tree.insert(
                    "",
                    "end",
                    values=(
                        c[1], c[2], c[3] or "", c[4], total,
                        level_nums[0], level_nums[1], level_nums[2], level_nums[3],
                        c[5]
                    )
                )
            # 如果没有数据，显示一行提示
            if not clusters:
                tree.insert(
                    "",
                    "end",
                    values=(
                        "", "", "", "", "", "", "", "", "", "（暂无题簇数据）"
                    )
                )
            print(clusters)  # 在末尾添加此行，输出查询结果
        # 查询区按钮（只保留 tk.Button 版本）
        btn_query = tk.Button(query_frame, text="查询", command=do_query, width=7)
        btn_query.grid(row=0, column=6, padx=10, pady=5)
        btn_add_cluster = tk.Button(query_frame, text="添加题簇", command=lambda: open_add_cluster(), width=7)
        btn_add_cluster.grid(row=0, column=7, padx=10, pady=5)

        # 结果区
        columns = (
            "模块类型", "模块名称", "标签名称", "题簇名称", "题组数量",
            "基础数量", "进阶数量", "疯狂数量", "暴躁数量", "题簇介绍"
        )
        tree = ttk.Treeview(win, columns=columns, show="headings", height=15)
        # 设置列宽
        col_widths = {
            "模块类型": 120,
            "模块名称": 120,
            "标签名称": 120,
            "题簇名称": 120,
            "题组数量": 70,      # 缩小
            "基础数量": 70,
            "进阶数量": 70,
            "疯狂数量": 70,
            "暴躁数量": 70,
            "题簇介绍": 220      # 增大
        }
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=col_widths.get(col, 120))
        tree.pack(fill="both", expand=True, padx=10, pady=5)

        # 公共题组编辑弹窗
        def open_group_editor(parent_win, group_data, on_save):
            group_win = tk.Toplevel(parent_win)
            group_win.title("编辑题组" if group_data else "添加题组")
            group_win.geometry("850x420")

            def on_group_close():
                group_win.destroy()
            group_win.protocol("WM_DELETE_WINDOW", on_group_close)

            group_name_var = tk.StringVar(value=group_data["group_name"] if group_data else "")
            group_level_var = tk.StringVar(value=group_data["group_level"] if group_data else "")
            group_intro_var = tk.StringVar(value=group_data["group_intro"] if group_data else "")

            top_frame = tk.Frame(group_win)
            top_frame.pack(fill="x", padx=15, pady=10)
            mid_frame = tk.Frame(group_win)
            mid_frame.pack(fill="x", padx=15, pady=5)
            text_row_frame = tk.Frame(group_win)
            text_row_frame.pack(fill="x", padx=15, pady=5)
            btn_frame = tk.Frame(group_win)
            btn_frame.pack(fill="x", padx=15, pady=15)

            tk.Label(top_frame, text="题组名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
            ttk.Entry(top_frame, textvariable=group_name_var, width=20).grid(row=0, column=1, padx=5, pady=5, sticky="w")

            tk.Label(top_frame, text="题组层次:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
            levels = ["基础", "进阶", "疯狂", "暴躁"]
            ttk.Combobox(top_frame, values=levels, textvariable=group_level_var, state="readonly", width=15).grid(row=0, column=3, padx=5, pady=5, sticky="w")

            tk.Label(mid_frame, text="题组介绍:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
            ttk.Entry(mid_frame, textvariable=group_intro_var, width=30).grid(row=0, column=1, padx=5, pady=5, sticky="w")

            example_frame = tk.Frame(text_row_frame)
            example_frame.pack(side="left", fill="y", expand=True, padx=5)
            exercise_frame = tk.Frame(text_row_frame)
            exercise_frame.pack(side="left", fill="y", expand=True, padx=5)

            tk.Label(example_frame, text="题组例题(每行一个ID):").pack(anchor="w", pady=(0,2))
            examples_text = tk.Text(example_frame, height=14, width=56)
            examples_text.pack(fill="x")
            if group_data:
                examples_text.insert("1.0", "\n".join(group_data["examples"]))

            tk.Label(exercise_frame, text="题组练习(每行一个ID):").pack(anchor="w", pady=(0,2))
            exercises_text = tk.Text(exercise_frame, height=14, width=56)
            exercises_text.pack(fill="x")
            if group_data:
                exercises_text.insert("1.0", "\n".join(group_data["exercises"]))

            def save_group():
                gname = group_name_var.get()
                glevel = group_level_var.get()
                gintro = group_intro_var.get()
                examples = [x.strip() for x in examples_text.get("1.0", "end").splitlines() if x.strip()]
                exercises = [x.strip() for x in exercises_text.get("1.0", "end").splitlines() if x.strip()]
                if not gname or not glevel:
                    messagebox.showerror("错误", "题组名称和层次不能为空")
                    return
                all_ids = examples + exercises
                if len(set(examples)) != len(examples):
                    messagebox.showerror("错误", "题组例题中有重复题目ID")
                    return
                if len(set(exercises)) != len(exercises):
                    messagebox.showerror("错误", "题组练习中有重复题目ID")
                    return
                if len(set(all_ids)) != len(all_ids):
                    messagebox.showerror("错误", "题组例题和练习之间有重复题目ID")
                    return
                # 交由on_save回调做冲突检查
                new_group = {
                    "group_name": gname,
                    "group_level": glevel,
                    "group_intro": gintro,
                    "examples": examples,
                    "exercises": exercises
                }
                if not on_save(new_group):
                    return
                group_win.destroy()

            btn_save_group = tk.Button(btn_frame, text="保存", command=save_group, width=10)
            btn_save_group.pack(pady=10)

        # 新增：添加题簇按钮
        def open_add_cluster():
            try:
                add_win = tk.Toplevel(win)
                add_win.title("添加题簇")
                add_win.geometry("580x640")  # 改为与编辑弹层一致
                add_win.lift()
                add_win.focus_force()

                def on_add_close():
                    add_win.destroy()
                add_win.protocol("WM_DELETE_WINDOW", on_add_close)

                add_module_var = tk.StringVar()
                add_tag_var = tk.StringVar()
                add_name_var = tk.StringVar()
                add_intro_var = tk.StringVar()

                top_frame = tk.Frame(add_win)
                top_frame.pack(fill="x", padx=15, pady=10)
                mid_frame = tk.Frame(add_win)
                mid_frame.pack(fill="x", padx=15, pady=5)
                group_frame = tk.Frame(add_win)
                group_frame.pack(fill="x", padx=15, pady=5)
                # 新增题组列表展示区
                group_list_frame = tk.Frame(add_win)
                group_list_frame.pack(fill="both", padx=15, pady=5)
                btn_frame = tk.Frame(add_win)
                btn_frame.pack(fill="x", padx=15, pady=15)

                tk.Label(top_frame, text="模块:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
                add_module_cb = ttk.Combobox(top_frame, values=module_choices, textvariable=add_module_var, state="readonly", width=18)
                add_module_cb.grid(row=0, column=1, padx=5, pady=5, sticky="w")

                tk.Label(top_frame, text="标签:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
                add_tag_cb = ttk.Combobox(top_frame, values=[""], textvariable=add_tag_var, state="readonly", width=18)
                add_tag_cb.grid(row=0, column=3, padx=5, pady=5, sticky="w")

                def update_add_tags(*_):
                    sel = add_module_var.get()
                    if sel and sel in module_id_map:
                        tags = get_tags_by_module(module_id_map[sel])
                        add_tag_cb["values"] = [""] + [t[1] for t in tags]
                    else:
                        add_tag_cb["values"] = [""]
                    add_tag_var.set("")
                add_module_cb.bind("<<ComboboxSelected>>", update_add_tags)

                tk.Label(mid_frame, text="题簇名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
                name_entry = ttk.Entry(mid_frame, textvariable=add_name_var, width=22)
                name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

                tk.Label(mid_frame, text="题簇介绍:").grid(row=1, column=0, padx=5, pady=5, sticky="ne")
                # 用Text替换Entry，高度3倍
                intro_text = tk.Text(mid_frame, height=6, width=32)
                intro_text.grid(row=1, column=1, padx=5, pady=5, sticky="w")
                # intro_entry = ttk.Entry(mid_frame, textvariable=add_intro_var, width=30)
                # intro_entry.grid(row=3, column=1, padx=5, pady=5)

                groups = []
                subject_param = load_subject_param()  # 用于弹层显示

                def refresh_group_list():
                    for widget in group_list_frame.winfo_children():
                        widget.destroy()
                    if not groups:
                        tk.Label(group_list_frame, text="暂无题组，请添加。", fg="gray").pack()
                        return
                    header = tk.Frame(group_list_frame)
                    header.pack(fill="x")
                    tk.Label(header, text="题组名称", width=14, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0)
                    tk.Label(header, text="层次", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=1)
                    tk.Label(header, text="例题数", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=2)
                    tk.Label(header, text="练习数", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=3)
                    tk.Label(header, text="操作", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=4)
                    for idx, g in enumerate(groups):
                        row = tk.Frame(group_list_frame)
                        row.pack(fill="x", pady=2)
                        tk.Label(row, text=g["group_name"], width=14, anchor="w").grid(row=0, column=0)
                        tk.Label(row, text=g["group_level"], width=8, anchor="w").grid(row=0, column=1)
                        # 例题数Label，支持双击弹层
                        example_label = tk.Label(row, text=str(len(g["examples"])), width=8, anchor="w", fg="blue", cursor="hand2")
                        example_label.grid(row=0, column=2)
                        def make_show_examples(idx):
                            def show_examples(event):
                                title = f"{groups[idx]['group_name']}-{groups[idx]['group_level']}-例题"
                                show_items_popup(add_win, title, groups[idx]["examples"], subject_param)
                            return show_examples
                        example_label.bind("<Double-Button-1>", make_show_examples(idx))
                        # 练习数Label，支持双击弹层
                        exercise_label = tk.Label(row, text=str(len(g["exercises"])), width=8, anchor="w", fg="blue", cursor="hand2")
                        exercise_label.grid(row=0, column=3)
                        def make_show_exercises(idx):
                            def show_exercises(event):
                                title = f"{groups[idx]['group_name']}-{groups[idx]['group_level']}-练习"
                                show_items_popup(add_win, title, groups[idx]["exercises"], subject_param)
                            return show_exercises
                        exercise_label.bind("<Double-Button-1>", make_show_exercises(idx))
                        def make_del(idx):
                            return lambda: (groups.pop(idx), refresh_group_list())
                        tk.Button(row, text="删除", command=make_del(idx), width=6).grid(row=0, column=4, padx=(0,2))
                        def make_edit(idx):
                            def edit_group():
                                def on_save(new_group):
                                    # 冲突检查
                                    used_ids = set()
                                    for i, gg in enumerate(groups):
                                        if i == idx:
                                            continue
                                        used_ids.update(gg.get("examples", []))
                                        used_ids.update(gg.get("exercises", []))
                                    all_ids = new_group["examples"] + new_group["exercises"]
                                    conflict_ids = set(all_ids) & used_ids
                                    if conflict_ids:
                                        messagebox.showerror("错误", f"以下题目ID已在本题簇其他题组中出现：{', '.join(conflict_ids)}")
                                        return False
                                    groups[idx] = new_group
                                    refresh_group_list()
                                    return True
                                open_group_editor(add_win, groups[idx], on_save)
                            return edit_group
                        tk.Button(row, text="修改", command=make_edit(idx), width=6).grid(row=0, column=5)

                def add_group():
                    def on_save(new_group):
                        # 冲突检查
                        used_ids = set()
                        for gg in groups:
                            used_ids.update(gg.get("examples", []))
                            used_ids.update(gg.get("exercises", []))
                        all_ids = new_group["examples"] + new_group["exercises"]
                        conflict_ids = set(all_ids) & used_ids
                        if conflict_ids:
                            messagebox.showerror("错误", f"以下题目ID已在本题簇其他题组中出现：{', '.join(conflict_ids)}")
                            return False
                        groups.append(new_group)
                        refresh_group_list()
                        return True
                    open_group_editor(add_win, None, on_save)

                add_group_btn = tk.Button(group_frame, text="添加题组", command=add_group, width=10)
                add_group_btn.pack(pady=5)

                # 初始化题组列表展示
                refresh_group_list()

                def save_cluster():
                    msel = add_module_var.get()
                    tsel = add_tag_var.get()
                    cname = add_name_var.get()
                    cintro = intro_text.get("1.0", "end").strip()
                    if not msel or not cname:
                        messagebox.showerror("错误", "模块和题簇名称不能为空")
                        return
                    if len(cname) > 20:
                        messagebox.showerror("错误", "题簇名称不能超过20字符")
                        return
                    if len(cintro) > 100:
                        messagebox.showerror("错误", "题簇介绍不能超过100字符")
                        return
                    module_id = module_id_map[msel]
                    tag_id = None
                    if tsel:
                        tags = get_tags_by_module(module_id) if module_id else []
                        tag_id = next((str(t[0]) for t in tags if t[1] == tsel), None)
                    if not groups:
                        messagebox.showerror("错误", "请至少添加一个题组")
                        return
                    insert_cluster(module_id, tag_id, cname, cintro, groups)
                    messagebox.showinfo("成功", "题簇添加成功")
                    add_win.destroy()
                    do_query()  # 添加此行，刷新主界面表格

                save_cluster_btn = tk.Button(btn_frame, text="保存题簇", command=save_cluster, width=10)
                save_cluster_btn.pack(pady=10)

                # 如果没有模块，禁用所有输入控件并提示
                if not modules:
                    add_module_cb.config(state="disabled")
                    add_tag_cb.config(state="disabled")
                    name_entry.config(state="disabled")
                    intro_text.config(state="disabled")
                    add_group_btn.config(state="disabled")
                    save_cluster_btn.config(state="disabled")
                    tk.Label(add_win, text="请先在模块管理中添加模块，才能创建题簇。", fg="red").pack(pady=30)
            except Exception as e:
                print("添加题簇弹层异常:", e)
                add_win.destroy()
        # 新增按钮放在筛选按钮后
        # ttk.Button(win, text="添加题簇", command=open_add_cluster).pack(pady=10)
        # 修改为 tk.Button，统一宽度和布局
        # btn_add_cluster = tk.Button(win, text="添加题簇", command=open_add_cluster, width=10)
        # btn_add_cluster.pack(pady=10)

        # 默认查询一次
        do_query()

        # 新增：双击表格行弹出编辑窗口
        def on_tree_double_click(event):
            item = tree.identify_row(event.y)
            if not item:
                return
            values = tree.item(item, "values")
            cluster_name = values[3]
            if not cluster_name or cluster_name == "（暂无题簇数据）":
                return
            cluster = get_cluster_detail(cluster_name)
            if not cluster:
                messagebox.showerror("错误", "未找到该题簇详情")
                return
            cluster_id, module_id, tag_id, cluster_name, cluster_intro = cluster
            groups_data = get_groups_by_cluster(cluster_id)

            edit_win = tk.Toplevel(win)
            edit_win.title(f"编辑题簇：{cluster_name}")
            edit_win.geometry("580x640")
            edit_win.lift()
            edit_win.focus_force()

            def on_edit_close():
                edit_win.destroy()
            edit_win.protocol("WM_DELETE_WINDOW", on_edit_close)

            edit_module_var = tk.StringVar()
            edit_tag_var = tk.StringVar()
            edit_name_var = tk.StringVar()
            edit_intro_var = tk.StringVar()

            top_frame = tk.Frame(edit_win)
            top_frame.pack(fill="x", padx=15, pady=10)
            mid_frame = tk.Frame(edit_win)
            mid_frame.pack(fill="x", padx=15, pady=5)
            group_frame = tk.Frame(edit_win)
            group_frame.pack(fill="x", padx=15, pady=5)
            group_list_frame = tk.Frame(edit_win)
            group_list_frame.pack(fill="both", padx=15, pady=5)
            btn_frame = tk.Frame(edit_win)
            btn_frame.pack(fill="x", padx=15, pady=15)

            tk.Label(top_frame, text="模块:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
            edit_module_cb = ttk.Combobox(top_frame, values=module_choices, textvariable=edit_module_var, state="readonly", width=18)
            edit_module_cb.grid(row=0, column=1, padx=5, pady=5, sticky="w")

            tk.Label(top_frame, text="标签:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
            edit_tag_cb = ttk.Combobox(top_frame, values=[""], textvariable=edit_tag_var, state="readonly", width=18)
            edit_tag_cb.grid(row=0, column=3, padx=5, pady=5, sticky="w")

            def update_edit_tags(*_):
                sel = edit_module_var.get()
                if sel and sel in module_id_map:
                    tags = get_tags_by_module(module_id_map[sel])
                    edit_tag_cb["values"] = [""] + [t[1] for t in tags]
                else:
                    edit_tag_cb["values"] = [""]
                edit_tag_var.set("")
            edit_module_cb.bind("<<ComboboxSelected>>", update_edit_tags)

            tk.Label(mid_frame, text="题簇名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
            name_entry = ttk.Entry(mid_frame, textvariable=edit_name_var, width=22)
            name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

            tk.Label(mid_frame, text="题簇介绍:").grid(row=1, column=0, padx=5, pady=5, sticky="ne")
            intro_text = tk.Text(mid_frame, height=6, width=32)
            intro_text.grid(row=1, column=1, padx=5, pady=5, sticky="w")

            # 初始化变量
            # 反查 module_choices
            module_val = next((k for k, v in module_id_map.items() if v == module_id), "")
            edit_module_var.set(module_val)
            update_edit_tags()
            if tag_id:
                tags = get_tags_by_module(module_id)
                tag_val = next((t[1] for t in tags if str(t[0]) == str(tag_id)), "")
                edit_tag_var.set(tag_val)
            else:
                edit_tag_var.set("")
            edit_name_var.set(cluster_name)
            intro_text.delete("1.0", "end")
            intro_text.insert("1.0", cluster_intro or "")

            groups = []
            for g in groups_data:
                groups.append({
                    "group_name": g["group_name"],
                    "group_level": g["group_level"],
                    "group_intro": g["group_intro"],
                    "examples": g["examples"],
                    "exercises": g["exercises"]
                })

            subject_param = load_subject_param()

            def refresh_group_list():
                for widget in group_list_frame.winfo_children():
                    widget.destroy()
                if not groups:
                    tk.Label(group_list_frame, text="暂无题组，请添加。", fg="gray").pack()
                    return
                header = tk.Frame(group_list_frame)
                header.pack(fill="x")
                tk.Label(header, text="题组名称", width=14, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0)
                tk.Label(header, text="层次", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=1)
                tk.Label(header, text="例题数", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=2)
                tk.Label(header, text="练习数", width=8, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=3)
                tk.Label(header, text="操作", width=18, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=4)
                for idx, g in enumerate(groups):
                    row = tk.Frame(group_list_frame)
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=g["group_name"], width=14, anchor="w").grid(row=0, column=0)
                    tk.Label(row, text=g["group_level"], width=8, anchor="w").grid(row=0, column=1)
                    # 例题数Label，支持双击
                    example_label = tk.Label(row, text=str(len(g["examples"])), width=8, anchor="w", fg="blue", cursor="hand2")
                    example_label.grid(row=0, column=2)
                    def make_show_examples(idx):
                        def show_examples(event):
                            title = f"{cluster_name}-{groups[idx]['group_name']}-{groups[idx]['group_level']}-例题"
                            show_items_popup(edit_win, title, groups[idx]["examples"], subject_param)
                        return show_examples
                    example_label.bind("<Double-Button-1>", make_show_examples(idx))
                    # 练习数Label，支持双击
                    exercise_label = tk.Label(row, text=str(len(g["exercises"])), width=8, anchor="w", fg="blue", cursor="hand2")
                    exercise_label.grid(row=0, column=3)
                    def make_show_exercises(idx):
                        def show_exercises(event):
                            title = f"{cluster_name}-{groups[idx]['group_name']}-{groups[idx]['group_level']}-练习"
                            show_items_popup(edit_win, title, groups[idx]["exercises"], subject_param)
                        return show_exercises
                    exercise_label.bind("<Double-Button-1>", make_show_exercises(idx))
                    def make_del(idx):
                        return lambda: (groups.pop(idx), refresh_group_list())
                    tk.Button(row, text="删除", command=make_del(idx), width=6).grid(row=0, column=4, padx=(0,2))
                    def make_edit(idx):
                        def edit_group():
                            def on_save(new_group):
                                used_ids = set()
                                for i, gg in enumerate(groups):
                                    if i == idx:
                                        continue
                                    used_ids.update(gg.get("examples", []))
                                    used_ids.update(gg.get("exercises", []))
                                all_ids = new_group["examples"] + new_group["exercises"]
                                conflict_ids = set(all_ids) & used_ids
                                if conflict_ids:
                                    messagebox.showerror("错误", f"以下题目ID已在本题簇其他题组中出现：{', '.join(conflict_ids)}")
                                    return False
                                groups[idx] = new_group
                                refresh_group_list()
                                return True
                            open_group_editor(edit_win, groups[idx], on_save)
                        return edit_group
                    tk.Button(row, text="修改", command=make_edit(idx), width=6).grid(row=0, column=5)

            def add_group():
                def on_save(new_group):
                    used_ids = set()
                    for gg in groups:
                        used_ids.update(gg.get("examples", []))
                        used_ids.update(gg.get("exercises", []))
                    all_ids = new_group["examples"] + new_group["exercises"]
                    conflict_ids = set(all_ids) & used_ids
                    if conflict_ids:
                        messagebox.showerror("错误", f"以下题目ID已在本题簇其他题组中出现：{', '.join(conflict_ids)}")
                        return False
                    groups.append(new_group)
                    refresh_group_list()
                    return True
                open_group_editor(edit_win, None, on_save)

            add_group_btn = tk.Button(group_frame, text="添加题组", command=add_group, width=10)
            add_group_btn.pack(pady=5)
            refresh_group_list()

            def save_cluster():
                msel = edit_module_var.get()
                tsel = edit_tag_var.get()
                cname = edit_name_var.get()
                cintro = intro_text.get("1.0", "end").strip()
                if not msel or not cname:
                    messagebox.showerror("错误", "模块和题簇名称不能为空")
                    return
                if len(cname) > 20:
                    messagebox.showerror("错误", "题簇名称不能超过20字符")
                    return
                if len(cintro) > 100:
                    messagebox.showerror("错误", "题簇介绍不能超过100字符")
                    return
                module_id_val = module_id_map[msel]
                tag_id_val = None
                if tsel:
                    tags = get_tags_by_module(module_id_val) if module_id_val else []
                    tag_id_val = next((str(t[0]) for t in tags if t[1] == tsel), None)
                if not groups:
                    messagebox.showerror("错误", "请至少添加一个题组")
                    return
                update_cluster(cluster_id, module_id_val, tag_id_val, cname, cintro, groups)
                messagebox.showinfo("成功", "题簇修改成功")
                do_query()  # 新增：保存后刷新表格
                edit_win.destroy()

            save_cluster_btn = tk.Button(btn_frame, text="保存修改", command=save_cluster, width=10)
            save_cluster_btn.pack(pady=10)

            # 如果没有模块，禁用所有输入控件并提示
            if not modules:
                edit_module_cb.config(state="disabled")
                edit_tag_cb.config(state="disabled")
                name_entry.config(state="disabled")
                intro_text.config(state="disabled")
                add_group_btn.config(state="disabled")
                save_cluster_btn.config(state="disabled")
                tk.Label(edit_win, text="请先在模块管理中添加模块，才能编辑题簇。", fg="red").pack(pady=30)

        tree.bind("<Double-1>", on_tree_double_click)
        # 修复：补全 try-except
        # 原来最后一行是 try:，没有 except
        # 这里直接补全
    except Exception as e:
        print("题簇管理窗口异常:", e)