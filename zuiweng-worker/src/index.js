// Worker 入口: 路由 + 春水号池 sync/管理/购买 API
import { hashPassword, randomSalt, signToken, verifyToken } from './auth.js';

const ok = (data) => new Response(JSON.stringify({ code: 0, message: 'ok', data }), {
  headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type,authorization', 'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS' },
});
const err = (code, message, status = 400) => new Response(JSON.stringify({ code, message, data: null }), {
  status, headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
});
const json = async (req) => { try { return await req.json(); } catch { return {}; } };
const now = () => new Date().toISOString().slice(0, 19).replace('T', ' ');

function bearer(auth) {
  if (!auth || !auth.startsWith('Bearer ')) return null;
  return auth.slice(7);
}
function randNo() {
  return 'ZW' + Date.now().toString(36).toUpperCase() + Math.floor(Math.random() * 1e6).toString(36).toUpperCase();
}
// 生成 8 位邀请码 (去除易混淆字符)
function randCode(len = 8) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let s = '';
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * chars.length)];
  return s;
}

// 渠道自动上架: 对上报账号评估是否满足准入阈值(渠道已开启 + petals>=min_petals), 满足则置为 on_sale 并定价
async function autolist(DB, accounts) {
  const cfgs = await DB.prepare('SELECT * FROM channel_configs').all();
  const cfgMap = {};
  for (const c of cfgs.results) cfgMap[c.platform] = c;
  const ops = [];
  for (const a of accounts || []) {
    const cfg = cfgMap[a.platform];
    if (!cfg || !cfg.enabled) continue;
    const petals = a.petals ?? 0;
    if (petals < cfg.min_petals) continue;
    const price = Math.max(1, Math.floor(petals / cfg.unit) * cfg.price_per_unit);
    ops.push(DB.prepare(
      "UPDATE chunshui_accounts SET status='on_sale', price=? WHERE platform=? AND email=? AND status='pool' AND price=0"
    ).bind(price, a.platform, a.email));
  }
  if (ops.length) await DB.batch(ops);
}

