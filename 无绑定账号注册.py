#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黑号批量注册器 (无邮箱快速注册)
用法:
  pip install aiohttp
  python register_black.py                      # 直连
  python register_black.py http://127.0.0.1:7890  # 走代理
  或环境变量 REG_PROXY=http://127.0.0.1:7890
注册结果: accounts.txt (格式: 账号 密码 JWT)
"""
import asyncio, aiohttp, sys, io, time, random, string, json, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROXY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('REG_PROXY', '')
DOMAINS = ["https://ai-xan.xyz", "https://acepro.store", "https://aquantancee.xyz"]
OUT_FILE = "accounts.txt"
CONCURRENCY = 8
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

stats = {'ok': 0, 'fail': 0}
start = time.time()
lock = asyncio.Lock()

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

async def register_one():
    """一次完整注册 (独立cookie会话)"""
    global stats
    base = random.choice(DOMAINS)
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=60, force_close=True)
    async with aiohttp.ClientSession(connector=connector,
                                     timeout=aiohttp.ClientTimeout(total=30)) as s:
        h = {'User-Agent': UA, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        try:
            # 1. 首页拿cookie
            async with s.get(base + '/', headers=h, proxy=PROXY or None) as r:
                await r.read()
            # 2. 获取滑块
            async with s.get(base + '/go/api/slide/get', headers=h, proxy=PROXY or None) as r:
                sd = (await r.json()).get('data', {})
            if not sd:
                stats['fail'] += 1
                return
            slide_id = sd.get('id')
            tile_y = sd.get('tile_y')
            reg_token = sd.get('reg_token')
            # 3. 滑块破解 (扫x 0-300)
            passed = False
            for x in range(0, 301, 20):
                try:
                    async with s.post(base + '/go/api/slide/check', proxy=PROXY or None,
                                      json={'id': slide_id, 'point': f'{x},{tile_y}'},
                                      headers=h) as r:
                        j = await r.json()
                    if j.get('code') == 100000:
                        passed = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.3)
            if not passed:
                stats['fail'] += 1
                return
            # 4. 注册 (无邮箱)
            name = 'u' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            pwd = 'Kilo' + ''.join(random.choices(string.ascii_letters + string.digits, k=6)) + '1'
            body = {'name': name, 'password': pwd, 'code': '', 'client': 'web_pc',
                    'interface_language': 'zh-Hans', 'reg_token': reg_token}
            async with s.post(base + '/console/api/register', json=body, headers=h,
                              proxy=PROXY or None) as r:
                j = await r.json()
            jwt = j.get('data')
            if isinstance(jwt, str) and jwt.startswith('eyJ'):
                async with lock:
                    with open(OUT_FILE, 'a', encoding='utf-8') as f:
                        f.write(f'{name} {pwd} {jwt}\n')
                    stats['ok'] += 1
                    if stats['ok'] % 10 == 0:
                        el = (time.time() - start) / 60
                        log(f"[OK] {stats['ok']}个 | {el:.0f}分 | {stats['ok']/max(el,0.1):.1f}个/分 | 失败{stats['fail']}")
            else:
                stats['fail'] += 1
                if 'frequent' in str(j) or '频繁' in str(j):
                    await asyncio.sleep(15)
        except Exception:
            stats['fail'] += 1

async def status_reporter():
    while True:
        await asyncio.sleep(30)
        el = (time.time() - start) / 60
        log(f"[状态] 成功{stats['ok']} 失败{stats['fail']} | 速率{stats['ok']/max(el,0.1):.1f}/分")

async def main():
    log(f"黑号注册器启动: 并发{CONCURRENCY} 代理{'启用' if PROXY else '直连'} 输出{OUT_FILE}")
    asyncio.create_task(status_reporter())
    while True:
        try:
            tasks = [asyncio.create_task(register_one()) for _ in range(CONCURRENCY)]
            await asyncio.gather(*tasks)
        except Exception as e:
            log(f"循环异常: {str(e)[:50]}")
            await asyncio.sleep(3)

if __name__ == '__main__':
    asyncio.run(main())
