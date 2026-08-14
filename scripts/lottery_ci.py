#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI风月 抽奖机器人 (GitHub Actions 版, 零依赖, 标准库)
在 CI 中自动执行: 查积分Top10 -> 签到 -> 抽奖 -> 补漏 -> 排行汇总
账号来源: 环境变量 BOT_ACCOUNTS (每行: 账号 密码 JWT, # 开头为注释)
运行: python lottery_ci.py
"""
import sys, io, json, time, os, subprocess, random, datetime, functools

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
print = functools.partial(print, flush=True)

BASE = "https://ai-xan.xyz"
BACKUP_DOMAINS = [
    "https://acepro.store",
    "https://acquainte.xyz",
    "https://acquant.xyz",
    "https://affectional.xyz",
    "https://aiwhatis.xyz",
    "https://aquantancee.xyz",
    "https://aigirlfriend.baby",
]
BASE_LIST = [BASE] + BACKUP_DOMAINS

PROXY = os.environ.get("BOT_PROXY", "")
SIGN_INTERVAL = 3       # CI 下缩短间隔
LOTTERY_INTERVAL = 5    # CI 下缩短间隔
CURL = "curl"           # Linux CI 用 curl; Windows 下也能解析到 curl.exe

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_accounts():
    """从 BOT_ACCOUNTS 环境变量读账号 (每行: 账号 密码 JWT)"""
    seen = set()
    accs = []
    raw = os.environ.get("BOT_ACCOUNTS", "")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) < 3 or not parts[-1].startswith('eyJ'):
            continue
        jwt = parts[-1]
        if jwt in seen:
            continue
        seen.add(jwt)
        email = ''
        if len(parts) >= 4 and '@' in parts[2]:
            email = parts[2]
        accs.append({'name': parts[0], 'pwd': parts[1], 'email': email, 'jwt': jwt})
    return accs

def http_req(path, method='GET', body=None, jwt=None, timeout=15):
    """请求平台API: 用系统curl (跨平台, TLS指纹放行) 多域名容错"""
    data = json.dumps(body).encode('utf-8') if body is not None else None
    errs = []
    for base in BASE_LIST:
        try:
            cmd = [CURL, '-s', '-k', '--max-time', str(timeout), '-X', method]
            if data is not None:
                cmd += ['-H', 'Content-Type: application/json', '-d', data.decode('utf-8')]
            if jwt:
                cmd += ['-H', 'Authorization: Bearer ' + jwt]
            if PROXY:
                cmd += ['-x', PROXY]
            cmd += [base + path]
            p = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
            out = p.stdout.decode('utf-8', 'ignore').strip()
            if out:
                return json.loads(out)
            errs.append(f"{base.split('//')[1]}: 空响应(exit {p.returncode})")
        except Exception as e:
            errs.append(f"{base.split('//')[1]}: {str(e)[:50]}")
    return {'_error': 'all domains failed: ' + ' | '.join(errs[-8:])}

def get_points(acct):
    r = http_req('/go/api/account/point', method='GET', jwt=acct['jwt'])
    if '_error' in r:
        return None
    try:
        return int(float(r.get('data', {}).get('points', 0)))
    except Exception:
        return 0

def do_sign(acct):
    r = http_req('/console/api/sign_in', method='GET', jwt=acct['jwt'])
    if '_error' in r:
        return 'ERROR', r['_error'], None
    code = r.get('code')
    if code == 200:
        return 'SIGNED', r.get('data', {}), None
    return 'SKIP', str(r.get('msg', ''))[:40], None

def do_lottery(acct):
    r = http_req('/console/api/daily_lottery/draw', method='POST', body={}, jwt=acct['jwt'])
    if '_error' in r:
        return 'ERROR', r['_error'], None
    code = r.get('code')
    if code == 200:
        d = r.get('data', {})
        prize = {'prize_key': d.get('prize_key', ''), 'display': d.get('display', ''),
                 'type': d.get('type', ''), 'amount': d.get('amount', 0)}
        is_big = (prize['type'] == 'points' and int(prize.get('amount') or 0) >= 50000) or \
                 ('月卡' in prize['display'])
        return ('BIG' if is_big else 'WIN'), prize, None
    return 'SKIP', str(r.get('msg', r.get('message', '')))[:40], None

def fetch_points(accs):
    rows = []
    for acct in accs:
        pts = get_points(acct)
        if pts is not None:
            rows.append((pts, acct))
        time.sleep(random.uniform(0.2, 0.5))
    rows.sort(key=lambda x: -x[0])
    return rows

def main():
    accs = load_accounts()
    if not accs:
        log("无账号! 请在 Secrets 中设置 BOT_ACCOUNTS (每行: 账号 密码 JWT)")
        sys.exit(1)
    log(f"抽奖机器人启动: 共 {len(accs)} 个账号")

    summary = ["# AI风月 自动抽奖报告", "", f"**运行时间**: {datetime.datetime.now():%Y-%m-%d %H:%M}",
               f"**账号数**: {len(accs)}", f"**域名**: {BASE_LIST[0]} + {len(BASE_LIST)-1}个备用", ""]

    # 1. 启动积分
    log("[启动] 查询当前积分...")
    before = fetch_points(accs)
    summary.append("## 运行前积分 Top10")
    for rank, (pts, acct) in enumerate(before[:10], 1):
        summary.append(f"{rank}. **{pts}分** - {acct['name']}")
    summary.append("")

    # 2. 签到
    sign_ok = 0
    failed_sign = []
    log(f"[签到] 开始...")
    for i, acct in enumerate(accs, 1):
        s_status, s_data, _ = do_sign(acct)
        if s_status == 'SIGNED':
            sign_ok += 1
            log(f"  [{i}/{len(accs)}] ✓ {acct['name']} 签到成功 reward={s_data}")
        elif s_status == 'ERROR':
            failed_sign.append(acct)
            log(f"  [{i}/{len(accs)}] ✗ {acct['name']} 签到失败(待补)")
        else:
            log(f"  [{i}/{len(accs)}] - {acct['name']} 已签到, 跳过")
        time.sleep(SIGN_INTERVAL)
    log(f"[签到] 完成: {sign_ok}/{len(accs)} 成功")
    summary.append(f"## 签到结果\n- 成功: **{sign_ok}/{len(accs)}**")

    # 3. 抽奖
    lottery_win = 0
    pts_sum = 0
    big_list = []
    failed_lottery = []
    win_lines = []
    log(f"[抽奖] 开始...")
    for i, acct in enumerate(accs, 1):
        l_status, l_data, _ = do_lottery(acct)
        if l_status == 'BIG':
            lottery_win += 1
            big_list.append((acct, l_data))
            line = f"★★★ 大奖! {acct['name']} -> {l_data['display']} (amount={l_data['amount']})"
            print(f"  [{i}/{len(accs)}] {line}")
            win_lines.append(f"🎉 {acct['name']} -> **{l_data['display']}** (+{l_data['amount']}分)")
        elif l_status == 'WIN':
            lottery_win += 1
            if l_data['type'] == 'points':
                pts_sum += int(l_data.get('amount') or 0)
            print(f"  [{i}/{len(accs)}] ✓ {acct['name']} 抽中 {l_data['display']}")
            win_lines.append(f"✅ {acct['name']} -> {l_data['display']} (+{l_data.get('amount', 0)}分)")
        elif l_status == 'ERROR':
            failed_lottery.append(acct)
            print(f"  [{i}/{len(accs)}] ✗ {acct['name']} 抽奖失败(待补): {l_data[:70]}")
        else:
            print(f"  [{i}/{len(accs)}] - {acct['name']} 已抽过, 跳过")
        time.sleep(LOTTERY_INTERVAL)
    log(f"[抽奖] 完成: 中奖{lottery_win}次, 积分合计+{pts_sum}, 大奖{len(big_list)}个")

    # 4. 补漏轮
    if failed_sign or failed_lottery:
        log(f"[补漏] 签到失败{len(failed_sign)}个, 抽奖失败{len(failed_lottery)}个, 开始重试...")
        for round_i in range(1, 3):
            still_fail_sign = []
            still_fail_lottery = []
            for acct in failed_sign:
                s_status, s_data, _ = do_sign(acct)
                if s_status == 'SIGNED':
                    sign_ok += 1
                    log(f"  [补{round_i}] ✓ {acct['name']} 签到补成功")
                elif s_status == 'ERROR':
                    still_fail_sign.append(acct)
                time.sleep(SIGN_INTERVAL)
            for acct in failed_lottery:
                l_status, l_data, _ = do_lottery(acct)
                if l_status in ('WIN', 'BIG'):
                    lottery_win += 1
                    if l_status == 'BIG':
                        big_list.append((acct, l_data))
                        line = f"★★★ 大奖! {acct['name']} -> {l_data['display']}"
                        print(f"  [补{round_i}] {line}")
                        win_lines.append(f"🎉 {acct['name']} -> **{l_data['display']}** (+{l_data['amount']}分)")
                    else:
                        if l_data['type'] == 'points':
                            pts_sum += int(l_data.get('amount') or 0)
                        print(f"  [补{round_i}] ✓ {acct['name']} 抽奖补成功: {l_data['display']}")
                        win_lines.append(f"✅ {acct['name']} -> {l_data['display']} (+{l_data.get('amount', 0)}分)")
                elif l_status == 'ERROR':
                    still_fail_lottery.append(acct)
                time.sleep(LOTTERY_INTERVAL)
            failed_sign, failed_lottery = still_fail_sign, still_fail_lottery
            if not failed_sign and not failed_lottery:
                break

    # 5. 汇总
    summary.append(f"## 抽奖结果\n- 中奖: **{lottery_win}** 次\n- 积分新增: **+{pts_sum}**\n- 大奖: **{len(big_list)}** 个\n")
    if win_lines:
        summary.append("### 中奖明细")
        summary += win_lines
        summary.append("")
    if failed_sign or failed_lottery:
        summary.append(f"### ⚠️ 失败账号\n- 签到失败: {len(failed_sign)} 个\n- 抽奖失败: {len(failed_lottery)} 个\n")

    log("[收尾] 重新查询积分排行...")
    after = fetch_points(accs)
    summary.append("## 运行后积分 Top10")
    for rank, (pts, acct) in enumerate(after[:10], 1):
        delta = ""
        for bpts, b in before:
            if b['jwt'] == acct['jwt'] and bpts is not None:
                d = pts - bpts
                delta = f" ({d:+d})" if d else ""
                break
        summary.append(f"{rank}. **{pts}分**{delta} - {acct['name']}")
    summary.append("")

    text = "\n".join(summary)
    print("\n" + text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
        log("[OK] 报告已写入 GITHUB_STEP_SUMMARY")

    # 失败账号写入文件 (可通过 artifact 下载)
    if failed_sign or failed_lottery:
        with open("failed_accounts.txt", "a", encoding="utf-8") as f:
            f.write(f"=== {datetime.datetime.now():%Y-%m-%d %H:%M} ===\n")
            for acct in failed_sign:
                f.write(f"签到 {acct['name']} {acct['pwd']} {acct['jwt']}\n")
            for acct in failed_lottery:
                f.write(f"抽奖 {acct['name']} {acct['pwd']} {acct['jwt']}\n")
        log(f"仍有{len(failed_sign)}签到/{len(failed_lottery)}抽奖失败, 已写入 failed_accounts.txt")

    log("全部完成!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"程序异常: {str(e)[:200]}")
        sys.exit(1)
