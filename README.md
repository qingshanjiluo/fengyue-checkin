# 🎋 风月AI 工具集

> 包含每日自动签到 + 角色卡批量制作工具，基于 [aiaha.xyz](https://aiaha.xyz)

---

## 📦 工具列表

| 工具 | 文件 | 说明 |
|---|---|---|
| 每日签到 | `scripts/fengyue_checkin.py` | GitHub Actions 定时自动签到 |
| 角色卡制作 | `scripts/character_maker.py` | 本地浏览器自动化批量创建角色卡 |

---

## 工具一：每日自动签到

基于 GitHub Actions，每天 UTC 00:30（北京时间 08:30）自动执行签到领取积分。

### 配置

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加：

| 名称 | 值 |
|---|---|
| `FENGYUE_EMAIL` | 你的账号（邮箱或用户名） |
| `FENGYUE_PASSWORD` | 你的密码 |

### 手动触发

Actions → `fengyue daily check-in` → Run workflow

### 运行流程

```
Login → 获取 JWT Token → 查询签到日历 → 检测今日是否已签到 → 未签到则签到 → 报告积分
```

---

## 工具二：角色卡制作工具

本地运行的浏览器自动化脚本，通过 Playwright 操控 Chrome 批量创建角色卡。

### 安装

```bash
pip install playwright
python -m playwright install chromium
```

### 用法

**方式一：命令行参数**
```bash
python scripts/character_maker.py \
  --email sifangzhiji@qq.com \
  --password 你的密码 \
  --name "角色名称" \
  --summary "简介" \
  --detail "详细介绍" \
  --prompt "角色设定prompt（人格、背景、说话风格等）" \
  --greeting "开场白" \
  --cover "D:/图片/封面.png" \
  --chat-bg "D:/图片/聊天背景.png" \
  --mobile-bg "D:/图片/移动端背景.png"
```

**方式二：JSON 配置文件**
```bash
python scripts/character_maker.py \
  --email sifangzhiji@qq.com \
  --password 你的密码 \
  --json card.json
```

JSON 文件示例 `card.json`：
```json
{
  "name": "温柔学姐",
  "summary": "一个温柔体贴的学姐角色",
  "detail": "她是你的大学学姐，性格温柔，总是照顾你",
  "prompt": "你是我的学姐，今年大四，性格温柔体贴...",
  "greeting": "你好呀，学弟！今天又来找我啦？",
  "cover": "D:/images/cover.png",
  "chat_bg": "D:/images/chat_bg.png"
}
```

**方式三：从环境变量读取账号**
```bash
set FENGYUE_EMAIL=sifangzhiji@qq.com
set FENGYUE_PASSWORD=你的密码
python scripts/character_maker.py --json card.json
```

### 无头模式

```bash
python scripts/character_maker.py --headless --email ... --password ... --name "..."
```

### 创作流程

脚本自动完成以下 4 步：

```
Step 1: 基础设定 → 封面/背景/语言/名称/简介
Step 2: 角色与背景设定 → Prompt/开场白
Step 3: 追加设定 → 可选配置
Step 4: 保存与发布 → 发布角色卡
```

---

## 项目结构

```
.github/workflows/
  daily-checkin.yml        # GitHub Actions 定时签到
scripts/
  fengyue_checkin.py       # 签到脚本
  character_maker.py       # 角色卡制作工具
requirements.txt           # Python 依赖
```

## 技术细节

- 签到 API：`GET /console/api/sign_in`
- 签到状态：`GET /console/api/monthly_calendar?date=YYYY-MM`
- 创建角色卡：浏览器自动化操作 `/zh/character/{uuid}/configuration`
- 鉴权方式：JWT Bearer Token

## 安全提示

仓库中的 `结构/`、`请求体/`、`未命名文件夹/` 包含抓包捕获的敏感数据。如为公开仓库，建议删除：

```bash
git rm -r --cached 结构 请求体 未命名文件夹
git commit -m "remove sensitive capture files"
git push
```
