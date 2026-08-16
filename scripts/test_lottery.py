import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts_bound.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[0][0], lines[0][1], lines[0][2]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/explore"}

API = "https://aiaha.xyz/console/api"
# status & probability
for ep in ['/daily_lottery/status', '/daily_lottery/probability']:
    r = requests.get(f"{API}{ep}", headers=h, timeout=20)
    print(f"{ep} [{r.status_code}]: {r.text[:300]}")
print()
# draw
r = requests.post(f"{API}/daily_lottery/draw", json={}, headers=h, timeout=20)
print(f"draw [{r.status_code}]: {r.text[:300]}")
print()
# sign in
r = requests.get(f"{API}/sign_in", headers=h, timeout=20)
print(f"sign_in [{r.status_code}]: {r.text[:300]}")
print()
# points
r = requests.get("https://aiaha.xyz/go/api/account/point", headers=h, timeout=20)
print(f"point: {r.text[:200]}")
# profile (level check)
r = requests.get(f"{API}/account/profile", headers=h, timeout=20)
print(f"profile: {r.text[:300]}")