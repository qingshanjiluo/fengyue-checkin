import sys, io, time, json
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

    # 探测月份和性别的 DOM 结构
    info = page.evaluate("""() => {
        const out = {};
        const q = (sel) => { const el = document.querySelector(sel); return el ? el.outerHTML.slice(0, 300) : null; };
        out.month = q('#month');
        out.month_select = q('select#month');
        out.gender = q('select#gender');
        out.gender_div = q('div.aXBtI.Wic03c');
        out.month_inputs = [];
        document.querySelectorAll('input[name="month"]').forEach(el => out.month_inputs.push(el.outerHTML.slice(0,150)));
        out.all_selects = [];
        document.querySelectorAll('select').forEach(el => out.all_selects.push(el.id + '=' + el.outerHTML.slice(0,120)));
        out.options = [];
        document.querySelectorAll('li[role="option"]').forEach(el => out.options.push(el.getAttribute('data-value') + ':' + el.textContent.trim()));
        return out;
    }""")
    for k, v in info.items():
        print(f"--- {k} ---")
        print(json.dumps(v, ensure_ascii=False, indent=1)[:800])
    page.screenshot(path=r'G:\皮皮\编程项目\fengyue\debug_birthday.png')
    ctx.close()
    browser.close()