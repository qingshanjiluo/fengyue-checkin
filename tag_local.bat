@echo off
cd /d "%~dp0"
echo ========================================
echo   风月AI - 图片智能标注
echo   模式: AI 识图（100MB 本地模型）
echo ========================================
echo.
node scripts\tag_images.js --vision --force %*
pause