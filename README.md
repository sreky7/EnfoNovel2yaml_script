# DeepSeek全自动小说转剧本部署指南
## 项目说明
本工具依据自研YAML Schema规范，实现本地TXT小说一键自动转为结构化影视剧剧本，依托DeepSeek大模型全自动拆分旁白、动作、人物台词，全程无需人工修改。

## 步骤1：DeepSeek平台注册配置密钥
1. 打开 https://platform.deepseek.com 注册并登录账号；
2. 左侧菜单栏【API Keys】→【Create new API Key】，生成 `sk-` 开头密钥；
3. 将密钥填写至项目 `config.ini` 配置文件中。

## 步骤2：项目目录结构
NovelToScript
├─ source/       存放待转换txt小说源文件
├─ output/       程序自动生成成品剧本YAML
├─ logs/         程序运行日志（自动生成）
├─ error_log/    AI解析失败原文存档目录（自动生成）
├─ doc/          Schema规范设计文档
├─ config.ini    DeepSeek接口配置文件
├─ novel2drama.py 主程序
└─ requirements.txt 项目依赖清单

## 步骤3：环境安装
在项目根目录打开终端，执行依赖安装命令：
pip install -r requirements.txt

## 步骤4：运行程序
1. 将小说 `.txt` 文件放入 `source` 文件夹；
2. 终端执行启动命令：
python novel2drama.py
3. 执行完成后，`output` 目录自动输出 `书名_成品剧本.yaml` 文件。

## 常见报错说明
1. 401：`config.ini` 内 API_KEY 错误、存在多余空格；
2. 402：DeepSeek 账户余额/免费额度不足，需在平台充值；
3. 接口超时：网络波动，重新运行脚本即可；
4. AI返回非JSON格式：禁止修改代码内 SYSTEM_PROMPT 提示词。

# PR8 迭代优化功能
1. 超长章节自动文本分片，解决单段内容过长接口超限报错；
2. API 接口支持3次自动重试 + 请求限流，规避高频调用封禁风险；
3. 全流程运行日志自动落地 `logs/run.log`，方便问题排查；
4. 解析失败的原文自动归档至 `error_log` 目录，单章异常不中断整本书转换；
5. 空内容/空白章节自动跳过AI请求，优化资源占用；
6. 修复分片仅解析首段导致原文内容丢失问题，保证全文完整输出。