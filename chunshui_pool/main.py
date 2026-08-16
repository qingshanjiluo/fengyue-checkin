#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""春水池 CLI: 自动注册号池 + 每日签到 + 花瓣同步 + 状态查看
用法:
  python main.py init                      # 建表
  python main.py register --count N        # 自动注册 N 个账号并入库 (串行 ~20s/个)
  python main.py signin                    # 批量签到全部账号 + 同步花瓣
  python main.py sync                      # 仅同步花瓣余额
  python main.py list                      # 号池列表
  python main.py show <id>                 # 账号详情 (签到/花瓣历史)
  python main.py import <账号文件>          # 从 txt 导入已有账号
"""
import io, sys, os, argparse, time, datetime, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, chunshui

PROX = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
BASE = os.path.dirname(os.path.abspath(__file__))
REG_GAP = 20  # aimagnet 每 IP 冷却

def cmd_init(_):
    db.init()
    print("数据库初始化完成:", db.DB)

def cmd_register(args):
    db.init()
    mt = chunshui.MailTM(PROX)
    ai = chunshui.Aimagnet(PROX)
    ok = fail = 0
    for i in range(args.count):
        print(f"[{i+1}/{args.count}] 建邮箱...", flush=True)
        try:
            email, epwd = mt.create()
            r = ai.register_start(email)
            if r.status_code != 200:
                print(f"  ✗ start 失败 {r.status_code}: {r.text[:120]}", flush=True)
                fail += 1
                time.sleep(REG_GAP)
                continue
            code = mt.wait_code(email, epwd)
            if not code:
                print(f"  ✗ {email} 验证码超时", flush=True)
                fail += 1
                time.sleep(REG_GAP)
                continue
            r = ai.register_complete(email, code)
            if r.status_code != 200:
                print(f"  ✗ complete 失败 {r.status_code}: {r.text[:120]}", flush=True)
                fail += 1
                time.sleep(REG_GAP)
                continue
            user = r.json()["user"]
            petals = 0
            try:
                _, tok = ai.login(email, ai.pwd)
                bal = ai.balance(user["id"], tok)
                petals = int(bal.get("petals", 0))
            except Exception as e:
                print(f"  ⚠ 登录/花瓣查询失败: {str(e)[:60]}")
            db.add_account(user.get("nickname", "?"), ai.pwd, email, epwd,
                           user["id"], user.get("createdAt"), petals)
            ok += 1
            print(f"  ✓ 注册成功 {user.get('nickname')} | {email} | id={user.get('id')[:8]}", flush=True)
        except Exception as e:
            print(f"  ✗ ERR {e}", flush=True)
            fail += 1
        time.sleep(REG_GAP)
    print(f"\n完成: 成功 {ok} / {fail} 失败")

def cmd_signin(args):
    db.init()
    ai = chunshui.Aimagnet(PROX)
    today = db.today_str()
    accts = db.accounts("active")
    print(f"今日 {today} | 待签到账号 {len(accts)}")
    s_ok = s_al = s_fail = 0
    for i, a in enumerate(accts, 1):
        try:
            user, tok = ai.login(a["email"], a["password"])
            st = ai.signin_status(tok)
            if st.get("todaySigned"):
                db.record_sign(a["id"], today, "ALREADY")
                db.update_account(a["id"], last_sign_date=today, last_sign_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                s_al += 1
                print(f"[{i}/{len(accts)}] {a['nickname']} · 已签", flush=True)
            else:
                r = ai.signin(tok)
                if r.status_code == 200:
                    j = r.json()
                    reward = int(j.get("petalsGranted", "0"))
                    db.record_sign(a["id"], today, "SIGNED", reward)
                    db.update_account(a["id"], last_sign_date=today, last_sign_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    s_ok += 1
                    print(f"[{i}/{len(accts)}] {a['nickname']} ✓ 签到 +{reward}花瓣", flush=True)
                else:
                    db.record_sign(a["id"], today, "ERROR", error=r.text[:100])
                    s_fail += 1
                    print(f"[{i}/{len(accts)}] {a['nickname']} ✗ {r.status_code}", flush=True)
            # 同步花瓣
            try:
                bal = ai.balance(user["id"], tok)
                pts = int(bal.get("petals", 0))
                db.update_account(a["id"], petals=pts)
                db.record_point(a["id"], today, pts)
            except Exception as e:
                print(f"    花瓣同步失败: {str(e)[:60]}")
        except Exception as e:
            db.record_sign(a["id"], today, "ERROR", error=str(e)[:100])
            s_fail += 1
            print(f"[{i}/{len(accts)}] {a['nickname']} ✗ ERR {str(e)[:70]}", flush=True)
        time.sleep(2)
    print(f"\n签到完成: 新签 {s_ok} | 已签 {s_al} | 失败 {s_fail}")

def cmd_sync(args):
    db.init()
    ai = chunshui.Aimagnet(PROX)
    today = db.today_str()
    accts = db.accounts("active")
    print(f"同步花瓣 ({len(accts)} 个账号)")
    for i, a in enumerate(accts, 1):
        try:
            user, tok = ai.login(a["email"], a["password"])
            bal = ai.balance(user["id"], tok)
            pts = int(bal.get("petals", 0))
            db.update_account(a["id"], petals=pts)
            if not a["registered_at"] and user.get("createdAt"):
                db.update_account(a["id"], registered_at=user["createdAt"], user_id=user["id"])
            db.record_point(a["id"], today, pts)
            print(f"[{i}/{len(accts)}] {a['nickname']}: {pts} 花瓣", flush=True)
        except Exception as e:
            print(f"[{i}/{len(accts)}] {a['nickname']}: ERR {str(e)[:60]}", flush=True)
        time.sleep(2)

def cmd_list(args):
    db.init()
    rows = db.accounts()
    today = db.today_str()
    total = sum(r["petals"] for r in rows)
    print(f"号池 {len(rows)} 个 | 总花瓣 {total}")
    print(f"{'ID':<4}{'网名':<12}{'邮箱':<30}{'注册时间':<12}{'花瓣':<7}{'今日':<5}{'最近签到':<12}{'状态'}")
    for r in rows:
        reg = datetime.datetime.fromtimestamp(int(r["registered_at"])).strftime("%m-%d %H:%M") if r["registered_at"] else "?"
        today_mark = "✓" if r["last_sign_date"] == today else "·"
        last = (r["last_sign_date"] or "")[:10]
        print(f"{r['id']:<4}{r['nickname']:<12}{r['email']:<30}{reg:<12}{r['petals']:<7}{today_mark:<5}{last:<12}{r['status']}")

def cmd_show(args):
    db.init()
    a = db.get_account(args.id)
    if not a:
        print("账号不存在"); return
    print(f"账号 {a['nickname']} | {a['email']} | id={a['user_id']}")
    if a["registered_at"]:
        print("注册时间:", datetime.datetime.fromtimestamp(int(a["registered_at"])))
    print("当前花瓣:", a["petals"])
    print("最近签到:", a["last_sign_date"], a["last_sign_at"])
    print("\n签到历史:")
    for s in db.sign_history(a["id"]):
        print(f"  {s['date']}  {s['status']:<8} {s['reward'] or ''} {s['error'] or ''}")
    print("\n花瓣走势:")
    for p in db.point_history(a["id"]):
        print(f"  {p['date']}: {p['points']}")

def cmd_import(args):
    db.init()
    lines = [l.split() for l in open(args.file, encoding="utf-8") if l.strip()]
    n = 0
    for row in lines:
        if len(row) < 4:
            continue
        nick, pwd, email, epwd = row[0], row[1], row[2], row[3]
        uid = row[4] if len(row) > 4 else None
        if db.add_account(nick, pwd, email, epwd, uid, None, 0):
            n += 1
    print(f"导入 {n} 个账号")

def main():
    ap = argparse.ArgumentParser(description="春水池")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    p = sub.add_parser("register"); p.add_argument("--count", type=int, default=1); p.set_defaults(fn=cmd_register)
    sub.add_parser("signin").set_defaults(fn=cmd_signin)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("show"); p.add_argument("id", type=int); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("import"); p.add_argument("file"); p.set_defaults(fn=cmd_import)
    args = ap.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()