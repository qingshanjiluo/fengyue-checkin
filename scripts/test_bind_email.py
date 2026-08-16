import sys, io, json, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

GO = "https://aiaha.xyz/go/api"
MTM = "https://api.mail.tm"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"

# 从 accounts.txt 取一个账号（最后一行）
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[-1][0], lines[-1][1], lines[-1][2]
print(f"测试账号: {name}")

# 1. 创建 mail.tm 临时邮箱
domains = requests.get(f"{MTM}/domains", timeout=20).json()
domain = domains['hydra:member'][0]['domain']
import random, string
addr = "".join(random.choices(string.ascii_lowercase, k=10)) + "@" + domain
mta = requests.post(f"{MTM}/accounts", json={"address": addr, "password": "TempPass123!"}, timeout=20)
print(f"创建临时邮箱: {addr} -> {mta.status_code} {mta.text[:100]}")
if mta.status_code >= 300:
    sys.exit(1)

# 2. 风月发验证码
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/settings"}
r = requests.post(f"{GO}/account/email/code", json={"email": addr}, headers=h, timeout=20)
print(f"风月发码: {r.json()}")

# 3. 登录 mail.tm 收信
tok = requests.post(f"{MTM}/token", json={"address": addr, "password": "TempPass123!"}, timeout=20).json()['token']
mh = {"Authorization": f"Bearer {tok}"}
code = None
for i in range(12):
    time.sleep(5)
    msgs = requests.get(f"{MTM}/messages", headers=mh, timeout=20).json()
    if msgs.get('hydra:member'):
        m = msgs['hydra:member'][0]
        body = requests.get(f"{MTM}/messages/{m['id']}", headers=mh, timeout=20).json()
        print(f"消息keys: {list(body.keys())}")
        print(f"消息内容(前500): {str(body)[:500]}")
        import re
        txt = str(body.get('text') or '')
        html = str(body.get('html') or '')
        mch = re.findall(r'\b(\d{6})\b', txt + re.sub(r'<[^>]+>', '', html))
        print(f"候选验证码: {mch[:5]}")
        if mch:
            code = mch[0]
            break
    print(f"  等待收信 {i+1}/12...")
if not code:
    print("未收到验证码")
    sys.exit(1)

# 4. 绑定
r = requests.post(f"{GO}/account/email/bind", json={"email": addr, "code": code}, headers=h, timeout=20)
print(f"绑定结果: {r.json()}")