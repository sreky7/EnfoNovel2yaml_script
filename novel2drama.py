import sys
sys.stdout.reconfigure(encoding="utf-8")
import os
import yaml
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "source")
OUT_DIR = os.path.join(BASE_DIR, "output")
CHAPTER_REG = re.compile(r"^(第[一二三四五六七八九十0-9]+[章节卷回])")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

def get_all_novel_files():
    res = []
    for name in os.listdir(SOURCE_DIR):
        if name.endswith(".txt"):
            res.append(os.path.join(SOURCE_DIR, name))
    return res

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def split_chapter(full_text):
    lines = full_text.splitlines()
    chap_list = []
    curr_title = "开篇正文"
    buf = []
    for line in lines:
        s = line.strip()
        if CHAPTER_REG.match(s):
            if buf:
                chap_list.append((curr_title, "\n".join(buf)))
                buf = []
            curr_title = s
        else:
            buf.append(line)
    if buf:
        chap_list.append((curr_title, "\n".join(buf)))
    return chap_list

# 2.核心：封装构造函数 build_drama_struct，两层结构 book_info、scene_list
def build_drama_struct(book_name, chapter_list):
    """
    1.功能描述：根据项目Schema规范，封装剧本标准YAML数据结构体，包含book_info书籍信息、scene_list场景列表两层字典结构。
    2.实现思路：使用字典映射yaml字段，封装build_drama_struct构造函数，对接前面文件读取模块。
    3.测试方式：运行代码无语法报错，可传入书名、正文生成规范剧本字典。
    """
    total_chap = len(chapter_list)
    book_info = {
        "book_name": book_name,
        "source": "本地txt小说素材",
        "chapter_total": total_chap
    }
    scene_list = []
    for sid, (title, content) in enumerate(chapter_list, start=1):
        scene_item = {
            "scene_id": sid,
            "chapter_title": title,
            "scene_content": content.strip()
        }
        scene_list.append(scene_item)
    result = {
        "book_info": book_info,
        "scene_list": scene_list
    }
    return result

if __name__ == "__main__":
    file_list = get_all_novel_files()
    for file_path in file_list:
        bk_name = os.path.splitext(os.path.basename(file_path))[0]
        txt_all = read_text(file_path)
        chap_data = split_chapter(txt_all)
        drama_dict = build_drama_struct(bk_name, chap_data)
        save_path = os.path.join(OUT_DIR, f"{bk_name}_剧本.yaml")
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(drama_dict, f, allow_unicode=True, sort_keys=False)
    print("✅ 基础两层结构转换完成")