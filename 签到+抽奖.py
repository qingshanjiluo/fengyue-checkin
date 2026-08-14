#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI风月 挂机机器人 v3 (零依赖, 标准库)
启动: 先查全部积分并显示Top10 -> 签到(5s间隔) -> 抽奖(60s间隔防发现) -> 汇总+排行
列表格式: 账号 密码 JWT (3字段) 或 账号 密码 邮箱 JWT (4字段, 兼容)
运行: daily_bot.exe        单次任务
      daily_bot.exe top    实时查积分Top10
      daily_bot.exe loop   24小时循环 (每天0:05自动, 每次自动重读列表=加号不用重启)
代理: 环境变量 BOT_PROXY=http://127.0.0.1:7890 (国内服务器用)
"""
import sys, io, json, time, os, subprocess, ssl, random, datetime, functools

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
LOTTERY_LIST = "lottery_accounts.txt"
FULL_LIST = "registered_accounts.txt"
RECORD_FILE = "daily_records.jsonl"
BIG_FILE = "big_prizes.txt"
SIGN_FILE = "sign_records.jsonl"
TOP_FILE = "top_accounts.txt"

PROXY = os.environ.get("BOT_PROXY", "")
SIGN_INTERVAL = 5      # 签到间隔(秒)
LOTTERY_INTERVAL = 60  # 抽奖间隔(秒, 防集中暴露)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_accounts():
    """读账号列表 (兼容3字段/4字段格式), 删除行=不参与"""
    seen = set()
    accs = []
    lines = []
    if os.path.exists(LOTTERY_LIST):
        lines = [l for l in open(LOTTERY_LIST, encoding='utf-8')
                 if l.strip() and not l.strip().startswith('#')]
    if not lines and os.path.exists(FULL_LIST):
        # 回退: 只读带邮箱的行 (4字段, 避免混入无邮箱黑号)
        lines = [l for l in open(FULL_LIST, encoding='utf-8')
                 if l.strip() and not l.strip().startswith('#') and len(l.split()) >= 4]
    for line in lines:
        parts = line.strip().split()
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
    """请求平台API: 用系统curl.exe (Python TLS指纹被CF拦截, curl指纹放行)
    每个域名快速尝试1次, 失败立即换下一个域名"""
    data = json.dumps(body).encode('utf-8') if body is not None else None
    errs = []
    for base in BASE_LIST:
        try:
            cmd = ['curl.exe', '-s', '-k', '--max-time', str(timeout), '-X', method]
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
        return 'ERROR', r['_error'], {}
    code = r.get('code')
    if code == 200:
        d = r.get('data', {})
        rec = {'date': time.strftime('%Y-%m-%d'), 'time': time.strftime('%H:%M:%S'),
               'account': acct['name'], 'email': acct['email'], 'status': 'SIGNED', 'reward': d}
        return 'SIGNED', d, rec
    return 'SKIP', str(r.get('msg', ''))[:40], {}

def do_lottery(acct):
    r = http_req('/console/api/daily_lottery/draw', method='POST', body={}, jwt=acct['jwt'])
    if '_error' in r:
        return 'ERROR', r['_error'], {}
    code = r.get('code')
    if code == 200:
        d = r.get('data', {})
        prize = {'prize_key': d.get('prize_key', ''), 'display': d.get('display', ''),
                 'type': d.get('type', ''), 'amount': d.get('amount', 0)}
        is_big = (prize['type'] == 'points' and int(prize.get('amount') or 0) >= 50000) or \
                 ('月卡' in prize['display'])
        rec = {'date': time.strftime('%Y-%m-%d'), 'time': time.strftime('%H:%M:%S'),
               'account': acct['name'], 'email': acct['email'], 'status': 'WIN', **prize}
        return ('BIG' if is_big else 'WIN'), prize, rec
    return 'SKIP', str(r.get('msg', r.get('message', '')))[:40], {}

def show_top(accs, title="积分 Top10"):
    """查积分排序显示 Top10"""
    rows = []
    for acct in accs:
        pts = get_points(acct)
        if pts is not None:
            rows.append((pts, acct))
        time.sleep(random.uniform(0.3, 0.6))
    rows.sort(key=lambda x: -x[0])
    top = rows[:10]
    print(f"\n========== {title} ==========")
    out_lines = [f"=== {time.strftime('%Y-%m-%d %H:%M')} {title} ===\n"]
    for rank, (pts, acct) in enumerate(top, 1):
        line = f"{rank}. {pts}积分 | 账号:{acct['name']} | 密码:{acct['pwd']}" + \
               (f" | 邮箱:{acct['email']}" if acct['email'] else "")
        print(f"  {line}")
        out_lines.append(line + '\n')
    with open(TOP_FILE, 'a', encoding='utf-8') as f:
        f.writelines(out_lines)
        f.write('\n')
    return top

def run_daily():
    accs = load_accounts()
    if not accs:
        print("=" * 50)
        print("无账号!")
        print("请在 lottery_accounts.txt 填入账号 (格式: 账号 密码 JWT)")
        print("该文件需与 daily_bot.exe 在同一目录")
        print("=" * 50)
        return
    print("=" * 50)
    print(f"挂机机器人启动: 共 {len(accs)} 个账号")
    print(f"签到间隔 {SIGN_INTERVAL}秒 | 抽奖间隔 {LOTTERY_INTERVAL}秒")
    print("=" * 50)
    # 1. 启动先查积分排行
    print("\n[启动] 查询全部账号当前积分...")
    show_top(accs)
    # 2. 签到 (失败收集, 最后补漏)
    print(f"\n[签到] 开始 (预计{len(accs)*SIGN_INTERVAL//60}分钟)...")
    sign_ok = 0
    failed_sign = []
    for i, acct in enumerate(accs, 1):
        s_status, s_data, s_rec = do_sign(acct)
        if s_status == 'SIGNED':
            sign_ok += 1
            print(f"  [{i}/{len(accs)}] ✓ {acct['name']} 签到成功 reward={s_data}")
            with open(SIGN_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(s_rec, ensure_ascii=False) + '\n')
        elif s_status == 'ERROR':
            failed_sign.append(acct)
            print(f"  [{i}/{len(accs)}] ✗ {acct['name']} 签到失败(待补): {s_data[:70]}")
        else:
            print(f"  [{i}/{len(accs)}] - {acct['name']} 已签到, 跳过")
        time.sleep(SIGN_INTERVAL)
    print(f"[签到] 完成: {sign_ok}/{len(accs)} 成功")
    # 3. 抽奖 (失败收集, 最后补漏)
    print(f"\n[抽奖] 开始 (每个{LOTTERY_INTERVAL}秒, 预计{len(accs)*LOTTERY_INTERVAL//60}分钟)...")
    lottery_win = 0
    pts_sum = 0
    big_list = []
    failed_lottery = []
    for i, acct in enumerate(accs, 1):
        l_status, l_data, l_rec = do_lottery(acct)
        if l_status == 'BIG':
            lottery_win += 1
            big_list.append((acct, l_data))
            print(f"  [{i}/{len(accs)}] ★★★ 大奖! {acct['name']} -> {l_data['display']} (amount={l_data['amount']})")
            with open(BIG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{l_rec['date']} {acct['name']} -> {l_data['display']} ({l_data['amount']})\n")
        elif l_status == 'WIN':
            lottery_win += 1
            if l_data['type'] == 'points':
                pts_sum += int(l_data.get('amount') or 0)
            print(f"  [{i}/{len(accs)}] ✓ {acct['name']} 抽中 {l_data['display']}")
        elif l_status == 'ERROR':
            failed_lottery.append(acct)
            print(f"  [{i}/{len(accs)}] ✗ {acct['name']} 抽奖失败(待补): {l_data[:70]}")
        else:
            print(f"  [{i}/{len(accs)}] - {acct['name']} 已抽过, 跳过")
        with open(RECORD_FILE, 'a', encoding='utf-8') as f:
            if l_rec:
                f.write(json.dumps(l_rec, ensure_ascii=False) + '\n')
        time.sleep(LOTTERY_INTERVAL)
    print(f"\n[抽奖] 完成: 中奖{lottery_win}次, 积分合计+{pts_sum}, 大奖{len(big_list)}个")
    # 4. 补漏轮 (失败的账号重试, 最多2轮)
    if failed_sign or failed_lottery:
        print(f"\n[补漏] 签到失败{len(failed_sign)}个, 抽奖失败{len(failed_lottery)}个, 开始重试...")
        for round_i in range(1, 3):
            still_fail_sign = []
            still_fail_lottery = []
            for acct in failed_sign:
                s_status, s_data, s_rec = do_sign(acct)
                if s_status == 'SIGNED':
                    sign_ok += 1
                    print(f"  [补{round_i}] ✓ {acct['name']} 签到补成功")
                    with open(SIGN_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(s_rec, ensure_ascii=False) + '\n')
                elif s_status == 'ERROR':
                    still_fail_sign.append(acct)
                time.sleep(SIGN_INTERVAL)
            for acct in failed_lottery:
                l_status, l_data, l_rec = do_lottery(acct)
                if l_status in ('WIN', 'BIG'):
                    lottery_win += 1
                    if l_status == 'BIG':
                        big_list.append((acct, l_data))
                        print(f"  [补{round_i}] ★★★ 大奖! {acct['name']} -> {l_data['display']}")
                        with open(BIG_FILE, 'a', encoding='utf-8') as f:
                            f.write(f"{l_rec['date']} {acct['name']} -> {l_data['display']} ({l_data['amount']})\n")
                    else:
                        if l_data['type'] == 'points':
                            pts_sum += int(l_data.get('amount') or 0)
                        print(f"  [补{round_i}] ✓ {acct['name']} 抽奖补成功: {l_data['display']}")
                    with open(RECORD_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(l_rec, ensure_ascii=False) + '\n')
                elif l_status == 'ERROR':
                    still_fail_lottery.append(acct)
                time.sleep(LOTTERY_INTERVAL)
            failed_sign, failed_lottery = still_fail_sign, still_fail_lottery
            if not failed_sign and not failed_lottery:
                break
        # 最终仍失败的写文件
        if failed_sign or failed_lottery:
            with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                f.write(f"=== {time.strftime('%Y-%m-%d %H:%M')} ===\n")
                for acct in failed_sign:
                    f.write(f"签到 {acct['name']} {acct['pwd']} {acct['jwt']}\n")
                for acct in failed_lottery:
                    f.write(f"抽奖 {acct['name']} {acct['pwd']} {acct['jwt']}\n")
            print(f"\n[补漏] 仍有签到{len(failed_sign)}个/抽奖{len(failed_lottery)}个失败, 已记入 failed_accounts.txt")
    # 5. 最终排行
    print("\n[收尾] 重新查询积分排行...")
    show_top(accs, title="任务后积分 Top10")
    print("\n全部完成!")

def loop_mode():
    last_run = ''
    while True:
        now = datetime.datetime.now()
        key = now.strftime('%Y-%m-%d')
        if now.hour == 0 and now.minute >= 5 and key != last_run:
            print(f"\n{'='*50}\n=== 每日任务开始 {key} ===\n{'='*50}")
            try:
                run_daily()
            except Exception as e:
                print(f"任务异常: {str(e)[:100]}")
            last_run = key
        time.sleep(60)

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'top':
            accs = load_accounts()
            print(f"共 {len(accs)} 个账号")
            show_top(accs)
            input("\n按回车键退出...")
        elif len(sys.argv) > 1 and sys.argv[1] == 'loop':
            print("挂机循环模式启动 (每天0:05自动执行, 每次自动重读列表)")
            print("窗口保持开启即可, Ctrl+C 退出")
            loop_mode()
        else:
            run_daily()
            input("\n任务完成, 按回车键退出...")
    except Exception as e:
        print(f"程序异常: {str(e)[:200]}")
        input("\n按回车键退出...")
