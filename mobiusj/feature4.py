import os
import json
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import font
import sqlite3

import config  # 新增：导入 config 模块

DB_FILENAME = "mobius_data.sqlite3"

def get_db_path(data_folder):
    return os.path.join(data_folder, DB_FILENAME)

def check_db_file(data_folder):
    db_path = get_db_path(data_folder)
    errors = []
    # 如果数据库文件不存在，则创建空库
    if not os.path.exists(db_path):
        try:
            create_empty_db(db_path)
        except Exception as e:
            raise ValueError(f"数据库文件创建失败: {str(e)}")
        return True

    # 校验数据库结构
    try:
        errors = validate_db_structure(db_path)
    except Exception as e:
        errors.append(f"数据库结构校验异常: {str(e)}")

    # 新增逻辑：如果仅缺少表，提示并询问是否自动补全
    if errors:
        missing_tables = []
        for err in errors:
            if err.startswith("缺少表:"):
                missing_tables = [t.strip() for t in err.replace("缺少表:", "").split(",")]
        if missing_tables:
            msg = f"数据库缺少以下表：{', '.join(missing_tables)}。\n是否自动补全这些表？"
            root = tk._default_root or tk.Tk()
            root.withdraw()
            if messagebox.askyesno("缺少表", msg):
                try:
                    add_missing_tables(db_path, missing_tables)
                    errors2 = validate_db_structure(db_path)
                    if errors2:
                        raise ValueError("\n".join(errors2))
                    return True
                except Exception as e:
                    raise ValueError(f"自动补全表失败: {str(e)}")
            else:
                raise ValueError("\n".join(errors))
        else:
            raise ValueError("\n".join(errors))
    return True

def create_empty_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        # 只建表，不插入数据
        c.executescript("""
        CREATE TABLE IF NOT EXISTS modules (
            module_id TEXT PRIMARY KEY CHECK (module_id GLOB '[0-9][0-9][0-9][0-9]' AND length(module_id) = 4),
            module_name TEXT NOT NULL CHECK (length(module_name) <= 10),
            module_type TEXT CHECK (module_type IN ('知识', '思想', '模型'))
        );
        CREATE TABLE IF NOT EXISTS tags (
            tag_id TEXT PRIMARY KEY CHECK (tag_id GLOB '[0-9][0-9][0-9][0-9][0-9]' AND length(tag_id) = 5),
            module_id TEXT NOT NULL REFERENCES modules(module_id),
            tag_name TEXT NOT NULL CHECK (length(tag_name) <= 25),
            tag_intro TEXT CHECK (length(tag_intro) <= 100)
        );
        CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY CHECK (item_id GLOB '*[0-9A-Za-z-]*' AND length(item_id) <= 64 AND item_id NOT GLOB '*[^0-9A-Za-z-]*'),
            item_level INTEGER CHECK (item_level IN (1, 2, 3, 4)),
            item_usage TEXT CHECK (item_usage IN ('例', '练') OR item_usage IS NULL),
            item_intro TEXT CHECK (length(item_intro) <= 200)
        );
        CREATE TABLE IF NOT EXISTS item_tag_relations (
            item_id TEXT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
            tag_id TEXT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
            PRIMARY KEY (item_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY CHECK (student_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(student_id) = 6),
            student_name TEXT NOT NULL CHECK (length(student_name) <= 10)
        );
        CREATE TABLE IF NOT EXISTS student_item_relations (
            student_id TEXT NOT NULL REFERENCES students(student_id),
            item_id TEXT NOT NULL REFERENCES items(item_id),
            date_created TEXT NOT NULL,
            PRIMARY KEY (student_id, item_id)
        );
        CREATE TABLE IF NOT EXISTS clusters (
            cluster_id TEXT PRIMARY KEY CHECK (cluster_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(cluster_id) = 6),
            cluster_name TEXT NOT NULL CHECK (length(cluster_name) <= 20),
            cluster_intro TEXT CHECK (length(cluster_intro) <= 100),
            module_id TEXT NOT NULL REFERENCES modules(module_id),
            tag_id TEXT REFERENCES tags(tag_id)
        );
        CREATE TABLE IF NOT EXISTS groups (
            group_id TEXT PRIMARY KEY CHECK (group_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(group_id) = 6),
            group_name TEXT NOT NULL CHECK (length(group_name) <= 20),
            group_level TEXT CHECK (group_level IN ('基础', '进阶', '疯狂', '暴躁')),
            cluster_id TEXT NOT NULL REFERENCES clusters(cluster_id),
            group_intro TEXT CHECK (length(group_intro) <= 100)
        );
        CREATE TABLE IF NOT EXISTS group_examples (
            group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES items(item_id),
            PRIMARY KEY (group_id, item_id)
        );
        CREATE TABLE IF NOT EXISTS group_exercises (
            group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES items(item_id),
            PRIMARY KEY (group_id, item_id)
        );
        CREATE TABLE IF NOT EXISTS TF_questions (
            TF_question_id TEXT PRIMARY KEY CHECK (TF_question_id GLOB 'TF[0-9][0-9][0-9][0-9][0-9]' AND length(TF_question_id) = 7),
            TF_question_text TEXT NOT NULL CHECK (length(TF_question_text) <= 100),
            TF_question_ans BOOLEAN NOT NULL
        );
        CREATE TABLE IF NOT EXISTS TF_tag_relations (
            tag_id TEXT NOT NULL REFERENCES tags(tag_id),
            TF_question_id TEXT NOT NULL REFERENCES TF_questions(TF_question_id) ON DELETE CASCADE,
            PRIMARY KEY (tag_id, TF_question_id)
        );
        """)
        conn.commit()
    finally:
        conn.close()

