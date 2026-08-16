import io, sys, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines = [l.split() for l in open(r'G:\皮皮\编程项目\fengyue\accounts.txt', encoding='utf-8') if l.strip()]
name, pwd, jwt = lines[0][0], lines[0][1], lines[0][2]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
h = {"user-agent": UA, "x-language": "zh-Hans", "x-timezone": "Asia/Shanghai", "accept": "application/json",
     "referer": "https://aiaha.xyz/zh/signin"}
API = "https://aiaha.xyz/console/api"
for body in [
    {"email": name, "password": pwd},
    {"name": name, "password": pwd},
    {"account": name, "password": pwd},
]:
    try:
        r = requests.post(f"{API}/login", json=body, headers=h, timeout=20)
        print(f"login {json.dumps(body, ensure_ascii=False)[:50]}: [{r.status_code}] {r.text[:150]}")
    except Exception as e:
        print(f"login {body}: ERR {str(e)[:60]}")
