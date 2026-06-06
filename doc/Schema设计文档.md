# DeepSeek全自动小说转剧本部署指南
## 步骤1：DeepSeek平台注册拿密钥
1.打开 https://platform.deepseek.com 注册账号；
2.左侧API Keys→Create new API Key，复制sk开头密钥填入config.ini。
## 步骤2：项目目录结构
NovelToScript
├─ source  存放待转换txt小说
├─ output  自动生成成品剧本
├─ doc     Schema规范文档
├─ config.ini 配置API密钥
├─ novel2drama.py
└─ requirements.txt
## 步骤3：安装依赖
pip install -r requirements.txt
## 步骤4：运行
python novel2drama.py
output自动生成成品yaml剧本，全自动拆分旁白/动作/台词，无需手动修改。
## 报错说明
401：密钥错误；超时：网络重试；返回非json：不要修改Prompt。
## 版本迭代记录
V1.0：基础书名+章节+单文本字段；
V2.0：拆分旁白/动作/台词三级结构；
V2.1：新增全局角色库、字数、生成时间、多可选拓展字段，定型最终规范。
## 版本迭代记录
V1.0：基础两层结构 book_info + scene_list，实现基础YAML封装；
V2.0：拆分旁白/动作/台词内容结构，丰富字段；
V2.1：新增全局角色库、字数、创建时间等拓展字段，Schema正式定型。