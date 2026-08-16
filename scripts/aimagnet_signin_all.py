#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密丝AI(春水Live) 批量每日签到: 登录 -> 检查签到状态 -> POST /v1/users/signin
用法: python aimagnet_signin_all.py [账号文件 默认 aimagnet_accounts.txt]"""
import io, sys, requests, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PROX = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
AB = "https://aimagnet.vip"
BASE = os.path.dirname(os.path.abspath(__file__))
acc = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "aimagnet_accounts.txt")
H = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36",
     "origin": AB, "referer": AB + "/", "content-type": "application/json", "accept": "application/json"}

rows = [l.split() for l in open(acc, encoding='utf-8') if l.strip()]
print(f"账号数: {len(rows)}")
new_sign, already, failed = 0, 0, []
for i, row in enumerate(rows, 1):
    user, pwd, email, mpwd, uid = row
    try:
        r = requests.post(f"{AB}/v1/auth/login", json={"identifier": email, "password": pwd},
                          headers=H, proxies=PROX, timeout=30)
        if r.status_code != 200:
            failed.append(f"{user}: 登录失败 {r.status_code}")
            print(f"[{i}/{len(rows)}] {user} ✗ 登录失败 {r.status_code}")
            continue
        tok = r.json()['tokens']['accessToken']
        h2 = dict(H); h2["authorization"] = f"Bearer {tok}"
        st = requests.get(f"{AB}/v1/users/signin/status", headers=h2, proxies=PROX, timeout=30).json()
        if st.get('todaySigned'):
            already += 1
            print(f"[{i}/{len(rows)}] {user} · 已签(今天)")
            continue
        r2 = requests.post(f"{AB}/v1/users/signin", headers=h2, proxies=PROX, timeout=30)
        if r2.status_code == 200:
            j = r2.json()
            new_sign += 1
            print(f"[{i}/{len(rows)}] {user} ✓ 签到成功 +{j.get('petalsGranted')}花瓣 连续{j.get('monthlyDays')}天")
        else:
            failed.append(f"{user}: 签到失败 {r2.status_code} {r2.text[:80]}")
            print(f"[{i}/{len(rows)}] {user} ✗ 签到失败 {r2.status_code} {r2.text[:80]}")
    except Exception as e:
        failed.append(f"{user}: {e}")
        print(f"[{i}/{len(rows)}] {user} ✗ ERR {e}")

print(f"\n结果: 新签 {new_sign} | 已签 {already} | 失败 {len(failed)}")
if failed:
    print("失败明细:"); [print("  ", f) for f in failed]