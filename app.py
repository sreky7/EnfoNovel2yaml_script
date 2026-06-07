import sys
sys.stdout.reconfigure(encoding="utf-8")
import os
import yaml
import re
import json
import requests
import configparser
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "source")
OUT_DIR = os.path.join(BASE_DIR, "output")
ERROR_DIR = os.path.join(BASE_DIR, "error_log")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CFG_PATH = os.path.join(BASE_DIR, "config.ini")
CHAPTER_REG = re.compile(r"^(第[一二三四五六七八九十0-9]+[章节卷回])")

MAX_CHUNK_LEN = 1800
REQ_DELAY = 0.8
MAX_RETRY = 3

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "run.log"),
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8"
)
logger = logging.getLogger()

cfg = configparser.ConfigParser()
cfg.read(CFG_PATH, encoding="utf-8")
API_KEY = cfg["DeepSeek"]["API_KEY"]
API_URL = cfg["DeepSeek"]["API_URL"]
MODEL_NAME = cfg["DeepSeek"]["MODEL"]
TEMP = float(cfg["DeepSeek"]["TEMPERATURE"])

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

def split_long_text(text, max_len):
    chunk_list = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunk_list.append(text[start:end])
        start = end
    return chunk_list

def llm_parse_with_retry(chapter_text):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":chapter_text}],
        "temperature": TEMP
    }
    retry_cnt = 0
    while retry_cnt < MAX_RETRY:
        try:
            time.sleep(REQ_DELAY)
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=90)
            resp.raise_for_status()
            ai_raw = resp.json()["choices"][0]["message"]["content"].strip()
            return json.loads(ai_raw)
        except Exception as e:
            retry_cnt += 1
            logger.warning(f"调用异常，第{retry_cnt}次重试：{str(e)}")
            time.sleep(1.2)
    err_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_err.txt"
    with open(os.path.join(ERROR_DIR, err_name), "w", encoding="utf-8") as f:
        f.write(chapter_text)
    logger.error("多次重试失败，原文存入error_log")
    return None

def get_all_novel():
    res = []
    for fname in os.listdir(SOURCE_DIR):
        if fname.endswith(".txt"):
            res.append({"name": fname, "path": os.path.join(SOURCE_DIR, fname)})
    return res

def get_all_output():
    res = []
    for fname in os.listdir(OUT_DIR):
        if fname.endswith(".yaml"):
            res.append({"name": fname, "path": os.path.join(OUT_DIR, fname)})
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
        if not body.strip():
            logger.info(f"【{title}】内容为空，跳过解析")
            scenes.append({
                "scene_id": sid,
                "scene_title": title,
                "location": "未知",
                "scene_synopsis": "章节无正文",
                "contents": [{"type": "narrate", "content": ""}]
            })
            continue
        logger.info(f"开始解析章节：{title}")

        chunks = split_long_text(body, MAX_CHUNK_LEN)
        if len(chunks) > 1:
            logger.info(f"章节超长，拆分为{len(chunks)}段")

        first_ai_data = None
        full_content = []

        for idx, chunk in enumerate(chunks):
            ai_data = llm_parse_with_retry(chunk)
            if ai_data is None:
                full_content.append({"type": "narrate", "content": chunk})
                continue

            if idx == 0:
                first_ai_data = ai_data
                for r in ai_data.get("role_list", []):
                    if not any(x["role_name"] == r["role_name"] for x in all_role):
                        r["role_id"] = global_rid
                        all_role.append(r)
                        global_rid += 1

            for item in ai_data.get("content_arr", []):
                if item["type"] == "narrate":
                    full_content.append(item)
                    continue

                found = False
                for r in ai_data.get("role_list", []):
                    if r["role_id"] == item["role_id"]:
                        tmp_name = r["role_name"]
                        real_rid = next((x["role_id"] for x in all_role if x["role_name"] == tmp_name), None)
                        if real_rid is not None:
                            item["role_id"] = real_rid
                            full_content.append(item)
                            found = True
                        break
                if not found:
                    full_content.append({"type": "narrate", "content": item.get("content", "")})

        if first_ai_data:
            scene_loc = first_ai_data.get("location", "未知")
            scene_syn = first_ai_data.get("scene_synopsis", "")
        else:
            scene_loc = "解析失败"
            scene_syn = "部分内容解析异常"

        scenes.append({
            "scene_id": sid,
            "scene_title": title,
            "location": scene_loc,
            "scene_synopsis": scene_syn,
            "contents": full_content
        })

    return {"drama_info": drama_info, "role_list": all_role, "scenes": scenes}

@app.route('/api/novels', methods=['GET'])
def list_novels():
    novels = get_all_novel()
    return jsonify(novels)

@app.route('/api/outputs', methods=['GET'])
def list_outputs():
    outputs = get_all_output()
    return jsonify(outputs)

@app.route('/api/novel/<filename>', methods=['GET'])
def get_novel_content(filename):
    filepath = os.path.join(SOURCE_DIR, filename)
    if os.path.exists(filepath):
        content = read_txt(filepath)
        return jsonify({"content": content})
    return jsonify({"error": "文件不存在"}), 404

@app.route('/api/output/<filename>', methods=['GET'])
def get_output_content(filename):
    filepath = os.path.join(OUT_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content, "yaml": yaml.safe_load(content)})
    return jsonify({"error": "文件不存在"}), 404

@app.route('/api/convert', methods=['POST'])
def convert_novel():
    data = request.get_json()
    novel_text = data.get('text', '')
    book_name = data.get('bookName', 'untitled')

    if not novel_text.strip():
        return jsonify({"error": "请输入小说内容"}), 400

    try:
        chapters = split_chapter(novel_text)
        final_data = build_drama(book_name, novel_text, chapters)
        
        save_path = os.path.join(OUT_DIR, f"{book_name}_成品剧本.yaml")
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
        
        logger.info(f"{book_name}剧本生成完成")
        return jsonify({"success": True, "data": final_data, "saved": True})
    except Exception as e:
        logger.error(f"转换失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/convert-file/<filename>', methods=['POST'])
def convert_file(filename):
    filepath = os.path.join(SOURCE_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404

    try:
        content = read_txt(filepath)
        book_name = os.path.splitext(filename)[0]
        chapters = split_chapter(content)
        final_data = build_drama(book_name, content, chapters)
        
        save_path = os.path.join(OUT_DIR, f"{book_name}_成品剧本.yaml")
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
        
        logger.info(f"{book_name}剧本生成完成")
        return jsonify({"success": True, "data": final_data})
    except Exception as e:
        logger.error(f"转换失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    logger.info("=====Flask服务启动=====")
    print("\n服务已启动！访问地址：")
    print("本机访问：http://localhost:5000")
    print("本机访问：http://127.0.0.1:5000")
    # 如果你想看到局域网地址，可以加上这段
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        print(f"局域网访问：http://{local_ip}:5000")
        s.close()
    except:
        pass
    print("\n按 Ctrl+C 停止服务\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)