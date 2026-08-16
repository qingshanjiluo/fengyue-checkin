import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API = "https://aiaha.xyz/console/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
s = requests.Session()
s.headers.update({
    "user-agent": UA,
    "x-language": "zh-Hans",
    "x-timezone": "Asia/Shanghai",
    "accept": "application/json",
})

def api_headers(auth=None, referer=None):
    h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json"}
    if auth: h["authorization"] = f"Bearer {auth}"
    if referer: h["referer"] = referer
    return h

# 登录
resp = s.post(f"{API}/login", json={"email": "sifangzhiji@qq.com", "password": "Pipi20100817"}, headers=api_headers(), timeout=30)
d = resp.json()
print("login:", d.get("result"), d.get("msg", ""))
if d.get("result") != "success":
    sys.exit(1)
token = d["data"]
print("token:", token[:40], "...")

# 探查可能的账号信息端点
for ep in ["/user/profile", "/profile", "/account/profile", "/user/info", "/account/info", "/user", "/account",
           "/user/settings", "/account/settings", "/setting", "/settings", "/go/api/account/info"]:
    try:
        r = s.get(API + ep, headers=api_headers(auth=token), timeout=15)
        j = r.json() if r.headers.get('content-type','').startswith('application/json') else {'raw': r.text[:200]}
        print(f"--- GET {ep} [{r.status_code}] ---")
        print(json.dumps(j, ensure_ascii=False)[:600])
    except Exception as e:
        print(f"--- GET {ep} error: {str(e)[:60]}")