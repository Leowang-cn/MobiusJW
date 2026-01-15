import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import config
import os
import webbrowser
from datetime import datetime

def get_subject_param():
    settings = config.load_settings()
    # 如果 subject_param 不存在，返回默认值
    return {"subject_param": settings.get("subject_param", "physics")}

# 全局变量
SUBJECT_PARAM = get_subject_param()

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

def feature3():
    # 主弹层
    win = tk.Toplevel()
    win.title("学生管理")
    win.geometry("600x400")
    win.grab_set()

    # 添加学生按钮
    add_btn = tk.Button(win, text="添加学生", command=lambda: show_add_student(win))
    add_btn.pack(pady=10)

    # 筛选区
    filter_frame = tk.Frame(win)
    filter_frame.pack(pady=5)
    tk.Label(filter_frame, text="学生姓名:").pack(side=tk.LEFT)
    name_var = tk.StringVar()
    name_entry = tk.Entry(filter_frame, textvariable=name_var, width=20)
    name_entry.pack(side=tk.LEFT, padx=5)
    search_btn = tk.Button(filter_frame, text="查询", command=lambda: refresh_table())
    search_btn.pack(side=tk.LEFT)

    # 表格区
    columns = ("student_name", "item_count")
    tree = ttk.Treeview(win, columns=columns, show="headings", height=15)
    tree.heading("student_name", text="学生姓名")
    tree.heading("item_count", text="关联题目数量")
    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 双击行事件
    def on_row_double(event):
        item = tree.selection()
        if item:
            student_name = tree.item(item, "values")[0]
            student_id = tree.item(item, "tags")[0]
            show_student_items(win, student_id, student_name)
    tree.bind("<Double-1>", on_row_double)

    def refresh_table():
        tree.delete(*tree.get_children())
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            if not table_exists(conn, "students"):
                messagebox.showerror("错误", "数据库缺少 students 表", parent=win)
                conn.close()
                return
            if not table_exists(conn, "student_item_relations"):
                messagebox.showerror("错误", "数据库缺少 student_item_relations 表", parent=win)
                conn.close()
                return
            cursor = conn.cursor()
            name_filter = name_var.get().strip()
            if name_filter:
                cursor.execute("SELECT student_id, student_name FROM students WHERE student_name LIKE ?", ('%' + name_filter + '%',))
            else:
                cursor.execute("SELECT student_id, student_name FROM students")
            students = cursor.fetchall()
            for sid, sname in students:
                cursor.execute("SELECT COUNT(*) FROM student_item_relations WHERE student_id=?", (sid,))
                count = cursor.fetchone()[0]
                tree.insert("", "end", values=(sname, count), tags=(sid,))
        except Exception as e:
            messagebox.showerror("错误", f"数据库查询失败: {e}", parent=win)
        finally:
            if 'conn' in locals():
                conn.close()
    refresh_table()
    # 让外部可刷新表格
    win.refresh_table = refresh_table

def show_add_student(parent):
    add_win = tk.Toplevel(parent)
    add_win.title("添加学生")
    add_win.geometry("300x150")
    add_win.grab_set()
    tk.Label(add_win, text="学生姓名:").pack(pady=10)
    name_var = tk.StringVar()
    entry = tk.Entry(add_win, textvariable=name_var, width=20)
    entry.pack(pady=5)
    def save_student():
        name = name_var.get().strip()
        if not name:
            messagebox.showerror("错误", "学生姓名不能为空", parent=add_win)
            return
        if len(name) > 10:
            messagebox.showerror("错误", "学生姓名不能超过10个字符", parent=add_win)
            return
        db_path = get_db_path()
        if not db_path:
            return
        try:
            conn = sqlite3.connect(db_path)
            if not table_exists(conn, "students"):
                messagebox.showerror("错误", "数据库缺少 students 表", parent=add_win)
                conn.close()
                return
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM students WHERE student_name=?", (name,))
            exists = cursor.fetchone()
            if exists:
                messagebox.showerror("错误", "该学生姓名已存在", parent=add_win)
                conn.close()
                return
            cursor.execute("SELECT MAX(student_id) FROM students")
            max_id = cursor.fetchone()[0]
            next_id = str(int(max_id) + 1).zfill(6) if max_id else "000001"
            cursor.execute("INSERT INTO students (student_id, student_name) VALUES (?, ?)", (next_id, name))
            conn.commit()
            messagebox.showinfo("成功", "学生添加成功", parent=add_win)
            add_win.destroy()
            if hasattr(parent, "refresh_table"):
                parent.refresh_table()
        except Exception as e:
            messagebox.showerror("错误", f"添加失败: {e}", parent=add_win)
        finally:
            if 'conn' in locals():
                conn.close()
    tk.Button(add_win, text="保存", command=save_student).pack(pady=10)

