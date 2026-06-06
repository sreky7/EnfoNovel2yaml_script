# 小说转剧本YAML输出规范
# 顶层：剧本基础信息+场景数组
drama_info:
  book_name: "原小说书名【字符串】"
  author: "原作者名【字符串】"
  total_scene: 总幕数【数字】
  brief: "全书故事简介【字符串】"

# 场景列表：多幕剧情
scenes:
  - scene_id: 场景序号【数字，从1自增】
    scene_title: "单幕小标题【字符串】"
    location: "发生地点【室内/野外/宫廷等】"
    scene_brief: "本幕梗概"
    contents:
      # 内容分三类：旁白、动作、人物台词
      - type: narration #旁白：环境、心理描写
        content: "旁白文本内容"
      - type: action   #动作描写
        role: "人物名称"
        content: "人物动作细节"
      - type: dialogue #人物对白
        role: "说话角色名"
        content: "台词内容"