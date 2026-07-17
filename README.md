# 风月AI 角色卡工作室

AI 驱动的角色卡批量创建工具。通过自然语言描述，自动生成完整角色卡并发布到 aiaha.xyz 平台。

## 功能

- **AI 生成角色卡** — 自然语言描述 → AI 自动补全角色设定、外貌、性格、背景、标签、开场白
- **一键发布** — 自动登录 → 填写信息 → 添加角色 → 设置开场白 → 上传 CG → 添加标签 → 切换模型 → 发布
- **图片管理** — 本地图库管理，AI 自动匹配合适的封面/背景/CG 图片
- **AI 识图标注** — 用本地 100MB 视觉模型自动为图片生成中文关键词标签
- **热榜浏览** — 浏览平台周/月/总榜，给 AI 提供创作灵感
- **多角色支持** — 每个作品可添加最多 10 个角色
- **CG 图片** — 配置关键词触发的 CG 场景图
- **模型切换** — 发布时可选游玩模型（默认 `deepseek-v4-flash`）

## 快速开始

### 本地运行

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium

# 启动 Web 界面
python scripts/character_studio.py
# 或双击 start.bat
```

打开 http://127.0.0.1:5000

### GitHub Actions 自动化

1. 推送代码到 GitHub
2. 在 Settings → Secrets and variables → Actions 添加：
   - `FY_EMAIL` — 风月账号邮箱
   - `FY_PASSWORD` — 风月密码
   - `AI_API_KEY` — API Key
3. 进入 Actions → **AI 角色卡自动创建** → Run workflow → 输入角色描述

## 项目结构

```
├── .github/workflows/
│   └── ai-create.yml          # GitHub Actions 工作流
├── scripts/
│   ├── character_maker.py     # Playwright 自动化核心
│   ├── character_studio.py    # Flask Web 服务器
│   ├── ai_runner.py           # CI 精简版运行器
│   ├── hotlist_scraper.py     # 热榜抓取
│   ├── image_tagger.py        # AI 识图标注（API版）
│   ├── vision_tagger.py       # AI 识图标注（本地模型版）
│   ├── tag_images.js          # 文件名清洗工具
│   └── templates/studio.html  # Web 前端界面
├── generated_imgs/            # 图片库目录
├── requirements.txt
└── start.bat
```

## 配置

在 Web 界面右侧设置面板中配置：

| 字段 | 说明 |
|------|------|
| 接口地址 | OpenAI 兼容 API 地址 |
| API Key | API 密钥 |
| 模型名称 | 生成角色卡 & 发布时使用的模型 |
| 风月账号 | 登录 aiaha.xyz 的邮箱密码 |
| AI 助手调教 | 自定义 AI 助手的性格、语气 |

## 命令行用法

```bash
# 从 JSON 创建角色卡
python scripts/character_maker.py --email user@example.com --password xxx --json card.json

# AI 识图标注（本地模型）
tag_local.bat

# 文件名清洗
tag_images.bat
```
