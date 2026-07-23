@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   角色扮演聊天机器人 · 本地 LLM 启动器
echo ============================================
echo.
echo [提示] 首次使用请确保已安装 Ollama 并执行：ollama pull qwen2.5:3b
echo.

if not exist ".venv" (
  echo 正在创建虚拟环境...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
echo 正在安装依赖...
pip install -r requirements.txt

echo.
echo 启动服务中： http://localhost:8000
echo.
python server.py
pause
