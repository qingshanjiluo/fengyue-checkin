-- 醉翁亭 · D1 Schema (春水号池)
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',   -- 'user' | 'admin'
  balance       INTEGER NOT NULL DEFAULT 0,     -- 代币
  created_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS chunshui_accounts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  platform       TEXT NOT NULL DEFAULT 'aimagnet',  -- 平台标识: aimagnet/...
  nickname       TEXT NOT NULL,
  password       TEXT NOT NULL,
  email          TEXT NOT NULL UNIQUE,
  email_password TEXT,
  user_id        TEXT,
  registered_at  TEXT,
  imported_at    TEXT DEFAULT (datetime('now','localtime')),
  petals         INTEGER DEFAULT 0,
  last_sign_date TEXT,
  last_sign_at   TEXT,
  last_check_at  TEXT,
  last_check_ok  INTEGER DEFAULT 1,
  check_error    TEXT,
  status         TEXT DEFAULT 'pool',           -- pool | sold | disabled
  owner_id       INTEGER,
  price          INTEGER NOT NULL DEFAULT 0,    -- 售价(代币)
  created_at     TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS chunshui_sign_records (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  date       TEXT NOT NULL,
  status     TEXT NOT NULL,                     -- SIGNED | ALREADY | ERROR
  reward     INTEGER,
  created_at TEXT DEFAULT (datetime('now','localtime')),
  UNIQUE(account_id, date)
);

CREATE TABLE IF NOT EXISTS chunshui_point_snapshots (
  account_id INTEGER NOT NULL,
  date       TEXT NOT NULL,
  petals     INTEGER NOT NULL,
  UNIQUE(account_id, date)
);

CREATE TABLE IF NOT EXISTS orders (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  order_no   TEXT NOT NULL UNIQUE,
  user_id    INTEGER NOT NULL,
  account_id INTEGER NOT NULL,
  amount     INTEGER NOT NULL,
  status     TEXT DEFAULT 'paid',               -- paid | refunded
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS transactions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  amount     INTEGER NOT NULL,                  -- 正=入 负=出
  type       TEXT NOT NULL,                     -- charge | buy | admin
  note       TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_cs_account ON chunshui_sign_records(account_id, date);
CREATE INDEX IF NOT EXISTS idx_cs_point ON chunshui_point_snapshots(account_id, date);
CREATE INDEX IF NOT EXISTS idx_cs_status ON chunshui_accounts(status);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);

-- 渠道售卖配置 (每个平台一条)
CREATE TABLE IF NOT EXISTS channel_configs (
  platform       TEXT PRIMARY KEY,
  label          TEXT,                  -- 平台中文名
  enabled        INTEGER DEFAULT 0,     -- 是否允许该渠道账号上架售卖
  min_petals     INTEGER DEFAULT 0,     -- 准入阈值: 账号 petals>=min_petals 才自动上架
  unit           INTEGER DEFAULT 100,   -- 定价单位: 每 unit 积分
  price_per_unit INTEGER DEFAULT 50,    -- 每 unit 积分售价(代币)
  max_on_sale    INTEGER DEFAULT 0,     -- 最多同时上架数 (0=不限)
  on_sale_count  INTEGER DEFAULT 0,     -- 当前已上架数 (自动维护)
  created_at     TEXT DEFAULT (datetime('now','localtime')),
  updated_at     TEXT
);

-- 系统设置 (key/value)
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- 通知 (管理员发布, 前台展示)
CREATE TABLE IF NOT EXISTS notifications (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT NOT NULL,
  content    TEXT,
  active     INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

INSERT OR IGNORE INTO settings(key,value) VALUES('token_per_rmb','100');
INSERT OR IGNORE INTO settings(key,value) VALUES('qq_group','充值群');
INSERT OR IGNORE INTO channel_configs(platform,label,enabled,min_petals,unit,price_per_unit)
  VALUES('fengyue','风月酒馆',0,100,100,50);
INSERT OR IGNORE INTO channel_configs(platform,label,enabled,min_petals,unit,price_per_unit)
  VALUES('aimagnet','春水酒馆',0,100,100,50);
INSERT OR IGNORE INTO channel_configs(platform,label,enabled,min_petals,unit,price_per_unit)
  VALUES('missai','密丝AI',0,100,100,50);
INSERT OR IGNORE INTO channel_configs(platform,label,enabled,min_petals,unit,price_per_unit)
  VALUES('dzmm','DZMM',0,100,100,50);

-- 邀请码 (每个用户一条)
CREATE TABLE IF NOT EXISTS invite_codes (
  user_id    INTEGER PRIMARY KEY,
  code       TEXT UNIQUE,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 邀请关系与奖励记录
CREATE TABLE IF NOT EXISTS invite_relations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  inviter_id INTEGER NOT NULL,
  invitee_id INTEGER NOT NULL,
  reward     INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_inv_rel ON invite_relations(inviter_id);

-- 渠道报错日志 (Actions 上报, 网站展示)
CREATE TABLE IF NOT EXISTS channel_logs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  platform   TEXT,
  level      TEXT DEFAULT 'error',     -- error|warn|info
  category   TEXT,                     -- register|daily|login
  message    TEXT,                     -- 详细报错
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chlog ON channel_logs(platform, id);

-- 充值订单 (用户下单 -> 管理员审核发放)
CREATE TABLE IF NOT EXISTS recharge_orders (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  order_no    TEXT UNIQUE,
  user_id     INTEGER NOT NULL,
  amount_rmb  INTEGER NOT NULL,        -- 人民币金额
  bonus       INTEGER DEFAULT 0,       -- 附赠代币
  token_amount INTEGER NOT NULL,       -- 应发放代币 = amount_rmb*汇率 + bonus
  status      TEXT DEFAULT 'pending',  -- pending | done | rejected
  note        TEXT,
  handled_by  INTEGER,
  handled_at  TEXT,
  created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_recharge_user ON recharge_orders(user_id, status);

-- 脚本/皮肤商品
CREATE TABLE IF NOT EXISTS products (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  type       TEXT NOT NULL DEFAULT 'script',  -- script | skin
  name       TEXT NOT NULL,
  desc       TEXT DEFAULT '',
  price      INTEGER NOT NULL DEFAULT 0,      -- 代币
  file_url   TEXT DEFAULT '',                 -- 下载链接
  thumbnail  TEXT DEFAULT '',
  platform   TEXT DEFAULT '',                 -- 适用平台, 空=通用
  active     INTEGER DEFAULT 1,
  sold       INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_products_type ON products(type, active);

-- 玩家市场 (发布/求购)
CREATE TABLE IF NOT EXISTS player_offers (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  title      TEXT NOT NULL,
  desc       TEXT DEFAULT '',
  kind       TEXT DEFAULT 'sell',            -- sell 出售 | buy 求购
  price      INTEGER DEFAULT 0,              -- 代币
  status     TEXT DEFAULT 'open',            -- open | closed
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_offers_status ON player_offers(status, id);

-- 聊天室消息
CREATE TABLE IF NOT EXISTS chat_messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  content    TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chat_msg ON chat_messages(id);