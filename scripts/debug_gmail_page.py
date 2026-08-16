"""调试脚本 v6：完整流程测试 - 生日/性别 -> 用户名 -> 密码"""
import sys, io, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

def click_next(page):
    btn = page.query_selector("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf")
    if btn:
        btn.click(force=True, timeout=10000)
    else:
        page.locator("button").last.click(force=True, timeout=10000)
    page.wait_for_timeout(3000)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, proxy={"server": "http://127.0.0.1:7890"})
    context = browser.new_context()
    page = context.new_page()

    page.goto('https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp', timeout=60000)
    page.wait_for_timeout(4000)

    # 第1步：姓名
    page.fill("input[name='firstName']", "Test")
    page.fill("input[name='lastName']", "User")
    page.wait_for_timeout(500)
    click_next(page)
    print("Step1 完成, URL:", page.url)

    # 第2步：生日性别
    page.fill("input[name='year']", "1990")
    page.fill("input[name='day']", "15")

    # 月份下拉
    page.click("#month", timeout=10000)
    page.wait_for_timeout(1000)
    print("月份下拉已打开，选项:")
    opts = page.query_selector_all("[jsname='K4r5Ff']")
    for o in opts[:5]:
        print("  ", o.inner_text().strip())
    # 选 3 月
    page.click("li[data-value='3']", timeout=10000)
    page.wait_for_timeout(800)
    print("已选择 3 月")

    # 性别下拉
    try:
        page.click("input[aria-label*='性别']", timeout=10000)
        page.wait_for_timeout(1000)
        print("\n性别下拉已打开，选项:")
        gender_opts = page.query_selector_all("[jsname='K4r5Ff'], [role='option'], .VfPpkd-rymPhb-fpDzbe-fmcmS")
        for o in gender_opts[:10]:
            txt = o.inner_text().strip()
            if txt:
                print("  ", txt)
        # 选择 男
        try:
            page.click("li[role='option']:has-text('男')", timeout=5000)
            print("已选择 男 (role=option)")
        except Exception as e:
            print("性别选择失败:", e)
        page.wait_for_timeout(800)
    except Exception as e:
        print("性别下拉操作失败:", e)
    click_next(page)

    # 第3步：用户名
    print("\n当前 input:")
    for el in page.query_selector_all("input"):
        print(f"  name={el.get_attribute('name')} aria={el.get_attribute('aria-label')}")

    user = f"test.user{random.randint(10000,99999)}"
    try:
        u = page.query_selector("input[name='Username']")
        if u:
            u.fill(user)
            print(f"用户名已填: {user}")
    except Exception as e:
        print("用户名填写失败:", e)

    click_next(page)
    print("\nStep3 完成, URL:", page.url)

    page.screenshot(path=r'G:\皮皮\编程项目\fengyue\debug_after_username.png')
    browser.close()