"""调试脚本：测试性别下拉打开方式"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

def click_next(page):
    btn = page.query_selector("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf")
    if btn:
        btn.click(force=True, timeout=10000)
    page.wait_for_timeout(3000)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, proxy={"server": "http://127.0.0.1:7890"})
    context = browser.new_context()
    page = context.new_page()

    page.goto('https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp', timeout=60000)
    page.wait_for_timeout(3000)
    page.fill("input[name='firstName']", "Test")
    page.fill("input[name='lastName']", "User")
    click_next(page)

    page.fill("input[name='year']", "1990")
    page.fill("input[name='day']", "15")
    page.click("#month", timeout=10000)
    page.wait_for_timeout(800)
    page.click("li[data-value='5']", timeout=10000)
    page.wait_for_timeout(500)
    print("月份已选")

    # 方式1：force 点击 input
    print("\n=== 尝试 force 点击性别 input ===")
    try:
        page.click("input[aria-label*='性别']", force=True, timeout=10000)
        print("force click 完成")
        page.wait_for_timeout(1200)
        opts = page.query_selector_all("li[role='option']")
        print(f"下拉选项数: {len(opts)}")
        for o in opts:
            print(f"  data-value={o.get_attribute('data-value')} text={o.inner_text().strip()[:20]}")
        # 选第一个选项
        if opts:
            opts[0].click()
            page.wait_for_timeout(500)
            print("已选择第一个选项")
    except Exception as e:
        print("force 点击失败:", e)

    page.screenshot(path=r'G:\皮皮\编程项目\fengyue\debug_gender.png')

    # 方式2：点击 input 的父容器
    print("\n=== 尝试点击父容器 ===")
    try:
        parent = page.evaluate("""() => {
            const el = document.querySelector("input[aria-label*='性别']");
            return el ? el.parentElement.outerHTML.slice(0, 300) : 'not found';
        }""")
        print("父元素:", parent)
        page.click("div.Xb9hP", timeout=5000)
        page.wait_for_timeout(1200)
        opts = page.query_selector_all("li[role='option']")
        print(f"下拉选项数: {len(opts)}")
        for o in opts:
            print(f"  data-value={o.get_attribute('data-value')} text={o.inner_text().strip()[:20]}")
    except Exception as e:
        print("父容器点击失败:", e)

    browser.close()