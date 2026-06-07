import sys
sys.stdout.reconfigure(encoding="utf-8")
import os,yaml,re,json,requests,configparser,time,logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "source")
OUT_DIR = os.path.join(BASE_DIR, "output")
ERROR_DIR = os.path.join(BASE_DIR, "error_log")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CFG_PATH = os.path.join(BASE_DIR, "config.ini")
CHAPTER_REG = re.compile(r"^(第[一二三四五六七八九十0-9]+[章节卷回])")

# 全局配置
MAX_CHUNK_LEN = 1800   # 单段最大字符，超长分片
REQ_DELAY = 0.8        # 请求间隔限流
MAX_RETRY = 3          # 接口最大重试次数

# 文件夹初始化
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# 日志配置
logging.basicConfig(
    filename=os.path.join(LOG_DIR,"run.log"),
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8"
)
logger = logging.getLogger()

# 读取配置
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
    """超长文本分片"""
    chunk_list = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunk_list.append(text[start:end])
        start = end
    return chunk_list

def llm_parse_with_retry(chapter_text):
    """带重试、限流的AI调用"""
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
            retry_cnt +=1
            logger.warning(f"调用异常，第{retry_cnt}次重试：{str(e)}")
            time.sleep(1.2)
    # 重试全部失败，写入错误文件
    err_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_err.txt"
    with open(os.path.join(ERROR_DIR,err_name),"w",encoding="utf-8") as f:
        f.write(chapter_text)
    logger.error("多次重试失败，原文存入error_log")
    return None

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
    """
    1.功能描述：在现有V2.1结构体基础上，新增超长分片、接口重试、限流、日志、异常归档能力，完善容错逻辑，保证批量稳定生成剧本。
    2.实现思路：在build_drama上层封装文本分片、异常捕获逻辑，复用原有结构体构造规则，不改动核心Schema字段映射，新增日志与异常落盘模块。
    3.测试方式：各种超长文本、网络异常、空章节场景运行无崩溃，失败内容单独归档，正常内容仍可输出标准剧本字典与YAML。
    """
    total_scene = len(chap_list)
    word_cnt = len(raw_text.replace("\n","").replace(" ",""))
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
                "contents": [{"type":"narrate","content":""}]
            })
            continue
        print(f"正在AI解析【{title}】")
        logger.info(f"开始解析章节：{title}")

        # 超长分片
        chunks = split_long_text(body, MAX_CHUNK_LEN)
        if len(chunks)>1:
            logger.info(f"章节超长，拆分为{len(chunks)}段")

        first_ai_data = None
        full_content = []

        # 遍历所有分片，逐段解析并拼接内容
        for idx, chunk in enumerate(chunks):
            ai_data = llm_parse_with_retry(chunk)
            if ai_data is None:
                # 单段解析失败，原文转为旁白
                full_content.append({"type":"narrate","content":chunk})
                continue

            # 第一段：记录地点、梗概、角色信息
            if idx == 0:
                first_ai_data = ai_data
                # 角色全局去重
                for r in ai_data.get("role_list", []):
                    if not any(x["role_name"] == r["role_name"] for x in all_role):
                        r["role_id"] = global_rid
                        all_role.append(r)
                        global_rid += 1

            # 处理当前分片内容，统一全局角色ID
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

        # 组装单场景数据
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

    return {"drama_info":drama_info,"role_list":all_role,"scenes":scenes}

if __name__ == "__main__":
    logger.info("=====项目启动=====")
    filelist = get_all_novel()
    logger.info(f"待处理文件：{filelist}")
    for filepath in filelist:
        bk_name = os.path.splitext(os.path.basename(filepath))[0]
        content = read_txt(filepath)
        chapters = split_chapter(content)
        final_data = build_drama(bk_name, content, chapters)
        save_path = os.path.join(OUT_DIR, f"{bk_name}_成品剧本.yaml")
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"{bk_name}剧本生成完成")
    print("✅ 全量转换结束")
    logger.info("=====项目执行完毕=====")