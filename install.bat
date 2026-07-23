@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   ChatSoul 一键安装启动器
echo ============================================
echo.
echo 本脚本会自动完成三件事：
echo   1) 安装 Ollama（本地运行 AI 所需的免费软件）
echo   2) 下载 AI 模型 qwen2.5:3b（约 2GB，首次需要联网）
echo   3) 启动 ChatSoul 聊天界面
echo.
echo 请保持网络畅通，整个过程可能要等几分钟，不要关闭本窗口。
echo.

REM ---------- 1) 检查 / 安装 Ollama ----------
set "OLLAMA="
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA=%ProgramFiles%\Ollama\ollama.exe"
where ollama >nul 2>&1
if not errorlevel 1 set "OLLAMA=ollama"

if not defined OLLAMA (
    echo [1/3] 未检测到 Ollama，正在下载安装包...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'"
    if not exist "%TEMP%\OllamaSetup.exe" (
        echo 下载失败。请手动到 https://ollama.com/download 下载并安装 Ollama，
        echo 安装完成后再双击本脚本（install.bat）继续。
        pause
        exit /b 1
    )
    echo 正在静默安装 Ollama，请稍候...
    start /wait "" "%TEMP%\OllamaSetup.exe" /SILENT
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    if not defined OLLAMA if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA=%ProgramFiles%\Ollama\ollama.exe"
    if not defined OLLAMA set "OLLAMA=ollama"
    echo Ollama 安装完成。
) else (
    echo [1/3] 已检测到 Ollama：%OLLAMA%
)

REM ---------- 2) 确保 Ollama 服务在运行 ----------
echo [2/3] 检查 Ollama 服务...
%OLLAMA% list >nul 2>&1
if errorlevel 1 (
    echo       未运行，正在后台启动 Ollama 服务...
    start "" /B "%OLLAMA%" serve >nul 2>&1
    timeout /t 8 >nul
) else (
    echo       Ollama 服务正常。
)

REM ---------- 3) 拉取模型 ----------
echo [3/3] 检查模型 qwen2.5:3b...
%OLLAMA% list 2>nul | findstr /I "qwen2.5:3b" >nul
if not errorlevel 1 (
    echo       模型已存在，跳过下载。
) else (
    echo       首次使用需要下载模型（约 2GB），开始下载...
    %OLLAMA% pull qwen2.5:3b
    if errorlevel 1 (
        echo       官方源下载失败，尝试国内镜像（需要 Python 环境）...
        python -m pip install modelscope >nul 2>&1
        if not errorlevel 1 (
            REM 把 Python 的 Scripts 目录加入 PATH，确保 modelscope 命令可用
            for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(sys.prefix,'Scripts'))"') do set "SC=%%P"
            if defined SC set "PATH=%SC%;%PATH%"
            modelscope download --model Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf --local_dir "%TEMP%\models"
            if not errorlevel 1 (
                echo FROM %TEMP%\models\qwen2.5-3b-instruct-q4_k_m.gguf > "%TEMP%\Modelfile"
                echo PARAMETER num_ctx 8192 >> "%TEMP%\Modelfile"
                %OLLAMA% create qwen2.5:3b -f "%TEMP%\Modelfile"
            )
        ) else (
            echo       国内镜像需要 Python 环境，未能自动完成。
            echo       请打开 README.md，按"方法二（国内加速）"手动操作，或用官方源重试。
        )
    )
)

REM ---------- 4) 启动 ChatSoul ----------
echo.
echo 模型就绪，正在启动 ChatSoul...
start "" "%~dp0ChatSoul.exe"
echo 浏览器将自动打开聊天界面。
echo 若没有自动打开，请手动访问 http://localhost:8000
echo （黑色窗口是程序本体，请勿关闭，最小化即可。）
echo.
pause
