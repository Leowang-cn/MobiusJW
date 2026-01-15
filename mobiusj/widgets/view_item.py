import config
import webbrowser

def open_question_url(question_id):
    """
    通用的触发事件：根据题目ID拼接网址并在默认浏览器中打开。
    网址格式：https://www.jyeoo.com/{subject}/ques/detail/{question_id}
    其中 subject 从 settings.json 中的 subject_param 参数获取。
    如果未设置 subject_param，则不执行任何操作。
    """
    settings = config.load_settings()
    subject = settings.get("subject_param")
    if not subject:
        return  # 如果未设置 subject_param，不打开浏览器
    url = f"https://www.jyeoo.com/{subject}/ques/detail/{question_id}"
    webbrowser.open(url)
