# 醉翁亭商城推进计划与 TODO

依据: 01-商城设计文档.md
推进方式: 分阶段，每阶段含后端改动 + 前端改动 + 部署验证，验收通过再进入下一阶段。

阶段标记约定:
- [ ] 未开始
- [x] 已完成
- 每项任务含文件路径与验收标准，按顺序执行。

---

## 阶段 1: 核心商城框架（首页/市场/用户中心/充值/邀请/管理员）

### 1.1 后端: 公开统计接口

- [ ] 任务 1.1.1 新增 `GET /api/stats`（公开）
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\src\index.js`（公开路由区，products/notifications 旁）
  - 改动: 查询 chunshui_accounts 按 platform 分组（total / on_sale / sold / dead / total_petals / signed_today），汇总 summary，附 token_per_rmb
  - 注意: 需先加 `signed_today` 计数（last_sign_date = today 的账号数）；无该字段则从 last_sign_date 判断
  - 验收: `GET /api/stats` 200 且返回 platforms 数组与 summary

- [ ] 任务 1.1.2 部署并验证
  - 命令: `npx wrangler deploy`（workdir `G:\皮皮\编程项目\fengyue\zuiweng-worker`）
  - 验收: curl 返回统计数据

### 1.2 后端: 邀请码

- [ ] 任务 1.2.1 schema 加列
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\schema.sql`（追加 CREATE TABLE IF NOT EXISTS invite_relations 与 ALTER 语句，重复执行安全）
  - 执行: `npx wrangler d1 execute zuiweng-db --remote --file=schema.sql`
  - 验收: D1 表中 users 含 invite_code/inviter_id，存在 invite_relations 表

- [ ] 任务 1.2.2 注册接口支持 invite_code
  - 文件: `G:\皮皮\编程项目\fengyue\zuiweng-worker\src\index.js`（/api/auth/register 段）
  - 改动: 接收可选 invite_code；校验邀请码对应用户存在则写入 inviter_id；新用户无码则生成 8 位随机码唯一
  - 验收: 带码注册后 users.inviter_id 正确；重复注册码不冲突

- [ ] 任务 1.2.3 新增 `GET /api/invite/code`（登录）
  - 文件: 同上（登录区）
  - 改动: 用户无邀请码则生成并保存；返回 { invite_code }
  - 验收: 登录态返回用户邀请码

### 1.3 前端: 全局改造

- [ ] 任务 1.3.1 常量扩展
  - 文件: `G:\皮皮\编程项目\fengyue\醉翁亭\醉翁亭.html`（顶部常量区）
  - 改动: PLATFORM_LABELS/PLATFORM_UNITS 增加 missai('密丝AI','体验点')、dzmm('DZMM','积分')；新增 RECHARGE_PACKAGES、QQ_GROUP 常量
  - 验收: 常量区新增定义完成

- [ ] 任务 1.3.2 导航栏扩展
  - 文件: 同上（Navbar 组件）
  - 改动: navItems 加入 账号市场/脚本皮肤/玩家市场/聊天室/用户中心/充值/邀请；管理员加 渠道管理/通知管理/系统设置
  - 验收: 移动端与 PC 端菜单项齐全

- [ ] 任务 1.3.3 App 路由扩展
  - 文件: 同上（App 组件）
  - 改动: case 增加 market/me/recharge/invite/scripts/players/chat/admin-channels/admin-notices/admin-settings；受保护页未登录跳 login
  - 验收: 各页可路由，未登录访问 me 跳登录

### 1.4 前端: 首页

- [ ] 任务 1.4.1 公告滚动栏 + 数据面板 + 平台卡片 + 公告列表
  - 文件: 同上（新增 HomePage 改造，替换现有 home）
  - 改动: 顶部公告轮播（每 5 秒切换）/ 主视觉 / stats 数据面板 4 卡片 / 平台介绍卡（调 /api/stats 的 platforms）/ 公告完整列表
  - 验收: 首页数据真实展示，无公告时隐藏栏

### 1.5 前端: 账号市场

- [ ] 任务 1.5.1 市场页（替代原 list/detail）
  - 文件: 同上（MarketPage 组件）
  - 改动: 平台筛选 / 商品卡（平台名+昵称+积分+价格+注册时间）/ 购买流程（确认弹窗->POST /api/orders->成功展示凭据+印章动画->刷新余额；未登录提示登栈；余额不足提示充值跳转）
  - 验收: 完整购买链路可用，余额实时刷新

### 1.6 前端: 用户中心 / 充值 / 邀请

