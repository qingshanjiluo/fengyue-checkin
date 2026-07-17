"""
GitHub Actions AI Runner — headless character creation automation.
Usage: python scripts/ai_runner.py --json card.json
"""
import os, sys, json, argparse, time
sys.stdout.reconfigure(encoding="utf-8")

from character_maker import CharacterMaker

BASE_URL = os.environ.get("BASE_URL", "https://aiaha.xyz")
API_KEY = os.environ.get("AI_API_KEY", "")
API_URL = os.environ.get("AI_API_URL", "https://api.xiaomimimo.com/v1")
MODEL = os.environ.get("AI_MODEL", "deepseek-v4-flash")

# Simple AI call without OpenAI SDK dependency (lightweight for CI)
def call_ai(system_prompt, user_message):
    import urllib.request, urllib.error
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
    }).encode()
    url = API_URL.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"].strip()
    import re
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    m = re.search(r'\{.*\}', content, re.DOTALL)
    if m: content = m.group()
    return json.loads(content)


def main():
    parser = argparse.ArgumentParser(description="AI Character Card Creator")
    parser.add_argument("--json", help="Path to JSON card (skip AI generation)")
    parser.add_argument("--prompt", help="Natural language prompt for AI generation")
    parser.add_argument("--email", default=os.environ.get("FY_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("FY_PASSWORD", ""))
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    if not args.email or not args.password:
        print("[!] 需要邮箱密码 (FY_EMAIL / FY_PASSWORD)")
        sys.exit(1)

    if not API_KEY:
        print("[!] 需要 API Key (AI_API_KEY)")
        sys.exit(1)

    # Step 1: Get character data
    if args.json:
        with open(args.json, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("[OK] 从 JSON 加载角色数据")
    elif args.prompt:
        print(f"[AI] 生成角色: {args.prompt[:60]}...")
        system_prompt = """你是一个角色卡制作助手。根据用户描述生成完整的角色卡 JSON。
输出格式（纯 JSON）：
{
  "plan": "说明",
  "character": {
    "name": "作品名称",
    "summary": "一句话简介",
    "detail": "详细介绍",
    "char_name": "主角姓名",
    "char_occupation": "职业",
    "char_age": "年龄",
    "char_gender": "性别",
    "char_setting": "人物设定",
    "char_appearance": "外貌",
    "char_personality": "性格",
    "char_tone": "语气",
    "char_background": "背景",
    "greeting": "开场白（40字以内）",
    "tags": ["标签1", "标签2"],
    "anonymous": false
  }
}
只输出 JSON，不要 markdown。"""
        data = call_ai(system_prompt, args.prompt)
        print(f"[AI] 生成完成: {data.get('plan', '')[:100]}")
    else:
        print("[!] 需要 --json 或 --prompt")
        sys.exit(1)

    char = data.get("character", data)

    # Step 2: Create character on site
    print(f"\n=== 开始创建角色: {char.get('name', '未命名')} ===")
    maker = CharacterMaker(args.email, args.password, headless=args.headless, slow_mo=100)
    maker.start()
    maker.login()

    maker.page.goto(f"{BASE_URL}/zh/apps")
    maker.page.wait_for_load_state("networkidle")
    time.sleep(2)
    maker.page.locator("text=简易创作").first.click()
    maker.page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Step 1: Basic info
    maker.step1_basic(
        name=char.get("name", "角色卡"),
        summary=char.get("summary", ""),
        detail=char.get("detail", ""),
        gender="男性向", language="简体中文",
    )
    maker.next_step()

    # Step 2: Character
    maker.step2_add_character(
        name=char.get("char_name", "角色"),
        occupation=char.get("char_occupation", ""),
        age=char.get("char_age", "18"),
        gender=char.get("char_gender", "女"),
        setting=char.get("char_setting", ""),
        appearance=char.get("char_appearance", ""),
        personality=char.get("char_personality", ""),
        tone=char.get("char_tone", ""),
        background=char.get("char_background", ""),
    )

    # Extra characters
    extra = char.get("characters", [])
    if extra:
        maker.step2_add_multiple_characters(extra)
    maker.next_step()

    # Step 3: Greeting
    greeting = char.get("greeting", "")
    if greeting:
        maker.step3_set_greeting(greeting)

    # CG images (skip in CI unless images provided)
    maker.next_step()

    # Step 4: Tags & model
    tags = char.get("tags", [])
    if tags:
        maker.step4_add_tags(tags)
    maker.step4_set_model(MODEL)

    # Publish
    anonymous = char.get("anonymous", False)
    maker.step4_publish(anonymous=anonymous)

    result_url = maker.page.url
    print(f"\n[OK] 发布成功: {result_url}")
    maker.close()

    # Output GitHub Steps summary
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## ✅ 角色卡已创建\n- **名称**: {char.get('name', '未命名')}\n- **URL**: {result_url}\n- **模型**: {MODEL}\n")


if __name__ == "__main__":
    main()
