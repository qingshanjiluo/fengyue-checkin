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

    # 探测性别相关元素
    info = page.evaluate("""() => {
        const out = {};
        out.aria_gender = [];
        document.querySelectorAll('[aria-label]').forEach(el => {
            const al = el.getAttribute('aria-label') || '';
            if (al.includes('性别') || al.includes('Gender') || al.includes('month') || al.includes('月份') || al.includes('月')) {
                out.aria_gender.push(el.tagName + '#' + (el.id||'') + ' | ' + al + ' | ' + el.className.slice(0,60));
            }
        });
        out.comboboxes = [];
        document.querySelectorAll('[role="combobox"]').forEach(el => out.comboboxes.push(el.outerHTML.slice(0,200)));
        out.listboxes = [];
        document.querySelectorAll('[role="listbox"]').forEach(el => out.listboxes.push(el.outerHTML.slice(0,120)));
        out.jsel = [];
        document.querySelectorAll('[jsname="wSASue"]').forEach(el => out.jsel.push(el.className.slice(0,80) + ' | id=' + (el.id||'') + ' | parent=' + (el.parentElement ? el.parentElement.className.slice(0,40) : '')));
        // 找包含 性别 文字的容器
        out.gender_text = [];
        document.querySelectorAll('div').forEach(el => {
            if (el.children.length === 0) return;
            const t = el.textContent.trim();
            if (t === '性别' || t === 'Gender') out.gender_text.push(el.outerHTML.slice(0,200));
        });
        return out;
    }""")
    for k, v in info.items():
        print(f"=== {k} ===")
        print(json.dumps(v, ensure_ascii=False, indent=1)[:1200])
    ctx.close()
    browser.close()