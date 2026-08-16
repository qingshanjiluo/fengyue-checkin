"""
Gmail 批量创建工具 v2（Playwright + Clash 自动切节点 + 指纹伪装）
- 每次创建前通过 Clash API (127.0.0.1:9090) 随机切换住宅节点并验证出口 IP
- 全新浏览器指纹（随机 UA/视口/时区/语言）+ stealth 反检测
- 会话预热 + 人形输入
- 验证步：手机号字段出现→尝试跳过；二维码出现→换节点重试
- 保存格式：gmail_accounts.txt (邮箱 密码)
用法：python gmail_creator.py <数量> [只住宅节点 1/0]
"""
import sys, io, time, random, string, csv, os, json, urllib.request, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

OUTPUT_FILE = r'G:\皮皮\编程项目\fengyue\gmail_accounts.txt'
DATA_DIR = r'D:\Temp\opencode\gmail-creator\data'
CLASH_API = "http://127.0.0.1:9090"
PROXY = "http://127.0.0.1:7890"
MAX_ACCOUNT_RETRY = 6
RESIDENTIAL_ONLY = True

# ---------- Clash 节点管理 ----------
def clash_get(path):
    req = urllib.request.Request(CLASH_API + path)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))

def clash_put(path, data):
    req = urllib.request.Request(CLASH_API + path, data=json.dumps(data).encode(),
                                 method='PUT', headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()

def list_nodes():
    """返回 (节点名列表, 当前节点)"""
    j = clash_get('/proxies')
    g = j['proxies'].get('GLOBAL', {})
    nodes = g.get('all', [])
    current = g.get('now', '')
    return nodes, current

def switch_node(node_name):
    """切换 GLOBAL 代理组到指定节点"""
    clash_put('/proxies/GLOBAL', {'name': node_name})
    time.sleep(2)

def get_exit_ip():
    """通过代理获取出口 IP 和城市"""
    try:
        req = urllib.request.Request('https://ipinfo.io/json')
        req.set_proxy('127.0.0.1:7890', 'http')
        req.set_proxy('127.0.0.1:7890', 'https')
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode('utf-8'))
            return j.get('ip', '?'), j.get('country', '?'), j.get('city', '?')
    except Exception:
        return '?', '?', '?'

def rotate_node(used_ips):
    """切换到未用过的节点，返回节点名；失败返回 None"""
    nodes, current = list_nodes()
    candidates = []
    for n in nodes:
        if n in ('DIRECT', 'REJECT', 'PASS', 'COMPATIBLE'):
            continue
        if 'GLOBAL' in n or '自动选择' in n or '故障转移' in n:
            continue
        if '流量' in n or '到期' in n or '重置' in n or '套餐' in n:
            continue
        if RESIDENTIAL_ONLY and not any(k in n for k in ('住宅', '专线')):
            continue
        candidates.append(n)
    random.shuffle(candidates)
    for node in candidates:
        switch_node(node)
        ip, cc, city = get_exit_ip()
        if ip == '?' or ip in used_ips:
            continue
        return node, ip, cc, city
    return None

# ---------- 生成器 ----------
def generate_password(length=11):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def human_type(page, value, delay_range=(40, 160)):
    """人形输入：逐字符随机延迟（毫秒）"""
    for ch in value:
        page.keyboard.type(ch)
        page.wait_for_timeout(random.randint(*delay_range))

def click_next(page):
    for _ in range(3):
        btn = page.query_selector("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf")
        if btn:
            btn.click(force=True, timeout=10000)
            return True
        page.wait_for_timeout(1500)
    page.locator("button").last.click(force=True, timeout=10000)
    return True

