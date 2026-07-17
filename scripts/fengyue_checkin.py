import os, sys, json, requests
from datetime import datetime, timezone, timedelta

API = "https://aiaha.xyz"
TZ = timezone(timedelta(hours=8))
s = requests.Session()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"


def log(msg):
    print(f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def api_headers(referer=None, auth=None):
    h = {
        "user-agent": UA,
        "x-language": "zh-Hans",
        "x-timezone": "Asia/Shanghai",
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
    }
    if auth:
        h["authorization"] = f"Bearer {auth}"
    if referer:
        h["referer"] = referer
    return h


def login(email, password):
    log("logging in...")
    resp = s.post(
        f"{API}/console/api/login",
        json={"email": email, "password": password},
        headers=api_headers(referer="https://aiaha.xyz/zh/signin"),
        timeout=30,
    )
    data = resp.json()
    if data.get("result") != "success":
        log(f"login failed: {json.dumps(data, ensure_ascii=False)}")
        sys.exit(1)
    token = data["data"]
    log(f"login ok, token: {token[:50]}...")
    return token


def check_today_signed(token):
    today = datetime.now(TZ).strftime("%Y-%m")
    resp = s.get(
        f"{API}/console/api/monthly_calendar",
        params={"date": today},
        headers=api_headers(referer="https://aiaha.xyz/zh/signin", auth=token),
        timeout=30,
    )
    data = resp.json()
    if data.get("code") != 200:
        log(f"get calendar failed: {json.dumps(data, ensure_ascii=False)}")
        return False
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    for day in data.get("data", {}).get("calendar", []):
        if day["date"] == today_str:
            return day["signed"]
    return False


def sign_in(token):
    resp = s.get(
        f"{API}/console/api/sign_in",
        headers=api_headers(referer="https://aiaha.xyz/zh/signin", auth=token),
        timeout=30,
    )
    data = resp.json()
    if data.get("code") == 200:
        reward = data.get("data", {}).get("reward", 0)
        log(f"sign in success! reward: {reward} point")
        return True, reward
    if data.get("msg") == "今日已签到，请勿重复签到":
        log("already signed in today")
        return True, 0
    log(f"sign in failed: {json.dumps(data, ensure_ascii=False)}")
    return False, None


def get_points(token):
    resp = s.get(
        f"{API}/go/api/account/point",
        headers=api_headers(referer="https://aiaha.xyz/zh/signin", auth=token),
        timeout=30,
    )
    data = resp.json()
    if data.get("code") == 100000:
        return data.get("data", {}).get("points", "?")
    return "?"


def main():
    email = os.environ.get("FENGYUE_EMAIL", "")
    password = os.environ.get("FENGYUE_PASSWORD", "")

    if not email or not password:
        log("error: FENGYUE_EMAIL and FENGYUE_PASSWORD must be set")
        sys.exit(1)

    try:
        token = login(email, password)
    except Exception as e:
        log(f"login exception: {e}")
        sys.exit(1)

    already = check_today_signed(token)
    if already:
        pts = get_points(token)
        log(f"already signed in today, current points: {pts}")
        print(f"result=signed_ok points={pts}")
        return

    ok, reward = sign_in(token)
    if ok:
        pts = get_points(token)
        log(f"sign in done, current points: {pts}")
        print(f"result=ok reward={reward} points={pts}")
    else:
        log("sign in failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
