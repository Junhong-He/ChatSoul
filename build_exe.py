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
import shutil
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
STAGE = HERE / "build_stage"          # 暂存：复制 skills 并剔除被排除角色
STAGE_SKILLS = STAGE / "skills"

# ===================== 要排除、不打包进 exe 的角色 =====================
# 按 skills/ 目录下的【文件名】填写（含扩展名）。
# 例：科研导师.md = 用户说的「王老师 / 陈教授」角色，不想分发就放进来。
#     珂莱塔.md / 珂莱塔.jpg = 可能侵权的示例角色，不上架故排除。
EXCLUDE_SKILLS = [
    "科研导师.md",
    "珂莱塔.md",
    "珂莱塔.jpg",
]
# 额外：读取根目录的 build_exclude.txt（每行一个文件名，# 开头为注释）
_excl_txt = HERE / "build_exclude.txt"
if _excl_txt.exists():
    for _line in _excl_txt.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#"):
            EXCLUDE_SKILLS.append(_line)
EXCLUDE_NAMES = set(EXCLUDE_SKILLS)
EXCLUDE_STEMS = {Path(n).stem for n in EXCLUDE_SKILLS}

# ===================== 准备暂存目录（整目录打包，避免逐文件嵌套 bug） =====================
if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE_SKILLS.mkdir(parents=True)

for item in sorted(SKILLS.iterdir()):
    if item.name == "_avatars":
        dst = STAGE_SKILLS / "_avatars"
        dst.mkdir(exist_ok=True)
        for av in sorted(item.iterdir()):
            if av.is_file() and av.stem in EXCLUDE_STEMS:
                print(f"  - 排除头像: skills/_avatars/{av.name}")
                continue
            shutil.copy2(av, dst / av.name)
    elif item.is_file():
        if item.name in EXCLUDE_NAMES:
            print(f"  - 排除角色: skills/{item.name}")
            continue
        shutil.copy2(item, STAGE_SKILLS / item.name)

if EXCLUDE_NAMES:
    print(f"本次打包排除 {len(EXCLUDE_NAMES)} 个角色：{', '.join(sorted(EXCLUDE_NAMES))}")
else:
    print("未设置排除角色，skills/ 下全部角色都会被打包。")

# ===================== 构造 PyInstaller 参数 =====================
# 注意：skills 必须作为【整个目录】打包（和 web 一样），
# 逐文件 add-data 在 PyInstaller 6.x 会把 "x.skill" 误建成目录，导致运行时读不到。
datas = [
    f"{WEB};web",
    f"{STAGE_SKILLS};skills",
]

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

try:
    PyInstaller.__main__.run(args)
finally:
    # 清理暂存目录（打包产物已在 dist/）
    try:
        if STAGE.exists():
            shutil.rmtree(STAGE)
    except Exception:
        pass

# ===================== 复制额外分发包文件（README / 启动器 / 安装器） =====================
# PyInstaller 的 COLLECT 会重建 dist/ChatSoul 并清掉里面的非打包文件，
# 所以这些"附带文件"必须在打包结束后重新拷进去，否则一重建就没了。
DIST = HERE / "dist" / "ChatSoul"
EXTRA_FILES = {
    "recipient_readme.md": "README.md",   # 收件人说明书（无 emoji，含一键安装说明）
    "install.bat": "install.bat",         # 一键安装脚本
    "dist_start.bat": "start.bat",        # 简易启动器
}
for src_name, dst_name in EXTRA_FILES.items():
    src = HERE / src_name
    if src.exists():
        shutil.copy2(src, DIST / dst_name)
        print(f"  附带文件已复制: dist/ChatSoul/{dst_name}")
    else:
        print(f"  [提示] 未找到 {src_name}，跳过复制 {dst_name}")

print("")
print("[完成] 打包完成：dist/ChatSoul/ChatSoul.exe")
print("        把 dist/ChatSoul 整个文件夹拷到别的电脑，双击 install.bat 或 ChatSoul.exe 即可。")
