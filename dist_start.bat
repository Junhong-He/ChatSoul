@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   ChatSoul 启动器
echo ============================================
echo.
echo 正在启动 ChatSoul，浏览器会自动打开…
echo 若端口 8000 被占用，会自动顺延到 8001、8002…
echo 关闭此窗口即停止服务。
echo.

ChatSoul.exe
pause
