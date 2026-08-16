import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts_bound.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[0][0], lines[0][1], lines[0][2]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/settings"}

API = "https://aiaha.xyz/console/api"
# 1. 性别设置
r = requests.post(f"{API}/account/gender", json={"gender": 1}, headers=h, timeout=20)
print(f"gender: [{r.status_code}] {r.text[:200]}")
# 2. profile 确认 gender
r = requests.get(f"{API}/account/profile", headers=h, timeout=20)
print(f"profile: {r.text[:260]}")
print()
# 3. 标签列表
for t in ['app', 'user', 'conversation']:
    r = requests.get(f"{API}/tags", params={"type": t}, headers=h, timeout=20)
    print(f"tags type={t}: [{r.status_code}] {r.text[:200]}")