- [ ] 任务 1.6.1 MePage
  - 文件: 同上
  - 改动: 用户信息卡 / 我的账号列表（展开凭据）/ 交易记录（类型中文映射）
  - 验收: 三块数据真实展示

- [ ] 任务 1.6.2 RechargePage
  - 文件: 同上
  - 改动: 汇率卡（token_per_rmb）/ 套餐选择 / 复制备注（含用户ID）/ QQ群提示
  - 验收: 复制功能可用，备注含用户ID与金额代币

- [ ] 任务 1.6.3 InvitePage
  - 文件: 同上
  - 改动: 调 GET /api/invite/code 展示邀请码 + 复制按钮 + 奖励规则文案
  - 验收: 显示并复制邀请码

### 1.7 前端: 占位页

- [ ] 任务 1.7.1 ScriptsPage / PlayersPage / ChatPage 占位
  - 文件: 同上
  - 改动: "敬请期待"占位组件
  - 验收: 三页可访问

### 1.8 前端: 管理员页

- [ ] 任务 1.8.1 ChannelsAdminPage
  - 文件: 同上
  - 改动: 渠道表格（enabled/min_petals/unit/price_per_unit/max_on_sale）+ 行内编辑保存 + "全池重新评估上架"按钮
  - 验收: 修改保存生效，refresh 后商品数量变化

- [ ] 任务 1.8.2 NoticesAdminPage
  - 文件: 同上
  - 改动: 新建表单 + 列表（停用/删除/编辑）
  - 验收: 前台公告即时更新

- [ ] 任务 1.8.3 SettingsAdminPage
  - 文件: 同上
  - 改动: token_per_rmb 编辑 + 汇率预览
  - 验收: 修改后充值页汇率同步

### 1.9 前端: 部署与验收

- [ ] 任务 1.9.1 部署副本同步
  - 命令: 复制 `醉翁亭.html` 到 `D:\Temp\opencode\zuiweng-site\index.html`，部署 Cloudflare Pages
  - 验收: 线上域名可见新商城

- [ ] 任务 1.9.2 阶段 1 验收清单（设计文档第 6 节逐条过）
  - 验收: 8 条全部通过

### 1.10 提交与推送

- [ ] 任务 1.10.1 提交 zuiweng-worker 改动（含此前渠道/通知/设置等未提交内容）
  - 命令: git add + commit（仓库 `G:\皮皮\编程项目\fengyue\zuiweng-worker`）
  - 验收: commit 含 schema.sql 与 index.js 全部改动

---

## 阶段 2: 套餐充值订单与 QQ 群配置

- [ ] 后端: 新增表 recharge_orders(id, user_id, amount_rmb, token_amount, status, note, created_at, handled_by)；POST /api/recharge（登录，创建待审核订单）；管理员 GET /api/admin/orders + PATCH 审核发放代币
- [ ] 前端: RechargePage 改为生成订单并展示"待审核"状态；QQ_GROUP 改为 settings 配置项（admin-settings 可改）
- [ ] 验收: 用户下单 -> 管理员审核 -> 余额到账 -> 交易记录出现 charge

## 阶段 3: 脚本/皮肤市场 + 玩家市场

- [ ] 脚本/皮肤: 表 products(type,name,desc,price,file_url,thumbnail,platform)；API 上架/列表/购买；前端页面完成
- [ ] 玩家市场: 细化数据模型（玩家卡/求购/交易），设计后实现
- [ ] 验收: 两类市场可浏览购买

## 阶段 4: 聊天室

- [ ] 方案决策: D1 消息表 + 轮询 或 Worker WebSocket
- [ ] 后端: 消息表 + 发送/拉取 API
- [ ] 前端: 聊天室界面（消息列表/输入框/自动刷新）
- [ ] 验收: 多端可见消息实时刷新

---

## 进行中工作（阶段 0 遗留，不影响阶段 1 主线）

- [ ] 密丝AI 邮箱认证 2000 体验点奖励领取方式确认（dailyTask claim taskType 枚举，或真实点击认证页抓包）；不影响注册+签到主线
- [ ] 风月账号 petals=0 确认（fengyue.py daily 是否跑过、points 接口字段）；影响 fengyue 渠道准入阈值，渠道默认 disabled 不阻塞

## 备注

- 前端单文件改动大，建议每次保存后立即在浏览器打开验证（本地 file:// 即可，API 走线上 Worker）
- 部署 Pages 路径与命令以现有 `D:\Temp\opencode\zuiweng-site` 为准
- 禁止在代码与文档中使用 emoji