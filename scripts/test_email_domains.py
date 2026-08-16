import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API = "https://aiaha.xyz/console/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
s = requests.Session()
s.headers.update({"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json"})

def login():
    r = s.post(f"{API}/login", json={"email": "sifangzhiji@qq.com", "password": "Pipi20100817"}, headers={"user-agent": UA}, timeout=30)
    d = r.json()
    if d.get("result") != "success":
        print("login fail:", d)
        sys.exit(1)
    return d["data"]

token = login()
print("登录成功")

# 测试各种邮箱域名的验证码发送
domains = [
    # 主流
    "gmail.com", "qq.com", "163.com", "126.com", "outlook.com", "hotmail.com", "foxmail.com",
    "aliyun.com", "sina.com", "139.com", "sohu.com", "yeah.net", "icloud.com", "proton.me", "yandex.com",
    # 临时/一次性
    "mail.tm", "guerrillamail.com", "guerrillamail.info", "10minutemail.com", "temp-mail.org",
    "tempmail.com", "mailinator.com", "sharklasers.com", "yopmail.com", "maildrop.cc",
    "trashmail.com", "dispostable.com", "getnada.com", "1secmail.com", "emailnator.com",
    "mailnesia.com", "mohmal.com", "moakt.com", "crazymailing.com", "inboxkitten.com",
    # 其它批量友好
    "cock.li", "tutanota.com", "disroot.org", "mail.com", "gmx.com", "zoho.com", "outlook.de",
]

h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "authorization": f"Bearer {token}", "referer": "https://aiaha.xyz/zh/settings"}

GO = "https://aiaha.xyz/go/api"
accepted = []
rejected = []

for d in domains:
    email = f"testbinding.{d.split('.')[0]}@{d}"
    try:
        r = s.post(f"{GO}/account/email/code", json={"email": email}, headers=h, timeout=20)
        j = r.json()
        code = j.get("code")
        msg = j.get("msg") or j.get("message") or json.dumps(j, ensure_ascii=False)[:80]
        if code == 100000:
            print(f"OK    {email}")
            accepted.append(d)
        else:
            print(f"拒绝  {email} -> code={code} msg={msg[:80]}")
            rejected.append((d, msg[:60]))
    except Exception as e:
        print(f"错误  {email} -> {str(e)[:50]}")
    import time; time.sleep(0.8)

print("\n=== 总结 ===")
print("接受:", ", ".join(accepted))
print("拒绝:", ", ".join(f"{d}({m})" for d, m in rejected))