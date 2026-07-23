#!/usr/bin/env python
"""把 ChatSoul 打包成可分发文件夹 dist/ChatSoul/。

运行方式：
    python build_exe.py
（首次会自动 pip install pyinstaller）

产物：dist/ChatSoul/ChatSoul.exe  +  web/  +  skills/
把整个 dist/ChatSoul 文件夹拷到别的电脑即可，
目标机只需另行安装 Ollama 并拉取 qwen2.5:3b 模型。
"""
import subprocess
import sys
from pathlib import Path

try:
    import PyInstaller  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent

args = [
    str(HERE / "server.py"),
    "--name", "ChatSoul",
    "--onedir",
    "--noconfirm",
    "--hidden-import", "yaml",
    "--hidden-import", "httpx",
    "--hidden-import", "uvicorn",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "fastapi",
    "--hidden-import", "starlette",
    "--add-data", f"{HERE / 'web'};web",
    "--add-data", f"{HERE / 'skills'};skills",
]

PyInstaller.__main__.run(args)
print("\n✅ 打包完成：dist/ChatSoul/ChatSoul.exe")
print("   把 dist/ChatSoul 整个文件夹拷到别的电脑，双击 ChatSoul.exe 即可。")