def validate_db_structure(db_path):
    errors = []
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        # 读取所有表名
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = set(row[0] for row in c.fetchall())
        required_tables = {
            "modules", "tags", "items", "item_tag_relations", "students", "student_item_relations",
            "clusters", "groups", "group_examples", "group_exercises",
            "TF_questions", "TF_tag_relations"
        }
        missing_tables = required_tables - tables
        if missing_tables:
            errors.append(f"缺少表: {', '.join(missing_tables)}")

        # 校验每个表的字段和约束（只做字段名和部分约束的简单校验，详细约束建议用迁移工具或手动检查）
        table_defs = {
            "modules": ["module_id", "module_name", "module_type"],
            "tags": ["tag_id", "module_id", "tag_name", "tag_intro"],
            "items": ["item_id", "item_level", "item_usage", "item_intro"],
            "item_tag_relations": ["item_id", "tag_id"],
            "students": ["student_id", "student_name"],
            "student_item_relations": ["student_id", "item_id", "date_created"],
            "clusters": ["cluster_id", "cluster_name", "cluster_intro", "module_id", "tag_id"],
            "groups": ["group_id", "group_name", "group_level", "cluster_id", "group_intro"],
            "group_examples": ["group_id", "item_id"],
            "group_exercises": ["group_id", "item_id"],
            "TF_questions": ["TF_question_id", "TF_question_text", "TF_question_ans"],
            "TF_tag_relations": ["tag_id", "TF_question_id"],
        }
        for table, columns in table_defs.items():
            if table not in tables:
                continue
            c.execute(f"PRAGMA table_info({table});")
            db_columns = [row[1] for row in c.fetchall()]
            missing_cols = set(columns) - set(db_columns)
            if missing_cols:
                errors.append(f"表 {table} 缺少字段: {', '.join(missing_cols)}")

        # 可选：校验主键、外键、CHECK约束等（这里只做字段和表名校验，详细约束建议用迁移工具或手动检查）
        return errors
    finally:
        conn.close()

