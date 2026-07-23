@echo off
chcp 65001 >nul
echo 正在打包 ChatSoul（会自动排除 build_exe.py 中设定的角色）...
python build_exe.py
echo.
echo 打包完成：dist\ChatSoul\ChatSoul.exe
echo 把 dist\ChatSoul 整个文件夹拷到别的电脑，双击 ChatSoul.exe 即可。
pause
