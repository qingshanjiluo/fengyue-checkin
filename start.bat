@echo off
chcp 65001 >nul
title 风月AI 角色卡工作室 - 启动器
cd /d "%~dp0"

echo ╔══════════════════════════════════╗
echo ║   ✦ 风月AI 角色卡工作室          ║
echo ║   正在启动...                    ║
echo ╚══════════════════════════════════╝
echo.

:: 检查 Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请安装 Node.js
    echo         https://nodejs.org/
    pause
    exit /b 1
)

node scripts/start.js

if %errorlevel% neq 0 (
    echo.
    echo [错误] 启动失败，请检查上方日志
    pause
)
