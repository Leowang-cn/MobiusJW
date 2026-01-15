import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import feature4

DB_FILENAME = feature4.DB_FILENAME

def get_db():
    settings_file = feature4.config.load_settings_path()
    with open(settings_file, "r", encoding="utf-8") as f:
        settings = feature4.json.load(f)
    db_path = feature4.get_db_path(settings.get("data_path", ""))
    return sqlite3.connect(db_path)

def TF_question_management():
    win = tk.Toplevel()
    win.title("判断题管理")
    win.geometry("900x600")
    win.resizable(False, False)

    # --- 添加判断题按钮（放在筛选条件上方） ---
    add_btn = tk.Button(win, text="添加判断题", command=lambda: open_add_edit_dialog())
    add_btn.pack(pady=(10, 0))

    # --- 筛选区域 ---
    filter_frame = tk.LabelFrame(win, text="筛选条件", padx=10, pady=10)
    filter_frame.pack(fill="x", padx=10, pady=5)

    # 下拉框变量
    var_module_type = tk.StringVar(value="")
    var_module_name = tk.StringVar()
    var_tag_name = tk.StringVar()

    # 级联下拉框数据
    def get_module_types():
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT module_type FROM modules")
            return [row[0] for row in cur.fetchall()]
    def get_module_names(module_type=None):
        with get_db() as conn:
            cur = conn.cursor()
            if module_type:
                cur.execute("SELECT module_name FROM modules WHERE module_type=?", (module_type,))
            else:
                cur.execute("SELECT module_name FROM modules")
            return [row[0] for row in cur.fetchall()]
    def get_tag_names(module_name=None):
        with get_db() as conn:
            cur = conn.cursor()
            if module_name:
                cur.execute("SELECT tag_name FROM tags WHERE module_id=(SELECT module_id FROM modules WHERE module_name=?)", (module_name,))
            else:
                cur.execute("SELECT tag_name FROM tags")
            return [row[0] for row in cur.fetchall()]

    # 级联逻辑
    def on_module_type_change(*_):
        module_type = var_module_type.get() or None
        names = get_module_names(module_type)
        module_name_cb['values'] = names
        var_module_name.set('')
        tag_name_cb['values'] = []
        var_tag_name.set('')
    def on_module_name_change(*_):
        tags = get_tag_names(var_module_name.get())
        tag_name_cb['values'] = tags
        var_tag_name.set('')

    tk.Label(filter_frame, text="模块类型:").grid(row=0, column=0, padx=5)
    module_type_cb = ttk.Combobox(filter_frame, textvariable=var_module_type, width=10)
    module_type_cb['values'] = get_module_types()
    module_type_cb.grid(row=0, column=1, padx=5)
    module_type_cb.bind('<<ComboboxSelected>>', on_module_type_change)
    module_type_cb.set('')
    module_name_cb = ttk.Combobox(filter_frame, textvariable=var_module_name, width=15)
    module_name_cb.grid(row=0, column=3, padx=5)
    module_name_cb.bind('<<ComboboxSelected>>', on_module_name_change)
    # 初始化模块名称下拉框
    module_name_cb['values'] = get_module_names()

    tk.Label(filter_frame, text="模块名称:").grid(row=0, column=2, padx=5)
    tk.Label(filter_frame, text="标签名称:").grid(row=0, column=4, padx=5)
    tag_name_cb = ttk.Combobox(filter_frame, textvariable=var_tag_name, width=15)
    tag_name_cb.grid(row=0, column=5, padx=5)
    tag_name_cb['values'] = get_tag_names()

    # 查询按钮
    def refresh_table():
        for row in tree.get_children():
            tree.delete(row)
        # 查询条件
        sql = '''SELECT tags.tag_name, TF_questions.TF_question_text, TF_questions.TF_question_ans, TF_questions.TF_question_id
                 FROM TF_questions
                 JOIN TF_tag_relations ON TF_questions.TF_question_id = TF_tag_relations.TF_question_id
                 JOIN tags ON TF_tag_relations.tag_id = tags.tag_id
                 JOIN modules ON tags.module_id = modules.module_id
                 WHERE 1=1'''
        params = []
        if var_module_type.get():
            sql += ' AND modules.module_type=?'
            params.append(var_module_type.get())
        if var_module_name.get():
            sql += ' AND modules.module_name=?'
            params.append(var_module_name.get())
        if var_tag_name.get():
            sql += ' AND tags.tag_name=?'
            params.append(var_tag_name.get())
        with get_db() as conn:
            cur = conn.cursor()
            for row in cur.execute(sql, params):
                ans = '正确' if row[2] else '错误'
                tree.insert('', 'end', values=(row[0], row[1], ans, row[3]))

    query_btn = tk.Button(filter_frame, text="查询", command=refresh_table)
    query_btn.grid(row=0, column=6, padx=10)

    def reset_filter():
        var_module_type.set('')
        var_module_name.set('')
        var_tag_name.set('')
        module_type_cb.set('')
        module_name_cb['values'] = get_module_names()
        tag_name_cb['values'] = get_tag_names()
        refresh_table()
    reset_btn = tk.Button(filter_frame, text="重置", command=reset_filter)
    reset_btn.grid(row=0, column=7, padx=5)

    # --- 动态表格 ---
    table_frame = tk.Frame(win)
    table_frame.pack(fill="both", expand=True, padx=10, pady=5)
    columns = ("标签名称", "判断题目", "答案", "TF_question_id")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
    for col in columns[:-1]:
        tree.heading(col, text=col)
        tree.column(col, width=200)
    tree.heading("TF_question_id", text="")
    tree.column("TF_question_id", width=0, stretch=False)
    tree.pack(fill="both", expand=True)

    def open_edit_dialog(row_values):
        # row_values: (tag_name, question_text, ans_label, TF_question_id)
        tag_name, question_text, ans_label, tf_id = row_values
        dialog = tk.Toplevel(win)
        dialog.title("编辑判断题")
        dialog.geometry("500x320")
        dialog.transient(win)
        dialog.grab_set()

        var_type = tk.StringVar(value="")
        var_name = tk.StringVar(value="")
        var_tag = tk.StringVar(value=tag_name)
        var_text = tk.StringVar(value=question_text)
        var_ans = tk.StringVar(value="1" if ans_label == '正确' else "0")

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT modules.module_type, modules.module_name, tags.tag_name
                FROM TF_tag_relations
                JOIN tags ON TF_tag_relations.tag_id = tags.tag_id
                JOIN modules ON tags.module_id = modules.module_id
                WHERE TF_tag_relations.TF_question_id=?
                LIMIT 1
                """,
                (tf_id,)
            )
            module_info = cur.fetchone()
            if module_info:
                var_type.set(module_info[0])
                var_name.set(module_info[1])
                var_tag.set(module_info[2])

        tk.Label(dialog, text="模块类型:").grid(row=0, column=0, padx=8, pady=10, sticky='e')
        cb_type = ttk.Combobox(dialog, textvariable=var_type, width=12, values=get_module_types())
        cb_type.grid(row=0, column=1, padx=8, pady=10, sticky='w')

        tk.Label(dialog, text="模块名称:").grid(row=1, column=0, padx=8, pady=10, sticky='e')
        cb_name = ttk.Combobox(dialog, textvariable=var_name, width=18)
        cb_name.grid(row=1, column=1, padx=8, pady=10, sticky='w')

        tk.Label(dialog, text="标签名称:").grid(row=2, column=0, padx=8, pady=10, sticky='e')
        cb_tag = ttk.Combobox(dialog, textvariable=var_tag, width=18)
        cb_tag.grid(row=2, column=1, padx=8, pady=10, sticky='w')

        tk.Label(dialog, text="判断题目:").grid(row=3, column=0, padx=8, pady=10, sticky='e')
        entry_text = tk.Entry(dialog, textvariable=var_text, width=40)
        entry_text.grid(row=3, column=1, padx=8, pady=10, sticky='w')

        tk.Label(dialog, text="答案:").grid(row=4, column=0, padx=8, pady=10, sticky='e')
        ans_frame = tk.Frame(dialog)
        ans_frame.grid(row=4, column=1, padx=8, pady=10, sticky='w')
        tk.Radiobutton(ans_frame, text="正确", variable=var_ans, value="1").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(ans_frame, text="错误", variable=var_ans, value="0").pack(side=tk.LEFT, padx=5)

        def update_module_names(reset_selected=True):
            module_type = var_type.get() or None
            names = get_module_names(module_type)
            cb_name['values'] = names
            if reset_selected:
                var_name.set('')
                update_tags()

        def update_tags(reset_selected=True):
            module_name = var_name.get() or None
            tags = get_tag_names(module_name)
            cb_tag['values'] = tags
            if reset_selected:
                var_tag.set('')

        def on_type_change(event=None):
            update_module_names(reset_selected=True)

        def on_name_change(event=None):
            update_tags(reset_selected=True)

        cb_type.bind('<<ComboboxSelected>>', on_type_change)
        cb_name.bind('<<ComboboxSelected>>', on_name_change)

        # 初始化下拉选项
        update_module_names(reset_selected=False)
        if var_name.get():
            cb_name.set(var_name.get())
            update_tags(reset_selected=False)
        if var_tag.get():
            cb_tag.set(var_tag.get())
        if var_type.get():
            cb_type.set(var_type.get())

        def on_save():
            if not var_type.get():
                messagebox.showwarning("提示", "请选择模块类型")
                return
            if not var_name.get():
                messagebox.showwarning("提示", "请选择模块名称")
                return
            if not var_tag.get():
                messagebox.showwarning("提示", "请选择标签名称")
                return
            if not var_text.get() or len(var_text.get()) > 100:
                messagebox.showwarning("提示", "请输入判断题目，且不超过100字")
                return
            if var_ans.get() not in ("1", "0"):
                messagebox.showwarning("提示", "请选择答案")
                return
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT tag_id FROM tags WHERE tag_name=?", (var_tag.get(),))
                tag_row = cur.fetchone()
                if not tag_row:
                    messagebox.showerror("错误", "标签不存在")
                    return
                tag_id = tag_row[0]
                cur.execute(
                    "UPDATE TF_questions SET TF_question_text=?, TF_question_ans=? WHERE TF_question_id=?",
                    (var_text.get()[:100], int(var_ans.get()), tf_id)
                )
                cur.execute("DELETE FROM TF_tag_relations WHERE TF_question_id=?", (tf_id,))
                cur.execute(
                    "INSERT INTO TF_tag_relations (tag_id, TF_question_id) VALUES (?, ?)",
                    (tag_id, tf_id)
                )
                conn.commit()
            messagebox.showinfo("成功", "修改成功")
            dialog.destroy()
            refresh_table()

        def on_delete():
            if not messagebox.askyesno("确认", "确定要删除该判断题吗？"):
                return
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM TF_tag_relations WHERE TF_question_id=?", (tf_id,))
                cur.execute("DELETE FROM TF_questions WHERE TF_question_id=?", (tf_id,))
                conn.commit()
            messagebox.showinfo("成功", "已删除该判断题")
            dialog.destroy()
            refresh_table()

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)
        tk.Button(btn_frame, text="保存", command=on_save).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="删除", command=on_delete, fg="red").pack(side=tk.LEFT, padx=10)

    # --- 添加/编辑弹层 ---
    def open_add_edit_dialog(edit_data=None):
        if edit_data:
            open_edit_dialog(edit_data)
            return
        dialog = tk.Toplevel(win)
        dialog.title("批量添加判断题")
        dialog.geometry("1200x400")
        dialog.transient(win)
        dialog.grab_set()

        # frame1: 多行输入
        frame1 = tk.Frame(dialog)
        frame1.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(frame1, text="批量题干：").pack(side=tk.LEFT, anchor="n")
        text_input = tk.Text(frame1, width=60, height=4)
        text_input.pack(side=tk.LEFT, padx=10)

        # frame2: 级联下拉
        frame2 = tk.Frame(dialog)
        frame2.pack(fill="x", padx=10, pady=5)
        var_type = tk.StringVar(value="知识")
        var_name = tk.StringVar()
        var_tag = tk.StringVar()
        tk.Label(frame2, text="模块类型:").grid(row=0, column=0, padx=5)
        cb_type = ttk.Combobox(frame2, textvariable=var_type, width=10)
        cb_type['values'] = get_module_types()
        cb_type.grid(row=0, column=1, padx=5)
        cb_type.set(var_type.get())
        tk.Label(frame2, text="模块:").grid(row=0, column=2, padx=5)
        cb_name = ttk.Combobox(frame2, textvariable=var_name, width=15)
        cb_name.grid(row=0, column=3, padx=5)
        cb_name['values'] = get_module_names("知识")
        tk.Label(frame2, text="标签:").grid(row=0, column=4, padx=5)
        cb_tag = ttk.Combobox(frame2, textvariable=var_tag, width=15)
        cb_tag.grid(row=0, column=5, padx=5)

        def on_type_change(*_):
            names = get_module_names(var_type.get())
            cb_name['values'] = names
            var_name.set('')
            cb_tag['values'] = []
            var_tag.set('')
        def on_name_change(*_):
            tags = get_tag_names(var_name.get())
            cb_tag['values'] = tags
            var_tag.set('')
        cb_type.bind('<<ComboboxSelected>>', on_type_change)
        cb_name.bind('<<ComboboxSelected>>', on_name_change)
        on_type_change()

        # frame3: 解析按钮
        frame3 = tk.Frame(dialog)
        frame3.pack(fill="x", padx=10, pady=5)
        # 记录动态行控件
        dynamic_rows = []

        def clear_dynamic_rows():
            for row in dynamic_rows:
                for widget in row['widgets']:
                    widget.destroy()
            dynamic_rows.clear()

        def parse_questions():
            clear_dynamic_rows()
            lines = text_input.get("1.0", tk.END).splitlines()
            lines = [l.strip() for l in lines if l.strip()]
            if not lines:
                messagebox.showwarning("提示", "请批量填写题干")
                return
            for idx, line in enumerate(lines):
                import re
                line = re.sub(r'^[A-ZＡ-Ｚ]\．', '', line).strip()
                row_widgets = []
                row_frame = tk.Frame(frame4)
                row_frame.pack(fill="x", pady=2)
                # 1.模块类型
                v_type = tk.StringVar(value=var_type.get())
                cb1 = ttk.Combobox(row_frame, textvariable=v_type, width=10, values=get_module_types())
                cb1.grid(row=0, column=0, padx=2)
                # 2.模块
                v_name = tk.StringVar(value=var_name.get())
                cb2 = ttk.Combobox(row_frame, textvariable=v_name, width=15)
                cb2.grid(row=0, column=1, padx=2)
                # 3.标签
                v_tag = tk.StringVar(value=var_tag.get())
                cb3 = ttk.Combobox(row_frame, textvariable=v_tag, width=15)
                cb3.grid(row=0, column=2, padx=2)
                # 4.题干
                v_text = tk.StringVar(value=line)
                entry = tk.Entry(row_frame, textvariable=v_text, width=60)
                entry.grid(row=0, column=3, padx=2)
                # 5.单选
                v_ans = tk.StringVar()
                rb1 = tk.Radiobutton(row_frame, text="正确", variable=v_ans, value="1")
                rb2 = tk.Radiobutton(row_frame, text="错误", variable=v_ans, value="0")
                rb1.grid(row=0, column=4, padx=2)
                rb2.grid(row=0, column=5, padx=2)


                # 级联逻辑：每行独立且互不影响（闭包方式）
                def update_module_names(event=None, reset_selected=True,
                                       cb2=cb2, cb3=cb3, v_type=v_type, v_name=v_name, v_tag=v_tag):
                    names = get_module_names(v_type.get())
                    cb2['values'] = names
                    if reset_selected:
                        v_name.set('')
                        update_tags(reset_selected=True, cb3=cb3, v_name=v_name, v_tag=v_tag)
                    else:
                        update_tags(reset_selected=False, cb3=cb3, v_name=v_name, v_tag=v_tag)

                def update_tags(event=None, reset_selected=True,
                               cb3=cb3, v_name=v_name, v_tag=v_tag):
                    tags = get_tag_names(v_name.get())
                    cb3['values'] = tags
                    if reset_selected:
                        v_tag.set('')

                cb1.bind('<<ComboboxSelected>>', lambda e, cb2=cb2, cb3=cb3, v_type=v_type, v_name=v_name, v_tag=v_tag: update_module_names(reset_selected=True, cb2=cb2, cb3=cb3, v_type=v_type, v_name=v_name, v_tag=v_tag))
                cb2.bind('<<ComboboxSelected>>', lambda e, cb3=cb3, v_name=v_name, v_tag=v_tag: update_tags(reset_selected=True, cb3=cb3, v_name=v_name, v_tag=v_tag))

                # 初始化下拉选项（每行独立）
                cb2['values'] = get_module_names(v_type.get())
                cb3['values'] = get_tag_names(v_name.get())
                if v_type.get():
                    cb1.set(v_type.get())
                if v_name.get():
                    cb2.set(v_name.get())
                if v_tag.get():
                    cb3.set(v_tag.get())

                row_widgets.extend([row_frame, cb1, cb2, cb3, entry, rb1, rb2])
                dynamic_rows.append({
                    'widgets': row_widgets,
                    'vars': {'type': v_type, 'name': v_name, 'tag': v_tag, 'text': v_text, 'ans': v_ans}
                })

        parse_btn = tk.Button(frame3, text="解析", command=parse_questions)
        parse_btn.pack(side=tk.LEFT)

        # frame4: 动态行容器
        frame4 = tk.Frame(dialog)
        frame4.pack(fill="both", expand=True, padx=10, pady=5)

        # frame5: 保存/清空
        frame5 = tk.Frame(dialog)
        frame5.pack(fill="x", padx=10, pady=10)
        def do_save():
            valid_rows = []
            for row in dynamic_rows:
                v = row['vars']
                if v['type'].get() and v['name'].get() and v['tag'].get() and v['text'].get() and v['ans'].get() in ("1", "0"):
                    valid_rows.append(v)
            if not valid_rows:
                messagebox.showwarning("提示", "请至少填写一行完整数据（模块类型、模块、标签、题干、答案）")
                return
            with get_db() as conn:
                cur = conn.cursor()
                # 获取当前最大TF_question_id
                cur.execute("SELECT TF_question_id FROM TF_questions ORDER BY TF_question_id DESC LIMIT 1")
                last = cur.fetchone()
                last_num = int(last[0][2:]) if last else 0
                new_num = last_num
                for v in valid_rows:
                    # tag_id
                    cur.execute("SELECT tag_id FROM tags WHERE tag_name=?", (v['tag'].get(),))
                    tag_row = cur.fetchone()
                    if not tag_row:
                        messagebox.showerror("错误", f"标签不存在: {v['tag'].get()}")
                        return
                    tag_id = tag_row[0]
                    # 新TF_question_id
                    new_num += 1
                    tf_id = f"TF{new_num:05d}"
                    # 插入TF_questions
                    cur.execute("INSERT INTO TF_questions (TF_question_id, TF_question_text, TF_question_ans) VALUES (?, ?, ?)",
                                (tf_id, v['text'].get()[:100], int(v['ans'].get())))
                    # 插入TF_tag_relations
                    cur.execute("INSERT INTO TF_tag_relations (tag_id, TF_question_id) VALUES (?, ?)", (tag_id, tf_id))
                conn.commit()
            messagebox.showinfo("成功", "批量添加成功！")
            text_input.delete("1.0", tk.END)
            clear_dynamic_rows()
            var_type.set("知识")
            var_name.set("")
            var_tag.set("")
            refresh_table()

        def do_clear():
            text_input.delete("1.0", tk.END)
            clear_dynamic_rows()
            var_type.set("知识")
            var_name.set("")
            var_tag.set("")

        save_btn = tk.Button(frame5, text="保存", command=do_save)
        save_btn.pack(side=tk.LEFT, padx=10)
        clear_btn = tk.Button(frame5, text="清空", command=do_clear)
        clear_btn.pack(side=tk.LEFT, padx=10)

    # 双击表格行编辑
    def on_row_double(event):
        item = tree.selection()
        if item:
            values = tree.item(item[0], 'values')
            open_add_edit_dialog(values)
    tree.bind('<Double-1>', on_row_double)

    refresh_table()
