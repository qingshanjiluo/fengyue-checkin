import sys, io, json, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, proxy={"server": "http://127.0.0.1:7890"})
    ctx = browser.new_context(locale='zh-CN')
    page = ctx.new_page()
    page.goto('https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp', timeout=60000)
    page.wait_for_timeout(3000)
    page.fill("input[name='firstName']", "Debug")
    page.fill("input[name='lastName']", "Account")
    page.locator("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf").first.click(force=True)
    page.wait_for_selector("input[name='year']", state='attached', timeout=15000)
    page.wait_for_timeout(1200)

    page.fill("input[name='year']", "1990")
    page.fill("input[name='day']", "15")
    page.evaluate("() => { const el = document.querySelector('#month .VfPpkd-TkwUic'); if (el) { el.click(); return true; } return false; }")
    page.wait_for_timeout(1000)
    page.evaluate("() => { const els = document.querySelectorAll(\"#month li[role='option']\"); for (const el of els) { if (el.getAttribute('data-value') === '5') { el.click(); return true; } } return false; }")
    page.wait_for_timeout(800)
    page.evaluate("() => { const el = document.querySelector('#gender .VfPpkd-TkwUic'); if (el) { el.click(); return true; } return false; }")
    page.wait_for_timeout(1200)
    page.evaluate("() => { const els = document.querySelectorAll(\"#gender li[role='option']\"); for (const el of els) { if (el.getAttribute('data-value') === '1') { el.click(); return true; } } return false; }")
    page.wait_for_timeout(500)
    page.locator("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf").first.click(force=True)

    # 用户名
    page.wait_for_selector("input[name='Username']", state='attached', timeout=15000)
    page.evaluate("() => { const el = document.querySelector(\"[jsname='CeL6Qc']\"); if (el) { el.click(); return true; } return false; }")
    page.wait_for_timeout(1000)
    uname = 'debugacct' + str(random.randint(10000,99999))
    page.evaluate("""(sel, val) => { const el = document.querySelector(sel); if (el) { el.focus(); el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); return true; } return false; }""", "input[name='Username']", uname)
    page.keyboard.type(uname)
    page.wait_for_timeout(800)
    page.locator("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf").first.click(force=True)
    page.wait_for_selector("input[name='Passwd']", state='attached', timeout=15000)
    page.evaluate("() => { const el = document.querySelector('input[name=Passwd]'); if (el) { el.focus(); el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); return true; } return false; }")
    page.keyboard.type("TestPass12345")
    page.wait_for_timeout(500)
    page.evaluate("() => { const el = document.querySelector('input[name=PasswdAgain]'); if (el) { el.focus(); el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); return true; } return false; }")
    page.keyboard.type("TestPass12345")
    page.wait_for_timeout(500)
    page.locator("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf").first.click(force=True)

    # 等待验证页出现（最多 40s）
    page.wait_for_timeout(5000)
    print("当前 URL:", page.url)
    page.screenshot(path=r'G:\皮皮\编程项目\fengyue\debug_verify.png')

    # 探测页面元素
    info = page.evaluate("""() => {
        const out = {};
        out.headings = [];
        document.querySelectorAll('h1, h2, h3').forEach(el => out.headings.push(el.textContent.trim().slice(0,80)));
        out.inputs = [];
        document.querySelectorAll('input').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 || r.height > 0) out.inputs.push({name: el.name, type: el.type, label: el.getAttribute('aria-label'), cls: el.className.slice(0,40)});
        });
        out.buttons = [];
        document.querySelectorAll('button, [role="button"], a').forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length < 30) {
                const r = el.getBoundingClientRect();
                if (r.width > 0) out.buttons.push(t.slice(0,30));
            }
        });
        out.qr = document.querySelectorAll('img, canvas').length;
        return out;
    }""")
    print(json.dumps(info, ensure_ascii=False, indent=1))
    ctx.close()
    browser.close()