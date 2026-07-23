# 角色扮演聊天机器人（本地 LLM · Skill 版）

借鉴 [mobileLLM](https://github.com/nanguoyu/mobileLLM) 的 **Skill** 设计：每个角色是一个本地写好的 `SKILL.md` 风格文件，
前端有「导入 skill」上传按钮，激活后由本机 **Ollama + Qwen2.5:3B** 生成回答，**不消耗任何云端 token**。

> mobileLLM 本身是 SwiftUI 原生 Apple App（iOS/macOS，跑 MLX/llama.cpp/Apple Intelligence），不能在 Windows 上构建。
> 本项目沿用它的 **skill 文件格式与「对话中激活一个 skill」的交互**，落地为可跨平台运行的本地 LLM Web 应用。
> 因为格式互通，你在本地写好的 `角色.skill` 文件**既能导入 mobileLLM（Mac/iOS），也能导入本程序**。

## 特性
-  **导入 skill 即换角色**：前端「＋」菜单里点「导入 skill 文件」上传本地 `.skill`/`.md`
-  **SKILL.md 兼容**：frontmatter（name/description/emoji）+ markdown 正文即角色设定，与 mobileLLM / AI Edge Gallery 互通
-  **完全本地**：调用本机 Ollama，断网也能用
-  **中文语感自然**：Qwen2.5:3B 针对中文优化
-  **8192 上下文**：记住更长角色设定与历史
-  **流式回复** + 移动端风格的 [+] 激活菜单

## 1. 安装并启动 Ollama
```bash
# 下载 https://ollama.com/download 并安装
ollama pull qwen2.5:3b
```
确保 Ollama 后台运行（默认 `http://localhost:11434`）。

## 2. 启动本服务
```bash
pip install -r requirements.txt
python server.py            # 打开 http://localhost:8000
```
Windows 可直接双击 `start.bat`。

环境变量：`OLLAMA_HOST` / `MODEL`(默认 `qwen2.5:3b`) / `NUM_CTX`(默认 `8192`) / `PORT`(默认 `8000`) / `MOCK`(设 `1` 仅预览)。

## 3. 使用
1. 点输入框左侧 **「＋」** → **「导入 skill 文件」**，选择本地写好的 `角色.skill`（或 `.md`）→ 导入后自动激活。
2. 也可在左侧角色库直接点选；或「＋」→「新建角色 skill」填表生成。
3. 对话中只激活一个 skill（同 mobileLLM），点角色名旁的 ✕ 可取消。

## 4. 角色 skill 文件格式（SKILL.md，兼容 mobileLLM）
文件 `角色.skill`（本质是 markdown）：
```markdown
---
name: 墨尘先生
description: 饱读诗书的古风文人，言辞典雅
emoji: 
---

# 角色设定
你是墨尘先生，一位饱读诗书的文人雅士……（身份、性格、说话方式）

# 语气与风格
- 文白相间，多用成语、典故
- 称呼对方为「阁下」

# 避免
- 不使用现代网络用语

# 示例对话
用户：你好
墨尘先生：阁下安好。
```
- `---` 之间是 YAML frontmatter（name/description/emoji 可选）
- 正文（markdown）直接作为 system 提示词，教模型模仿该角色的语调与措辞
- 后端会自动追加「请以该角色口吻作答、不要跳出角色」的约束

## 5. 接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health` | Ollama / 模型状态 |
| GET  | `/api/skills` | 角色列表 |
| GET  | `/api/skills/{id}` | 单个角色详情 |
| POST | `/api/skills` | 上传 `.skill`/`.md` 文件，或提交 JSON 保存为 `.skill` |
| POST | `/api/chat` | 对话（SSE 流式），body: `{skill, message, history}`（`skill` 为 id 或角色对象，可空） |
| DELETE | `/api/skills/{id}` | 删除角色（含头像、记忆） |
| GET/POST | `/api/skills/{id}/history` | 读取 / 保存某角色的对话记忆 |
| POST | `/api/skills/{id}/avatar` | 为角色上传头像 |

---

## 6. 记忆功能（已内置）

每个角色的对话会**自动持久化**到本地 `data/history/{角色id}.json`，所以：

- **切换角色再切回来** → 之前的对话还在；
- **关闭浏览器 / 刷新页面** → 重新打开会自动恢复上一次激活的角色和它的对话；
- **点「清空对话」** → 同时清空本地记忆；
- **删除角色** → 该角色的设定、头像、记忆一并删除。

无需任何手动操作，发送每条消息后会自动保存。记忆文件按 `KEEP_HISTORY`（默认 20 条，环境变量可调）截断，不会无限膨胀。

---

## 7. 打包与分发到其他电脑

ChatSoul 的核心回答由**本机 Ollama 里的 Qwen2.5 模型**生成，所以「另一台电脑能用」有两条路线。

### 路线 A：目标机完全本地运行（推荐，零依赖你的机器）

目标机自己装好模型，断网也能用，不耗任何云端 token。

1. 在你这台开发机上打包（生成可分发文件夹）：
   ```bash
   python build_exe.py
   # 或双击 build.bat
   ```
   产物为 `dist/ChatSoul/`（含 `ChatSoul.exe` + `web/` + `skills/`）。
2. 把 **整个 `dist/ChatSoul` 文件夹** 拷到目标机（U 盘 / 网盘均可）。
3. 目标机只需再装两样东西：
   - **Ollama**：https://ollama.com/download （若官网慢，参考下方「中国大陆加速」）
   - 拉模型：`ollama pull qwen2.5:3b`
4. 目标机双击 `ChatSoul.exe` → 自动开服务 → 浏览器开 `http://localhost:8000`。
   - 首次运行会把 `web/`、`skills/` 复制到 `ChatSoul.exe` 旁边，之后你新增/导入的角色都持久保存在那。
   - 关闭那个黑色控制台窗口即停止服务。

### 路线 B：局域网共享（你机器当服务器，别人不装模型）

适合小团队临时共用，计算仍发生在你这台机器：

1. 你这台机器启动服务（已默认监听 `0.0.0.0:8000`）：
   ```bash
   python server.py
   ```
2. 让 Ollama 允许局域网连接（管理员 PowerShell）：
   ```powershell
   ollama serve --host 0.0.0.0
   ```
   （或设置环境变量 `OLLAMA_HOST=0.0.0.0:11434` 后重启 Ollama 服务）
3. 查你机器的内网 IP：`ipconfig` → IPv4（如 `192.168.1.50`）。
4. 同一局域网的其它电脑，浏览器直接访问 `http://192.168.1.50:8000`。
5. Windows 防火墙放行 `8000` 端口（入站规则）。

> 注意：路线 B 下所有对话的推理都在你机器上，多人同时用会占你机器算力；目标机若想**独立、断网、不依赖你**，请走路线 A。

### 换模型 / 换机器地址

所有关键参数都是环境变量，无需改代码：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL` | `qwen2.5:3b` | Ollama 中的模型名 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 地址（跨机用对方 IP） |
| `NUM_CTX` | `8192` | 上下文长度 |
| `PORT` | `8000` | Web 服务端口 |
| `MOCK` | `0` | 设为 `1` 走演示模式（不连模型） |
| `KEEP_HISTORY` | `20` | 每个角色保留的最近对话条数 |
