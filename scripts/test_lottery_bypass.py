import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
def hdr(jwt):
    return {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
            "authorization": f"Bearer {jwt}", "referer": "https://aiaha.xyz/zh/explore"}
API = "https://aiaha.xyz/console/api"

def login(email, password):
    h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
         "referer": "https://aiaha.xyz/zh/signin"}
    return requests.post(f"{API}/login", json={"email": email, "password": password}, headers=h, timeout=20).json()['data']

def get_profile(jwt):
    r = requests.get("https://aiaha.xyz/go/api/account/profile", headers=hdr(jwt), timeout=20)
    return r.json().get('data', {})

def draw(jwt, body=None, **kw):
    return requests.post(f"{API}/daily_lottery/draw", json=body or {}, headers=hdr(jwt), **kw, timeout=20)

# 1. 无邮箱新账号
jwt_nb = login("书卷林间", "rQ4kguM5")
prof = get_profile(jwt_nb)
print("新账号 profile: email=%r gender=%s is_new=%s sign_eligible=%s" % (prof.get('email'), prof.get('gender'), prof.get('is_new_user'), prof.get('is_sign_eligible')))
r = draw(jwt_nb)
print("新账号(无邮箱) draw:", r.json())

# 2. 已绑临时邮箱账号
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts_bound.txt', encoding='utf-8') if l.strip()]
jwt_tmp = lines[0][2]
r = draw(jwt_tmp)
print("临时邮箱账号 draw:", r.json())

# 3. 主账号(QQ白名单)
jwt_main = login("sifangzhiji@qq.com", "Pipi20100817")
prof = get_profile(jwt_main)
print("主账号 profile: email=%r gender=%s" % (prof.get('email'), prof.get('gender')))
for ep in ['/daily_lottery/status', '/daily_lottery/probability']:
    r = requests.get(f"{API}{ep}", headers=hdr(jwt_main), timeout=20)
    print(f"主账号 {ep}:", r.text[:200])
r = draw(jwt_main)
print("主账号 draw:", r.text[:300])

# 4. draw body 变体（临时邮箱账号）
for body in [{"email": "test@qq.com"}, {"email": "grv4hkv1mm@emalupe.com"}, {"type": "points"}, {"count": 1}]:
    r = draw(jwt_tmp, body)
    print(f"draw body={body}:", r.text[:150])