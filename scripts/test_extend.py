import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts_bound.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[0][0], lines[0][1], lines[0][2]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/settings"}

API = "https://aiaha.xyz/console/api"
tags = requests.get(f"{API}/tags", params={"type": "app"}, headers=h, timeout=20).json()
sel = [{"id": tags[0]['id'], "name": tags[0]['name'], "type": "app"}]
print("设置 favorite_tags:", sel)
# 尝试两种 body 结构
for body in [
    {"key": "favorite_tags", "value": sel},
    {"key": "favorite_tags", "value": [tags[0]['id']]},
]:
    r = requests.post(f"{API}/account/extend_set", json=body, headers=h, timeout=20)
    print(f"extend_set {json.dumps(body)[:80]}: [{r.status_code}] {r.text[:200]}")
# 验证 profile
r = requests.get(f"{API}/account/profile", headers=h, timeout=20)
ext = r.json().get('extend', {})
print("favorite_tags:", ext.get('favorite_tags'))
print("gender_preference:", ext.get('gender_preference'), "gender_options:", ext.get('gender_options'))
# 试 gender_preference
r = requests.post(f"{API}/account/extend_set", json={"key": "gender_preference", "value": 1}, headers=h, timeout=20)
print(f"gender_preference: [{r.status_code}] {r.text[:200]}")
r = requests.get(f"{API}/account/profile", headers=h, timeout=20)
print("gender_preference now:", r.json().get('extend', {}).get('gender_preference'))
