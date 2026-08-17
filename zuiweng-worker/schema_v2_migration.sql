-- 醉翁亭 · D1 迁移 v2 (交易优化)
-- 用法: wrangler d1 execute zuiweng-db --remote --file=schema_v2_migration.sql
-- 注意: ALTER TABLE ADD COLUMN 只对已存在表执行一次, 重复执行会报错 (可忽略 Duplicate column)

-- 1. 用户注册 IP (一 IP 一号)
ALTER TABLE users ADD COLUMN ip TEXT;

-- 1b. 账号星尘 (风月签到真实代币, 出资源单位之一)
ALTER TABLE chunshui_accounts ADD COLUMN stardust INTEGER DEFAULT 0;
ALTER TABLE chunshui_point_snapshots ADD COLUMN stardust INTEGER DEFAULT 0;

-- 2. 玩家市场分类扩展
ALTER TABLE player_offers ADD COLUMN category TEXT DEFAULT 'account';
ALTER TABLE player_offers ADD COLUMN platform TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN account_name TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN account_password TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN account_email TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN verified INTEGER DEFAULT 0;
ALTER TABLE player_offers ADD COLUMN verify_detail TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN file_url TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN file_name TEXT DEFAULT '';
ALTER TABLE player_offers ADD COLUMN file_tip TEXT DEFAULT '';

-- 3. 玩家交易订单 (托管/冻结结算)
CREATE TABLE IF NOT EXISTS player_orders (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  order_no       TEXT UNIQUE,
  offer_id       INTEGER NOT NULL,
  buyer_id       INTEGER NOT NULL,
  seller_id      INTEGER NOT NULL,
  category       TEXT NOT NULL,
  amount         INTEGER NOT NULL,
  status         TEXT DEFAULT 'paid',
  buyer_confirm  INTEGER DEFAULT 0,
  seller_confirm INTEGER DEFAULT 0,
  created_at     TEXT DEFAULT (datetime('now','localtime')),
  updated_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_po_buyer ON player_orders(buyer_id, status);
CREATE INDEX IF NOT EXISTS idx_po_seller ON player_orders(seller_id, status);

-- 4. 玩家私聊会话与消息
CREATE TABLE IF NOT EXISTS player_conversations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  offer_id   INTEGER NOT NULL,
  buyer_id   INTEGER NOT NULL,
  seller_id  INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime')),
  UNIQUE(offer_id, buyer_id)
);
CREATE TABLE IF NOT EXISTS player_messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  sender_id       INTEGER NOT NULL,
  content         TEXT NOT NULL,
  created_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_pm_conv ON player_messages(conversation_id, id);