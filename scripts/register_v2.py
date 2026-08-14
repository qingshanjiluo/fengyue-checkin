#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风月账号批量注册器 v2 — 精细滑块扫描 + 网名库 + 随机密码
用法:
  python register_v2.py                        # 注册3个
  python register_v2.py 10                     # 注册10个
  python register_v2.py 5 http://127.0.0.1:7890  # 走代理
  或环境变量 REG_PROXY=http://127.0.0.1:7890
注册结果: accounts.txt (格式: 网名 密码 JWT)
"""
import asyncio, aiohttp, sys, io, time, random, string, json, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
PROXY = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1].isdigit() else os.environ.get('REG_PROXY', '')
NAMES_FILE = "网名库.txt"
OUT_FILE = "accounts.txt"
DOMAINS = ["https://ai-xan.xyz", "https://acepro.store", "https://aquantancee.xyz"]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

stats = {'ok': 0, 'fail': 0}
start = time.time()
lock = asyncio.Lock()

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_names(count):
    """从网名库随机取 count 个名字（不重复）"""
    names = [l.strip() for l in open(NAMES_FILE, encoding='utf-8')
             if l.strip() and not l.strip().startswith('#')]
    random.shuffle(names)
    return names[:count]

def gen_password():
    """生成纯随机8位密码（字母+数字混合）"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=8))

async def try_slide(base, s, h):
    """尝试一次滑块验证，返回 reg_token 或 None"""
    try:
        async with s.get(base + '/go/api/slide/get', headers=h, proxy=PROXY or None) as r:
            sd = (await r.json()).get('data', {})
        if not sd:
            return None, 'no slide data'
        slide_id = sd.get('id')
        tile_y = sd.get('tile_y')
        reg_token = sd.get('reg_token')
        
        # 精细扫描：5px步长，随机起始点
        x_positions = list(range(0, 301, 5))
        random.shuffle(x_positions)
        
        for x in x_positions:
            try:
                async with s.post(base + '/go/api/slide/check', proxy=PROXY or None,
                                  json={'id': slide_id, 'point': f'{x},{tile_y}'},
                                  headers=h) as r:
                    j = await r.json()
                if j.get('code') == 100000:
                    return reg_token, f'slide ok at x={x}'
                await asyncio.sleep(random.uniform(0.1, 0.2))
            except Exception:
                pass
        return None, 'slide check failed'
    except Exception as e:
        return None, f'slide error: {str(e)[:40]}'

async def register_one(name, retries=3):
    """用指定名字注册，最多重试 retries 次滑块"""
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
            
            # 2. 尝试滑块验证（最多 retries 次）
            reg_token = None
            slide_msg = ''
            for attempt in range(retries):
                reg_token, slide_msg = await try_slide(base, s, h)
                if reg_token:
                    break
                log(f"    滑块第{attempt+1}次失败: {slide_msg}")
                await asyncio.sleep(random.uniform(1, 2))
            
            if not reg_token:
                stats['fail'] += 1
                return False, f'slide failed after {retries} attempts'
            
            # 3. 注册
            pwd = gen_password()
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
                return True, f'pwd={pwd} jwt={jwt[:20]}...'
            else:
                stats['fail'] += 1
                msg = str(j.get('msg') or j.get('message') or '')[:60]
                return False, f'register failed: {msg}'
        except Exception as e:
            stats['fail'] += 1
            return False, f'exception: {str(e)[:60]}'

async def main():
    names = load_names(COUNT)
    log(f"风月账号批量注册 v2: {COUNT}个 | 代理{'启用' if PROXY else '直连'}")
    for i, name in enumerate(names, 1):
        ok, msg = await register_one(name)
        if ok:
            log(f"[{i}/{COUNT}] ✓ 注册成功: {name} -> {msg}")
        else:
            log(f"[{i}/{COUNT}] ✗ 注册失败: {name} -> {msg}")
        if i < COUNT:
            await asyncio.sleep(random.uniform(3, 6))
    el = (time.time() - start) / 60
    log(f"\n完成: 成功{stats['ok']} 失败{stats['fail']} | 用时{el:.1f}分 | 结果写入 {OUT_FILE}")

if __name__ == '__main__':
    asyncio.run(main())
