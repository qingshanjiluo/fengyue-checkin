import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts.txt', encoding='utf-8') if l.strip()]
name, pwd = lines[0][0], lines[0][1]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "referer": "https://aiaha.xyz/zh/signin"}
API = "https://aiaha.xyz/console/api"
jwt = requests.post(f"{API}/login", json={"email": name, "password": pwd}, headers=h, timeout=20).json()['data']
h["authorization"] = f"Bearer {jwt}"
print("登录:", name)
tags = requests.get(f"{API}/tags", params={"type": "app"}, headers=h, timeout=20).json()
t0 = tags[0]
print("tag0:", t0)
# 尝试多种结构
cands = [
    {"key": "favorite_tags", "value": [t0['id']]},
    {"key": "favorite_tags", "value": [{"id": t0['id'], "name": t0['name']}]},
    {"key": "favorite_tags", "value": [t0]},
    {"key": "favorite_tags", "value": [{"tag_id": t0['id']}]},
]
for b in cands:
    r = requests.post(f"{API}/account/extend_set", json=b, headers=h, timeout=20)
    rj = requests.get(f"{API}/account/profile", headers=h, timeout=20).json()
    print(f"value={json.dumps(b['value'], ensure_ascii=False)[:60]} -> set[{r.status_code}] {str(r.text)[:80]} | profile.favorite_tags={rj.get('extend',{}).get('favorite_tags')}")
