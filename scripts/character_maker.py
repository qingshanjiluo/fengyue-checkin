# -*- coding: utf-8 -*-
"""
风月AI 角色卡制作工具
基于 Playwright 的浏览器自动化脚本，操控 Chrome 创建角色卡

用法：
  # 命令行参数
  python scripts/character_maker.py --email 账号 --password 密码 --name "角色名"

  # 从 JSON 配置
  python scripts/character_maker.py --email 账号 --password 密码 --json card.json

  # 首次运行需要安装 Playwright 浏览器：
  pip install playwright && python -m playwright install chromium
"""

import os, sys, json, argparse
sys.stdout.reconfigure(encoding="utf-8")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("请先安装 playwright: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

BASE_URL = "https://aiaha.xyz"


class CharacterMaker:
    def __init__(self, email, password, headless=False, slow_mo=300):
        self.email = email
        self.password = password
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.page = None

    def start(self):
        p = sync_playwright().start()
        self.browser = p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900},
                                       locale="zh-CN", timezone_id="Asia/Shanghai")
        self.page = ctx.new_page()
        return self

    def close(self):
        if self.browser:
            self.browser.close()

    def login(self):
        p = self.page
        p.goto(f"{BASE_URL}/zh/signin")
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1000)
        p.locator('input[type="email"], input[name="email"]').first.fill(self.email)
        p.locator('input[type="password"]').first.fill(self.password)
        # 按回车提交
        p.keyboard.press("Enter")
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(2000)
        print(f"[OK] login: {p.url}")

    def create_simple(self):
        p = self.page
        p.goto(f"{BASE_URL}/zh/apps")
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(2000)
        p.locator("text=简易创作").first.click()
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(3000)
        print(f"[OK] create: {p.url}")

    def _click(self, selector):
        p = self.page
        try:
            loc = p.locator(selector).first
            if loc.is_visible():
                loc.scroll_into_view_if_needed()
                p.wait_for_timeout(300)
                loc.click(force=True)
                return True
        except Exception:
            pass
        return False

    def step1_basic(self, name="", summary="", detail="", gender="男性向",
                    language="简体中文", cover_path=None, bg_path=None, mobile_bg_path=None):
        p = self.page

        # 上传图片
        for idx, path in enumerate([cover_path, bg_path, mobile_bg_path]):
            if path and os.path.exists(path):
                p.locator('input[type="file"]').nth(idx).set_input_files(path)
                p.wait_for_timeout(1500)
                print(f"[OK] upload img {idx+1}: {os.path.basename(path)}")

        # 语言
        if language:
            try:
                lang_btn = p.locator('button:has-text("请选择作品的语言")')
                if lang_btn.is_visible():
                    lang_btn.click()
                    p.wait_for_timeout(500)
                    opt = p.locator(f"text={language}").first
                    if opt.is_visible():
                        opt.click(force=True)
                        p.wait_for_timeout(300)
                        print(f"[OK] lang: {language}")
            except Exception:
                pass

        # 名称
        if name:
            try:
                inp = p.locator('input[placeholder*="给你的作品起个名字"]').first
                inp.fill(name)
                print(f"[OK] name: {name}")
            except Exception:
                pass

        # 简介 & 详细介绍
        for idx, val in enumerate([summary, detail]):
            if val:
                try:
                    p.locator("textarea").nth(idx).fill(val)
                    print(f"[OK] textarea {idx+1}")
                except Exception:
                    pass

    def next_step(self):
        p = self.page
        try:
            p.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            p.wait_for_timeout(500)
            p.locator("button:has-text('下一步')").first.click(force=True, timeout=10000)
            p.wait_for_timeout(3000)
            p.wait_for_load_state("networkidle")
            print(f"[OK] next step: {p.url[:80]}")
        except Exception as e:
            print(f"[!] next step failed: {e}")
            raise

    def step2_character(self, prompt="", greeting=""):
        p = self.page
        if prompt:
            try:
                editors = p.locator('[contenteditable="true"]')
                if editors.count() > 0:
                    editors.first.fill(prompt)
                    print(f"[OK] prompt ({len(prompt)} chars)")
            except Exception:
                try:
                    p.locator("textarea").first.fill(prompt)
                    print(f"[OK] prompt via textarea")
                except Exception:
                    print("[!] prompt field not found")

        if greeting:
            try:
                editors = p.locator('[contenteditable="true"]')
                if editors.count() > 1:
                    editors.nth(1).fill(greeting)
                    print(f"[OK] greeting")
            except Exception:
                pass

    def step3_additional(self):
        p = self.page
        p.wait_for_timeout(1000)

    def step4_publish(self):
        p = self.page
        p.wait_for_timeout(1000)
        try:
            p.locator("button:has-text('发布')").first.click(force=True, timeout=10000)
            p.wait_for_timeout(3000)
            p.wait_for_load_state("networkidle")
            print(f"[OK] published: {p.url}")
        except Exception:
            try:
                p.locator("button:has-text('保存')").first.click(force=True, timeout=10000)
                p.wait_for_timeout(2000)
                print(f"[OK] saved")
            except Exception as e:
                print(f"[!] save failed: {e}")

    def screenshot(self, path):
        self.page.screenshot(path=path)
        print(f"[SCREENSHOT] {path}")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="风月AI 角色卡制作工具")
    parser.add_argument("--email", help="登录邮箱")
    parser.add_argument("--password", help="登录密码")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--slow", type=int, default=300, help="操作延迟(ms)")
    parser.add_argument("--name", default="", help="角色名称")
    parser.add_argument("--summary", default="", help="简介")
    parser.add_argument("--detail", default="", help="详细介绍")
    parser.add_argument("--prompt", default="", help="角色设定(人格prompt)")
    parser.add_argument("--greeting", default="", help="开场白")
    parser.add_argument("--cover", default="", help="封面图路径")
    parser.add_argument("--chat-bg", default="", help="聊天背景图路径")
    parser.add_argument("--mobile-bg", default="", help="移动端背景图路径")
    parser.add_argument("--json", default="", help="从 JSON 文件读取完整配置")
    args = parser.parse_args()

    # 合并配置
    cfg = load_json(args.json) if args.json and os.path.exists(args.json) else {}
    for key in ["name", "summary", "detail", "prompt", "greeting",
                "cover", "chat_bg", "mobile_bg"]:
        val = getattr(args, key.replace("chat_bg", "chat_bg").replace("mobile_bg", "mobile_bg"), "") or cfg.get(key, "")
        cfg[key] = val
    # map args with hyphens to config keys
    cfg["chat_bg"] = cfg.get("chat_bg") or args.chat_bg
    cfg["mobile_bg"] = cfg.get("mobile_bg") or args.mobile_bg

    email = args.email or os.environ.get("FENGYUE_EMAIL") or cfg.get("email")
    password = args.password or os.environ.get("FENGYUE_PASSWORD") or cfg.get("password")
    if not email or not password:
        print("错误: 需要提供 --email 和 --password, 或设置 FENGYUE_EMAIL/FENGYUE_PASSWORD 环境变量")
        sys.exit(1)

    maker = CharacterMaker(email, password, args.headless, args.slow)
    try:
        maker.start()
        maker.login()
        maker.create_simple()
        maker.step1_basic(
            name=cfg.get("name", ""),
            summary=cfg.get("summary", ""),
            detail=cfg.get("detail", ""),
            cover_path=cfg.get("cover"),
            bg_path=cfg.get("chat_bg"),
            mobile_bg_path=cfg.get("mobile_bg"),
        )
        maker.screenshot("D:\\Temp\\opencode\\step1.png")
        maker.next_step()

        maker.step2_character(
            prompt=cfg.get("prompt", ""),
            greeting=cfg.get("greeting", ""),
        )
        maker.screenshot("D:\\Temp\\opencode\\step2.png")
        maker.next_step()

        maker.step3_additional()
        maker.screenshot("D:\\Temp\\opencode\\step3.png")
        maker.next_step()

        maker.step4_publish()
        maker.screenshot("D:\\Temp\\opencode\\done.png")

        print("\n[完成] 角色卡制作完成!")

    finally:
        maker.close()


if __name__ == "__main__":
    main()