def on_set_data_path(folder_selected):
    settings_file = config.load_settings_path()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {"data_path": "", "subjects": [], "subject_param": ""}

        settings["data_path"] = folder_selected

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)

        # 新增：检查并创建item_img_path文件夹
        img_folder = os.path.join(folder_selected, "item_img_path")
        if not os.path.exists(img_folder):
            try:
                os.makedirs(img_folder)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建图片文件夹: {str(e)}")
                return

        try:
            check_db_file(folder_selected)
            messagebox.showinfo("信息", "数据位置设置成功")
        except ValueError as e:
            messagebox.showerror("错误", f"数据位置设置失败:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("错误", f"设置数据路径时出错: {str(e)}")

def on_validate_data_path():
    settings_file = config.load_settings_path()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {"data_path": "", "subjects": [], "subject_param": ""}

        path = settings.get("data_path", "")
        if not path:
            messagebox.showwarning("警告", "未设置数据路径，请先设置数据路径")
            return

        # 新增：校验item_img_path文件夹
        img_folder = os.path.join(path, "item_img_path")
        if not os.path.exists(img_folder):
            root = tk._default_root or tk.Tk()
            root.withdraw()
            if messagebox.askyesno("缺少文件夹", "数据路径下缺少 item_img_path 文件夹，是否自动创建？"):
                try:
                    os.makedirs(img_folder)
                    messagebox.showinfo("信息", "已自动创建 item_img_path 文件夹。")
                except Exception as e:
                    messagebox.showerror("错误", f"无法创建 item_img_path 文件夹: {str(e)}")
                    return
            else:
                messagebox.showwarning("警告", "未检测到 item_img_path 文件夹，校验未通过。")
                return
        try:
            check_db_file(path)
            messagebox.showinfo("信息", "校验成功")
        except ValueError as e:
            messagebox.showerror("错误", f"校验失败:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("错误", f"校验数据路径时出错: {str(e)}")

def on_save_subject_param(param):
    settings_file = config.load_settings_path()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {"data_path": "", "subjects": [], "subject_param": ""}

        settings["subject_param"] = param

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        messagebox.showerror("错误", f"保存配置失败: {str(e)}")

def create_setting_window():
    settings_file = config.load_settings_path()
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        settings = {"data_path": "", "subjects": [], "subject_param": ""}

    root = tk.Toplevel()
    root.title("设置")
    root.geometry("600x600")
    root.resizable(width=False, height=False)
    root.protocol("WM_DELETE_WINDOW", root.destroy)  # 修改：关闭时调用 destroy

    default_font = font.nametofont("TkDefaultFont")

    data_path_label = tk.Label(root, text=f"数据位置: {settings.get('data_path', '')}")
    data_path_label.pack(pady=10)

    def select_folder():
        folder_selected = filedialog.askdirectory(title="选择数据文件夹")
        if folder_selected:
            on_set_data_path(folder_selected)
            data_path_label.config(text=f"数据位置: {folder_selected}")

    button_frame = tk.Frame(root)
    button_frame.pack(pady=5)

    browse_button = tk.Button(button_frame, text="设置", command=select_folder)
    browse_button.pack(side=tk.LEFT, padx=5)

    validate_button = tk.Button(button_frame, text="校验", command=on_validate_data_path)
    validate_button.pack(side=tk.LEFT, padx=5)

    current_subject_param_label = tk.Label(root, text=f"当前学科参数: {settings.get('subject_param', '')}")
    current_subject_param_label.pack(pady=10)

    subject_param_label = tk.Label(root, text="学科参数:")
    subject_param_label.pack(pady=10)

    subject_param_var = tk.StringVar(value=settings.get("subject_param", ""))
    subject_param_entry = tk.Entry(root, textvariable=subject_param_var, width=25)
    subject_param_entry.pack(pady=5)

    def save_subject_param():
        param = subject_param_var.get()
        if not param:
            messagebox.showwarning("警告", "请输入学科参数")
            return

        settings_file = config.load_settings_path()
        try:
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                settings = {"data_path": "", "subjects": [], "subject_param": ""}

            # 单条保存时，直接弹窗错误
            settings["subject_param"] = param

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())

            with open(settings_file, "r", encoding="utf-8") as f:
                saved_settings = json.load(f)
                if saved_settings.get("subject_param") != param:
                    raise ValueError("参数保存后验证失败")

            current_subject_param_label.config(text=f"当前学科参数: {param}")
            messagebox.showinfo("信息", f"学科参数已保存: {param}")
            
        except Exception as e:
            with open(settings_file, "r", encoding="utf-8") as f:
                current_settings = json.load(f)
                current_value = current_settings.get("subject_param", "")
            current_subject_param_label.config(text=f"当前学科参数: {current_value}")
            subject_param_var.set(current_value)
            
            messagebox.showerror("保存错误", 
                f"保存失败: {str(e)}\n"
                f"当前工作目录: {os.getcwd()}\n"
                f"文件路径: {os.path.abspath(settings_file)}\n"
                f"文件存在: {os.path.exists(settings_file)}\n"
                f"文件可写: {os.access(settings_file, os.W_OK)}")

    save_button = tk.Button(root, text="保存", command=save_subject_param)
    save_button.pack(pady=5)

    root.mainloop()

def add_missing_tables(db_path, missing_tables):
    table_sql = {
        "modules": """
            CREATE TABLE IF NOT EXISTS modules (
                module_id TEXT PRIMARY KEY CHECK (module_id GLOB '[0-9][0-9][0-9][0-9]' AND length(module_id) = 4),
                module_name TEXT NOT NULL CHECK (length(module_name) <= 10),
                module_type TEXT CHECK (module_type IN ('知识', '思想', '模型'))
            );
        """,
        "tags": """
            CREATE TABLE IF NOT EXISTS tags (
                tag_id TEXT PRIMARY KEY CHECK (tag_id GLOB '[0-9][0-9][0-9][0-9][0-9]' AND length(tag_id) = 5),
                module_id TEXT NOT NULL REFERENCES modules(module_id),
                tag_name TEXT NOT NULL CHECK (length(tag_name) <= 25),
                tag_intro TEXT CHECK (length(tag_intro) <= 100)
            );
        """,
        "items": """
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY CHECK (item_id GLOB '*[0-9A-Za-z-]*' AND length(item_id) <= 64 AND item_id NOT GLOB '*[^0-9A-Za-z-]*'),
                item_level INTEGER CHECK (item_level IN (1, 2, 3, 4)),
                item_usage TEXT CHECK (item_usage IN ('例', '练') OR item_usage IS NULL),
                item_intro TEXT CHECK (length(item_intro) <= 200)
            );
        """,
        "item_tag_relations": """
            CREATE TABLE IF NOT EXISTS item_tag_relations (
                item_id TEXT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
                tag_id TEXT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
                PRIMARY KEY (item_id, tag_id)
            );
        """,
        "students": """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY CHECK (student_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(student_id) = 6),
                student_name TEXT NOT NULL CHECK (length(student_name) <= 10)
            );
        """,
        "student_item_relations": """
            CREATE TABLE IF NOT EXISTS student_item_relations (
                student_id TEXT NOT NULL REFERENCES students(student_id),
                item_id TEXT NOT NULL REFERENCES items(item_id),
                date_created TEXT NOT NULL,
                PRIMARY KEY (student_id, item_id)
            );
        """,
        "clusters": """
            CREATE TABLE IF NOT EXISTS clusters (
                cluster_id TEXT PRIMARY KEY CHECK (cluster_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(cluster_id) = 6),
                cluster_name TEXT NOT NULL CHECK (length(cluster_name) <= 20),
                cluster_intro TEXT CHECK (length(cluster_intro) <= 100),
                module_id TEXT NOT NULL REFERENCES modules(module_id),
                tag_id TEXT REFERENCES tags(tag_id)
            );
        """,
        "groups": """
            CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY CHECK (group_id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' AND length(group_id) = 6),
                group_name TEXT NOT NULL CHECK (length(group_name) <= 20),
                group_level TEXT CHECK (group_level IN ('基础', '进阶', '疯狂', '暴躁')),
                cluster_id TEXT NOT NULL REFERENCES clusters(cluster_id),
                group_intro TEXT CHECK (length(group_intro) <= 100)
            );
        """,
        "group_examples": """
            CREATE TABLE IF NOT EXISTS group_examples (
                group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
                item_id TEXT NOT NULL REFERENCES items(item_id),
                PRIMARY KEY (group_id, item_id)
            );
        """,
        "group_exercises": """
            CREATE TABLE IF NOT EXISTS group_exercises (
                group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
                item_id TEXT NOT NULL REFERENCES items(item_id),
                PRIMARY KEY (group_id, item_id)
            );
        """,
        "TF_questions": """
            CREATE TABLE IF NOT EXISTS TF_questions (
                TF_question_id TEXT PRIMARY KEY CHECK (TF_question_id GLOB 'TF[0-9][0-9][0-9][0-9][0-9]' AND length(TF_question_id) = 7),
                TF_question_text TEXT NOT NULL CHECK (length(TF_question_text) <= 100),
                TF_question_ans BOOLEAN NOT NULL
            );
        """,
        "TF_tag_relations": """
            CREATE TABLE IF NOT EXISTS TF_tag_relations (
                tag_id TEXT NOT NULL REFERENCES tags(tag_id),
                TF_question_id TEXT NOT NULL REFERENCES TF_questions(TF_question_id) ON DELETE CASCADE,
                PRIMARY KEY (tag_id, TF_question_id)
            );
        """,
    }
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        for table in missing_tables:
            sql = table_sql.get(table)
            if sql:
                c.executescript(sql)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    create_setting_window()
    root.mainloop()
