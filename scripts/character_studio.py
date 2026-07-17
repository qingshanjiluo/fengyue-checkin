# -*- coding: utf-8 -*-
"""
风月AI 角色卡工作室 - Web UI
提供聊天界面，通过 AI 对话自动创建角色卡
"""
import os, sys, json, threading, time, re
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

import flask
from flask import Flask, request, jsonify, render_template, url_for

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from character_maker import CharacterMaker, BASE_URL
from hotlist_scraper import fetch_ranking, extract_cards, format_for_ai, RANKINGS

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"))

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "studio_settings.json")
tasks = {}
tasks_lock = threading.Lock()
hotlist_cache = {"data": None, "time": 0, "ranking": None}
hotlist_cache_lock = threading.Lock()
hotlist_browser = None

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    return render_template("studio.html")

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(load_settings())

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json() or {}
    save_settings(data)
    return jsonify({"ok": True})

@app.route("/api/models", methods=["GET"])
def api_list_models():
    api_url = request.args.get("api_url", "").rstrip("/")
    api_key = request.args.get("api_key", "")
    if not api_url or not api_key:
        return jsonify({"error": "Missing api_url or api_key"}), 400

    import urllib.request, urllib.error
    req = urllib.request.Request(f"{api_url}/models")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        models = [m["id"] for m in data.get("data", []) if m.get("id")]
        models.sort()
        return jsonify({"ok": True, "models": models})
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        return jsonify({"ok": False, "error": f"HTTP {e.code}: {body}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

def get_hotlist_browser():
    global hotlist_browser
    if hotlist_browser is None:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        hotlist_browser = p.chromium.launch(headless=True, slow_mo=100)
    return hotlist_browser

@app.route("/api/hotlist", methods=["GET"])
def api_hotlist():
    ranking = request.args.get("ranking", "weekly")
    refresh = request.args.get("refresh", "0") == "1"

    with hotlist_cache_lock:
        if not refresh and hotlist_cache["data"] and hotlist_cache["ranking"] == ranking and (time.time() - hotlist_cache["time"]) < 120:
            return jsonify({"ok": True, "ranking": ranking, "items": hotlist_cache["data"], "cached": True})

    try:
        browser = get_hotlist_browser()
        ctx = browser.contexts[0] if browser.contexts else browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Ensure logged in
        if "/zh/signin" in page.url or page.url == "about:blank":
            settings = load_settings()
            page.goto(f"{BASE_URL}/zh/signin")
            page.wait_for_load_state("networkidle")
            page.locator('input[type="email"]').first.fill(settings.get("email", ""))
            page.locator('input[type="password"]').first.fill(settings.get("password", ""))
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

        cards = fetch_ranking(page, ranking)
        if not cards:
            return jsonify({"ok": False, "error": "未提取到数据"}), 500

        with hotlist_cache_lock:
            hotlist_cache["data"] = cards
            hotlist_cache["time"] = time.time()
            hotlist_cache["ranking"] = ranking

        return jsonify({"ok": True, "ranking": ranking, "items": cards, "cached": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/hotlist/rankings", methods=["GET"])
def api_hotlist_rankings():
    return jsonify(RANKINGS)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    settings = load_settings()
    api_key = settings.get("api_key", "")
    api_url = settings.get("api_url", "https://api.openai.com/v1")
    model = settings.get("model", "gpt-4o-mini")
    # Support comma-separated models, use the first one
    if model and "," in model:
        model = model.split(",")[0].strip()

    if not api_key:
        return jsonify({"error": "请先在设置中配置 OpenAI API Key"}), 400

    # Call OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=api_url)
    except Exception as e:
        return jsonify({"error": f"OpenAI 客户端初始化失败: {e}"}), 500

    system_prompt = """你是一个角色卡制作助手。用户会描述他们想要的 AI 角色卡。
请分析需求并输出 JSON（不要用 markdown 包裹），格式如下：
{
  "plan": "用自然语言向用户说明你将创建什么样的角色卡，包含角色名、性格、风格等关键信息（中文）",
  "character": {
    "name": "作品名称（角色卡对外名称）",
    "summary": "一句话简介",
    "detail": "详细介绍",
    "char_name": "角色名",
    "char_occupation": "职业",
    "char_age": "年龄",
    "char_gender": "性别",
    "char_appearance": "外貌描述",
    "char_personality": "角色性格",
    "char_tone": "说话语气/口吻",
    "char_background": "背景设定"
  }
}
注意：
- 如果用户描述不完整，请合理补充细节
- 所有字段都用中文
- char_age 填数字字符串如 "18"
- 输出纯 JSON，不要 markdown"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        content = resp.choices[0].message.content.strip()
        # Strip markdown code fences
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return jsonify({"error": f"AI 返回格式错误，原始内容: {content[:200]}"}), 500
    except Exception as e:
        return jsonify({"error": f"AI 调用失败: {e}"}), 500

    plan = parsed.get("plan", "")
    character = parsed.get("character", {})

    # Start background task
    task_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(threading.get_ident())

    with tasks_lock:
        tasks[task_id] = {
            "current_step": -1,
            "status_text": "准备开始",
            "log": "",
            "done": False,
            "error": None,
            "result": None,
            "settings": settings,
            "character": character,
        }

    t = threading.Thread(target=run_automation, args=(task_id,), daemon=True)
    t.start()

    return jsonify({
        "task_id": task_id,
        "plan": plan,
        "steps": [
            "AI 分析需求并生成角色设定",
            "登录风月平台",
            "填写基础信息",
            "添加角色到角色卡",
            "发布角色卡",
        ],
    })

@app.route("/api/task/<task_id>")
def api_task_status(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify({
        "current_step": task.get("current_step", -1),
        "status_text": task.get("status_text", ""),
        "log": task.get("log", ""),
        "done": task.get("done", False),
        "error": task.get("error"),
        "result": task.get("result"),
    })

def run_automation(task_id):
    def update(step=None, text=None, log=None, error=None, done=False, result=None):
        with tasks_lock:
            t = tasks.get(task_id)
            if not t:
                return
            if step is not None:
                t["current_step"] = step
            if text:
                t["status_text"] = text
            if log:
                t["log"] = (t.get("log", "") + log + "\n")[-2000:]
            if error:
                t["error"] = error
                t["done"] = True
            if done:
                t["done"] = True
            if result:
                t["result"] = result

    try:
        settings = load_settings()
        char = tasks[task_id]["character"]

        update(step=0, text="AI 分析完成，开始执行", log="[AI] 角色设定已生成")

        # Validate account
        email = settings.get("email", "")
        password = settings.get("password", "")
        if not email or not password:
            update(error="请先在设置中配置风月账号邮箱和密码")
            return

        # Generate test images if needed
        cover_path = settings.get("cover", "")
        chat_bg_path = settings.get("chat_bg", "")
        mobile_bg_path = settings.get("mobile_bg", "")

        img_dir = os.path.join(os.path.dirname(__file__), "..", "generated_imgs")
        os.makedirs(img_dir, exist_ok=True)

        if not cover_path or not os.path.exists(cover_path):
            cover_path = os.path.join(img_dir, "cover.png")
            if not os.path.exists(cover_path):
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new("RGB", (400, 300), "#4A90D9")
                    d = ImageDraw.Draw(img)
                    d.text((150, 140), char.get("char_name", "角色"), fill="white")
                    img.save(cover_path)
                    update(log=f"[IMG] 已生成封面: {cover_path}")
                except ImportError:
                    pass

        if not chat_bg_path or not os.path.exists(chat_bg_path):
            chat_bg_path = os.path.join(img_dir, "chat_bg.png")
            if not os.path.exists(chat_bg_path):
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new("RGB", (800, 450), "#2C3E50")
                    d = ImageDraw.Draw(img)
                    d.text((350, 220), char.get("char_name", "角色") + " Background", fill="white")
                    img.save(chat_bg_path)
                    update(log=f"[IMG] 已生成聊天背景: {chat_bg_path}")
                except ImportError:
                    pass

        if not mobile_bg_path or not os.path.exists(mobile_bg_path):
            mobile_bg_path = os.path.join(img_dir, "mobile_bg.png")
            if not os.path.exists(mobile_bg_path):
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new("RGB", (360, 640), "#34495E")
                    d = ImageDraw.Draw(img)
                    d.text((130, 310), char.get("char_name", "角色"), fill="white")
                    img.save(mobile_bg_path)
                    update(log=f"[IMG] 已生成移动背景: {mobile_bg_path}")
                except ImportError:
                    pass

        maker = CharacterMaker(email, password, headless=False, slow_mo=200)
        maker.start()

        try:
            # Step 1: Login
            update(step=1, text="正在登录风月平台...", log="[Step 1/5] 登录中")
            maker.login()
            maker.create_simple()
            update(log=f"[OK] 已登录: {maker.page.url}")

            # Step 2: Fill basic info
            update(step=2, text="正在填写基础信息...", log="[Step 2/5] 填写基础信息")
            maker.step1_basic(
                name=char.get("name", ""),
                summary=char.get("summary", ""),
                detail=char.get("detail", ""),
                cover_path=cover_path or None,
                bg_path=chat_bg_path or None,
                mobile_bg_path=mobile_bg_path or None,
            )
            update(log=f"[OK] 基础信息已填写")
            maker.next_step()

            # Step 3: Add character
            update(step=3, text="正在添加角色...", log="[Step 3/5] 添加角色")
            maker.step2_add_character(
                name=char.get("char_name", "角色"),
                occupation=char.get("char_occupation", ""),
                age=char.get("char_age", "18"),
                gender=char.get("char_gender", "女"),
                appearance=char.get("char_appearance", ""),
                personality=char.get("char_personality", ""),
                tone=char.get("char_tone", ""),
                background=char.get("char_background", ""),
            )
            update(log=f"[OK] 角色已添加")
            maker.next_step()

            # Step 4: Additional (skip)
            update(step=3, log="[Step 4/5] 跳过追加设定")
            maker.next_step()

            # Step 5: Publish
            update(step=4, text="正在发布角色卡...", log="[Step 5/5] 发布中")
            maker.step4_publish()
            update(log=f"[OK] 已发布: {maker.page.url}")

            char_id = maker.page.url.split('/')[-2] if 'character' in maker.page.url else ''
            result_url = f"{BASE_URL}/zh/explore/installed/{char_id}" if char_id else maker.page.url

            update(
                step=5,
                text="完成",
                log="[完成] 角色卡已成功创建!",
                done=True,
                result={"url": result_url, "char_id": char_id},
            )

        except Exception as e:
            update(error=f"自动化执行失败: {e}")
            import traceback
            update(log=traceback.format_exc())
        finally:
            try:
                maker.close()
            except Exception:
                pass

    except Exception as e:
        update(error=f"系统错误: {e}")

if __name__ == "__main__":
    print("✦ 风月AI 角色卡工作室")
    print(f"  打开浏览器访问: http://127.0.0.1:5000")
    print(f"  设置文件: {SETTINGS_FILE}")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
