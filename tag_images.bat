@echo off
cd /d "%~dp0"
echo ========================================
echo   风月AI - 图片文件名清洗工具
echo   如需 AI 识图请用 tag_local.bat
echo ========================================
echo.
node scripts\tag_images.js --all --force %*
pause