def show_student_items(parent, student_id, student_name):
    items_win = tk.Toplevel(parent)
    items_win.title(student_name)
    items_win.geometry("1000x400")  # 修改宽度为原来的2倍
    items_win.grab_set()

    db_path = get_db_path()
    items = []
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        if not table_exists(conn, "student_item_relations"):
            messagebox.showerror("错误", "数据库缺少 student_item_relations 表", parent=items_win)
            conn.close()
            items = []
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT item_id, date_created FROM student_item_relations WHERE student_id=? ORDER BY date_created DESC", (student_id,))
            items = cursor.fetchall()
    except Exception as e:
        messagebox.showerror("错误", f"数据库查询失败: {e}", parent=items_win)
        items = []
    finally:
        if 'conn' in locals():
            conn.close()

    # 简单文字+按钮展示
    scroll_canvas = tk.Canvas(items_win)
    scroll_frame = tk.Frame(scroll_canvas)
    vbar = tk.Scrollbar(items_win, orient=tk.VERTICAL, command=scroll_canvas.yview)
    scroll_canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll_canvas.create_window((0,0), window=scroll_frame, anchor='nw')

    def on_frame_configure(event):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
    scroll_frame.bind("<Configure>", on_frame_configure)

    for idx, (item_id, date_created) in enumerate(items):
        dt_str = datetime.strptime(date_created, "%Y-%m-%d %H:%M:%S").strftime("%y-%m-%d %H:%M")
        row_frame = tk.Frame(scroll_frame)
        row_frame.pack(fill=tk.X, padx=10, pady=4)
        info_label = tk.Label(row_frame, text=f"{dt_str}｜{item_id}", anchor="w")
        info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 按钮组合，宽度缩减为4，整体右移15px（padx=20）
        btns_frame = tk.Frame(row_frame)
        btns_frame.pack(side=tk.RIGHT, padx=20)
        view_btn = tk.Button(btns_frame, text="查看", width=4, command=lambda iid=item_id: open_item_url(iid))
        view_btn.pack(side=tk.LEFT)
        del_btn = tk.Button(btns_frame, text="删除", width=4, command=lambda iid=item_id: delete_student_item(items_win, student_id, iid))
        del_btn.pack(side=tk.LEFT, padx=(4,0))

def show_item_actions(parent, student_id, item_id, tree=None):
    act_win = tk.Toplevel(parent)
    act_win.title(f"题目ID: {item_id}")
    act_win.geometry("350x120")
    act_win.grab_set()
    tk.Label(act_win, text=f"题目ID: {item_id}").pack(pady=10)
    btn_frame = tk.Frame(act_win)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="查看", command=lambda: open_item_url(item_id)).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="删除", command=lambda: delete_student_item(act_win, student_id, item_id, tree)).pack(side=tk.LEFT, padx=10)

def open_item_url(item_id):
    url = f"https://www.jyeoo.com/{SUBJECT_PARAM.get('subject_param', 'physics')}/ques/detail/{item_id}"
    webbrowser.open(url)

def delete_student_item(win, student_id, item_id, tree=None):
    if not messagebox.askyesno("确认", "是否解除该题目与学生的关联？", parent=win):
        return
    db_path = get_db_path()
    if not db_path:
        win.destroy()
        return
    try:
        conn = sqlite3.connect(db_path)
        if not table_exists(conn, "student_item_relations"):
            messagebox.showerror("错误", "数据库缺少 student_item_relations 表", parent=win)
            conn.close()
            win.destroy()
            return
        cursor = conn.cursor()
        cursor.execute("DELETE FROM student_item_relations WHERE student_id=? AND item_id=?", (student_id, item_id))
        conn.commit()
        messagebox.showinfo("成功", "已解除关联", parent=win)
        if tree:
            for i in tree.get_children():
                if tree.item(i, "tags")[0] == item_id:
                    tree.delete(i)
                    break
    except Exception as e:
        messagebox.showerror("错误", f"解除关联失败: {e}", parent=win)
    finally:
        if 'conn' in locals():
            conn.close()
    win.destroy()


