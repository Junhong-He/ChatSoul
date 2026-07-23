#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 ChatSoul 打包成可分发文件夹 dist/ChatSoul/。

运行方式：
    python build_exe.py
（首次会自动 pip install pyinstaller）

产物：dist/ChatSoul/ChatSoul.exe  +  web/  +  skills/
把整个 dist/ChatSoul 文件夹拷到别的电脑即可，
目标机只需另行安装 Ollama 并拉取 qwen2.5:3b 模型。

------------------------------------------------------------------
如何「不打包某个角色」？
------------------------------------------------------------------
打包时会把 skills/ 里【所有】角色一起塞进 exe。
如果某个角色你不想分发出去（比如私人的、或示例里不想带的），
把它加到下面的 EXCLUDE_SKILLS 列表即可（按 skills/ 下的文件名填写）。

也可用更省事的方式：在项目根目录新建一个 build_exclude.txt，
每行写一个要排除的文件名（# 开头的是注释），打包时自动读取合并。
------------------------------------------------------------------
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
SKILLS = HERE / "skills"
WEB = HERE / "web"

# ===================== 要排除、不打包进 exe 的角色 =====================
# 按 skills/ 目录下的【文件名】填写（含扩展名）。
# 例：科研导师.md = 用户说的「王老师 / 陈教授」角色，不想分发就放进来。
EXCLUDE_SKILLS = [
    "科研导师.md",
]
# 额外：读取根目录的 build_exclude.txt（每行一个文件名，# 开头为注释）
_excl_txt = HERE / "build_exclude.txt"
if _excl_txt.exists():
    for _line in _excl_txt.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#"):
            EXCLUDE_SKILLS.append(_line)
# 去重并保留原始文件名集合 + 词干集合（用于清理对应的头像文件）
EXCLUDE_NAMES = set(EXCLUDE_SKILLS)
EXCLUDE_STEMS = {Path(n).stem for n in EXCLUDE_SKILLS}

# ===================== 手动构造打包资源列表（跳过被排除的） =====================
datas = [f"{WEB};web"]  # web 整目录正常打包
for p in sorted(SKILLS.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(HERE).as_posix()
    # 1) 角色文件本身在被排除名单里
    if p.name in EXCLUDE_NAMES:
        print(f"  · 排除角色: {rel}")
        continue
    # 2) skills/_avatars 下、与被排除角色同名的头像（避免孤儿头像）
    if p.parent.name == "_avatars" and p.stem in EXCLUDE_STEMS:
        print(f"  · 排除头像: {rel}")
        continue
    datas.append(f"{p};{rel}")

if EXCLUDE_NAMES:
    print(f"本次打包将排除 {len(EXCLUDE_NAMES)} 个角色：{', '.join(sorted(EXCLUDE_NAMES))}")
else:
    print("未设置排除角色，skills/ 下全部角色都会被打包。")

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
    "--hidden-import", "python_multipart",   # 头像上传接口依赖
]
for d in datas:
    args += ["--add-data", d]

PyInstaller.__main__.run(args)
print("\n✅ 打包完成：dist/ChatSoul/ChatSoul.exe")
print("   把 dist/ChatSoul 整个文件夹拷到别的电脑，双击 ChatSoul.exe 即可。")
