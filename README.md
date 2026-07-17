# 风月AI 角色卡工作室

> 通过自然语言描述，AI 自动生成完整角色卡并一键发布到 aiaha.xyz 平台。
> 支持 Web 可视化操作、命令行批量创建、GitHub Actions 自动化三种使用方式。

## 项目介绍

风月AI 角色卡工作室是一个面向 aiaha.xyz 平台的角色卡批量创建工具。用户只需用自然语言描述角色想法，AI 会自动补全角色设定、外貌、性格、背景、开场白、标签等全部字段，并操控浏览器完成从登录到发布的完整流程。

### 痛点解决

- 手动创建角色卡需填写 20+ 字段，耗时长
- 平台模型选择繁琐，CG 配图、标签添加等操作分散
- 批量创作缺乏自动化手段

### 核心能力

| 能力 | 说明 |
|------|------|
| AI 角色生成 | 自然语言 → 完整角色卡 JSON |
| 自动发布 | 浏览器自动化完成 4 步创建流程 |
| 多角色支持 | 每作品最多 10 个角色 |
| CG 图片 | 关键词触发场景图，自动上传匹配 |
| 开场白 | 自动生成角色问候语 |
| 标签管理 | AI 自动打标签 + 手动管理 |
| 模型选举 | 发布时可选游玩模型（默认 deepseek-v4-flash） |
| 图片库 | 本地图库，AI 自动匹配封面/背景 |
| 识图标注 | 图片自动生成中文关键词标签 |
| 热榜浏览 | 查看平台周/月/总榜获取灵感 |

## 架构

```
┌─────────────────────────────────────────────────────┐
│                    用户交互层                        │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Web 界面     │  │ CLI 命令行│  │ GitHub Actions│  │
│  │ (studio.html)│  │ (终端)   │  │ (CI 工作流)  │  │
│  └──────┬───────┘  └────┬─────┘  └──────┬────────┘  │
└─────────┼────────────────┼───────────────┼──────────┘
          │                │               │
┌─────────▼────────────────▼───────────────▼──────────┐
│                    服务层                            │
│  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │ character_studio│  │ ai_runner / ai_runner.py │  │
│  │ .py (Flask)     │  │ (CI 执行器)              │  │
│  └────────┬────────┘  └────────┬─────────────────┘  │
│           │                    │                    │
│  ┌────────▼────────────────────▼─────────────────┐  │
│  │         character_maker.py (核心引擎)          │  │
│  │   Playwright 浏览器自动化，操控 aiaha.xyz     │  │
│  │   - login / step1~4 / greeting / tags / model │  │
│  └────────────────┬──────────────────────────────┘  │
│                   │                                 │
│  ┌────────────────▼──────────────────────────────┐  │
│  │      AI 接口层                                │  │
│  │  OpenAI 兼容 API → 角色卡 JSON 生成           │  │
│  │  (api.xiaomimimo.com/v1 / 自定义)             │  │
│  └───────────────────────────────────────────────┘  │
│                                                   │
│  ┌───────────────────────────────────────────────┐  │
│  │      辅助工具                                 │  │
│  │  vision_tagger.py  (本地 100MB 视觉模型)      │  │
│  │  hotlist_scraper.py (热榜数据抓取)            │  │
│  │  tag_images.js       (文件名清洗)             │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 数据流

```
用户描述 → AI API → JSON 角色卡数据
                  → character_maker 浏览器自动化
                    → 登录 → 填写基础信息 → 添加角色
                    → 开场白 → CG图片 → 标签
                    → 切换模型 → 发布 → 完成
```

## 两个核心工具

### 1️⃣ character_studio.py — Web 可视化工作室

Flask Web 服务器，提供浏览器端可视化操作界面。适合日常交互式使用。

**启动方式：**
```bash
python scripts/character_studio.py
# 或双击 start.bat
```
打开 http://127.0.0.1:5000

**功能：**
- 对话式角色卡创建（输入角色想法，AI 自动生成）
- 热榜浏览（获取平台热门作品灵感）
- 图片管理（上传/预览/删除/重命名）
- AI 识图标注（一键为图片生成中文标签）
- 设置面板（API Key、模型、AI 人格调教、匿名发布等）

**界面布局：**
```
┌──────────┬────────────────────────────────────┐
│ 侧边栏   │       主内容区                      │
│          │                                    │
│ 热榜     │  ┌──────────────────────────────┐  │
│ 图片库   │  │   聊天对话面板               │  │
│ 设置     │  │   - AI 助手交流              │  │
│          │  │   - 角色卡自动生成           │  │
│          │  └──────────────────────────────┘  │
│          │  ┌──────────────────────────────┐  │
│          │  │   进度面板                   │  │
│          │  │   - 实时步骤更新            │  │
│          │  │   - 发布结果/链接           │  │
│          │  └──────────────────────────────┘  │
└──────────┴────────────────────────────────────┘
```

### 2️⃣ character_maker.py — 命令行自动化引擎

Playwright 浏览器自动化核心，支持 JSON 配置文件批量创建。适合脚本化、CI/CD 场景。

**命令行用法：**
```bash
# 直接使用 Python 脚本
python scripts/ai_runner.py --prompt "创建一个古风少女角色，温柔善良"
python scripts/ai_runner.py --json card.json

