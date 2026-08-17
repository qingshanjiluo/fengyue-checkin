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
// 取客户端 IP (Cloudflare 直连头优先)
const clientIp = (req) => (req.headers.get('cf-connecting-ip') || req.headers.get('x-forwarded-for') || '').split(',')[0].trim();

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

// ============ 渠道官方验证 ============
// 用卖家提供的账号名/密码调用已知渠道登录, 取得真实积分作为官方验证数据
const VERIFY_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36';
const PLATFORM_UNITS = { aimagnet: '花瓣', fengyue: '积分', missai: '体验点', dzmm: '积分' };
const PLATFORM_LABELS = { aimagnet: '春水酒馆', fengyue: '风月酒馆', missai: '密丝AI', dzmm: 'DZMM' };

async function verifyAccount(platform, username, password) {
  if (!platform || !username || !password) return { ok: false, error: '渠道/账号/密码必填' };
  if (platform === 'fengyue' || platform === 'aimagnet') {
    // 风月/春水: console/api/login -> go/api/account/point + stardust/balance (多域名容错)
    const domains = ['https://aiaha.xyz', 'https://ai-xan.xyz', 'https://acepro.store', 'https://aquantancee.xyz'];
    let lastErr = '';
    for (const base of domains) {
      let raw = '';
      try {
        const r = await fetch(base + '/console/api/login', {
          method: 'POST', headers: { 'content-type': 'application/json', 'user-agent': VERIFY_UA, 'referer': base + '/zh/signin', 'x-language': 'zh-Hans', 'x-timezone': 'Asia/Shanghai' },
          body: JSON.stringify({ email: username, password }),
        });
        raw = await r.clone().text();
        const j = JSON.parse(raw);
        if (j.result === 'success' && typeof j.data === 'string' && j.data.startsWith('eyJ')) {
          // 积分 (go/api/account/point): 风月/春水平台该接口固定返回 0, 属平台限制
          const pr = await fetch(base + '/go/api/account/point', { headers: { 'authorization': 'Bearer ' + j.data, 'user-agent': VERIFY_UA } });
          const pj = await pr.json();
          let points = 0;
          if (pj.code === 100000 && pj.data) points = Math.floor(Number(pj.data.points) || 0);
          // 星尘 (console/api/stardust/balance): 签到获得的真实代币
          let stardust = null;
          try {
            const sr = await fetch(base + '/console/api/stardust/balance', { headers: { 'authorization': 'Bearer ' + j.data, 'user-agent': VERIFY_UA, 'x-language': 'zh-Hans', 'x-timezone': 'Asia/Shanghai' } });
            const sj = await sr.json();
            if (sj.code === 200 && sj.data) stardust = Math.floor(Number(sj.data.current_amount) || 0);
          } catch (e) { /* 星尘读取失败不影响验证 */ }
          const label = PLATFORM_LABELS[platform] || platform;
          const unit = PLATFORM_UNITS[platform] || '积分';
          const parts = [`${label} · ${unit} ${points}`];
          if (stardust !== null) parts.push(`星尘 ${stardust}`);
          return { ok: true, username, points, stardust, label, unit, detail: parts.join(' · ') };
        }
        if (!r.ok) { try { lastErr = `${base} HTTP ${r.status} ${(await r.clone().text()).slice(0, 100)}`; } catch { lastErr = `${base} HTTP ${r.status}`; } }
        else { try { lastErr = `${base} resp:${raw.slice(0, 120)}`; } catch {} }
      } catch (e) { lastErr = `${base} ${String(e).slice(0, 80)}`; }
    }
    return { ok: false, error: `登录失败：账号或密码有误 (${lastErr || '全部域名'})` };
  }
  if (platform === 'missai') {
    try {
      const r = await fetch('https://www.miss001.org/api/gva/base/login', {
        method: 'POST', headers: { 'content-type': 'application/json', 'user-agent': VERIFY_UA, 'origin': 'https://www.miss001.org', 'referer': 'https://www.miss001.org/' },
        body: JSON.stringify({ username, password }),
      });
      const j = await r.json();
      if (j.code === 0 && j.data && j.data.token) {
        const pr = await fetch('https://www.miss001.org/api/gva/pointsAcc/getUserPointsAccount', {
          headers: { 'user-agent': VERIFY_UA, 'x-token': j.data.token, 'origin': 'https://www.miss001.org' },
        });
        const pj = await pr.json();
        const points = Math.floor(Number(pj.data && pj.data.combinedBalance) || 0);
        return { ok: true, username, points, label: '密丝AI', unit: '体验点', detail: `密丝AI · 体验点 ${points}` };
      }
      return { ok: false, error: (j.msg || '登录失败：账号或密码有误') };
    } catch (e) { return { ok: false, error: '登录失败：网络异常' }; }
  }
  if (platform === 'dzmm') {
    return { ok: false, error: 'DZMM 受 Cloudflare 保护，无法自动验证' };
  }
  return { ok: false, error: '未知渠道' };
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
      // 一 IP 一号: 同一 IP 已有注册用户则拒绝
      const ip = clientIp(req);
      if (ip) {
        const dup = await DB.prepare('SELECT id FROM users WHERE ip=? LIMIT 1').bind(ip).first();
        if (dup) return err(4003, '该 IP 已注册过账号，一个网络只能注册一枚信物');
      }
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
        const r = await DB.prepare('INSERT INTO users(username,password_hash,role,ip) VALUES(?,?,?,?)')
          .bind(b.username, `${salt}:${ph}`, 'user', ip || null).run();
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
          (platform,nickname,password,email,email_password,user_id,registered_at,petals,stardust,status,imported_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
          ON CONFLICT(email) DO UPDATE SET
            platform=excluded.platform, nickname=excluded.nickname, password=excluded.password, user_id=excluded.user_id,
            registered_at=excluded.registered_at, petals=excluded.petals, stardust=excluded.stardust,
            email_password=excluded.email_password, status=CASE WHEN chunshui_accounts.status='sold' THEN 'sold' ELSE excluded.status END`)
          .bind(a.platform ?? 'aimagnet', a.nickname ?? '', a.password ?? '', a.email ?? '', a.email_password ?? '',
                a.user_id ?? '', a.registered_at ?? '', a.petals ?? 0, a.stardust ?? 0, a.status ?? 'pool'));
        upserted++;
      }
      for (const s of b.sign_records || []) {
        ops.push(DB.prepare('INSERT OR REPLACE INTO chunshui_sign_records(account_id,date,status,reward,created_at) VALUES(?,?,?,?,datetime(\'now\',\'localtime\'))')
          .bind(s.account_id, s.date, s.status, s.reward || 0));
      }
      for (const pt of b.points || []) {
        ops.push(DB.prepare('INSERT OR REPLACE INTO chunshui_point_snapshots(account_id,date,petals,stardust) VALUES(?,?,?,?)')
          .bind(pt.account_id, pt.date, pt.petals || 0, pt.stardust ?? 0));
      }
      for (const h of b.health || []) {
        ops.push(DB.prepare("UPDATE chunshui_accounts SET last_check_at=?, last_check_ok=?, check_error=?, petals=?, stardust=? WHERE id=?")
          .bind(now(), h.ok ? 1 : 0, h.error || '', h.petals ?? 0, h.stardust ?? 0, h.account_id));
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
      const st = await DB.prepare("SELECT key,value FROM settings WHERE key IN('token_per_rmb','qq_group')").all();
      const setMap = {};
      for (const r of st.results) setMap[r.key] = r.value;
      return ok({ platforms, summary, token_per_rmb: Number(setMap.token_per_rmb) || 100, qq_group: setMap.qq_group || '' });
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

    // ============ 公开: 脚本/皮肤商品 & 玩家市场 ============
    if (p === '/api/script-products' && method === 'GET') {
      const sp = new URL(req.url).searchParams;
      const t = sp.get('type') || '';
      let sql = "SELECT id,type,name,desc,price,file_url,thumbnail,platform,sold,created_at FROM products WHERE active=1";
      const vals = [];
      if (t === 'script' || t === 'skin') { sql += ' AND type=?'; vals.push(t); }
      sql += ' ORDER BY id DESC';
      const rows = await DB.prepare(sql).bind(...vals).all();
      return ok({ products: rows.results });
    }
    if (p === '/api/player-offers' && method === 'GET') {
      const sp = new URL(req.url).searchParams;
      const cat = sp.get('category') || '';
      let sql = "SELECT o.id,o.title,o.desc,o.kind,o.price,o.category,o.platform,o.verified,o.verify_detail,o.account_name,o.account_email,o.file_name,o.file_tip,o.created_at,u.username FROM player_offers o LEFT JOIN users u ON u.id=o.user_id WHERE o.status='open'";
      const vals = [];
      if (cat === 'account' || cat === 'resource' || cat === 'script') { sql += ' AND o.category=?'; vals.push(cat); }
      sql += ' ORDER BY o.id DESC LIMIT 100';
      const rows = await DB.prepare(sql).bind(...vals).all();
      return ok({ offers: rows.results });
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

    // 充值下单 (登录)
    if (p === '/api/recharge' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const rmb = Number(b.amount_rmb);
      if (!rmb || rmb < 1 || rmb > 10000) return err(4001, '金额不合法');
      const bonus = Math.max(0, Number(b.bonus) || 0);
      const st = await DB.prepare("SELECT value FROM settings WHERE key='token_per_rmb'").first();
      const rate = Number(st?.value) || 100;
      const tokenAmount = rmb * rate + bonus;
      const no = 'RC' + Date.now().toString(36).toUpperCase() + Math.floor(Math.random() * 1e6).toString(36).toUpperCase();
      const r = await DB.prepare('INSERT INTO recharge_orders(order_no,user_id,amount_rmb,bonus,token_amount,note) VALUES(?,?,?,?,?,?)')
        .bind(no, auth.uid, rmb, bonus, tokenAmount, String(b.note || '').slice(0, 200)).run();
      return ok({ id: r.meta.last_row_id, order_no: no, amount_rmb: rmb, token_amount: tokenAmount, rate });
    }

    // 我的充值订单 (登录)
    if (p === '/api/recharge/orders' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const rows = await DB.prepare('SELECT * FROM recharge_orders WHERE user_id=? ORDER BY id DESC LIMIT 30').bind(auth.uid).all();
      return ok({ orders: rows.results });
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

    // 购买脚本/皮肤
    if (p === '/api/script-orders' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const prod = await DB.prepare('SELECT * FROM products WHERE id=? AND active=1').bind(b.product_id).first();
      if (!prod) return err(4003, '商品不存在或已下架');
      const u = await DB.prepare('SELECT * FROM users WHERE id=?').bind(auth.uid).first();
      if (u.balance < prod.price) return err(4004, '代币不足');
      await DB.batch([
        DB.prepare('UPDATE users SET balance=balance-? WHERE id=?').bind(prod.price, auth.uid),
        DB.prepare('UPDATE products SET sold=sold+1 WHERE id=?').bind(prod.id),
        DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(auth.uid, -prod.price, 'buy', `购买${prod.type === 'skin' ? '皮肤' : '脚本'} ${prod.name}`),
      ]);
      return ok({ product: { name: prod.name, type: prod.type, file_url: prod.file_url, desc: prod.desc } });
    }

    // 我的玩家市场发布
    if (p === '/api/player-offers/mine' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const rows = await DB.prepare("SELECT * FROM player_offers WHERE user_id=? ORDER BY id DESC LIMIT 50").bind(auth.uid).all();
      return ok({ offers: rows.results });
    }
    // 发布玩家市场 (出号/出资源/出脚本)
    if (p === '/api/player-offers' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const title = String(b.title || '').trim();
      if (!title || title.length > 40) return err(4001, '标题必填且不超过 40 字');
      if (b.kind !== 'sell' && b.kind !== 'buy') return err(4001, '类型必填(sell/buy)');
      const price = Math.max(0, Number(b.price) || 0);
      const category = ['account', 'resource', 'script'].includes(b.category) ? b.category : 'account';
      let platform = '', accountName = '', accountPwd = '', accountEmail = '', verified = 0, verifyDetail = '';
      let fileUrl = '', fileName = '', fileTip = '';
      if (category === 'account') {
        platform = String(b.platform || '').trim();
        accountName = String(b.account_name || '').trim();
        accountPwd = String(b.account_password || '').trim();
        accountEmail = String(b.account_email || '').trim();
        if (!['fengyue', 'missai', 'aimagnet', 'dzmm'].includes(platform)) return err(4001, '渠道必须从内置选项中选择');
        if (!accountName || !accountPwd) return err(4001, '出号需填写账号名与账号密码');
        // 渠道官方自动验证受平台 IP 风控限制 (Worker 数据中心 IP 被各渠道拦截), 发布时标记未验证
        verified = 0; verifyDetail = '发布时未自动验证 (渠道平台风控限制)';
      }
      if (category === 'script') {
        fileUrl = String(b.file_url || '').trim().slice(0, 500);
        fileName = String(b.file_name || '').trim().slice(0, 100);
        fileTip = String(b.file_tip || '').trim().slice(0, 300);
        if (!fileUrl) return err(4001, '出脚本需填写文件/网盘链接');
      }
      const r = await DB.prepare(
        'INSERT INTO player_offers(user_id,title,desc,kind,price,category,platform,account_name,account_password,account_email,verified,verify_detail,file_url,file_name,file_tip) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
      ).bind(auth.uid, title, String(b.desc || '').slice(0, 300), b.kind, price, category,
             platform, accountName, accountPwd, accountEmail, verified, verifyDetail, fileUrl, fileName, fileTip).run();
      return ok({ id: r.meta.last_row_id, verified, verify_detail: verifyDetail });
    }
    const mOffer = p.match(/^\/api\/player-offers\/(\d+)$/);
    if (mOffer && method === 'PATCH') {
      if (!auth) return err(4010, '未登录', 401);
      const off = await DB.prepare('SELECT * FROM player_offers WHERE id=?').bind(mOffer[1]).first();
      if (!off) return err(4004, '不存在');
      if (off.user_id !== auth.uid && auth.role !== 'admin') return err(4030, '无权限', 403);
      const b = await json(req);
      const st = b.status === 'closed' ? 'closed' : b.status === 'open' ? 'open' : null;
      if (!st) return err(4001, 'status 非法');
      await DB.prepare('UPDATE player_offers SET status=? WHERE id=?').bind(st, off.id).run();
      return ok({ status: st });
    }
    // 重新验证出号 (卖家/管理员)
    const mOfferVerify = p.match(/^\/api\/player-offers\/(\d+)\/verify$/);
    if (mOfferVerify && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const off = await DB.prepare('SELECT * FROM player_offers WHERE id=?').bind(mOfferVerify[1]).first();
      if (!off) return err(4004, '不存在');
      if (off.user_id !== auth.uid && auth.role !== 'admin') return err(4030, '无权限', 403);
      if (off.category !== 'account') return err(4001, '仅出号可验证');
      // 渠道官方自动验证受平台 IP 风控限制, 统一标记验证不可用
      await DB.prepare('UPDATE player_offers SET verified=0, verify_detail=? WHERE id=?').bind('渠道平台风控限制, 自动验证不可用', off.id).run();
      return ok({ verified: 0, verify_detail: '渠道平台风控限制, 自动验证不可用' });
    }

    // ============ 玩家交易订单 (托管/冻结) ============
    // 拍下: 买家冻结代币 -> 出号即交付凭证 -> 双方确认 -> 结算给卖家
    if (p === '/api/player-orders' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const off = await DB.prepare("SELECT * FROM player_offers WHERE id=? AND status='open'").bind(b.offer_id).first();
      if (!off) return err(4003, '该发布不存在或已关闭');
      if (off.user_id === auth.uid) return err(4001, '不能购买自己的发布');
      const u = await DB.prepare('SELECT * FROM users WHERE id=?').bind(auth.uid).first();
      if (u.balance < off.price) return err(4004, '代币不足');
      if (!off.price) return err(4001, '免费发布无需拍下');
      const no = 'PO' + Date.now().toString(36).toUpperCase() + Math.floor(Math.random() * 1e6).toString(36).toUpperCase();
      // 出号: 首个拍下者获得凭证, 立即关闭发布防重复售号
      if (off.category === 'account') {
        const paid = await DB.prepare("SELECT COUNT(*) n FROM player_orders WHERE offer_id=? AND status IN('paid','completed')").bind(off.id).first();
        if (paid.n > 0) return err(4003, '该号已被拍下');
      }
      const r = await DB.prepare(
        "INSERT INTO player_orders(order_no,offer_id,buyer_id,seller_id,category,amount,status,buyer_confirm,seller_confirm) VALUES(?,?,?,?,?,?,'paid',0,0)"
      ).bind(no, off.id, auth.uid, off.user_id, off.category, off.price).run();
      const ops = [
        DB.prepare('UPDATE users SET balance=balance-? WHERE id=?').bind(off.price, auth.uid),
        DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(auth.uid, -off.price, 'buy', `拍下玩家发布「${off.title}」(冻结)`),
      ];
      if (off.category === 'account') {
        ops.push(DB.prepare("UPDATE player_offers SET status='closed' WHERE id=? AND status='open'").bind(off.id));
      }
      await DB.batch(ops);
      const order = { id: r.meta.last_row_id, order_no: no, category: off.category, amount: off.price, status: 'paid',
        account: off.category === 'account' ? { platform: off.platform, account_name: off.account_name, account_password: off.account_password, account_email: off.account_email, verified: off.verified, verify_detail: off.verify_detail } : null,
        file: off.category === 'script' ? { file_url: off.file_url, file_name: off.file_name, file_tip: off.file_tip } : null };
      return ok(order);
    }
    // 我的玩家订单 (买家或卖家)
    if (p === '/api/player-orders/mine' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const rows = await DB.prepare(
        "SELECT o.*, of.title, of.category AS offer_category, bu.username AS buyer_name, su.username AS seller_name FROM player_orders o LEFT JOIN player_offers of ON of.id=o.offer_id LEFT JOIN users bu ON bu.id=o.buyer_id LEFT JOIN users su ON su.id=o.seller_id WHERE o.buyer_id=? OR o.seller_id=? ORDER BY o.id DESC LIMIT 50"
      ).bind(auth.uid, auth.uid).all();
      // 附上交付信息 (账号凭证/脚本附件, 仅买家或卖家可见)
      const out = [];
      for (const o of rows.results) {
        const off = await DB.prepare('SELECT * FROM player_offers WHERE id=?').bind(o.offer_id).first();
        const oo = { ...o };
        if (off) {
          if (off.category === 'account') {
            oo.account = { platform: off.platform, account_name: off.account_name, account_password: off.account_password, account_email: off.account_email, verified: off.verified, verify_detail: off.verify_detail };
          }
          if (off.category === 'script') {
            oo.file = { file_url: off.file_url, file_name: off.file_name, file_tip: off.file_tip };
          }
        }
        out.push(oo);
      }
      return ok({ orders: out });
    }
    // 订单确认/取消
    const mPOrder = p.match(/^\/api\/player-orders\/(\d+)$/);
    if (mPOrder && method === 'PATCH') {
      if (!auth) return err(4010, '未登录', 401);
      const ord = await DB.prepare('SELECT * FROM player_orders WHERE id=?').bind(mPOrder[1]).first();
      if (!ord) return err(4004, '订单不存在');
      const b = await json(req);
      // 确认到货 (买家/卖家各自点确认, 双方都确认后结算)
      if (b.act === 'confirm') {
        if (ord.status !== 'paid') return err(4001, '订单状态已变更');
        const as = b.as === 'seller' ? 'seller' : 'buyer';
        const me = as === 'buyer' ? ord.buyer_id : ord.seller_id;
        if (auth.uid !== me && auth.role !== 'admin') return err(4030, '无权限', 403);
        if (as === 'buyer') {
          await DB.prepare('UPDATE player_orders SET buyer_confirm=1, updated_at=? WHERE id=?').bind(now(), ord.id).run();
        } else {
          await DB.prepare('UPDATE player_orders SET seller_confirm=1, updated_at=? WHERE id=?').bind(now(), ord.id).run();
        }
        const upd = await DB.prepare('SELECT * FROM player_orders WHERE id=?').bind(ord.id).first();
        if (upd.buyer_confirm && upd.seller_confirm) {
          // 双方确认 -> 结算: 冻结金额发放给卖家
          await DB.batch([
            DB.prepare("UPDATE player_orders SET status='completed', updated_at=? WHERE id=?").bind(now(), ord.id),
            DB.prepare('UPDATE users SET balance=balance+? WHERE id=?').bind(ord.amount, ord.seller_id),
            DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(ord.seller_id, ord.amount, 'sell', `玩家交易结算 #${ord.order_no}`),
          ]);
          return ok({ status: 'completed', settled: true });
        }
        return ok({ status: 'paid', confirmed: as });
      }
      // 取消退款 (管理员)
      if (b.act === 'cancel' && auth.role === 'admin') {
        if (ord.status !== 'paid') return err(4001, '订单状态已变更');
        await DB.batch([
          DB.prepare("UPDATE player_orders SET status='cancelled', updated_at=? WHERE id=?").bind(now(), ord.id),
          DB.prepare('UPDATE users SET balance=balance+? WHERE id=?').bind(ord.amount, ord.buyer_id),
          DB.prepare('INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)').bind(ord.buyer_id, ord.amount, 'refund', `玩家交易退款 #${ord.order_no}`),
          DB.prepare("UPDATE player_offers SET status='open' WHERE id=? AND category='account' AND status='closed'").bind(ord.offer_id),
        ]);
        return ok({ status: 'cancelled' });
      }
      return err(4001, 'act 非法');
    }

    // ============ 玩家私聊 ============
    // 买家发起会话 (与卖家私聊)
    const mConvCreate = p.match(/^\/api\/player-offers\/(\d+)\/conversations$/);
    if (mConvCreate && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const off = await DB.prepare('SELECT * FROM player_offers WHERE id=?').bind(mConvCreate[1]).first();
      if (!off) return err(4004, '不存在');
      if (off.user_id === auth.uid) return err(4001, '不能与自己私聊');
      const exist = await DB.prepare('SELECT * FROM player_conversations WHERE offer_id=? AND buyer_id=?').bind(off.id, auth.uid).first();
      if (exist) return ok({ conversation: exist });
      const r = await DB.prepare('INSERT INTO player_conversations(offer_id,buyer_id,seller_id) VALUES(?,?,?)')
        .bind(off.id, auth.uid, off.user_id).run();
      const conv = { id: r.meta.last_row_id, offer_id: off.id, buyer_id: auth.uid, seller_id: off.user_id };
      return ok({ conversation: conv });
    }
    // 我的会话列表
    if (p === '/api/conversations' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const rows = await DB.prepare(
        "SELECT c.id, c.offer_id, c.buyer_id, c.seller_id, of.title, of.category, bu.username AS buyer_name, su.username AS seller_name, (SELECT content FROM player_messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_msg, (SELECT MAX(id) FROM player_messages m WHERE m.conversation_id=c.id) AS last_msg_id FROM player_conversations c LEFT JOIN player_offers of ON of.id=c.offer_id LEFT JOIN users bu ON bu.id=c.buyer_id LEFT JOIN users su ON su.id=c.seller_id WHERE c.buyer_id=? OR c.seller_id=? ORDER BY last_msg_id IS NULL, last_msg_id DESC"
      ).bind(auth.uid, auth.uid).all();
      return ok({ conversations: rows.results });
    }
    // 会话消息
    const mConv = p.match(/^\/api\/conversations\/(\d+)(?:\/messages)?$/);
    if (mConv) {
      const conv = await DB.prepare('SELECT * FROM player_conversations WHERE id=?').bind(mConv[1]).first();
      if (!conv) return err(4004, '会话不存在');
      if (conv.buyer_id !== auth.uid && conv.seller_id !== auth.uid && auth.role !== 'admin') return err(4030, '无权限', 403);
      if (method === 'GET' && p.endsWith('/messages')) {
        const sp = new URL(req.url).searchParams;
        const after = Number(sp.get('after')) || 0;
        let sql = 'SELECT m.id,m.sender_id,m.content,m.created_at,u.username FROM player_messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=?';
        const vals = [conv.id];
        if (after > 0) { sql += ' AND m.id>?'; vals.push(after); }
        sql += ' ORDER BY m.id DESC LIMIT 100';
        const rows = await DB.prepare(sql).bind(...vals).all();
        return ok({ messages: rows.results.reverse() });
      }
      if (method === 'POST' && p.endsWith('/messages')) {
        const b = await json(req);
        const content = String(b.content || '').trim();
        if (!content || content.length > 500) return err(4001, '消息内容必填且不超过 500 字');
        const r = await DB.prepare('INSERT INTO player_messages(conversation_id,sender_id,content) VALUES(?,?,?)')
          .bind(conv.id, auth.uid, content).run();
        return ok({ id: r.meta.last_row_id, content });
      }
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

    // ============ 聊天室 ============
    if (p === '/api/chat/messages' && method === 'GET') {
      if (!auth) return err(4010, '未登录', 401);
      const sp = new URL(req.url).searchParams;
      const after = Number(sp.get('after')) || 0;
      let sql = 'SELECT m.id,m.user_id,m.content,m.created_at,u.username FROM chat_messages m LEFT JOIN users u ON u.id=m.user_id';
      const vals = [];
      if (after > 0) { sql += ' WHERE m.id>?'; vals.push(after); }
      sql += ' ORDER BY m.id DESC LIMIT 100';
      const rows = await DB.prepare(sql).bind(...vals).all();
      return ok({ messages: rows.results.reverse() });
    }
    if (p === '/api/chat/messages' && method === 'POST') {
      if (!auth) return err(4010, '未登录', 401);
      const b = await json(req);
      const content = String(b.content || '').trim();
      if (!content || content.length > 500) return err(4001, '消息内容必填且不超过 500 字');
      const r = await DB.prepare('INSERT INTO chat_messages(user_id,content) VALUES(?,?)').bind(auth.uid, content).run();
      return ok({ id: r.meta.last_row_id, content, username: auth.username });
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

    // ============ 脚本/皮肤商品管理 (admin) ============
    if (p === '/api/admin/products' && method === 'GET') {
      const rows = await DB.prepare('SELECT * FROM products ORDER BY id DESC LIMIT 100').all();
      return ok({ products: rows.results });
    }
    if (p === '/api/admin/products' && method === 'POST') {
      const b = await json(req);
      const name = String(b.name || '').trim();
      if (!name || name.length > 40) return err(4001, '名称必填且不超过 40 字');
      if (b.type !== 'script' && b.type !== 'skin') return err(4001, '类型必填(script/skin)');
      const price = Math.max(0, Number(b.price) || 0);
      const r = await DB.prepare('INSERT INTO products(type,name,desc,price,file_url,thumbnail,platform,active) VALUES(?,?,?,?,?,?,?,?)')
        .bind(b.type, name, String(b.desc || '').slice(0, 300), price, String(b.file_url || '').slice(0, 500), String(b.thumbnail || '').slice(0, 500), String(b.platform || '').slice(0, 20), b.active === undefined ? 1 : (b.active ? 1 : 0)).run();
      return ok({ id: r.meta.last_row_id });
    }
    const mProd = p.match(/^\/api\/admin\/products\/(\d+)$/);
    if (mProd && method === 'PATCH') {
      const b = await json(req);
      const sets = [], vals = [];
      if (b.name !== undefined) { sets.push('name=?'); vals.push(String(b.name).trim()); }
      if (b.desc !== undefined) { sets.push('desc=?'); vals.push(String(b.desc).slice(0, 300)); }
      if (b.price !== undefined) { sets.push('price=?'); vals.push(Math.max(0, Number(b.price) || 0)); }
      if (b.file_url !== undefined) { sets.push('file_url=?'); vals.push(String(b.file_url).slice(0, 500)); }
      if (b.thumbnail !== undefined) { sets.push('thumbnail=?'); vals.push(String(b.thumbnail).slice(0, 500)); }
      if (b.platform !== undefined) { sets.push('platform=?'); vals.push(String(b.platform).slice(0, 20)); }
      if (b.active !== undefined) { sets.push('active=?'); vals.push(b.active ? 1 : 0); }
      if (b.type !== undefined && (b.type === 'script' || b.type === 'skin')) { sets.push('type=?'); vals.push(b.type); }
      if (!sets.length) return err(4001, '无字段');
      vals.push(mProd[1]);
      await DB.prepare(`UPDATE products SET ${sets.join(',')} WHERE id=?`).bind(...vals).run();
      return ok({ updated: true });
    }
    if (mProd && method === 'DELETE') {
      await DB.prepare('DELETE FROM products WHERE id=?').bind(mProd[1]).run();
      return ok({ deleted: true });
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
      if (b.qq_group !== undefined) {
        const s = String(b.qq_group).trim();
        if (!s || s.length > 100) return err(4001, 'qq_group 非法');
        await DB.prepare("INSERT INTO settings(key,value) VALUES('qq_group',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(s).run();
      }
      return ok({ updated: true });
    }

    // ============ 充值订单 (admin 查看/审核) ============
    if (p === '/api/admin/orders' && method === 'GET') {
      const sp = new URL(req.url).searchParams;
      const st = sp.get('status') || '';
      let sql = 'SELECT o.*, u.username FROM recharge_orders o LEFT JOIN users u ON u.id=o.user_id';
      const vals = [];
      if (st) { sql += ' WHERE o.status=?'; vals.push(st); }
      sql += ' ORDER BY o.id DESC LIMIT 100';
      const rows = await DB.prepare(sql).bind(...vals).all();
      return ok({ orders: rows.results });
    }
    const mOrd = p.match(/^\/api\/admin\/orders\/(\d+)$/);
    if (mOrd && method === 'PATCH') {
      const b = await json(req);
      const ord = await DB.prepare('SELECT * FROM recharge_orders WHERE id=?').bind(mOrd[1]).first();
      if (!ord) return err(4004, '订单不存在');
      if (ord.status !== 'pending') return err(4004, '订单已处理');
      if (b.status === 'done') {
        await DB.batch([
          DB.prepare('UPDATE users SET balance=balance+? WHERE id=?').bind(ord.token_amount, ord.user_id),
          DB.prepare("UPDATE recharge_orders SET status='done', handled_by=?, handled_at=datetime('now','localtime') WHERE id=?").bind(auth?.uid || null, ord.id),
          DB.prepare("INSERT INTO transactions(user_id,amount,type,note) VALUES(?,?,?,?)").bind(ord.user_id, ord.token_amount, 'charge', `充值订单 ${ord.order_no} 到账`),
        ]);
        return ok({ token_amount: ord.token_amount });
      }
      if (b.status === 'rejected') {
        await DB.prepare("UPDATE recharge_orders SET status='rejected', handled_by=?, handled_at=datetime('now','localtime') WHERE id=?").bind(auth?.uid || null, ord.id).run();
        return ok({ rejected: true });
      }
      return err(4001, 'status 非法');
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