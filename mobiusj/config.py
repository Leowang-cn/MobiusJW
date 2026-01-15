# config.py
import os
import sys
import json

# 获取程序所在目录（开发环境或打包后都适用）
if getattr(sys, 'frozen', False):
    # 打包后的路径
    APP_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境路径
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

# 如果 settings.json 不存在，则自动创建
def ensure_settings_file():
    if not os.path.exists(SETTINGS_FILE):
        default_config = {
            "data_path": "",
            "subjects": [],
            "subject_param": ""
        }
        save_settings(default_config)

# 读取配置
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "data_path": "",
        "subjects": [],
        "subject_param": ""
    }

# 写入配置
def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

# 新增：获取设置文件路径
def load_settings_path():
    return SETTINGS_FILE