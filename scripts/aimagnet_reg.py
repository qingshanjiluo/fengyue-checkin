#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密丝AI(春水Live, aimagnet.vip) 批量注册工具
链路: mail.tm 创建临时邮箱 -> aimagnet register/start -> 邮箱收验证码 -> register/complete -> 登录
限制: 每出口IP 20s 冷却 (ip_cooldown), mail.tm 创建账号也限速(~20s/4个)
用法:
  python aimagnet_reg.py --count 5
  python aimagnet_reg.py --count 50 --threads 3 --proxies proxies.txt   # 每线程独立代理(轮换)
输出: aimagnet_accounts.txt  (网名 密码 邮箱 邮箱密码 user_id)
"""
import argparse, io, sys, requests, json, random, string, time, re, os, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

AB = "https://aimagnet.vip"
MT = "https://api.mail.tm"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aimagnet_accounts.txt")

def make_headers(origin, extra=None):
    h = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36",
         "content-type": "application/json", "accept": "application/json"}
    if origin == AB:
        h.update({"origin": AB, "referer": AB + "/auth"})
    else:
        h.update({"referer": MT})
    if extra: h.update(extra)
    return h

class RateLimiter:
    """全局 start 冷却控制(单IP模式)"""
    def __init__(self, interval):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_at = 0
    def wait(self):
        with self.lock:
            wait = self.next_at - time.time()
            if wait > 0:
                time.sleep(wait)
            self.next_at = time.time() + self.interval

def rand_str(n, pool=string.ascii_lowercase + string.digits):
    return ''.join(random.choices(pool, k=n))

def rand_pwd():
    """密码: 确保至少含1字母+1数字"""
    while True:
        s = rand_str(10)
        if any(c.isdigit() for c in s) and any(c.isalpha() for c in s):
            return "Aa" + s + "!"

def mailtm_create(sess):
    """创建 mail.tm 邮箱, 处理429"""
    for _ in range(6):
        email = f"aim{rand_str(9)}@emalupe.com"
        pwd = rand_pwd()
        r = sess.post(f"{MT}/accounts", json={"address": email, "password": pwd},
                      headers=make_headers(MT), timeout=25)
        if r.status_code == 201:
            return email, pwd
        if r.status_code == 429:
            time.sleep(6)
            continue
        time.sleep(2)
    raise RuntimeError("mail.tm 创建失败")

def mailtm_token(sess, email, pwd):
    r = sess.post(f"{MT}/token", json={"address": email, "password": pwd},
                  headers=make_headers(MT), timeout=25)
    return r.json()['token']

def mailtm_wait_code(sess, email, pwd, timeout=75):
    tok = mailtm_token(sess, email, pwd)
    h = make_headers(MT, {"authorization": f"Bearer {tok}"})
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            msgs = sess.get(f"{MT}/messages", headers=h, timeout=20).json()
            if msgs and isinstance(msgs, list):
                d = sess.get(f"{MT}/messages/{msgs[0]['id']}", headers=h, timeout=20).json()
                txt = d.get('intro') or ''
                if isinstance(txt, list): txt = ' '.join(map(str, txt))
                m = re.search(r'(\d{6})', re.sub(r'\D', '', txt))
                if m: return m.group(1)
        except Exception:
            pass
        time.sleep(4)
    return None

def aim_start(sess, email, user, visitor=None, limiter=None):
    body = {"email": email, "password": rand_pwd(), "nickname": user,
            "contentPreferences": ["male", "female", "all"], "contentPreferenceConfirmed": True}
    if visitor:
        body["visitorId"] = visitor
    for _ in range(8):
        if limiter: limiter.wait()
        r = sess.post(f"{AB}/v1/auth/register/start", json=body, headers=make_headers(AB), timeout=30)
        if r.status_code == 200:
            return body["password"]
        if r.status_code == 429:
            try:
                j = r.json()
                wait = int(j.get('metadata', {}).get('retry_after_seconds', 20))
            except Exception:
                wait = 20
            time.sleep(wait + 1)
            continue
        raise RuntimeError(f"start 失败 {r.status_code}: {r.text[:120]}")
    raise RuntimeError("start 冷却超时")

def aim_complete(sess, email, code):
    r = sess.post(f"{AB}/v1/auth/register/complete", json={"email": email, "code": code},
                  headers=make_headers(AB), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"complete 失败 {r.status_code}: {r.text[:150]}")
    u = r.json()['user']
    return u.get('id'), u.get('username') or u.get('nickname')

def register_one(idx, proxy, limiter, results, errs, lock):
    try:
        sess = requests.Session()
        if proxy:
            sess.proxies.update({"http": proxy, "https": proxy})
        email, mpwd = mailtm_create(sess)
        user = f"cn{rand_str(7)}"
        pwd = aim_start(sess, email, user, limiter=limiter)
        code = mailtm_wait_code(sess, email, mpwd)
        if not code:
            raise RuntimeError("验证码超时")
        uid, uname = aim_complete(sess, email, code)
        line = f"{user} {pwd} {email} {mpwd} {uid}"
        with lock:
            results.append(line)
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        print(f"[{idx}] ✓ {user} | {email}")
    except Exception as e:
        with lock:
            errs.append(f"{idx}: {e}")
        print(f"[{idx}] ✗ {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--proxies", default="", help="代理文件(每行一个 http://ip:port), 线程轮换; 留空=本机IP串行")
    args = ap.parse_args()

    proxies = []
    if args.proxies:
        with open(args.proxies, encoding="utf-8") as f:
            proxies = [l.strip() for l in f if l.strip()]
    # 单IP模式下 start 有 20s 冷却 -> 强制串行
    use_limiter = len(proxies) < args.threads
    limiter = RateLimiter(20) if use_limiter else None
    threads = args.threads if proxies else 1

    print(f"目标: {args.count} 个 | 线程: {threads} | 代理: {len(proxies)} 个 | "
          f"{'串行限速20s/个' if use_limiter else '独立代理并行'}")
    results, errs, lock = [], [], threading.Lock()
    ts = []
    for i in range(args.count):
        while sum(1 for t in ts if t.is_alive()) >= threads:
            time.sleep(1)
        proxy = proxies[i % len(proxies)] if proxies else None
        t = threading.Thread(target=register_one, args=(i + 1, proxy, limiter, results, errs, lock))
        t.start(); ts.append(t)
    for t in ts: t.join()

    print(f"\n完成: 成功 {len(results)} / {args.count} | 失败 {len(errs)}")
    if errs:
        print("失败明细:"); [print("  ", e) for e in errs[:20]]
    print(f"结果: {OUT}")

if __name__ == "__main__":
    main()
