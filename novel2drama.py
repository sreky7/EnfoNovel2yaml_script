import os
import yaml

# 改成项目完整根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "source")

def get_all_novel_files():
    """遍历source文件夹，获取全部txt路径"""
    file_list = []
    for fname in os.listdir(SOURCE_DIR):
        if fname.endswith(".txt"):
            file_list.append(os.path.join(SOURCE_DIR, fname))
    return file_list

def read_novel_text(file_path):
    """读取单个txt全文"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def build_drama_struct(book_name, content):
    """按照Schema规范构造标准剧本YAML字典"""
    drama_data = {
        "book_info": {
            "book_name": book_name,
            "source": "本地txt素材"
        },
        "scene_list": [
            {
                "scene_id": 1,
                "scene_content": content
            }
        ]
    }
    return drama_data

if __name__ == "__main__":
    files = get_all_novel_files()
    print("待转换小说列表：", files)