// 全池重新评估上架 (admin refresh): 返回本次上架数
async function refreshAutolist(DB) {
  const cfgs = await DB.prepare('SELECT * FROM channel_configs').all();
  const enabled = cfgs.results.filter(c => c.enabled && c.min_petals > 0);
  let listed = 0;
  const ops = [];
  for (const cfg of enabled) {
    const maxN = cfg.max_on_sale || 0;
    const rows = await DB.prepare(
      "SELECT id,petals FROM chunshui_accounts WHERE platform=? AND status IN('pool','on_sale') AND petals>=? ORDER BY petals DESC"
    ).bind(cfg.platform, cfg.min_petals).all();
    let avail = maxN > 0 ? maxN : rows.results.length;
    for (const r of rows.results) {
      if (avail <= 0) {
        ops.push(DB.prepare("UPDATE chunshui_accounts SET status='pool', price=0 WHERE id=? AND status='on_sale'").bind(r.id));
        continue;
      }
      const price = Math.max(1, Math.floor(r.petals / cfg.unit) * cfg.price_per_unit);
      ops.push(DB.prepare("UPDATE chunshui_accounts SET status='on_sale', price=? WHERE id=? AND status IN('pool','on_sale')").bind(price, r.id));
      avail--;
      listed++;
    }
  }
  if (ops.length) await DB.batch(ops);
  return listed;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    const method = req.method;
    const DB = env.DB;
    if (method === 'OPTIONS') return ok({});

    // ============ 用户认证 ============
    if (p === '/api/auth/register' && method === 'POST') {
      const b = await json(req);
      if (!b.username || !b.password || b.username.length > 32 || b.password.length < 6)
        return err(4001, '参数错误');
      const salt = randomSalt();
      const ph = await hashPassword(b.password, salt);
      // 邀请码: 校验存在则登记邀请关系
      let inviterId = null;
      if (b.invite_code) {
        const ic = await DB.prepare('SELECT user_id FROM invite_codes WHERE code=?').bind(String(b.invite_code).trim()).first();
        if (ic) inviterId = ic.user_id;
      }
      const code = randCode();
      try {
        const r = await DB.prepare('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)')
          .bind(b.username, `${salt}:${ph}`, 'user').run();
        const uid = r.meta.last_row_id;
        await DB.prepare('INSERT OR IGNORE INTO invite_codes(user_id,code) VALUES(?,?)').bind(uid, code).run();
        if (inviterId) {
          await DB.prepare('INSERT INTO invite_relations(inviter_id,invitee_id) VALUES(?,?)').bind(inviterId, uid).run();
        }
        return ok({ id: uid });
      } catch { return err(4002, '用户名已存在'); }
    }
    if (p === '/api/auth/login' && method === 'POST') {
      const b = await json(req);
      const u = await DB.prepare('SELECT * FROM users WHERE username=?').bind(b.username).first();
      if (!u) return err(4010, '用户名或密码错误', 401);
      const [salt, hash] = u.password_hash.split(':');
      if ((await hashPassword(b.password, salt)) !== hash) return err(4010, '用户名或密码错误', 401);
      const token = await signToken({ uid: u.id, role: u.role }, env.JWT_SECRET);
      return ok({ token, user: { id: u.id, username: u.username, role: u.role, balance: u.balance } });
    }

    // ============ Actions 同步入口 (ADMIN_TOKEN, 无需登录) ============
    if (p === '/api/chunshui/sync' && method === 'POST') {
      if (req.headers.get('authorization') !== `Bearer ${env.ADMIN_TOKEN}`) return err(4010, '未授权', 401);
      const b = await json(req);
      const ops = [];
      let upserted = 0;
      for (const a of b.accounts || []) {
        ops.push(DB.prepare(`INSERT INTO chunshui_accounts
          (platform,nickname,password,email,email_password,user_id,registered_at,petals,status,imported_at)
          VALUES(?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
          ON CONFLICT(email) DO UPDATE SET
            platform=excluded.platform, nickname=excluded.nickname, password=excluded.password, user_id=excluded.user_id,
            registered_at=excluded.registered_at, petals=excluded.petals,
            email_password=excluded.email_password, status=CASE WHEN chunshui_accounts.status='sold' THEN 'sold' ELSE excluded.status END`)
          .bind(a.platform ?? 'aimagnet', a.nickname ?? '', a.password ?? '', a.email ?? '', a.email_password ?? '',
                a.user_id ?? '', a.registered_at ?? '', a.petals ?? 0, a.status ?? 'pool'));
        upserted++;
      }
      for (const s of b.sign_records || []) {
        ops.push(DB.prepare('INSERT OR REPLACE INTO chunshui_sign_records(account_id,date,status,reward,created_at) VALUES(?,?,?,?,datetime(\'now\',\'localtime\'))')
          .bind(s.account_id, s.date, s.status, s.reward || 0));
      }
      for (const pt of b.points || []) {
        ops.push(DB.prepare('INSERT OR REPLACE INTO chunshui_point_snapshots(account_id,date,petals) VALUES(?,?,?)')
          .bind(pt.account_id, pt.date, pt.petals || 0));
      }
      for (const h of b.health || []) {
        ops.push(DB.prepare("UPDATE chunshui_accounts SET last_check_at=?, last_check_ok=?, check_error=?, petals=? WHERE id=?")
          .bind(now(), h.ok ? 1 : 0, h.error || '', h.petals ?? 0, h.account_id));
      }
      try {
        if (ops.length) await DB.batch(ops);
        await autolist(DB, b.accounts || []);
        return ok({ upserted });
      } catch (e) {
        return err(5000, `sync失败: ${e.message}`, 500);
      }
    }

    // ============ 公开: 商品列表 & 公告 ============
    if (p === '/api/products' && method === 'GET') {
      const rows = await DB.prepare(
        "SELECT id,nickname,petals,registered_at,price,platform FROM chunshui_accounts WHERE status IN('pool','on_sale') AND price>0 ORDER BY id DESC LIMIT 100").all();
      return ok({ products: rows.results });
    }
    if (p === '/api/notifications' && method === 'GET') {
      const rows = await DB.prepare("SELECT id,title,content,created_at FROM notifications WHERE active=1 ORDER BY id DESC LIMIT 20").all();
      return ok({ notifications: rows.results });
    }
    if (p === '/api/stats' && method === 'GET') {
      const today = now().slice(0, 10);
      const rows = await DB.prepare(
        "SELECT platform, COUNT(*) AS total, SUM(CASE WHEN status='on_sale' THEN 1 ELSE 0 END) AS on_sale, SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) AS sold, SUM(CASE WHEN last_check_ok=0 THEN 1 ELSE 0 END) AS dead, SUM(petals) AS petals, SUM(CASE WHEN last_sign_date=? THEN 1 ELSE 0 END) AS signed_today FROM chunshui_accounts GROUP BY platform").bind(today).all();
      const platforms = rows.results.map(r => ({
        platform: r.platform, total: r.total || 0, on_sale: r.on_sale || 0, sold: r.sold || 0,
        dead: r.dead || 0, total_petals: r.petals || 0, signed_today: r.signed_today || 0,
      }));
      const summary = { total: 0, on_sale: 0, sold: 0, dead: 0, total_petals: 0, signed_today: 0, date: today };
      for (const pl of platforms) {
        summary.total += pl.total; summary.on_sale += pl.on_sale; summary.sold += pl.sold;
        summary.dead += pl.dead; summary.total_petals += pl.total_petals; summary.signed_today += pl.signed_today;
      }
      const st = await DB.prepare("SELECT value FROM settings WHERE key='token_per_rmb'").first();
      return ok({ platforms, summary, token_per_rmb: Number(st?.value) || 100 });
    }

    // 渠道报错上报 (Actions 用 ADMIN_TOKEN)
    if (p === '/api/channel-logs' && method === 'POST') {
      if (req.headers.get('authorization') !== `Bearer ${env.ADMIN_TOKEN}`) return err(4010, '未授权', 401);
      const b = await json(req);
      const ops = [];
      for (const L of b.logs || []) {
        if (!L.platform || !L.message) continue;
        ops.push(DB.prepare('INSERT INTO channel_logs(platform,level,category,message) VALUES(?,?,?,?)')
          .bind(L.platform, L.level || 'error', L.category || 'register', String(L.message).slice(0, 1000)));
      }
      if (ops.length) await DB.batch(ops);
      return ok({ inserted: ops.length });
    }
    // 渠道报错公开查询 (首页渠道状态: 每平台最新 error)
    if (p === '/api/channel-logs' && method === 'GET') {
      const rows = await DB.prepare("SELECT platform,level,category,message,created_at FROM channel_logs WHERE level='error' ORDER BY id DESC LIMIT 200").all();
      const byPlat = {};
      for (const r of rows.results) {
        if (!byPlat[r.platform]) byPlat[r.platform] = { platform: r.platform, recent: [], count: 0 };
        byPlat[r.platform].count++;
        if (byPlat[r.platform].recent.length < 3) byPlat[r.platform].recent.push(r);
      }
      return ok({ platforms: Object.values(byPlat) });
    }

    // ============ 需要登录 ============
    const token = bearer(req.headers.get('authorization'));
    const auth = token ? await verifyToken(token, env.JWT_SECRET) : null;
    const adminTokenHit = req.headers.get('authorization') === `Bearer ${env.ADMIN_TOKEN}`;
    if (!auth && !adminTokenHit) return err(4010, '未登录', 401);

    // 钱包
    if (p === '/api/wallet' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const u = await DB.prepare('SELECT id,username,balance,role FROM users WHERE id=?').bind(auth.uid).first();
      const tx = await DB.prepare('SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 50').bind(auth.uid).all();
      return ok({ balance: u.balance, user: u, transactions: tx.results });
    }

    // 邀请码 (登录)
    if (p === '/api/invite/code' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      let ic = await DB.prepare('SELECT code FROM invite_codes WHERE user_id=?').bind(auth.uid).first();
      if (!ic) {
        const code = randCode();
        await DB.prepare('INSERT OR IGNORE INTO invite_codes(user_id,code) VALUES(?,?)').bind(auth.uid, code).run();
        ic = await DB.prepare('SELECT code FROM invite_codes WHERE user_id=?').bind(auth.uid).first();
      }
      const invited = await DB.prepare('SELECT COUNT(*) n FROM invite_relations WHERE inviter_id=?').bind(auth.uid).first();
      return ok({ invite_code: ic.code, invited: invited.n || 0 });
    }

    // 购买账号
    if (p === '/api/orders' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const acc = await DB.prepare("SELECT * FROM chunshui_accounts WHERE id=? AND status IN('pool','on_sale') AND price>0").bind(b.account_id).first();
      if (!acc) return err(4003, '账号不存在或已售出');
      const u = await DB.prepare('SELECT * FROM users WHERE id=?').bind(auth.uid).first();
      if (u.balance < acc.price) return err(4004, '代币不足');
      const no = randNo();
      await DB.batch([
        DB.prepare('UPDATE users SET balance=balance-? WHERE id=?').bind(acc.price, auth.uid),
        DB.prepare("UPDATE chunshui_accounts SET status='sold', owner_id=?, last_check_ok=1 WHERE id=?").bind(auth.uid, acc.id),
        DB.prepare('INSERT INTO orders(order_no,user_id,account_id,amount) VALUES(?,?,?,?)').bind(no, auth.uid, acc.id, acc.price),
        DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(auth.uid, -acc.price, 'buy', `购买账号 ${acc.nickname}`),
      ]);
      return ok({ order_no: no, account: { nickname: acc.nickname, email: acc.email, password: acc.password, petals: acc.petals, registered_at: acc.registered_at } });
    }

    // 我的账号
    if (p === '/api/accounts/mine' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const rows = await DB.prepare(
        "SELECT id,nickname,email,petals,registered_at,last_sign_date,price,platform FROM chunshui_accounts WHERE owner_id=? ORDER BY id DESC").bind(auth.uid).all();
      return ok({ accounts: rows.results });
    }

    // 账号记录(签到/花瓣)
    const mRecords = p.match(/^\/api\/accounts\/(\d+)\/records$/);
    if (mRecords && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const acc = await DB.prepare('SELECT * FROM chunshui_accounts WHERE id=?').bind(mRecords[1]).first();
      if (!acc || (acc.owner_id !== auth.uid && auth.role !== 'admin')) return err(4030, '无权限', 403);
      const signs = await DB.prepare('SELECT * FROM chunshui_sign_records WHERE account_id=? ORDER BY date DESC LIMIT 60').bind(acc.id).all();
      const points = await DB.prepare('SELECT * FROM chunshui_point_snapshots WHERE account_id=? ORDER BY date DESC LIMIT 60').bind(acc.id).all();
      return ok({ signs: signs.results, points: points.results });
    }

    // ============ 管理端 (admin 或 ADMIN_TOKEN) ============
    const isAdmin = (auth && auth.role === 'admin') || adminTokenHit;

    // 手动触发注册 (经 GitHub workflow_dispatch) - admin 预留

    if (!isAdmin) return err(4030, '无权限', 403);

    // 用户列表 (admin)
    if (p === '/api/admin/users' && method === 'GET') {
      const users = await DB.prepare('SELECT id,username,role,balance,created_at FROM users ORDER BY id').all();
      const bought = await DB.prepare('SELECT owner_id, COUNT(*) n FROM chunshui_accounts GROUP BY owner_id').all();
      const map = {};
      for (const r of bought.results) map[r.owner_id] = r.n;
      return ok({ users: users.results.map(u => ({ ...u, purchased: map[u.id] || 0 })) });
    }

    // 用户管理 (admin): 提权/降权/改余额
    const mUser = p.match(/^\/api\/admin\/users\/(\d+)$/);
    if (mUser && method === 'PATCH') {
      const b = await json(req);
      if (b.role !== undefined && !['user', 'admin'].includes(b.role)) return err(4001, '角色非法');
      if (b.balance !== undefined && (!Number.isFinite(Number(b.balance)) || Number(b.balance) < 0)) return err(4001, '余额非法');
      const sets = [], vals = [];
      if (b.role !== undefined) { sets.push('role=?'); vals.push(b.role); }
      if (b.balance !== undefined) { sets.push('balance=?'); vals.push(Number(b.balance)); }
      if (!sets.length) return err(4001, '无字段');
      const target = await DB.prepare('SELECT id FROM users WHERE id=?').bind(mUser[1]).first();
      if (!target) return err(4003, '用户不存在');
      vals.push(mUser[1]);
      await DB.prepare(`UPDATE users SET ${sets.join(',')} WHERE id=?`).bind(...vals).run();
      if (b.balance !== undefined) {
        await DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)')
          .bind(mUser[1], Number(b.balance), 'admin', '管理员调整余额').run();
      }
      return ok({ updated: true });
    }

    // 用户充值 (admin)
    if (p === '/api/admin/charge' && method === 'POST') {
      const b = await json(req);
      const amount = Number(b.amount);
      if (!b.user_id || !Number.isFinite(amount) || amount <= 0) return err(4001, '参数错误');
      const u = await DB.prepare('SELECT id FROM users WHERE id=?').bind(b.user_id).first();
      if (!u) return err(4003, '用户不存在');
      await DB.batch([
        DB.prepare('UPDATE users SET balance=balance+? WHERE id=?').bind(amount, b.user_id),
        DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(b.user_id, amount, 'charge', b.note || '管理充值'),
      ]);
      return ok({ balance: (await DB.prepare('SELECT balance FROM users WHERE id=?').bind(b.user_id).first()).balance });
    }

    // 号池监控列表
    if (p === '/api/admin/chunshui/accounts' && method === 'GET') {
      const q = url.searchParams.get('q') || '';
      const status = url.searchParams.get('status') || '';
      const platform = url.searchParams.get('platform') || '';
      let sql = 'SELECT c.*, (SELECT date FROM chunshui_sign_records s WHERE s.account_id=c.id ORDER BY date DESC LIMIT 1) AS last_reward_date, (SELECT reward FROM chunshui_sign_records s WHERE s.account_id=c.id ORDER BY date DESC LIMIT 1) AS last_reward FROM chunshui_accounts c WHERE 1=1';
      const binds = [];
      if (status) { sql += ' AND c.status=?'; binds.push(status); }
      if (platform) { sql += ' AND c.platform=?'; binds.push(platform); }
      if (q) { sql += ' AND (c.nickname LIKE ? OR c.email LIKE ?)'; binds.push(`%${q}%`, `%${q}%`); }
      const limit = Math.min(parseInt(url.searchParams.get('limit') || '500', 10) || 500, 5000);
      const offset = parseInt(url.searchParams.get('offset') || '0', 10) || 0;
      sql += ' ORDER BY c.id DESC LIMIT ? OFFSET ?';
      binds.push(limit, offset);
      const rows = await DB.prepare(sql).bind(...binds).all();
      return ok({ accounts: rows.results });
    }

    // 号池统计
    if (p === '/api/admin/chunshui/stats' && method === 'GET') {
      const platform = url.searchParams.get('platform') || '';
      const where = platform ? ' WHERE platform=?' : '';
      const binds = platform ? [platform] : [];
      const total = await DB.prepare('SELECT COUNT(*) n FROM chunshui_accounts' + where).bind(...binds).first();
      const pool = await DB.prepare("SELECT COUNT(*) n FROM chunshui_accounts WHERE status='pool'" + (platform ? ' AND platform=?' : '')).bind(...binds).first();
      const sold = await DB.prepare("SELECT COUNT(*) n FROM chunshui_accounts WHERE status='sold'" + (platform ? ' AND platform=?' : '')).bind(...binds).first();
      const dead = await DB.prepare('SELECT COUNT(*) n FROM chunshui_accounts WHERE last_check_ok=0' + (platform ? ' AND platform=?' : '')).bind(...binds).first();
      const petals = await DB.prepare('SELECT COALESCE(SUM(petals),0) n FROM chunshui_accounts' + where).bind(...binds).first();
      const today = now().slice(0, 10);
      const signedToday = await DB.prepare("SELECT COUNT(DISTINCT account_id) n FROM chunshui_sign_records WHERE date=? AND status IN('SIGNED','ALREADY')" + (platform ? ' AND account_id IN (SELECT id FROM chunshui_accounts WHERE platform=?)' : '')).bind(today, ...binds).first();
      return ok({ total: total.n, pool: pool.n, sold: sold.n, dead: dead.n, totalPetals: petals.n, signedToday: signedToday.n, date: today });
    }

    // 账号详情 (管理)
    const mAcc = p.match(/^\/api\/admin\/chunshui\/accounts\/(\d+)$/);
    if (mAcc && method === 'GET') {
      const acc = await DB.prepare('SELECT * FROM chunshui_accounts WHERE id=?').bind(mAcc[1]).first();
      if (!acc) return err(4003, '不存在');
      const signs = await DB.prepare('SELECT * FROM chunshui_sign_records WHERE account_id=? ORDER BY date DESC LIMIT 90').bind(acc.id).all();
      const points = await DB.prepare('SELECT * FROM chunshui_point_snapshots WHERE account_id=? ORDER BY date DESC LIMIT 90').bind(acc.id).all();
      return ok({ account: acc, signs: signs.results, points: points.results });
    }

    // 修改账号 (状态/价格/花瓣)
    const mPatch = p.match(/^\/api\/admin\/chunshui\/accounts\/(\d+)$/);
    if (mPatch && method === 'PATCH') {
      const b = await json(req);
      const allowed = ['status', 'price', 'petals'];
      const sets = [], vals = [];
      for (const k of allowed) if (b[k] !== undefined) { sets.push(`${k}=?`); vals.push(b[k]); }
      if (!sets.length) return err(4001, '无字段');
      vals.push(mPatch[1]);
      await DB.prepare(`UPDATE chunshui_accounts SET ${sets.join(',')} WHERE id=?`).bind(...vals).run();
      return ok({ updated: true });
    }

    // ============ 渠道售卖配置 (admin) ============
    if (p === '/api/admin/channels' && method === 'GET') {
      const cfgs = await DB.prepare('SELECT * FROM channel_configs ORDER BY platform').all();
      const cnts = await DB.prepare("SELECT platform, COUNT(*) n FROM chunshui_accounts GROUP BY platform").all();
      const onSale = await DB.prepare("SELECT platform, COUNT(*) n FROM chunshui_accounts WHERE status='on_sale' GROUP BY platform").all();
      const cm = {}, sm = {}, om = {};
      for (const r of cnts.results) cm[r.platform] = r.n;
      for (const r of onSale.results) om[r.platform] = r.n;
      const out = cfgs.results.map(c => ({ ...c, account_count: cm[c.platform] || 0, on_sale_count: om[c.platform] || 0 }));
      const token = await DB.prepare("SELECT value FROM settings WHERE key='token_per_rmb'").first();
      return ok({ channels: out, token_per_rmb: token ? Number(token.value) : 100 });
    }
    const mChan = p.match(/^\/api\/admin\/channels\/([^/]+)$/);
    if (mChan && method === 'PATCH') {
      const b = await json(req);
      const allowed = ['label', 'enabled', 'min_petals', 'unit', 'price_per_unit', 'max_on_sale'];
      const sets = [], vals = [];
      for (const k of allowed) if (b[k] !== undefined) { sets.push(`${k}=?`); vals.push(b[k]); }
      if (!sets.length) return err(4001, '无字段');
      sets.push("updated_at=datetime('now','localtime')");
      vals.push(mChan[1]);
      const r = await DB.prepare(`UPDATE channel_configs SET ${sets.join(',')} WHERE platform=?`).bind(...vals).run();
      if (!r.meta.changes) return err(4003, '渠道不存在');
      return ok({ updated: true });
    }

    // 全池重新评估上架
    if (p === '/api/admin/channels/refresh' && method === 'POST') {
      const listed = await refreshAutolist(DB);
      return ok({ listed });
    }

    // ============ 系统设置 (admin) ============
    if (p === '/api/admin/settings' && method === 'GET') {
      const rows = await DB.prepare('SELECT * FROM settings').all();
      const m = {};
      for (const r of rows.results) m[r.key] = r.value;
      return ok(m);
    }
    if (p === '/api/admin/settings' && method === 'PATCH') {
      const b = await json(req);
      if (b.token_per_rmb !== undefined) {
        const n = Number(b.token_per_rmb);
        if (!Number.isFinite(n) || n <= 0) return err(4001, 'token_per_rmb 非法');
        await DB.prepare("INSERT INTO settings(key,value) VALUES('token_per_rmb',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(String(n)).run();
      }
      return ok({ updated: true });
    }

    // ============ 通知 (admin CRUD) ============
    if (p === '/api/admin/notifications' && method === 'POST') {
      const b = await json(req);
      if (!b.title || !b.title.trim()) return err(4001, '标题必填');
      const r = await DB.prepare('INSERT INTO notifications(title,content,active) VALUES(?,?,?)')
        .bind(b.title.trim(), b.content || '', b.active === undefined ? 1 : (b.active ? 1 : 0)).run();
      return ok({ id: r.meta.last_row_id });
    }
    if (p === '/api/admin/notifications' && method === 'GET') {
      const rows = await DB.prepare('SELECT * FROM notifications ORDER BY id DESC LIMIT 50').all();
      return ok({ notifications: rows.results });
    }
    const mNoti = p.match(/^\/api\/admin\/notifications\/(\d+)$/);
    if (mNoti && method === 'DELETE') {
      await DB.prepare('DELETE FROM notifications WHERE id=?').bind(mNoti[1]).run();
      return ok({ deleted: true });
    }
    if (mNoti && method === 'PATCH') {
      const b = await json(req);
      const sets = [], vals = [];
      if (b.active !== undefined) { sets.push('active=?'); vals.push(b.active ? 1 : 0); }
      if (b.title !== undefined) { sets.push('title=?'); vals.push(b.title); }
      if (b.content !== undefined) { sets.push('content=?'); vals.push(b.content); }
      if (!sets.length) return err(4001, '无字段');
      vals.push(mNoti[1]);
      await DB.prepare(`UPDATE notifications SET ${sets.join(',')} WHERE id=?`).bind(...vals).run();
      return ok({ updated: true });
    }

    // ============ 渠道报错 (admin 全量查询) ============
    if (p === '/api/admin/channel-logs' && method === 'GET') {
      const sp = new URL(req.url).searchParams;
      const plat = sp.get('platform') || '';
      const lev = sp.get('level') || '';
      const limit = Math.min(Number(sp.get('limit') || 100), 500);
      const offset = Number(sp.get('offset') || 0);
      let sql = "SELECT * FROM channel_logs WHERE 1=1";
      const vals = [];
      if (plat) { sql += " AND platform=?"; vals.push(plat); }
      if (lev) { sql += " AND level=?"; vals.push(lev); }
      sql += " ORDER BY id DESC LIMIT ? OFFSET ?";
      const rows = await DB.prepare(sql).bind(...vals, limit, offset).all();
      return ok({ logs: rows.results });
    }

    return err(4004, 'Not Found', 404);
  },
};