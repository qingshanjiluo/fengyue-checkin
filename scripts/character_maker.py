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

    def _scroll_to_text(self, text):
        self.page.evaluate("""
            ([t]) => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    if (el.innerText && el.innerText.includes(t) && el.tagName === 'P') {
                        el.scrollIntoView({block: 'center'}); return;
                    }
                }
            }
        """, [text])
        self.page.wait_for_timeout(500)

    def _js_fill_input(self, index, value):
        return self.page.evaluate("""
            ({idx, val}) => {
                const all = document.querySelectorAll('*');
                let d = null;
                for (const el of all) {
                    const slot = el.getAttribute('data-slot');
                    if ((slot === 'dialog-content' || el.getAttribute('role') === 'dialog') && el.offsetParent !== null) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100) { d = el; break; }
                    }
                }
                if (!d) return false;
                const inputs = d.querySelectorAll('input:not([type="file"]):not([type="hidden"])');
                if (inputs[idx]) {
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    s.call(inputs[idx], val);
                    inputs[idx].dispatchEvent(new Event('input', {bubbles: true}));
                    return true;
                }
                return false;
            }
        """, {"idx": index, "val": value})

    def _js_fill_textarea(self, index, value):
        return self.page.evaluate("""
            ({idx, val}) => {
                const all = document.querySelectorAll('*');
                let d = null;
                for (const el of all) {
                    const slot = el.getAttribute('data-slot');
                    if ((slot === 'dialog-content' || el.getAttribute('role') === 'dialog') && el.offsetParent !== null) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100) { d = el; break; }
                    }
                }
                if (!d) return false;
                const tas = d.querySelectorAll('textarea');
                if (tas[idx]) {
                    const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    s.call(tas[idx], val);
                    tas[idx].dispatchEvent(new Event('input', {bubbles: true}));
                    return true;
                }
                return false;
            }
        """, {"idx": index, "val": value})

    def _js_click_dialog_btn(self, btn_text):
        return self.page.evaluate("""
            ([text]) => {
                const all = document.querySelectorAll('*');
                let d = null;
                for (const el of all) {
                    const slot = el.getAttribute('data-slot');
                    if ((slot === 'dialog-content' || el.getAttribute('role') === 'dialog') && el.offsetParent !== null) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100) { d = el; break; }
                    }
                }
                if (!d) return false;
                const btns = d.querySelectorAll('button');
                for (const btn of btns) {
                    if ((btn.innerText || '').trim() === text && btn.offsetParent !== null) {
                        btn.click(); return true;
                    }
                }
                return false;
            }
        """, [btn_text])

    def step2_add_character(self, name="小风", occupation="", age="18", gender="女",
                            setting="", appearance="", personality="", tone="", background=""):
        """点击 + 卡片打开弹窗，填入角色信息"""
        p = self.page

        # 滚动到角色设定区
        self._scroll_to_text("角色设定")

        # 点击 + 卡片
        clicked = p.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const w = el.getBoundingClientRect().width;
                    const h = el.getBoundingClientRect().height;
                    if (Math.abs(w - 200) < 5 && Math.abs(h - 150) < 5 && el.offsetParent !== null) {
                        el.click(); return true;
                    }
                }
                return false;
            }
        """)
        if not clicked:
            print("[!] add character card not found")
            return False
        p.wait_for_timeout(1500)

        # 检查弹窗
        has_dialog = p.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const slot = el.getAttribute('data-slot');
                    if (slot === 'dialog-content' && el.offsetParent !== null) return true;
                }
                return false;
            }
        """)
        if not has_dialog:
            print("[!] dialog did not open")
            return False

        # 填字段 (都带 * 必填)
        # inputs: 姓名, 职业, 年龄, 性别
        self._js_fill_input(0, name or "小风")
        self._js_fill_input(1, occupation or "AI精灵")
        self._js_fill_input(2, age or "18")
        self._js_fill_input(3, gender or "女")

        # textareas: 人物设定, 外貌, 性格, 语气, 背景
        self._js_fill_textarea(0, setting or "来自数字世界的AI精灵，拥有治愈人心的力量")
        self._js_fill_textarea(1, appearance or "身高165cm，银色长发及腰，浅蓝色眼眸，身穿白色长袍")
        self._js_fill_textarea(2, personality or "温柔善良、耐心细致、乐观开朗")
        self._js_fill_textarea(3, tone or "语气温柔，说话轻声细语")
        self._js_fill_textarea(4, background or "诞生于数字世界的AI精灵，穿越到人类世界")

        # 点击确认
        ok = self._js_click_dialog_btn("确认")
        p.wait_for_timeout(2000)
        print(f"[OK] add character: {name}" if ok else "[!] confirm btn not found")
        return ok

    def step2_add_multiple_characters(self, characters):
        """批量添加多个角色，characters 是 dict 列表，每个包含:
        name, occupation, age, gender, setting, appearance, personality, tone, background
        """
        results = []
        for i, ch in enumerate(characters):
            print(f"\n[角色 {i+1}/{len(characters)}] 添加: {ch.get('name', '')}")
            ok = self.step2_add_character(
                name=ch.get("name", ""),
                occupation=ch.get("occupation", ""),
                age=ch.get("age", "18"),
                gender=ch.get("gender", "女"),
                setting=ch.get("setting", ""),
                appearance=ch.get("appearance", ""),
                personality=ch.get("personality", ""),
                tone=ch.get("tone", ""),
                background=ch.get("background", ""),
            )
            results.append(ok)
            if not ok:
                print(f"  [!] 角色 {i+1} 添加失败，停止继续添加")
                break
        ok_count = sum(1 for r in results if r)
        print(f"[OK] 共添加 {ok_count}/{len(characters)} 个角色")
        return ok_count

    def step2_fill_protagonist(self, name="", setting="", goal=""):
        """填主人公（玩家）设定"""
        p = self.page
        self._scroll_to_text("主人公（玩家）设定")

        # 主人公名称 (input, placeholder="玩家（您）扮演的角色")
        for sel, val in [
            ('input[placeholder*="玩家（您）扮演的角色"]', name or "玩家"),
            ('input[placeholder*="故事开展的世界"]', ""),
        ]:
            try:
                if val:
                    p.locator(sel).first.fill(val)
            except Exception:
                pass

        # 主人公设定 (textarea)
        if setting:
            try:
                p.locator("textarea").nth(1).fill(setting)
            except Exception:
                pass
        if goal:
            try:
                p.locator("textarea").nth(2).fill(goal)
            except Exception:
                pass

    def step3_set_greeting(self, greeting_text):
        """在Step 3设置开场白（问候语）：
        - greeting_text: 开场白文本，最多40字
        点击开场白区域的"添加"按钮，填入输入框后按回车确认。
        """
        p = self.page
        # 在开场白区域点击"添加"按钮
        clicked = p.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                let section = null;
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    if (el.tagName === 'P' && el.innerText.trim() === '开场白') {
                        // Get the outermost parent div with border
                        let parent = el.parentElement;
                        while (parent) {
                            const cls = parent.className || '';
                            if (typeof cls === 'string' && cls.includes('border') && cls.includes('rounded')) {
                                section = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        break;
                    }
                }
                if (!section) return false;
                const btns = section.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText.trim() === '添加' && btn.offsetParent !== null) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        if not clicked:
            print("[!] 开场白 添加 button not found")
            return False
        p.wait_for_timeout(1500)

        # 填输入框 - find the first empty input inside the greeting section
        filled = p.evaluate("""
            ([greeting]) => {
                const all = document.querySelectorAll('*');
                let section = null;
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    if (el.tagName === 'P' && el.innerText.trim() === '开场白') {
                        let parent = el.parentElement;
                        while (parent) {
                            const cls = parent.className || '';
                            if (typeof cls === 'string' && cls.includes('border') && cls.includes('rounded')) {
                                section = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        break;
                    }
                }
                if (!section) return false;
                const inputs = section.querySelectorAll('input');
                for (const inp of inputs) {
                    if (inp.offsetParent !== null && inp.value === '') {
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(inp, greeting);
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
                        return true;
                    }
                }
                return false;
            }
        """, [greeting_text])
        if filled:
            print(f"[OK] 开场白: {greeting_text[:30]}...")
        else:
            print("[!] 开场白 input not found")
        p.wait_for_timeout(500)
        return filled

    def step4_set_model(self, model_name):
        """在Step 4设置默认游玩模型：
        - model_name: 模型名称，如 "deepseek-v4-flash"
        """
        p = self.page
        # 点击 popover trigger
        clicked = p.evaluate("""
            () => {
                const trigger = document.querySelector('[data-slot="popover-trigger"]');
                if (trigger && trigger.offsetParent !== null) {
                    trigger.click();
                    return true;
                }
                return false;
            }
        """)
        if not clicked:
            print("[!] model selector trigger not found")
            return False
        p.wait_for_timeout(2000)

        # 在弹出框中找到目标模型并点击
        found = p.evaluate("""
            ([name]) => {
                const dialog = document.querySelector('[role="dialog"]');
                if (!dialog) return false;
                const all = dialog.querySelectorAll('*');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const t = (el.innerText || '').trim();
                    // Match exact model name (skip provider headers and info lines)
                    if (t === name && el.children.length <= 1 && el.tagName !== 'svg') {
                        el.click();
                        return true;
                    }
                }
                return false;
            }
        """, [model_name])
        if found:
            print(f"[OK] 模型已切换: {model_name}")
        else:
            print(f"[!] 模型未找到: {model_name}")
        p.wait_for_timeout(1000)
        return found

    def step4_add_tags(self, tags):
        """在Step 4添加标签：
        - tags: 标签字符串列表，如 ["可爱", "御姐", "古风"]
        """
        p = self.page
        for tag in tags:
            # 点击"添加标签"按钮
            clicked = p.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if (btn.offsetParent === null) continue;
                        if (btn.innerText.trim() === '添加标签') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if not clicked:
                print("[!] 添加标签 button not found")
                return False
            p.wait_for_timeout(1500)

            # 在弹窗的搜索框中输入标签名
            filled = p.evaluate("""
                ([tag]) => {
                    const all = document.querySelectorAll('input');
                    for (const inp of all) {
                        if (inp.offsetParent === null) continue;
                        const pl = inp.getAttribute('placeholder') || '';
                        if (pl.includes('搜索') || pl.includes('创建')) {
                            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            s.call(inp, tag);
                            inp.dispatchEvent(new Event('input', {bubbles: true}));
                            inp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
                            return true;
                        }
                    }
                    return false;
                }
            """, [tag])
            if not filled:
                # Try clicking the tag button directly
                tag_found = p.evaluate("""
                    ([tag]) => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            if (btn.offsetParent === null) continue;
                            const t = (btn.innerText || '').trim();
                            if (t.startsWith(tag) && t.length < 20) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """, [tag])
                if tag_found:
                    print(f"[OK] 标签已选择: {tag}")
                else:
                    print(f"[!] 标签未找到: {tag}")
            else:
                print(f"[OK] 标签已输入: {tag}")
                p.wait_for_timeout(1000)
                # Try to click the matching tag button that appears after typing
                tag_found = p.evaluate("""
                    ([tag]) => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            if (btn.offsetParent === null) continue;
                            const t = (btn.innerText || '').trim();
                            if (t.startsWith(tag) && t.length < 20) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """, [tag])
                if tag_found:
                    print(f"[OK] 标签已匹配: {tag}")

            # Click 保存
            p.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if (btn.offsetParent === null) continue;
                        if (btn.innerText.trim() === '保存' && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            p.wait_for_timeout(1000)
        return True

    def step3_add_cg(self, keywords, image_path):
        """在Step 3新增一条CG图片条目：
        - keywords: 触发关键词，多个用逗号分隔
        - image_path: 本地图片路径
        """
        p = self.page

        # 点击 新增
        try:
            new_btn = p.locator("button").filter(has_text="新增").first
            if not new_btn.is_visible():
                print("[!] 新增 button not found")
                return False
            new_btn.scroll_into_view_if_needed()
            p.wait_for_timeout(500)
            new_btn.click(force=True)
            p.wait_for_timeout(2000)
        except Exception as e:
            print(f"[!] 点击新增失败: {e}")
            return False

        # 填关键词 (tag-style input: type keyword, press Enter to add as tag)
        filled = p.evaluate("""
            ([kw]) => {
                const all = document.querySelectorAll('input');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const pl = el.getAttribute('placeholder') || '';
                    if (pl.includes('触发关键词') || pl.includes('填写触发关键词')) {
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(el, kw);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
                        return true;
                    }
                }
                return false;
            }
        """, [keywords])
        if not filled:
            print("[!] keyword input not found")
        else:
            print(f"[OK] keywords: {keywords}")
        p.wait_for_timeout(1000)

        # 上传图片
        if image_path and os.path.exists(image_path):
            try:
                file_input = p.locator('input[type="file"]').last
                if file_input.is_visible():
                    file_input.set_input_files(image_path)
                    p.wait_for_timeout(2000)
                    print(f"[OK] upload CG: {os.path.basename(image_path)}")
                    return True
            except Exception as e:
                print(f"[!] CG upload failed: {e}")
                return False
        else:
            print(f"[!] image not found: {image_path}")
            return False
        return True

    def step3_add_multiple_cg(self, cg_list):
        """批量添加CG图片，cg_list 是 dict 列表，每个包含:
        keywords: 触发关键词
        image: 图片路径
        """
        results = []
        for i, cg in enumerate(cg_list):
            kw = cg.get("keywords", "")
            img = cg.get("image", "")
            if not kw and not img:
                continue
            print(f"\n[CG {i+1}/{len(cg_list)}] {kw} -> {os.path.basename(img) if img else 'no image'}")
            ok = self.step3_add_cg(keywords=kw, image_path=img)
            results.append(ok)
        ok_count = sum(1 for r in results if r)
        print(f"[OK] 共添加 {ok_count}/{len(cg_list)} 条CG")
        return ok_count

    def step4_publish(self, anonymous=False):
        p = self.page
        p.wait_for_timeout(1000)

        # Try anonymous toggle if requested
        if anonymous:
            try:
                toggled = p.evaluate("""
                    () => {
                        const labels = document.querySelectorAll('label, span, div');
                        for (const el of labels) {
                            if ((el.innerText || '').includes('匿名') && el.offsetParent !== null) {
                                const chk = el.closest('label')?.querySelector('input[type="checkbox"]');
                                if (chk && !chk.checked) { chk.click(); return true; }
                                if (!chk) { el.click(); return true; }
                            }
                        }
                        return false;
                    }
                """)
                if toggled:
                    print("[OK] anonymous mode enabled")
                    p.wait_for_timeout(500)
            except:
                pass

        # 点击发布
        clicked = p.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText.trim() === '发布' && btn.offsetParent !== null) {
                        btn.click(); return true;
                    }
                }
                return false;
            }
        """)
        if not clicked:
            print("[!] 发布 button not found")
            return False
        print("[OK] clicked 发布")
        p.wait_for_timeout(2000)

        # 点击确认弹窗
        confirmed = p.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const t = (el.innerText || '').trim();
                    if (el.tagName === 'BUTTON' && (t === '确认' || t === '确定') && el.offsetParent !== null) {
                        el.click(); return true;
                    }
                }
                return false;
            }
        """)
        if confirmed:
            print("[OK] confirmed publish")
        else:
            print("[!] no confirm dialog")
        p.wait_for_timeout(3000)

        return True

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
    parser.add_argument("--name", default="", help="角色名称(作品名)")
    parser.add_argument("--summary", default="", help="简介")
    parser.add_argument("--detail", default="", help="详细介绍")
    parser.add_argument("--char-name", default="小风", help="角色卡中的角色名")
    parser.add_argument("--char-occupation", default="AI精灵", help="角色职业")
    parser.add_argument("--char-age", default="18", help="角色年龄")
    parser.add_argument("--char-gender", default="女", help="角色性别")
    parser.add_argument("--cover", default="", help="封面图路径")
    parser.add_argument("--chat-bg", default="", help="聊天背景图路径")
    parser.add_argument("--mobile-bg", default="", help="移动端背景图路径")
    parser.add_argument("--json", default="", help="从 JSON 文件读取完整配置")
    args = parser.parse_args()

    # 合并配置
    cfg = load_json(args.json) if args.json and os.path.exists(args.json) else {}
    for key in ["name", "summary", "detail", "char_name", "char_occupation",
                "char_age", "char_gender", "cover", "chat_bg", "mobile_bg"]:
        val = getattr(args, key.replace("chat_bg", "chat_bg").replace("mobile_bg", "mobile_bg"), "") or cfg.get(key, "")
        cfg[key] = val
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

        maker.step2_add_character(
            name=cfg.get("char_name", "小风"),
            occupation=cfg.get("char_occupation", "AI精灵"),
            age=cfg.get("char_age", "18"),
            gender=cfg.get("char_gender", "女"),
        )
        maker.screenshot("D:\\Temp\\opencode\\step2.png")
        maker.next_step()

        # step3: CG图片由AI自动添加，命令行模式跳过
        maker.screenshot("D:\\Temp\\opencode\\step3.png")
        maker.next_step()

        maker.step4_publish()
        maker.screenshot("D:\\Temp\\opencode\\done.png")

        print("\n[完成] 角色卡制作完成!")

    finally:
        maker.close()


if __name__ == "__main__":
    main()
