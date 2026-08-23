@echo off
chcp 65001 >nul
cd /d %~dp0
echo ChatAnalyst 启动中，浏览器将自动打开 http://127.0.0.1:7860
echo 关闭本窗口或按 Ctrl+C 即可停止服务
.venv\Scripts\python.exe app.py
pause
