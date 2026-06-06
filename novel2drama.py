import sys
sys.stdout.reconfigure(encoding="utf-8")
import os
import yaml
import re
import json
import requests
import configparser
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "source")
OUT_DIR = os.path.join(BASE_DIR, "output")
CFG_PATH = os.path.join(BASE_DIR, "config.ini")
CHAPTER_REG = re.compile(r"^(第[一二三四五六七八九十0-9]+[章节卷回])")

cfg = configparser.ConfigParser()
cfg.read(CFG_PATH, encoding="utf-8")
API_KEY = cfg["DeepSeek"]["API_KEY"]
API_URL = cfg["DeepSeek"]["API_URL"]
MODEL_NAME = cfg["DeepSeek"]["MODEL"]
TEMP = float(cfg["DeepSeek"]["TEMPERATURE"])

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

SYSTEM_PROMPT = """
你是专业剧本改编师，接收小说正文，只返回纯标准JSON，无任何多余注释、说明、中文解释，严格遵守下面JSON结构：
{
    "location": "本场景发生地点",
    "scene_synopsis": "本章节简短剧情梗概（≤50字）",
    "role_list": [{"role_id":数字,"role_name":"角色名","role_desc":"简短人物介绍"}],
    "content_arr": [
        {"type":"narrate","content":"环境/心理旁白"},
        {"type":"action","role_id":数字,"content":"人物动作描写"},
        {"type":"dialogue","role_id":数字,"content":"人物对话台词"}
    ]
}
强制规则：
1.type只有三种：narrate/action/dialogue；
2.narrate不能出现role_id字段，action、dialogue必须绑定对应role_id；
3.全文文字100%拆分，原文内容不能丢字漏段；
4.同一人物角色名统一，不重复新建角色。
"""

def llm_parse_novel(chapter_text):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":chapter_text}],
        "temperature": TEMP
    }
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    ai_raw = resp.json()["choices"][0]["message"]["content"].strip()
    return json.loads(ai_raw)

def get_all_novel():
    res = []
    for fname in os.listdir(SOURCE_DIR):
        if fname.endswith(".txt"):
            res.append(os.path.join(SOURCE_DIR, fname))
    return res

def read_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def split_chapter(full_text):
    lines = full_text.splitlines()
    chap_list = []
    cur_title = "开篇序章"
    buf = []
    for line in lines:
        s = line.strip()
        if CHAPTER_REG.match(s):
            if buf:
                chap_list.append((cur_title, "\n".join(buf)))
                buf = []
            cur_title = s
        else:
            buf.append(line)
    if buf:
        chap_list.append((cur_title, "\n".join(buf)))
    return chap_list

def build_drama(bookname, raw_text, chap_list):
    total_scene = len(chap_list)
    word_cnt = len(raw_text.replace("\n", "").replace(" ", ""))
    drama_info = {
        "book_name": bookname,
        "source": "本地txt小说素材",
        "total_scene": total_scene,
        "original_word_count": word_cnt,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    all_role = []
    global_rid = 1
    scenes = []
    for sid, (title, body) in enumerate(chap_list, start=1):
        print(f"正在AI解析【{title}】")
        try:
            ai_data = llm_parse_novel(body)
        except Exception as e:
            print(f"AI解析失败，章节【{title}】将按纯旁白处理：{e}")
            scenes.append({
                "scene_id": sid,
                "scene_title": title,
                "location": "未知",
                "scene_synopsis": "AI解析失败",
                "contents": [{"type": "narrate", "content": body}]
            })
            continue
        # 角色全局去重
        for r in ai_data.get("role_list", []):
            if not any(x["role_name"] == r["role_name"] for x in all_role):
                r["role_id"] = global_rid
                all_role.append(r)
                global_rid += 1
        # 替换角色ID，加入安全判断
        new_content = []
        for item in ai_data.get("content_arr", []):
            if item["type"] == "narrate":
                new_content.append(item)
                continue
            # 安全查找角色ID
            found = False
            for r in ai_data.get("role_list", []):
                if r["role_id"] == item["role_id"]:
                    tmp_name = r["role_name"]
                    real_rid = next((x["role_id"] for x in all_role if x["role_name"] == tmp_name), None)
                    if real_rid is not None:
                        item["role_id"] = real_rid
                        new_content.append(item)
                        found = True
                    break
            # 如果找不到角色，直接转为旁白
            if not found:
                new_content.append({"type": "narrate", "content": item.get("content", "")})
        scenes.append({
            "scene_id": sid,
            "scene_title": title,
            "location": ai_data.get("location", "未知"),
            "scene_synopsis": ai_data.get("scene_synopsis", ""),
            "contents": new_content
        })
    return {"drama_info": drama_info, "role_list": all_role, "scenes": scenes}

if __name__ == "__main__":
    filelist = get_all_novel()
    for filepath in filelist:
        bk_name = os.path.splitext(os.path.basename(filepath))[0]
        content = read_txt(filepath)
        chapters = split_chapter(content)
        final_data = build_drama(bk_name, content, chapters)
        save_path = os.path.join(OUT_DIR, f"{bk_name}_成品剧本.yaml")
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
    print("✅ 程序执行完毕，剧本已生成")