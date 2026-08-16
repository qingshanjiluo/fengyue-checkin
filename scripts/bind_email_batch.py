#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风月账号批量绑定临时邮箱（mail.tm）
链路: mail.tm 创建临时邮箱 -> 风月发验证码 -> 收码 -> 绑定
用法: python bind_email_batch.py [数量] [起始行]
输出: accounts_bound.txt (网名 密码 JWT 绑定邮箱 邮箱密码)
"""
import sys, io, time, random, string, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACCOUNTS_FILE = r'G:\皮皮\编程项目\fengyue\accounts.txt'
BOUND_FILE = r'G:\皮皮\编程项目\fengyue\accounts_bound.txt'
GO = "https://aiaha.xyz/go/api"
PROFILE = "https://aiaha.xyz/console/api/account/profile"
MTM = "https://api.mail.tm"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
START = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0

stats = {'ok': 0, 'skip': 0, 'fail': 0}

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def get_auth_h(jwt):
    return {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai",
            "accept": "application/json", "authorization": f"Bearer {jwt}"}

def check_email_bound(jwt):
    """检查账号是否已绑定邮箱，返回 (是否已绑定, 邮箱)"""
    try:
        r = requests.get(PROFILE, headers=get_auth_h(jwt), timeout=15)
        j = r.json()
        email = j.get('email') or ''
        return bool(email), email
    except Exception:
        return False, ''

def create_temp_email():
    """创建 mail.tm 临时邮箱，返回 (地址, 密码, token)"""
    domains = requests.get(f"{MTM}/domains", timeout=20).json()
    domain = random.choice(domains['hydra:member'])['domain']
    addr = "".join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@" + domain
    tpwd = "".join(random.choices(string.ascii_letters + string.digits, k=12)) + "!Aa"
    r = requests.post(f"{MTM}/accounts", json={"address": addr, "password": tpwd}, timeout=20)
    if r.status_code >= 300:
        return None, None, None
    tok = requests.post(f"{MTM}/token", json={"address": addr, "password": tpwd}, timeout=20).json()['token']
    return addr, tpwd, tok

def send_code(jwt, email):
    r = requests.post(f"{GO}/account/email/code", json={"email": email}, headers=get_auth_h(jwt), timeout=20)
    j = r.json()
    return j.get('code') == 100000, j.get('msg', '')

def get_code(tok, email, timeout=90):
    """轮询收验证码，返回 6 位码或 None"""
    mh = {"Authorization": f"Bearer {tok}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msgs = requests.get(f"{MTM}/messages", headers=mh, timeout=20).json()
            for m in msgs.get('hydra:member', []):
                body = requests.get(f"{MTM}/messages/{m['id']}", headers=mh, timeout=20).json()
                txt = str(body.get('text') or '')
                html = str(body.get('html') or '')
                intro = str(body.get('intro') or '')
                import re
                mch = re.findall(r'\b(\d{6})\b', intro + txt + re.sub(r'<[^>]+>', '', html))
                if mch:
                    return mch[0]
        except Exception:
            pass
        time.sleep(4)
    return None

def bind_email(jwt, email, code):
    r = requests.post(f"{GO}/account/email/bind", json={"email": email, "code": code}, headers=get_auth_h(jwt), timeout=20)
    j = r.json()
    return j.get('code') == 100000, j

def process_account(name, pwd, jwt):
    bound, cur_email = check_email_bound(jwt)
    if bound:
        log(f"  {name}: 已绑定 {cur_email}，跳过")
        stats['skip'] += 1
        return None

    # 风月发码可能有频率限制，失败重试
    addr = tpwd = tok = None
    for attempt in range(3):
        addr, tpwd, tok = create_temp_email()
        if addr:
            break
        log(f"  {name}: 创建临时邮箱失败，重试 {attempt+1}")
        time.sleep(2)
    if not addr:
        stats['fail'] += 1
        return None

    ok, msg = send_code(jwt, addr)
    if not ok:
        log(f"  {name}: 发码失败 {msg}，账号可能受限")
        stats['fail'] += 1
        return None

    code = get_code(tok, addr)
    if not code:
        log(f"  {name}: 收码超时 ({addr})")
        stats['fail'] += 1
        return None

    ok, resp = bind_email(jwt, addr, code)
    if ok:
        log(f"  {name}: ✓ 绑定成功 {addr} (码 {code})")
        stats['ok'] += 1
        return (name, pwd, jwt, addr, tpwd)
    else:
        log(f"  {name}: 绑定失败 {json.dumps(resp, ensure_ascii=False)[:100]}")
        stats['fail'] += 1
        return None

def main():
    lines = [l.split() for l in open(ACCOUNTS_FILE, encoding='utf-8') if l.strip()]
    log(f"共 {len(lines)} 个账号，本次处理 {COUNT} 个（从第 {START} 个开始）")
    done = []
    for i in range(START, min(START + COUNT, len(lines))):
        name, pwd, jwt = lines[i][0], lines[i][1], lines[i][2]
        log(f"[{i+1}/{len(lines)}] {name}")
        res = process_account(name, pwd, jwt)
        if res:
            done.append(res)
        time.sleep(random.uniform(1.5, 3.5))

    with open(BOUND_FILE, 'a', encoding='utf-8') as f:
        for name, pwd, jwt, addr, tpwd in done:
            f.write(f"{name} {pwd} {jwt} {addr} {tpwd}\n")
    log(f"\n完成: 成功{stats['ok']} 跳过{stats['skip']} 失败{stats['fail']}")

if __name__ == '__main__':
    main()