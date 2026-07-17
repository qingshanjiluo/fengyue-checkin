# -*- coding: utf-8 -*-
"""
风月AI 热榜爬虫 - 提取探索页各排行榜作品列表
"""
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")

RANKINGS = {
    "recommended": "推荐",
    "latest": "最近发布",
    "daily": "日榜",
    "weekly": "周榜",
    "monthly": "月榜",
    "total": "总榜",
    "author": "作者榜",
}

def extract_cards(page, ranking="weekly"):
    """从当前探索页提取排行榜卡片数据"""
    return page.evaluate("""
        (ranking) => {
            const all = document.querySelectorAll('a[href*="/explore/installed/"]');
            const results = [];
            const seen = new Set();

            for (const a of all) {
                if (a.offsetParent === null) continue;
                const href = a.getAttribute('href') || '';
                const uuid = href.split('/').pop();
                if (seen.has(uuid) || !uuid) continue;
                seen.add(uuid);

                const card = a.closest('[class*="rounded"]') || a.parentElement;
                const text = card ? (card.innerText || '').trim() : a.innerText.trim();
                const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

                let playCount = '';
                for (const l of lines) {
                    const m = l.match(/([\\d,.]+)\\s*[亿万]/);
                    if (m) { playCount = m[0]; break; }
                }

                let title = '';
                for (const l of lines) {
                    if (l !== playCount && l !== '' && !l.includes('作者') && !l.match(/^[\\d.]+$/) && !l.includes('/')) {
                        title = l; break;
                    }
                }

                let author = '';
                for (const l of lines) {
                    if (l.startsWith('作者：') || l.startsWith('作者:')) {
                        author = l.replace(/^作者[：:]/, '').trim();
                        break;
                    }
                }

                let rating = '';
                for (const l of lines) {
                    const m = l.match(/^([\\d.]+)$/);
                    if (m) { const v = parseFloat(m[1]); if (v > 0 && v <= 10) { rating = m[1]; break; } }
                }

                let tags = '';
                for (const l of lines) {
                    if (l.includes('/') && l.length < 80 && !l.startsWith('作者')) {
                        tags = l; break;
                    }
                }

                let description = '';
                for (const l of lines) {
                    if (l.length > 30 && l !== playCount && !l.startsWith('作者') && !l.match(/^[\\d.]+$/) && !l.includes('http')) {
                        description = l.slice(0, 200); break;
                    }
                }

                results.push({
                    uuid, title: title.slice(0, 100),
                    url: 'https://aiaha.xyz' + href,
                    playCount, author: author.slice(0, 40),
                    rating, tags: tags.slice(0, 100),
                    description: description.slice(0, 300),
                    ranking,
                });
            }
            return results;
        }
    """, ranking)

def fetch_ranking(page, ranking="weekly", display="simple"):
    """导航到指定排行榜并返回卡片数据"""
    url = f"https://aiaha.xyz/zh/explore/apps?ranking={ranking}&display={display}"
    page.goto(url, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    return extract_cards(page, ranking)

def format_for_ai(card):
    """将作品卡片格式化为 AI prompt 参考文本"""
    return f"""作品: {card.get('title', '')}
热度: {card.get('playCount', '')}
作者: {card.get('author', '')}
评分: {card.get('rating', '')}
标签: {card.get('tags', '')}
简介: {card.get('description', '')}"""

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=100)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        page.goto("https://aiaha.xyz/zh/signin")
        page.wait_for_load_state("networkidle")
        page.locator('input[type="email"]').first.fill("sifangzhiji@qq.com")
        page.locator('input[type="password"]').first.fill("Pipi20100817")
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        for rank in ["weekly", "daily", "monthly", "total"]:
            cards = fetch_ranking(page, rank)
            print(f"\n[{RANKINGS.get(rank, rank)}] {len(cards)} 个作品")
            for c in cards[:3]:
                print(f"  {c['playCount']:10s} {c['title'][:40]}")

        browser.close()
