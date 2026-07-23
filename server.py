"""
角色扮演聊天机器人 · 借鉴 mobileLLM 的 Skill 设计
=================================================
- 角色 = 一个本地写好的 skill 文件（markdown，兼容 mobileLLM / AI Edge Gallery 的 SKILL.md 格式）
- 前端有「导入 skill」上传按钮；也可从角色库点选激活，对话中只激活一个 skill
- 回答由本机 Ollama 的 Qwen2.5:3B 生成，不消耗任何云端 token
- skill 文件可同时导入 mobileLLM（Mac/iOS）与本程序，格式互通
- 每个角色支持自定义头像图片（上传后存为 {id}.avatar）
"""

import os
import sys
import re
import json
import yaml
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# 清理模型输出的引用标记（如 [reference:43]、[1]、【reference:N】等）
_REF_RE = re.compile(r'\[?(?:reference|ref|来源)?[:：]?\d+\]?|\[\d+\]', re.IGNORECASE)

def _clean_token(text: str) -> str:
    """移除 LLM 输出中的引用/索引/来源标记。"""
    return _REF_RE.sub('', text).strip()

def _base_dir() -> Path:
    """定位资源根目录：打包成 exe 后用 exe 所在目录（可写、持久），
    未打包时用脚本所在目录。首次运行会把内置的 web/skills 复制到该目录。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    # 打包后首次运行：把 _MEIPASS 里的默认资源复制到 base（让用户新增/修改持久）
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        import shutil
        for name in ("web", "skills"):
            src = Path(meipass) / name
            dst = base / name
            if src.exists() and not dst.exists():
                try:
                    shutil.copytree(src, dst)
                except Exception:
                    pass
    return base


APP_DIR = _base_dir()
SKILLS_DIR = APP_DIR / "skills"
WEB_DIR = APP_DIR / "web"
AVATAR_DIR = SKILLS_DIR / "_avatars"
HISTORY_DIR = APP_DIR / "data" / "history"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("MODEL", "qwen2.5:3b")
MOCK = os.environ.get("MOCK", "0") == "1"
NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))
KEEP_HISTORY = int(os.environ.get("KEEP_HISTORY", "20"))

SKILLS_DIR.mkdir(exist_ok=True)
AVATAR_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="角色扮演聊天机器人 (本地 LLM · Skill 版)")


# ----------------------------- 开发期禁缓存 -----------------------------

@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """开发阶段：静态文件和 HTML 禁用浏览器缓存，避免改了代码不生效。"""
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ----------------------------- 头像管理 -----------------------------

def _avatar_path(skill_id: str) -> Path:
    """返回该角色的头像文件路径（可能不存在）。"""
    # 按优先级查找：png > jpg > jpeg > webp > gif
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        p = AVATAR_DIR / f"{skill_id}{ext}"
        if p.exists():
            return p
    return None


def _has_avatar(skill_id: str) -> bool:
    return _avatar_path(skill_id) is not None


@app.post("/api/skills/{skill_id}/avatar")
async def upload_avatar(skill_id: str, file: UploadFile = File(...)):
    """为已有角色上传头像。"""
    # 确认 skill 存在
    skill_path = None
    for ext in (".skill", ".md", ".markdown", ".yaml"):
        p = SKILLS_DIR / f"{skill_id}{ext}"
        if p.exists():
            skill_path = p
            break
    if not skill_path:
        return JSONResponse(status_code=404, content={"error": "角色不存在"})

    data = await file.read()
    suffix = Path(file.filename).suffix.lower() if file.filename else ".png"
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ".png"

    dest = AVATAR_DIR / f"{skill_id}{suffix}"
    dest.write_bytes(data)
    return {"ok": True, "url": f"/api/skills/{skill_id}/avatar"}


@app.get("/api/skills/{skill_id}/avatar")
def get_avatar(skill_id: str):
    p = _avatar_path(skill_id)
    if not p:
        return JSONResponse(status_code=404, content={"error": "无头像"})
    return FileResponse(p, media_type=f"image/{p.suffix.lstrip('.')}")


# ----------------------------- Skill 解析 -----------------------------

def parse_skill_markdown(text: str) -> dict:
    """解析 mobileLLM / AI Edge Gallery 风格的 SKILL.md：
    ---\n name / description\n---\n 正文(markdown 即角色设定)"""
    text = text.strip()
    name = None
    description = ""
    body = text
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except Exception:
                fm = {}
            body = m.group(2).strip()
            name = fm.get("name")
            description = fm.get("description", "")
    return {
        "name": name,
        "description": description,
        "system_prompt": body,
        "raw": text,
    }


def skill_to_markdown(s: dict) -> str:
    """把结构化角色数据转换回 SKILL.md 文本（供「新建角色」保存为 .skill）。"""
    fm = {
        "name": s.get("name", ""),
        "description": s.get("description", ""),
    }
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    parts = []
    if s.get("system_prompt"):
        parts.append(s["system_prompt"].strip())
    if s.get("speech_style"):
        parts.append("## 语气与风格\n" + "\n".join(f"- {x}" for x in s["speech_style"]))
    if s.get("forbidden"):
        parts.append("## 避免\n" + "\n".join(f"- {x}" for x in s["forbidden"]))
    if s.get("examples"):
        ex = "## 示例对话\n"
        nm = s.get("name", "角色")
        for e in s["examples"]:
            ex += f"用户：{e.get('user', '')}\n{nm}：{e.get('assistant', '')}\n"
        parts.append(ex)
    return f"---\n{front}\n---\n\n" + "\n\n".join(parts)


def load_skill_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".md", ".skill", ".markdown"):
        meta = parse_skill_markdown(text)
    else:  # 兼容旧版纯 YAML
        d = yaml.safe_load(text) or {}
        meta = {
            "name": d.get("name"),
            "description": d.get("description", ""),
            "system_prompt": d.get("system_prompt", ""),
            "raw": text,
            "_legacy": True,
            "speech_style": d.get("speech_style"),
            "forbidden": d.get("forbidden"),
            "examples": d.get("examples"),
        }
    meta["id"] = path.stem
    return meta


def get_prompt_text(skill: dict) -> str:
    """从 skill 中取出作为 system 提示词的文本。"""
    if skill.get("speech_style") or skill.get("examples") or skill.get("forbidden"):
        lines = []
        if skill.get("system_prompt"):
            lines.append(skill["system_prompt"])
        if skill.get("speech_style"):
            lines += ["", "【言语风格】"] + [f"- {x}" for x in skill["speech_style"]]
        if skill.get("forbidden"):
            lines += ["", "【避免】"] + [f"- {x}" for x in skill["forbidden"]]
        if skill.get("examples"):
            nm = skill.get("name", "角色")
            lines += ["", "【示例对话】"]
            for e in skill["examples"]:
                lines.append(f"用户：{e.get('user', '')}")
                lines.append(f"{nm}：{e.get('assistant', '')}")
        return "\n".join(lines)
    return skill.get("system_prompt") or skill.get("raw") or ""


def build_system_prompt(skill: dict) -> str:
    prompt = get_prompt_text(skill).strip()
    guard = (
        "\n\n请始终严格以该角色的口吻、语调与用语习惯作答，"
        "完整模仿其上文中设定的性格与说话方式，不要跳出角色，也不要声明自己是 AI 或语言模型。"
        "不要输出任何引用标记（如 [reference:N] 或 [N]），直接用自然语言回答。"
    )
    return prompt + guard


_UNSAFE_FS = set('/\\:*?"<>|')


def safe_id(name: str) -> str:
    cleaned = "".join(c for c in str(name) if c not in _UNSAFE_FS).strip()
    return cleaned or "character"


# ----------------------------- 接口 -----------------------------

@app.get("/api/health")
async def health():
    if MOCK:
        return {"ollama": False, "mock": True, "model": MODEL}
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
            r = await c.get(f"{OLLAMA_HOST}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ollama": True, "model": MODEL, "available": MODEL in models, "models": models}
    except Exception as e:
        return {"ollama": False, "error": str(e), "model": MODEL}


@app.get("/api/skills")
def list_skills():
    skills = []
    files = []
    for ext in ("*.md", "*.skill", "*.markdown", "*.yaml"):
        files.extend(SKILLS_DIR.glob(ext))
    for f in sorted(files, key=lambda p: p.stem):
        try:
            meta = load_skill_file(f)
        except Exception:
            continue
        skills.append({
            "id": meta["id"],
            "name": meta.get("name") or meta["id"],
            "description": meta.get("description", ""),
            "has_avatar": _has_avatar(meta["id"]),
        })
    return skills


@app.get("/api/skills/{skill_id}")
def get_skill(skill_id: str):
    for ext in (".skill", ".md", ".markdown", ".yaml"):
        path = SKILLS_DIR / f"{skill_id}{ext}"
        if path.exists():
            result = load_skill_file(path)
            result["has_avatar"] = _has_avatar(skill_id)
            return JSONResponse(result)
    return JSONResponse(status_code=404, content={"error": "角色不存在"})


@app.post("/api/skills")
async def save_skill(request: Request, file: UploadFile = File(None)):
    """保存 skill：上传 .skill/.md 文件，或提交 JSON 表单（自动转成 SKILL.md）。"""
    if file is not None:
        text = (await file.read()).decode("utf-8")
        suffix = Path(file.filename).suffix.lower() if file.filename else ".skill"
        if suffix in (".md", ".skill", ".markdown"):
            meta = parse_skill_markdown(text)
            content = text
        else:
            d = yaml.safe_load(text) or {}
            meta = d
            content = skill_to_markdown(d)
        name = meta.get("name") or Path(file.filename).stem
    else:
        data = await request.json()
        content = skill_to_markdown(data)
        name = data.get("name") or "character"

    base = SKILLS_DIR / f"{safe_id(name)}.skill"
    path = base
    if path.exists():
        i = 1
        while (SKILLS_DIR / f"{safe_id(name)}-{i}.skill").exists():
            i += 1
        path = SKILLS_DIR / f"{safe_id(name)}-{i}.skill"
    path.write_text(content, encoding="utf-8")
    return {"id": path.stem, "name": name}


@app.delete("/api/skills/{skill_id}")
def delete_skill(skill_id: str):
    """删除角色：删除对应的 skill 文件及其头像。"""
    # 查找 skill 文件（按扩展名），避免路径穿越
    skill_path = None
    for ext in (".skill", ".md", ".markdown", ".yaml"):
        p = SKILLS_DIR / f"{skill_id}{ext}"
        if p.exists():
            skill_path = p
            break
    if not skill_path:
        return JSONResponse(status_code=404, content={"error": "角色不存在"})

    try:
        skill_path.unlink()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"删除失败: {e}"})

    # 一并删除该角色的所有头像文件
    removed_avatars = 0
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ap = AVATAR_DIR / f"{skill_id}{ext}"
        if ap.exists():
            try:
                ap.unlink()
                removed_avatars += 1
            except Exception:
                pass

    # 一并删除对话历史
    hist = HISTORY_DIR / f"{skill_id}.json"
    if hist.exists():
        try:
            hist.unlink()
        except Exception:
            pass

    return {"ok": True, "id": skill_id, "removed_avatars": removed_avatars}


# ----------------------------- 对话记忆 -----------------------------

def _safe_history_path(skill_id: str) -> Path | None:
    """构造历史文件路径并做路径穿越防护。"""
    p = (HISTORY_DIR / f"{skill_id}.json").resolve()
    if p.parent != HISTORY_DIR.resolve():
        return None
    return p


@app.get("/api/skills/{skill_id}/history")
def get_history(skill_id: str):
    """读取某角色的对话记忆。"""
    p = _safe_history_path(skill_id)
    if not p or not p.exists():
        return {"history": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"history": data.get("history", [])}
    except Exception:
        return {"history": []}


@app.post("/api/skills/{skill_id}/history")
async def save_history(skill_id: str, request: Request):
    """保存某角色的对话记忆。"""
    p = _safe_history_path(skill_id)
    if not p:
        return JSONResponse(status_code=400, content={"error": "非法角色名"})
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = body.get("history", [])
    # 仅保留 user/assistant，并截断到最近 KEEP_HISTORY 条
    clean = [
        {"role": m.get("role"), "content": str(m.get("content", ""))}
        for m in raw if isinstance(m, dict) and m.get("role") in ("user", "assistant")
    ][-KEEP_HISTORY:]
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"history": clean}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(clean)}


@app.delete("/api/skills/{skill_id}/history")
def delete_history(skill_id: str):
    """彻底删除某角色的对话记忆文件（释放本地缓存）。"""
    p = _safe_history_path(skill_id)
    if not p:
        return JSONResponse(status_code=400, content={"error": "非法角色名"})
    if p.exists():
        try:
            p.unlink()
        except Exception:
            return JSONResponse(status_code=500, content={"error": "删除失败"})
    return {"ok": True, "id": skill_id}


@app.delete("/api/history")
def clear_all_history():
    """清空所有角色的对话记忆文件（释放本地缓存空间）。"""
    removed = 0
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        for f in HISTORY_DIR.glob("*.json"):
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    except Exception:
        pass
    return {"ok": True, "removed": removed}


def _mock_stream(skill: dict, message: str):
    name = skill.get("name") or "角色"
    reply = (
        f"（演示模式 · 未连接本地模型）{name} 收到了你的消息：「{message}」。\n"
        f"请在本机安装并启动 Ollama，执行 `ollama pull {MODEL}` 后，"
        f"即可获得真实的中文角色扮演回复。"
    )
    for ch in reply:
        yield f"data: {json.dumps({'token': ch}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    skill = body.get("skill")
    message = body.get("message", "")
    history = body.get("history", [])

    if skill:
        if isinstance(skill, str):
            meta = None
            for ext in (".skill", ".md", ".markdown", ".yaml"):
                p = SKILLS_DIR / f"{skill}{ext}"
                if p.exists():
                    meta = load_skill_file(p)
                    break
            if not meta:
                return JSONResponse(status_code=404, content={"error": "角色不存在"})
            skill = meta
        elif not isinstance(skill, dict):
            return JSONResponse(status_code=400, content={"error": "缺少有效的角色设定"})

    system_prompt = build_system_prompt(skill) if skill else "你是一个乐于助人的中文助手。"

    messages = [{"role": "system", "content": system_prompt}]
    for m in (history or [])[-KEEP_HISTORY:]:
        role = m.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": m.get("content", "")})
    messages.append({"role": "user", "content": message})

    if MOCK:
        return StreamingResponse(_mock_stream(skill or {"name": "助手"}, message),
                                 media_type="text/event-stream")

    async def event_stream():
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0), trust_env=False) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_HOST}/api/chat",
                    json={
                        "model": MODEL,
                        "messages": messages,
                        "stream": True,
                        "options": {"temperature": 0.8, "top_p": 0.9, "num_ctx": NUM_CTX},
                    },
                ) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        yield f"data: {json.dumps({'error': err.decode('utf-8', '')}, ensure_ascii=False)}\n\n"
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue
                        if chunk.get("done"):
                            yield "data: [DONE]\n\n"
                            return
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            token = _clean_token(token)
                            if token:
                                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ----------------------------- 静态页面 -----------------------------

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
