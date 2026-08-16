# 醉翁亭商城推进计划与 TODO

依据: 01-商城设计文档.md
推进方式: 分阶段，每阶段含后端改动 + 前端改动 + 部署验证，验收通过再进入下一阶段。

阶段标记约定:
- [ ] 未开始
- [x] 已完成
- 每项任务含文件路径与验收标准，按顺序执行。

---

## 阶段 1: 核心商城框架（首页/市场/用户中心/充值/邀请/管理员）— 已完成

### 1.1 后端: 公开统计接口

- [x] 任务 1.1.1 新增 `GET /api/stats`（公开）
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\src\index.js`（公开路由区，products/notifications 旁）
  - 改动: 查询 accounts 按 platform 分组（total / on_sale / sold / dead / total_petals / signed_today），汇总 summary，附 token_per_rmb
  - 验收: `GET /api/stats` 200 且返回 platforms 数组与 summary

- [x] 任务 1.1.2 部署并验证
  - 命令: `npx wrangler deploy`（workdir `G:\皮皮\编程项目\fengyue\zuiweng-worker`）
  - 验收: 请求返回统计数据

### 1.2 后端: 邀请码

- [x] 任务 1.2.1 schema 加表
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\schema.sql`
  - 改动: 新增 invite_codes(user_id, code) 唯一表 + invite_relations(inviter_id, invitee_id)（代替 users 加列方案）
  - 验收: D1 中存在 invite_codes / invite_relations 表

