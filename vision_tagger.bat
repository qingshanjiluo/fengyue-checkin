@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   风月AI - Qwen-VL 本地识图标注
echo ========================================
echo.
echo 用法:
echo   python scripts/vision_tagger.py --dir generated_imgs
echo   python scripts/vision_tagger.py img1.jpg img2.jpg
echo   python scripts/vision_tagger.py --list
echo.
echo 首次运行需下载模型，需要能访问 huggingface.co
echo 如无法访问，请设置代理: set HF_ENDPOINT=https://hf-mirror.com
echo.
set /p img="输入图片路径（或目录）: "
if "%img%"=="" (
    echo 未输入，退出
    pause
    exit /b
)
python scripts/vision_tagger.py --dir "%img%"
pause
