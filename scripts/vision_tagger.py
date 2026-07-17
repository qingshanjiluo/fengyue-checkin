#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tiny Image Captioning — 100MB 本地识图标注
用法:
  python scripts/vision_tagger.py img1.jpg img2.jpg ...
  python scripts/vision_tagger.py --dir <folder>
输出: JSON lines, 每行 {"path":"xx","tags":"xx","time":1.23}
"""
import os, sys, json, time, re, argparse
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from transformers import VisionEncoderDecoderModel, AutoTokenizer, AutoImageProcessor

MODEL_NAME = "cnmoro/tiny-image-captioning"
STOP_WORDS = {"a", "an", "the", "in", "on", "at", "is", "are", "with", "and", "of", "to", "this", "that", "it", "its"}

_model = None
_tokenizer = None
_processor = None

def load_model():
    global _model, _tokenizer, _processor
    if _model is None:
        print(f"[model] 加载: {MODEL_NAME} ...", file=sys.stderr)
        _model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
        print(f"[model] 就绪", file=sys.stderr)
    return _model, _tokenizer, _processor

def tag_image(image_path):
    """返回英文关键词标签，下划线连接"""
    from PIL import Image

    model, tokenizer, processor = load_model()
    img = Image.open(image_path).convert("RGB")
    pixel_values = processor(img, return_tensors="pt").pixel_values
    output_ids = model.generate(pixel_values, max_new_tokens=30, num_beams=3)
    caption = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip().rstrip(".")

    # 提取关键词：去停用词、标点，取实词
    words = re.findall(r"[a-zA-Z]+", caption.lower())
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    if not keywords:
        # 回退：用完整描述前40字符
        raw = re.sub(r"[^a-zA-Z_ ]", "", caption).strip().replace(" ", "_")
        return raw[:40] if raw else None
    return "_".join(keywords[:5])

def main():
    parser = argparse.ArgumentParser(description="Tiny Image Captioning 识图标注")
    parser.add_argument("images", nargs="*", help="图片文件路径")
    parser.add_argument("--dir", default=None, help="扫描目录")
    args = parser.parse_args()

    image_paths = list(args.images)
    if args.dir:
        exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        for f in sorted(os.listdir(args.dir)):
            if os.path.splitext(f)[1].lower() in exts:
                image_paths.append(os.path.join(args.dir, f))

    if not image_paths:
        print("[]")
        sys.exit(0)

    # 预加载模型
    load_model()

    for path in image_paths:
        t0 = time.time()
        try:
            tags = tag_image(path)
            elapsed = round(time.time() - t0, 2)
            print(json.dumps({"path": os.path.basename(path), "tags": tags, "time": elapsed}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"path": os.path.basename(path), "tags": None, "error": str(e)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
