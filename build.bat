@echo off
chcp 65001 >nul
echo 正在准备打包 ChatSoul ...
pip install pyinstaller
pyinstaller --name ChatSoul --onedir --noconfirm ^
  --hidden-import yaml --hidden-import httpx ^
  --hidden-import uvicorn --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import fastapi --hidden-import starlette ^
  --add-data "web;web" --add-data "skills;skills" server.py
echo.
echo 打包完成：dist\ChatSoul\ChatSoul.exe
echo 把 dist\ChatSoul 整个文件夹拷到别的电脑，双击 ChatSoul.exe 即可。
pause