def js_fill(page, selector, value):
    page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        el.focus();
        el.value = '';
        el.dispatchEvent(new Event('input', {bubbles: true}));
        return true;
    }""", selector)
    page.wait_for_timeout(400)
    human_type(page, value)
    return True

def warmup_session(page):
    """会话预热：先访问 Google，模拟真人"""
    for url in ('https://www.google.com',):
        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(random.randint(2000, 4000))
        except Exception:
            pass

def random_context(browser):
    """创建带随机指纹的全新上下文"""
    uas = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    ]
    locales = ['en-US', 'en-GB', 'en-AU', 'en-CA']
    tzones = ['America/New_York', 'Europe/London', 'Asia/Tokyo', 'Asia/Singapore', 'America/Los_Angeles']
    ctx = browser.new_context(
        user_agent=random.choice(uas),
        locale=random.choice(locales),
        timezone_id=random.choice(tzones),
        viewport={'width': random.choice([1280, 1366, 1440, 1536, 1920]),
                  'height': random.choice([720, 768, 800, 900])},
        color_scheme='light',
        screen={'width': 1920, 'height': 1080},
        extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'},
    )
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    return ctx, page

# ---------- 注册流程 ----------
def create_one_account(page, first_name, last_name, password, birthday):
    """返回 ('OK', email) / ('NEED_PHONE', None) / ('NEED_QR', None) / None"""
    user_name = f"{first_name.lower()}.{last_name.lower()}{random.randint(1000,99999)}"

    for gtry in range(3):
        try:
            page.goto('https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp', timeout=60000)
            break
        except Exception as e:
            print(f"  页面加载失败(第{gtry+1}次): {str(e)[:60]}")
            page.wait_for_timeout(3000)
    page.wait_for_timeout(3000)

    for attempt in range(MAX_ACCOUNT_RETRY):
        try:
            # 第一步：姓名
            page.fill("input[name='firstName']", first_name)
            page.wait_for_timeout(200)
            page.fill("input[name='lastName']", last_name)
            page.wait_for_timeout(500)
            click_next(page)
            try:
                page.wait_for_selector("input[name='year']", state='attached', timeout=15000)
            except:
                click_next(page)
                page.wait_for_selector("input[name='year']", state='attached', timeout=15000)

            # 第二步：生日 & 性别
            month, day, year = birthday.split('/')
            print("  填生日...")
            page.fill("input[name='year']", year)
            page.fill("input[name='day']", day)

            # 月份下拉：点击触发器打开 + JS 选择
            page.evaluate("() => { const el = document.querySelector('#month .VfPpkd-TkwUic'); if (el) { el.click(); return true; } return false; }")
            page.wait_for_timeout(1200)
            month_sel = page.evaluate("""(val) => {
                const els = document.querySelectorAll("#month li[role='option']");
                for (const el of els) {
                    if (el.getAttribute('data-value') === val) {
                        el.scrollIntoView({block:'center'});
                        el.click();
                        return true;
                    }
                }
                return false;
            }""", month)
            if month_sel:
                print(f"  月份已选: {month}")
            else:
                print("  月份选择失败")
            page.wait_for_timeout(800)

            # 性别下拉
            try:
                page.evaluate("() => { const el = document.querySelector('#gender .VfPpkd-TkwUic'); if (el) { el.click(); return true; } return false; }")
                page.wait_for_timeout(1500)
                clicked = page.evaluate("""() => {
                    const els = document.querySelectorAll("#gender li[role='option']");
                    for (const el of els) {
                        if (el.getAttribute('data-value') === '1') {
                            el.scrollIntoView({block:'center'});
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(500)
                if clicked:
                    print("  性别已选: 男")
                else:
                    # 备用：文本匹配
                    page.evaluate("""() => {
                        const els = document.querySelectorAll("#gender li[role='option']");
                        for (const el of els) {
                            const t = el.textContent.trim();
                            if (t === '男' || t === 'Male') { el.click(); return true; }
                        }
                        return false;
                    }""")
            except Exception as e:
                print(f"  性别选择跳过: {str(e)[:40]}")
            click_next(page)

            # 第三步：用户名
            page.wait_for_selector("input[name='Username']", state='attached', timeout=15000)
            try:
                page.evaluate("() => { const el = document.querySelector(\"[jsname='CeL6Qc']\"); if (el) { el.click(); return true; } return false; }")
                page.wait_for_timeout(800)
                page.evaluate("""() => {
                    const els = document.querySelectorAll("div, span, li");
                    for (const el of els) {
                        const t = el.textContent.trim();
                        if (t && t.length < 40 && (t.includes('自定义') || t.includes('custom') || t.includes('own'))) { el.click(); return true; }
                    }
                    return false;
                }""")
                page.wait_for_timeout(1000)
            except:
                pass

            username_ok = False
            for _ in range(5):
                js_fill(page, "input[name='Username']", user_name)
                page.wait_for_timeout(1000)
                click_next(page)
                page.wait_for_timeout(2000)
                warning = page.query_selector("[class*='error'], [role='alert'], .jibhHc")
                if warning:
                    txt = warning.inner_text().strip()
                    if '占用' in txt or '已使用' in txt or 'taken' in txt or '无法使用' in txt or '使用中' in txt:
                        user_name = f"{first_name.lower()}.{last_name.lower()}{random.randint(1000,99999)}"
                        print(f"  用户名被占用，换: {user_name}")
                        continue
                username_ok = True
                break
            if not username_ok:
                return None

            # 第四步：密码
            page.wait_for_selector("input[name='Passwd']", state='attached', timeout=15000)
            js_fill(page, "input[name='Passwd']", password)
            page.wait_for_timeout(700)
            js_fill(page, "input[name='PasswdAgain']", password)
            page.wait_for_timeout(700)
            p1 = page.evaluate("() => document.querySelector('input[name=Passwd]') ? document.querySelector('input[name=Passwd]').value : ''")
            p2 = page.evaluate("() => document.querySelector('input[name=PasswdAgain]') ? document.querySelector('input[name=PasswdAgain]').value : ''")
            print(f"  密码验证: 一致={p1 == p2} len1={len(p1)} len2={len(p2)}")
            if not p1 or p1 != p2:
                return None
            click_next(page)
            page.wait_for_timeout(2500)

            # 第五步：验证（手机号 / 二维码 / 跳过）
            # 先找跳过按钮
            skip_found = page.evaluate("""() => {
                const btns = document.querySelectorAll("button, [role='button']");
                for (const b of btns) {
                    const t = b.textContent.trim().toLowerCase();
                    if (t === 'skip' || t.includes('跳过') || t === '跳过') { b.click(); return true; }
                    if (t.includes('try another way') || t.includes('改用其他方式')) { b.click(); return 'another'; }
                }
                return false;
            }""")
            if skip_found:
                print("  点击跳过验证")
                page.wait_for_timeout(1500)
                # 跳过后再点一次下一步
                click_next(page)
                page.wait_for_timeout(2000)

            phone = page.query_selector("#phoneNumberId")
            if phone:
                print("  出现手机号验证框（需接码，跳过此账号）")
                return ('NEED_PHONE', None)

            qr = page.query_selector("img[alt*='QR' i], [class*='qr' i]")
            if qr:
                print("  出现二维码验证（需换节点）")
                return ('NEED_QR', None)

            # 同意条款
            click_next(page)
            page.wait_for_timeout(1500)
            try:
                agree = page.query_selector("button.VfPpkd-LgbsSe-OWXEXe-dgl2Hf:has-text('我同意')")
                if agree:
                    page.evaluate("window.scrollTo(0, 800)")
                    page.wait_for_timeout(800)
                    agree.click(force=True, timeout=10000)
                else:
                    page.locator("button:has-text('我同意')").last.click(force=True, timeout=10000)
            except:
                pass
            page.wait_for_timeout(4000)

            if 'signup' in page.url or 'challenge' in page.url:
                print(f"  仍在注册流程: {page.url[:70]}")
                qr2 = page.query_selector("img[alt*='QR' i], [class*='qr' i], [id*='qr' i]")
                if qr2:
                    return ('NEED_QR', None)
                return None

            email = f"{user_name}@gmail.com"
            print(f"  注册成功: {email}")
            return ('OK', email)

        except Exception as e:
            print(f"  第{attempt+1}次尝试失败: {str(e)[:80]}")
            continue

    return None


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    global RESIDENTIAL_ONLY
    if len(sys.argv) > 2:
        RESIDENTIAL_ONLY = sys.argv[2] == '1'

    with open(os.path.join(DATA_DIR, 'First_Name_DB.csv'), 'r') as f:
        first_names = [row[0] for row in csv.reader(f) if row]
    with open(os.path.join(DATA_DIR, 'Last_Name_DB.csv'), 'r') as f:
        last_names = [row[0] for row in csv.reader(f) if row]
    print(f"姓名库: {len(first_names)} 名, {len(last_names)} 姓")

    nodes, current = list_nodes()
    print(f"Clash 节点: {len(nodes)} 个, 当前: {current}")
    print(f"=== 开始创建 {count} 个 Gmail 账号（住宅节点={'是' if RESIDENTIAL_ONLY else '否'}）===")

    results = []
    success = fail = qr_hits = 0
    used_ips = set()
    cur_node = current
    node_stats = {}  # 节点 → {qr, ok, phone}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, proxy={"server": PROXY})

        for i in range(count):
            print(f"\n[{i+1}/{count}]")
            # 每次尝试 1 次切节点；若上次出二维码，强制切新节点
            node, ip, cc, city = rotate_node(used_ips)
            if node:
                cur_node = node
                used_ips.add(ip)
                print(f"  节点: {node[:30]} → IP {ip} ({cc}/{city})")
            else:
                print(f"  使用当前节点: {cur_node}")

            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            password = generate_password()
            birthday = f"{random.randint(1,12)}/{random.randint(1,28)}/{random.randint(1985,2002)}"
            print(f"  生成: {first_name} {last_name} / {password} / {birthday}")

            ctx, page = random_context(browser)
            try:
                warmup_session(page)
                result = create_one_account(page, first_name, last_name, password, birthday)
                tag = 'other'
                if result and result[0] == 'OK':
                    results.append((result[1], password))
                    success += 1
                    tag = 'ok'
                elif result and result[0] == 'NEED_QR':
                    qr_hits += 1
                    print("  → 二维码，下个账号将强制换节点")
                    fail += 1
                    tag = 'qr'
                elif result and result[0] == 'NEED_PHONE':
                    fail += 1
                    tag = 'phone'
                else:
                    fail += 1
                node_stats.setdefault(cur_node, {'qr': 0, 'ok': 0, 'phone': 0, 'other': 0})
                node_stats[cur_node][tag] += 1
            except Exception as e:
                print(f"  异常: {str(e)[:80]}")
                fail += 1
            finally:
                try:
                    ctx.close()
                except:
                    pass

            delay = random.uniform(4, 10)
            print(f"  等待 {delay:.1f}s...")
            time.sleep(delay)

        browser.close()

    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        for email, pwd in results:
            f.write(f"{email} {pwd}\n")

    print(f"\n=== 完成 ===")
    print(f"成功: {success}, 失败: {fail}, 其中二维码 {qr_hits} 次")
    print("节点统计:")
    for node, s in sorted(node_stats.items(), key=lambda x: -x[1]['qr']):
        print(f"  {node[:40]}: OK={s['ok']} QR={s['qr']} PHONE={s['phone']} 其它={s['other']}")
    print(f"结果保存到: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()