- [x] 任务 1.2.2 注册接口支持 invite_code
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\src\index.js`（/api/auth/register 段）
  - 改动: 接收可选 invite_code；校验邀请码对应用户存在则写入 invite_relations；新用户无码则生成 8 位随机码唯一
  - 验收: 带码注册后 invite_relations 正确；重复注册码不冲突

- [x] 任务 1.2.3 新增 `GET /api/invite/code`（登录）
  - 文件: 同上（登录区）
  - 改动: 用户无邀请码则生成并保存；返回 { invite_code, invited }
  - 验收: 登录态返回用户邀请码

### 1.3 前端: 全局改造

- [x] 任务 1.3.1 常量扩展
  - 文件: `G:\皮皮\编程项目\fengyue\醉翁亭\醉翁亭.html`（顶部常量区）
  - 改动: PLATFORM_LABELS/PLATFORM_UNITS 增加 missai('密丝AI','体验点')、dzmm('DZMM','积分')；新增 RECHARGE_PACKAGES、QQ_GROUP 常量
  - 验收: 常量区新增定义完成

- [x] 任务 1.3.2 导航栏扩展
  - 文件: 同上（Navbar 组件）
  - 改动: navItems 加入 账号市场/脚本皮肤/玩家市场/聊天室/用户中心/充值/邀请；管理员加 渠道管理/通知管理/系统设置
  - 验收: 移动端与 PC 端菜单项齐全

- [x] 任务 1.3.3 App 路由扩展
  - 文件: 同上（App 组件）
  - 改动: case 增加 market/me/recharge/invite/scripts/players/chat/admin-channels/admin-notices/admin-settings；受保护页未登录跳 login
  - 验收: 各页可路由，未登录访问 me 跳登录

### 1.4 前端: 首页

- [x] 任务 1.4.1 公告滚动栏 + 数据面板 + 平台卡片 + 公告列表
  - 文件: 同上（HomePage）
  - 改动: 顶部公告轮播 / 主视觉 / stats 数据面板 4 卡片 / 平台介绍卡（调 /api/stats）/ 公告完整列表 / 号池一览 + 渠道状态
  - 验收: 首页数据真实展示，无公告时隐藏栏

### 1.5 前端: 账号市场

- [x] 任务 1.5.1 市场页（替代原 list/detail）
  - 文件: 同上（MarketPage 组件）
  - 改动: 平台筛选 / 商品卡 / 购买流程（确认弹窗->POST /api/orders->成功展示凭据+印章动画->刷新余额；未登录提示登栈；余额不足提示充值跳转）
  - 验收: 完整购买链路可用，余额实时刷新

### 1.6 前端: 用户中心 / 充值 / 邀请

- [x] 任务 1.6.1 MePage
  - 文件: 同上
  - 改动: 用户信息卡 / 我的账号列表（展开凭据）/ 交易记录（类型中文映射）
  - 验收: 三块数据真实展示

- [x] 任务 1.6.2 RechargePage
  - 文件: 同上
  - 改动: 汇率卡（token_per_rmb）/ 套餐选择 / 复制备注（含用户ID）/ QQ群提示
  - 验收: 复制功能可用，备注含用户ID与金额代币

- [x] 任务 1.6.3 InvitePage
  - 文件: 同上
  - 改动: 调 GET /api/invite/code 展示邀请码 + 复制按钮 + 奖励规则文案
  - 验收: 显示并复制邀请码

### 1.7 前端: 占位页

- [x] 任务 1.7.1 ScriptsPage / PlayersPage / ChatPage 占位
  - 文件: 同上
  - 改动: "敬请期待"占位组件
  - 验收: 三页可访问

### 1.8 前端: 管理员页

- [x] 任务 1.8.1 ChannelsAdminPage
  - 文件: 同上
  - 改动: 渠道表格 + 行内编辑保存 + "全池重新评估上架"按钮
  - 验收: 修改保存生效，refresh 后商品数量变化

- [x] 任务 1.8.2 NoticesAdminPage
  - 文件: 同上
  - 改动: 新建表单 + 列表（停用/删除/编辑）
  - 验收: 前台公告即时更新

- [x] 任务 1.8.3 SettingsAdminPage
  - 文件: 同上
  - 改动: token_per_rmb 编辑 + 汇率预览
  - 验收: 修改后充值页汇率同步

### 1.9 前端: 部署与验收

- [x] 任务 1.9.1 部署副本同步
  - 命令: 复制 `醉翁亭.html` 到 `D:\Temp\opencode\zuiweng-site\index.html`，部署 Cloudflare Pages（--branch=main）
  - 验收: 线上域名可见新商城

- [x] 任务 1.9.2 阶段 1 验收清单（设计文档第 6 节逐条过）
  - 验收: 全部通过（含购买 500 代币账号交付、余额/流水/邀请码/管理员页实测）

### 1.10 提交与推送

- [x] 任务 1.10.1 提交推送
  - 命令: git commit + push（仓库 `G:\皮皮\编程项目\fengyue`）
  - 验收: commit 3403541 已推送

---

## 阶段 2: 套餐充值订单与 QQ 群配置 — 已完成

- [x] 后端: schema 新增 recharge_orders 表（order_no 唯一 / user_id / amount_rmb / bonus / token_amount / status / note / handled_by / handled_at / created_at）+ settings 种子 `qq_group`
  - `POST /api/recharge`（登录，创建待审核订单，按 token_per_rmb 计算应到账）
  - `GET /api/recharge/orders`（登录，我的订单）
  - `GET /api/admin/orders?status=` + `PATCH /api/admin/orders/:id`（done 发放代币+记 transactions charge；rejected 拒绝）
  - `/api/admin/settings` PATCH 支持 qq_group；`/api/stats` 返回 qq_group
- [x] 前端: RechargePage 改为"生成订单"（展示订单号/金额/应到账/复制备注）+ 我的充值订单列表（待审核/已到账/已拒绝）；SettingsAdminPage 加 QQ 群编辑；新增 OrdersAdminPage（筛选+确认到账+拒绝）并入管理员导航；顶栏余额经 MePage onRefresh 同步
- [x] 验收: 用户下单（RCMSVSJPEH8GOV 待审核）-> 管理员确认到账 -> 余额 2500+1000=3500 -> 交易记录出现 charge 1000 充值订单
- [x] 部署与提交: Worker 已 deploy（e39a274d），Pages 已发布，commit 130b813 已推送

## 阶段 3: 脚本/皮肤市场 + 玩家市场 — 已完成

- [x] 后端: schema 新增 products 表（type=script/skin, name, desc, price, file_url, thumbnail, platform, active, sold）+ player_offers 表（user_id, title, desc, kind=sell/buy, price, status=open/closed）
  - 公开: `GET /api/script-products`（?type=）、`GET /api/player-offers`（open 列表含发布人）
  - 登录: `POST /api/script-orders`（扣代币+sold+1+记流水 buy）、`POST /api/player-offers`（发布）、`GET /api/player-offers/mine`、`PATCH /api/player-offers/:id`（本人或管理员关闭）
  - 管理: `GET/POST /api/admin/products`、`PATCH/DELETE /api/admin/products/:id`
- [x] 前端: ScriptsPage（全部/脚本/皮肤 tab + 商品卡 + 确认购取 + 购得弹窗含下载链接，余额不足跳充值）；PlayersPage（当前发布 + 我要发布表单 + 我的发布关闭）；ProductsAdminPage（上架表单 + 行内编辑/上下架/删除）；导航加"商品管理"
- [x] 验收: 管理员上架 2 商品 -> 脚本皮肤市场可见 -> 购买自动签到脚本扣 50 代币并展示下载链接 -> 发布"出售密丝180体验点号"成功 -> 关闭后我的发布减 1 -> 商品管理页行内编辑/上下架/删除可用
- [x] 部署与提交: Worker 已 deploy（7fe9a6ed），Pages 已发布，commit ab097ac 已推送

## 阶段 4: 聊天室 — 已完成

- [x] 方案决策: D1 消息表 + 前端轮询（3 秒间隔，简单可靠）
- [x] 后端: schema 新增 chat_messages 表（user_id, content, created_at）；`GET /api/chat/messages?after=`（登录，拉取 after 之后的消息，最多 100 条）；`POST /api/chat/messages`（登录，发送消息，限 500 字）
- [x] 前端: ChatPage（消息列表含头像+用户名+内容+时间，自己消息右侧琥珀色气泡，输入框+发送，Enter 快捷键，自动轮询拉取新消息，空状态提示，未登录跳转）
- [x] 验收: 发送"大家好，欢迎来到醉翁亭聊天室！" -> 消息出现在列表（1 条消息 + 头像 + 用户名 + 时间 + 内容）-> 3 秒后轮询拉取（无新消息时不重复）-> 多端同步
- [x] 部署与提交: Worker 已 deploy（f1ed5fa7），Pages 已发布，commit 0b12959 已推送

---

## 进行中工作（阶段 0 遗留，不影响主线）

- [ ] 密丝AI 邮箱认证 2000 体验点奖励领取方式确认（dailyTask claim taskType 枚举，或真实点击认证页抓包）；不影响注册+签到主线
- [ ] 风月账号 petals=0 确认（fengyue.py daily 是否跑过、points 接口字段）；影响 fengyue 渠道准入阈值，渠道默认 disabled 不阻塞

## 备注

- 前端单文件改动大，建议每次保存后立即在浏览器打开验证（本地 file:// 即可，API 走线上 Worker）
- 部署 Pages 路径与命令以现有 `D:\Temp\opencode\zuiweng-site` 为准，必须 `--branch=main`
- 禁止在代码与文档中使用 emoji