# 剧本YAML Schema V1.0
## 结构定义（两层结构：book_info + scene_list）
```yaml
book_info:
  book_name: str       # 必填：书名
  source: str          # 必填：素材来源
  chapter_total: int   # 必填：总章节数，用于3章分幕判断
scene_list:
  - scene_id: int
    chapter_title: str
    scene_content: str