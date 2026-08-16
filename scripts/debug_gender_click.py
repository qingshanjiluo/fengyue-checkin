import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, proxy={"server": "http://127.0.0.1:7890"})
    ctx = browser.new_context(locale='zh-CN')
    page = ctx.new_page()
    page.goto('https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp', timeout=60000)
    page.wait_for_timeout(3000)
    page.fill("input[name='firstName']", "Test")
    page.fill("input[name='lastName']", "User")
    page.locator("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf").first.click(force=True)
    page.wait_for_selector("input[name='year']", state='attached', timeout=15000)
    page.wait_for_timeout(1500)

    # 方法A：点击性别隐藏输入
    clicked = page.evaluate("""() => {
        const el = document.querySelector("input[aria-label='您的性别是什么？']");
        if (el) { el.click(); return true; }
        return false;
    }""")
    print("点性别输入:", clicked)
    page.wait_for_timeout(1500)

    # 检查下拉是否打开（li 是否可见）
    state = page.evaluate("""() => {
        const els = document.querySelectorAll("li[role='option']");
        const res = [];
        for (const el of els) {
            if (el.getAttribute('data-value') === '1') {
                const r = el.getBoundingClientRect();
                res.push({text: el.textContent.trim(), w: r.width, h: r.height, disp: getComputedStyle(el).display, vis: getComputedStyle(el).visibility});
            }
        }
        return res;
    }""")
    print("data-value=1 状态:", json.dumps(state, ensure_ascii=False))

    # 点击 男
    res = page.evaluate("""() => {
        const els = document.querySelectorAll("li[role='option']");
        for (const el of els) {
            if (el.getAttribute('data-value') === '1' && el.textContent.trim() === '男') {
                el.click();
                return true;
            }
        }
        return false;
    }""")
    print("点男:", res)
    page.wait_for_timeout(1000)
    val = page.evaluate("() => { const el = document.querySelector(\"input[aria-label='您的性别是什么？']\"); return el ? el.value : null; }")
    print("性别输入值:", val)
    page.screenshot(path=r'G:\皮皮\编程项目\fengyue\debug_gender_after.png')
    ctx.close()
    browser.close()