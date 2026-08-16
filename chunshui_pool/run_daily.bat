@echo off
rem 春水池每日签到 + 花瓣同步 (建议每日 08:10 运行, 春水 04:00 刷新)
set PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe
set DIR=%~dp0
%PY% "%DIR%main.py" signin
%PY% "%DIR%main.py" sync