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

    # 探测性别菜单 UL 的父链和对应触发器
    info = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('ul[aria-label]').forEach(ul => {
            const label = ul.getAttribute('aria-label');
            if (label !== '性别' && label !== '月') return;
            const chain = [];
            let n = ul;
            for (let i = 0; i < 6 && n; i++) {
                chain.push(n.tagName + '#' + (n.id||'') + '.' + String(n.className).split(' ').slice(0,2).join('.'));
                n = n.parentElement;
            }
            // 同容器内的触发器
            let container = ul.closest('.O1htCb-H9tDt');
            let trigger = container ? container.querySelector('.VfPpkd-TkwUic') : null;
            out.push({
                label: label,
                chain: chain,
                hasContainer: !!container,
                trigger: trigger ? trigger.outerHTML.slice(0,160) : null,
                triggerParent: trigger ? trigger.parentElement.className.slice(0,60) : null
            });
        });
        return out;
    }""")
    print(json.dumps(info, ensure_ascii=False, indent=1))
    ctx.close()
    browser.close()