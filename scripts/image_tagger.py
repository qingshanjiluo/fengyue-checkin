# -*- coding: utf-8 -*-
"""
图片关键词标注工具
扫描图库文件夹中的图片，调用 AI 视觉识别生成关键词，重命名文件

用法：
  python scripts/image_tagger.py                          # 处理全部图片
  python scripts/image_tagger.py --name xxx.jpg           # 处理单张
  python scripts/image_tagger.py --all --dry-run          # 预览不改名
  python scripts/image_tagger.py --all --force            # 强制覆盖已有标签
"""
import os, sys, json, base64, re, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "generated_imgs"))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "studio_settings.json")
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

TAGGED_MARKER = "_tagged"  # marker to prevent re-tagging

def load_settings():
    path = SETTINGS_FILE
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def call_vision(api_url, api_key, model, image_b64, filename):
    """调用 vision API 识图，返回关键词"""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是一个图片标签生成器。分析图片内容，输出3-6个中文关键词标签，用下划线连接。\n"
                           "规则：\n"
                           "1. 只输出关键词，不要任何解释\n"
                           "2. 关键词要准确描述图片中的主体、场景、风格、色调\n"
                           "3. 用下划线连接，如：古风_少女_竹林_淡雅\n"
                           "4. 不要包含原文件名中的内容\n"
                           "5. 控制在4-20个汉字之间"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"为这张图片生成关键词标签（图片名: {filename}）"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }
        ],
        "max_tokens": 100,
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        # Clean: remove non-Chinese/non-underscore characters
        content = re.sub(r'[^\u4e00-\u9fff_a-zA-Z0-9]', '', content)
        content = re.sub(r'_+', '_', content).strip('_')
        if not content:
            return None
        # Limit length
        if len(content) > 40:
            content = content[:40]
        return content
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:200]
        print(f"  [HTTP Error {e.code}] {body}")
        return None
    except Exception as e:
        print(f"  [Error] {e}")
        return None

def build_new_name(old_name, tags):
    """构建新文件名：原名_关键词.ext"""
    base, ext = os.path.splitext(old_name)
    # Strip existing marker and tag segments
    if TAGGED_MARKER in base:
        base = base[:base.index(TAGGED_MARKER)]
        base = base.rstrip('_')
    # Remove the last original segment before extension (e.g. _fd05, _6c50)
    segs = base.split('_')
    if len(segs) > 1:
        base = '_'.join(segs[:-1])
    new_base = f"{base}_{tags}{TAGGED_MARKER}"
    return f"{new_base}{ext}"

def process_image(path, settings, dry_run=False, force=False):
    """处理单张图片：识图 → 重命名"""
    filename = os.path.basename(path)
    base, ext = os.path.splitext(filename)

    # Skip already tagged
    if TAGGED_MARKER in filename and not force:
        print(f"  SKIP (已标注): {filename}")
        return False

    print(f"\n  识别: {filename}")
    image_b64 = encode_image(path)

    api_url = settings.get("api_url", "")
    api_key = settings.get("api_key", "")
    model = settings.get("model", "gpt-4o-mini")

    if not api_url or not api_key:
        print("  [!] 请先在 studio_settings.json 中配置 api_url 和 api_key")
        return False

    tags = call_vision(api_url, api_key, model, image_b64, filename)
    if not tags:
        print("  [!] 识别失败")
        return False

    new_name = build_new_name(filename, tags)
    new_path = os.path.join(os.path.dirname(path), new_name)

    print(f"  标签: {tags}")
    print(f"  新名: {new_name}")

    if dry_run:
        print(f"  [DRY RUN] 未实际改名")
        return True

    # Handle name conflict
    counter = 1
    while os.path.exists(new_path):
        base2, ext2 = os.path.splitext(new_name)
        new_name = f"{base2}_{counter}{ext2}"
        new_path = os.path.join(os.path.dirname(path), new_name)
        counter += 1

    os.rename(path, new_path)
    print(f"  [OK] → {new_name}")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="图片关键词标注工具")
    parser.add_argument("--name", default="", help="处理单张图片文件名")
    parser.add_argument("--all", action="store_true", help="处理全部未标注图片")
    parser.add_argument("--dry-run", action="store_true", help="预览不改名")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有标签")
    args = parser.parse_args()

    if not os.path.exists(IMG_DIR):
        print(f"[!] 图库目录不存在: {image_dir}")
        sys.exit(1)

    settings = load_settings()
    if not settings.get("api_key"):
        print("[!] 请先在 studio 设置中配置 API Key")
        sys.exit(1)

    # Collect images
    images = []
    if args.name:
        path = os.path.join(IMG_DIR, args.name)
        if os.path.exists(path):
            images.append(path)
        else:
            print(f"[!] 文件不存在: {path}")
            sys.exit(1)
    elif args.all:
        for fname in sorted(os.listdir(IMG_DIR)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in ALLOWED_EXT and TAGGED_MARKER not in fname:
                images.append(os.path.join(IMG_DIR, fname))

    if not images:
        print("[!] 没有找到图片")
        sys.exit(1)

    print(f"共 {len(images)} 张图片待处理\n")
    ok = 0
    for path in images:
        if process_image(path, settings, args.dry_run, args.force):
            ok += 1
        time.sleep(1)  # rate limit

    print(f"\n{'='*40}")
    if args.dry_run:
        print(f"预览完成: {ok}/{len(images)} 可标注")
    else:
        print(f"处理完成: {ok}/{len(images)} 已标注")
    print(f"图库: {IMG_DIR}")

if __name__ == "__main__":
    main()
