import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts_bound.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[0][0], lines[0][1], lines[0][2]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/explore"}

API = "https://aiaha.xyz/console/api"
# 用户 id
pid = requests.get(f"{API}/account/profile", headers=h, timeout=20).json()['id']
print("user id:", pid)
# 拿 app 标签前5个
tags = requests.get(f"{API}/tags", params={"type": "app"}, headers=h, timeout=20).json()
tag_ids = [t['id'] for t in tags[:5]]
print("tags:", [(t['id'][:8], t['name']) for t in tags[:5]])
# 试不同 type
for ty in ['user', 'app', 'conversation']:
    r = requests.post(f"{API}/tag-bindings/create", json={"tag_ids": tag_ids, "target_id": pid, "type": ty}, headers=h, timeout=20)
    print(f"bind type={ty}: [{r.status_code}] {r.text[:200]}")
# 验证：获取用户绑定标签
for ep in [f"/tag-bindings?target_id={pid}", f"/account_extend/favorite_tags", f"/user/tags", f"/tags/bindings?target_id={pid}"]:
    r = requests.get(f"{API}{ep}", headers=h, timeout=20)
    print(f"check {ep}: [{r.status_code}] {r.text[:200]}")
