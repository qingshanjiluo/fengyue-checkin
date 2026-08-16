#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""春水(aimagnet.vip) + mail.tm 集成客户端"""
import random, string, time, re, requests

AB = "https://aimagnet.vip"
MT = "https://api.mail.tm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "Chrome/150.0.0.0 Safari/537.36")

def rand_pwd():
    """密码: 至少含1字母+1数字, 总长度>=8"""
    while True:
        s = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        if any(c.isdigit() for c in s) and any(c.isalpha() for c in s):
            return "Aa" + s + "!"

def rand_name(prefix="cn"):
    return prefix + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

class MailTM:
    """mail.tm 临时邮箱 (限速约 4个/20s/IP)"""
    def __init__(self, proxies=None):
        self.s = requests.Session()
        self.s.headers.update({"user-agent": UA})
        self.proxies = proxies or {}
        self.domain = self._first_domain()

    def _first_domain(self):
        for _ in range(3):
            try:
                d = self.s.get(f"{MT}/domains", proxies=self.proxies, timeout=25).json()
                m = d.get("hydra:member", [])
                if m:
                    return m[0]["domain"]
            except Exception:
                time.sleep(2)
        raise RuntimeError("mail.tm 域名获取失败")

    def create(self):
        """创建邮箱, 返回 (address, password), 处理429退避"""
        pwd = rand_pwd()
        for _ in range(8):
            address = f"aim{rand_name()[2:] + ''.join(random.choices(string.ascii_lowercase+string.digits, k=3))}@{self.domain}"
            try:
                r = self.s.post(f"{MT}/accounts", json={"address": address, "password": pwd},
                                proxies=self.proxies, timeout=25)
                if r.status_code == 201:
                    return address, pwd
                if r.status_code == 429:
                    retry = int(r.headers.get("Retry-After", 20))
                    time.sleep(retry)
                    continue
            except Exception:
                time.sleep(3)
        raise RuntimeError("mail.tm 建邮箱连续失败")

    def login(self, address, password):
        for _ in range(5):
            r = self.s.post(f"{MT}/token", json={"address": address, "password": password},
                            proxies=self.proxies, timeout=25)
            if r.status_code == 200:
                return r.json()["token"]
            time.sleep(3)
        raise RuntimeError("mail.tm 登录失败")

    def wait_code(self, address, password, timeout=90):
        """轮询取验证码 (6位数字), 返回验证码"""
        tok = self.login(address, password)
        h = {"authorization": f"Bearer {tok}"}
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                r = self.s.get(f"{MT}/messages", headers=h, proxies=self.proxies, timeout=25)
                msgs = r.json().get("hydra:member", [])
                if msgs:
                    mid = msgs[0]["id"]
                    full = self.s.get(f"{MT}/messages/{mid}", headers=h, proxies=self.proxies, timeout=25).json()
                    text = full.get("intro", "") + " " + full.get("text", "")
                    m = re.search(r"(\d{6})", re.sub(r"[\s\u200b\u200c\u200d\ufeff]", "", text))
                    if m:
                        return m.group(1)
            except Exception:
                pass
            time.sleep(5)
        return None

class Aimagnet:
    """春水 API 客户端"""
    def __init__(self, proxies=None):
        self.proxies = proxies or {}
        self.pwd = None
        self.s = requests.Session()
        self.s.headers.update({
            "user-agent": UA, "origin": AB, "referer": AB + "/",
            "content-type": "application/json", "accept": "application/json",
        })

    def _post(self, path, body=None, token=None, timeout=30):
        h = dict(self.s.headers)
        if token:
            h["authorization"] = f"Bearer {token}"
        return self.s.post(f"{AB}{path}", json=body or {}, headers=h, proxies=self.proxies, timeout=timeout)

    def _get(self, path, token=None, timeout=25):
        h = dict(self.s.headers)
        if token:
            h["authorization"] = f"Bearer {token}"
        return self.s.get(f"{AB}{path}", headers=h, proxies=self.proxies, timeout=timeout)

    def register_start(self, email):
        """触发验证码邮件, 返回 200 判定; 受限 20s/IP"""
        self.pwd = rand_pwd()
        body = {"email": email, "password": self.pwd, "nickname": rand_name(),
                "contentPreferences": ["male", "female", "all"], "contentPreferenceConfirmed": True}
        return self._post("/v1/auth/register/start", body)

    def register_complete(self, email, code):
        return self._post("/v1/auth/register/complete", {"email": email, "code": code})

    def login(self, email, password):
        for attempt in range(4):
            r = self._post("/v1/auth/login", {"identifier": email, "password": password})
            if r.status_code == 429:
                wait = 25 * (attempt + 1)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                raise RuntimeError(f"登录失败 {r.status_code}: {r.text[:150]}")
            j = r.json()
            return j["user"], j["tokens"]["accessToken"]
        raise RuntimeError("登录连续 429")

    def signin_status(self, token):
        return self._get("/v1/users/signin/status", token).json()

    def signin(self, token):
        return self._post("/v1/users/signin", token=token)

    def balance(self, user_id, token):
        return self._get(f"/v1/users/{user_id}/balance", token).json()