# 或直接调用底层引擎
python scripts/character_maker.py --email user@x.com --password xxx --json card.json
```

**JSON 配置示例 (card.json)：**
```json
{
  "name": "青萝",
  "summary": "隐世药仙，温柔如水",
  "detail": "出生于药王谷的少女，自幼随师父习医...",
  "char_name": "青萝",
  "char_occupation": "药师",
  "char_age": "18",
  "char_gender": "女",
  "char_setting": "药王谷传人，精通百草",
  "char_appearance": "青丝如瀑，眸若星辰，一袭青衣",
  "char_personality": "温柔善良、恬静淡然",
  "char_tone": "语气轻柔，如春风拂面",
  "char_background": "自幼被药王谷谷主收养",
  "greeting": "公子，你来了。我煮了新茶，要尝尝吗？",
  "tags": ["古风", "治愈", "仙侠"],
  "anonymous": false
}
```

## GitHub Actions 自动化

一键部署到 CI，定时或手动触发。

**工作流文件：** `.github/workflows/ai-create.yml`

**需要设置的 Secrets：**
| Secret | 值 |
|--------|-----|
| `FY_EMAIL` | 风月账号邮箱 |
| `FY_PASSWORD` | 风月密码 |
| `AI_API_KEY` | API Key |

**触发方式：**
- 手动：Actions → AI 角色卡自动创建 → Run workflow
- 定时：默认每周一早 10 点（可修改 cron 表达式）

## 辅助工具

| 工具 | 文件 | 用途 |
|------|------|------|
| 识图标注（本地） | `tag_local.bat` → `vision_tagger.py` | 用 100MB 模型为图片生成中文标签 |
| 识图标注（API） | `tag_images.js --vision` → `image_tagger.py` | 调用云端 API 识图标注 |
| 文件名清洗 | `tag_images.bat` → `tag_images.js` | 去除文件名中的随机哈希后缀 |
| 热榜抓取 | `hotlist_scraper.py` | 抓取平台热门作品数据 |

## 项目结构

```
├── .github/workflows/
│   └── ai-create.yml           # GitHub Actions 自动化工作流
├── scripts/
│   ├── character_maker.py      # 核心引擎 — Playwright 浏览器自动化
│   ├── character_studio.py     # Web 界面 — Flask 可视化工作室
│   ├── ai_runner.py            # CI 运行器 — 轻量级命令行版本
│   ├── hotlist_scraper.py      # 热榜抓取工具
│   ├── image_tagger.py         # 云端 API 识图标注
│   ├── vision_tagger.py        # 本地模型识图标注（100MB）
│   ├── tag_images.js           # 文件名清洗 + AI 标注入口
│   └── templates/
│       └── studio.html         # 前端界面（玻璃拟态设计）
├── generated_imgs/             # 本地图片库
├── start.bat                   # 快速启动脚本
├── tag_local.bat               # 本地识图标注启动
├── tag_images.bat              # 文件名清洗启动
├── requirements.txt            # Python 依赖
└── README.md
```

## 快速开始

### 本地运行

```bash
pip install -r requirements.txt
python -m playwright install chromium
python scripts/character_studio.py
```

打开 http://127.0.0.1:5000

### 配置 AI 助手

在设置面板中可自定义 AI 助手人格。默认为拟人化助手，兼具男女特征，高冷理性，可涩涩，20岁出头。可在"AI 助手调教"文本框中修改。

### 图片管理

将图片放入 `generated_imgs/` 目录，AI 会自动匹配合适的封面/背景图。
双击 `tag_local.bat` 可对新增图片执行本地 AI 识图标注。
