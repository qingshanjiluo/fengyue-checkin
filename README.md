# 🎋 风月AI 每日自动签到

> 基于 GitHub Actions 的 [aiaha.xyz](https://aiaha.xyz) 每日自动签到工具，每天北京时间 08:30 自动执行。

## 功能

- 自动登录获取 JWT Token
- 检测当日是否已签到，避免重复
- 自动签到领取积分
- 通过 GitHub Actions 定时执行，无需手动操作
- 支持手动触发签到

## 快速开始

### 1. 配置 GitHub Secrets

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加两个密钥：

| 名称 | 值 |
|---|---|
| `FENGYUE_EMAIL` | 你的账号（邮箱或用户名） |
| `FENGYUE_PASSWORD` | 你的密码 |

### 2. 启用 GitHub Actions

推送代码后，Action 会自动启用。默认每天 `UTC 00:30`（北京时间 08:30）执行签到。

### 3. 手动触发

进入 **Actions → fengyue daily check-in → Run workflow** 即可手动签到。

## 运行流程

```
Login → 获取 JWT Token
  ↓
查询月度签到日历 (monthly_calendar)
  ↓
检测今日是否已签到
  ↓
未签到 → GET sign_in 签到  → 查询积分余额
已签到 → 直接返回积分余额
```

## 文件结构

```
.github/workflows/daily-checkin.yml   # GitHub Actions 工作流
scripts/fengyue_checkin.py            # 签到脚本
requirements.txt                      # Python 依赖
```

## 安全提示

仓库中的 `结构/`、`请求体/`、`未命名文件夹/` 目录包含抓包捕获的 HTTP 请求/响应数据（如 JWT Token 等敏感信息）。如为公开仓库，建议删除这些目录：

```bash
git rm -r --cached 结构 请求体 未命名文件夹
git commit -m "remove sensitive capture files"
git push
```

## 技术细节

- 签到 API：`GET /console/api/sign_in`（非 POST）
- 签到状态查询：`GET /console/api/monthly_calendar?date=YYYY-MM`
- 积分查询：`GET /go/api/account/point`
- 鉴权方式：JWT Bearer Token
