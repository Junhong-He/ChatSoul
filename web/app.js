// ===================== 角色扮演聊天机器人 · 前端逻辑（Skill 版 v3 · 防御式）=====================

const $ = (sel) => document.querySelector(sel);

const AVATAR_BASE = "/api/skills";

const state = {
  skills: [],
  current: null,
  history: [],
  pendingAvatar: null,
};

// ---- 全局错误捕获：任何未捕获异常都会显示在页面上 ----
window.addEventListener("error", (ev) => {
  console.error("JS 运行时错误:", ev.error);
  const el = document.getElementById("js-error");
  if (el) { el.textContent = "JS 错误: " + (ev.message || String(ev.error)); el.style.display = ""; }
});
window.addEventListener("unhandledrejection", (ev) => {
  console.error("未捕获的 Promise 拒绝:", ev.reason);
  const el = document.getElementById("js-error");
  if (el) { el.textContent = "异步错误: " + (String(ev.reason || ev.message)); el.style.display = ""; }
});

// ----------------------------- 初始化（每步独立容错）-----------------------------
async function init() {
  showDebug("正在初始化…");
  try { await loadSkills(); showDebug("✅ 角色列表已加载"); } catch (e) { showDebug("❌ 角色列表加载失败: " + e.message); }
  try { await loadHealth(); showDebug("✅ 健康检查完成"); } catch (e) { showDebug("❌ 健康检查失败: " + e.message); }
  try { bindEvents(); showDebug("✅ 事件绑定完成"); } catch (e) { showDebug("❌ 事件绑定失败: " + e.message); }
}

function showDebug(msg) {
  console.log("[暖伴]", msg);
  let el = document.getElementById("debug-log");
  if (!el) {
    el = document.createElement("div");
    el.id = "debug-log";
    el.style.cssText = "position:fixed;bottom:60px;right:16px;z-index:9999;background:#4E3D35;color:#FAF7F2;padding:8px 14px;border-radius:12px;font-size:12px;max-width:360px;word-break:break-all;box-shadow:0 6px 20px rgba(0,0,0,.18);font-family:monospace;";
    document.body.appendChild(el);
  }
  el.textContent = msg;
}

async function loadSkills() {
  const resp = await fetch("/api/skills");
  if (!resp.ok) throw new Error(`/api/skills 返回 ${resp.status}`);
  state.skills = await resp.json();
  renderSkillList();
  renderMenuList();
}

async function loadHealth() {
  const resp = await fetch("/api/health");
  if (!resp.ok) throw new Error(`/api/health 返回 ${resp.status}`);
  const h = await resp.json();
  const el = $("#status");
  if (!el) return;
  if (h.mock) { el.className = "status warn"; el.textContent = `演示模式 · ${h.model}`; }
  else if (h.ollama && h.available) { el.className = "status ok"; el.textContent = `已连接 Ollama · ${h.model} 就绪`; }
  else if (h.ollama && !h.available) { el.className = "status warn"; el.textContent = `Ollama 已连，但未拉取 ${h.model}`; }
  else { el.className = "status err"; el.textContent = "未检测到 Ollama" + (h.error ? "：" + h.error : ""); }
}

// ----------------------------- 头像 URL 工具 -----------------------------
function avatarUrl(skillId) { return `${AVATAR_BASE}/${skillId}/avatar`; }

function avatarImgHtml(skillId, size) {
  const sz = size || 34;
  return `<img class="ava-img" src="${avatarUrl(skillId)}" alt="" style="width:${sz}px;height:${sz}px" onerror="this.style.display='none'" />`;
}

// ----------------------------- 渲染 -----------------------------
function renderSkillList() {
  const ul = $("#skill-list");
  if (!ul) return;
  ul.innerHTML = "";
  state.skills.forEach((s) => {
    const li = document.createElement("li");
    li.className = "skill-item" + (isActive(s.id) ? " active" : "");
    li.dataset.id = s.id;
    li.innerHTML = `${s.has_avatar ? avatarImgHtml(s.id, 34) : ''}
      <span class="meta"><span class="nm">${escapeHtml(s.name)}</span>
      <span class="ds">${escapeHtml(s.description || "")}</span></span>`;
    li.onclick = () => { activateSkill(s.id); closeMenu(); };
    ul.appendChild(li);
  });
}

function renderMenuList() {
  const ul = $("#menu-skill-list");
  if (!ul) return;
  ul.innerHTML = "";
  if (state.skills.length === 0) {
    ul.innerHTML = `<li class="mi" style="color:var(--brown-soft);cursor:default">（暂无角色，先导入或新建）</li>`;
    return;
  }
  state.skills.forEach((s) => {
    const li = document.createElement("li");
    li.className = "mi" + (isActive(s.id) ? " active" : "");
    li.innerHTML = `${s.has_avatar ? `<img class="menu-ava" src="${avatarUrl(s.id)}" onerror="this.style.display='none'" />` : ''}<span>${escapeHtml(s.name)}</span>`;
    li.onclick = () => { activateSkill(s.id); closeMenu(); };
    ul.appendChild(li);
  });
}

function isActive(id) { return (typeof state.current === "string") && state.current === id; }

// ----------------------------- 激活 / 取消角色 -----------------------------
function updateHeaderAvatar(skillId) {
  const img = $("#char-avatar");
  if (!img) return;
  if (!skillId) { img.src = ""; img.style.display = "none"; return; }
  img.src = avatarUrl(skillId); img.style.display = "";
  img.onerror = function () { this.style.display = "none"; };
}
function updateActiveAvatar(skillId) {
  const img = $("#active-avatar");
  if (!img) return;
  if (!skillId) { img.src = ""; img.style.display = "none"; return; }
  img.src = avatarUrl(skillId); img.style.display = "";
  img.onerror = function () { this.style.display = "none"; };
}

async function activateSkill(id) {
  const s = state.skills.find((x) => x.id === id);
  if (!s) return;
  state.current = id; state.history = [];
  $("#char-name").textContent = s.name;
  $("#char-desc").textContent = s.description || "已激活该角色 skill";
  updateHeaderAvatar(id); updateActiveAvatar(id);
  const as = $("#active-skill");
  if (as) { as.classList.remove("hidden"); $("#active-skill-name").textContent = s.name; }
  clearMessages(); renderSkillList(); renderMenuList();
}

function deactivate() {
  state.current = null; state.history = [];
  $("#char-name").textContent = "未激活角色 · 普通对话";
  $("#char-desc").textContent = "点左侧角色或下方「＋」导入并激活一个 skill";
  updateHeaderAvatar(null); updateActiveAvatar(null);
  const as = $("#active-skill");
  if (as) as.classList.add("hidden");
  clearMessages(); renderSkillList(); renderMenuList();
}

// ----------------------------- [+] / [×] 菜单切换 -----------------------------
let menuOpen = false;

function openMenu() {
  const menu = $("#skill-menu"), btn = $("#btn-plus");
  if (menu) menu.classList.remove("hidden");
  if (btn) btn.classList.add("open");
  menuOpen = true;
}
function closeMenu() {
  const menu = $("#skill-menu"), btn = $("#btn-plus");
  if (menu) menu.classList.add("hidden");
  if (btn) btn.classList.remove("open");
  menuOpen = false;
}
function toggleMenu() { if (menuOpen) closeMenu(); else openMenu(); }

// ----------------------------- 对话 -----------------------------
function clearMessages() { const m = $("#messages"); if (m) m.innerHTML = ""; }

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const who = role === "user" ? "你" : (typeof state.current === "string"
    ? (state.skills.find((s) => s.id === state.current)?.name || "角色")
    : (state.current?.name || "助手"));
  const whoEl = document.createElement("span"); whoEl.className = "who"; whoEl.textContent = who;
  const body = document.createElement("div"); body.className = "body"; body.textContent = text;
  wrap.appendChild(whoEl); wrap.appendChild(body);
  const msgs = $("#messages");
  if (msgs) { msgs.appendChild(wrap); scrollBottom(); }
  return body;
}
function scrollBottom() { const m = $("#messages"); if (m) m.scrollTop = m.scrollHeight; }

async function sendMessage() {
  const input = $("#input");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = ""; autoGrow(input);

  addMessage("user", text);
  state.history.push({ role: "user", content: text });

  const body = addMessage("assistant", "");
  if (body) body.classList.add("typing");

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill: state.current, message: text, history: state.history }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      if (body) { body.classList.remove("typing"); body.textContent = "⚠️ " + (err.error || "请求失败"); }
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n"); buffer = parts.pop();
      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line || line === "[DONE]") continue;
        try {
          const obj = JSON.parse(line);
          if (obj.error) full += "\n[错误] " + obj.error;
          else if (obj.token) { full += obj.token; if (body) body.textContent = full; scrollBottom(); }
        } catch (e) { /* 不完整片段忽略 */ }
      }
    }
    if (body) body.classList.remove("typing");
    state.history.push({ role: "assistant", content: full });
  } catch (e) {
    if (body) { body.classList.remove("typing"); body.textContent = "⚠️ 网络错误：" + e.message; }
  }
}

// ----------------------------- 新建角色（含头像预览）-----------------------------
function parseExamples(text) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const examples = []; let cur = null;
  for (const line of lines) {
    if (line.startsWith("user:")) { cur = { user: line.slice(5).trim(), assistant: "" }; examples.push(cur); }
    else if (line.includes("：") && cur) { cur.assistant += line.split("：").slice(1).join("："); }
    else if (cur) { cur.assistant += line; }
  }
  return examples;
}

function collectFormSkill() {
  return {
    name: ($("#f-name")?.value?.trim()) || "未命名角色",
    description: ($("#f-desc")?.value?.trim()) || "",
    system_prompt: ($("#f-prompt")?.value?.trim()) || "",
    speech_style: ($("#f-style")?.value?.split("\n").map((s) => s.trim()).filter(Boolean)) || [],
    forbidden: ($("#f-forbidden")?.value?.split("\n").map((s) => s.trim()).filter(Boolean)) || [],
    examples: parseExamples($("#f-examples")?.value || ""),
  };
}

function openModal() {
  state.pendingAvatar = null;
  const prev = $("#f-avatar-preview"); if (prev) { prev.src = ""; prev.style.display = "none"; }
  const ph = $("#f-avatar-placeholder"); if (ph) ph.style.display = "";
  const modal = $("#modal"); if (modal) modal.classList.remove("hidden");
}
function closeModal() { const modal = $("#modal"); if (modal) modal.classList.add("hidden"); }

/** 上传头像到后端 */
async function uploadAvatarForSkill(skillId, file) {
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/avatar`, { method: "POST", body: fd });
    return res.ok;
  } catch (e) { console.warn("头像上传失败:", e); return false; }
}

async function saveAndUse(skill, persist) {
  if (persist) {
    const res = await fetch("/api/skills", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(skill) });
    const data = await res.json();
    if (state.pendingAvatar) { await uploadAvatarForSkill(data.id, state.pendingAvatar); state.pendingAvatar = null; }
    await loadSkills(); activateSkill(data.id);
  } else {
    state.current = skill; state.history = [];
    $("#char-name").textContent = skill.name;
    $("#char-desc").textContent = skill.description || "已激活（未保存）";
    if (state.pendingAvatar) {
      const reader = new FileReader();
      reader.onload = () => {
        const url = reader.result;
        const ca = $("#char-avatar"); if (ca) { ca.src = url; ca.style.display = ""; }
        const aa = $("#active-avatar"); if (aa) { aa.src = url; aa.style.display = ""; }
      };
      reader.readAsDataURL(state.pendingAvatar);
    } else { updateHeaderAvatar(null); updateActiveAvatar(null); }
    const as = $("#active-skill");
    if (as) { as.classList.remove("hidden"); $("#active-skill-name").textContent = skill.name; }
    clearMessages();
  }
  closeModal();
}

// ----------------------------- 事件绑定 -----------------------------
function bindEvents() {
  const btnSend = $("#btn-plus"); // safety check
  const sendBtn = $("#btn-send");
  if (sendBtn) sendBtn.onclick = sendMessage;

  const input = $("#input");
  if (input) {
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    input.addEventListener("input", () => autoGrow(input));
  }

  const clearBtn = $("#btn-clear");
  if (clearBtn) clearBtn.onclick = () => { state.history = []; clearMessages(); };

  // [+] / [×] 切换
  const plusBtn = $("#btn-plus");
  if (plusBtn) plusBtn.onclick = (e) => { e.stopPropagation(); toggleMenu(); };
  document.addEventListener("click", (e) => { if (!e.target.closest(".plus-wrap")) closeMenu(); });

  const deactBtn = $("#btn-deactivate");
  if (deactBtn) deactBtn.onclick = deactivate;
  const newBtn = $("#btn-new");
  if (newBtn) newBtn.onclick = () => { closeMenu(); openModal(); };
  const closeBtn = $("#btn-close-modal");
  if (closeBtn) closeBtn.onclick = closeModal;
  const useOnlyBtn = $("#btn-use-only");
  if (useOnlyBtn) useOnlyBtn.onclick = () => saveAndUse(collectFormSkill(), false);
  const saveUseBtn = $("#btn-save-use");
  if (saveUseBtn) saveUseBtn.onclick = () => saveAndUse(collectFormSkill(), true);

  // 导入 skill 文件
  const fileInput = $("#file-input");
  if (fileInput) fileInput.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const res = await fetch("/api/skills", { method: "POST", body: fd });
    const data = await res.json();
    const avatarFile = $("#avatar-input")?.files[0];
    if (avatarFile) { await uploadAvatarForSkill(data.id, avatarFile); $("#avatar-input").value = ""; }
    await loadSkills(); activateSkill(data.id); closeMenu();
    e.target.value = "";
  };

  // 弹窗内头像预览
  const fAvatarInput = $("#f-avatar-input");
  if (fAvatarInput) fAvatarInput.onchange = (e) => {
    const file = e.target.files[0]; if (!file) return;
    state.pendingAvatar = file;
    const reader = new FileReader();
    reader.onload = () => {
      const prev = $("#f-avatar-preview"); if (prev) { prev.src = reader.result; prev.style.display = ""; }
      const ph = $("#f-avatar-placeholder"); if (ph) ph.style.display = "none";
    };
    reader.readAsDataURL(file);
  };
}

function autoGrow(el) { if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 140px) + "px"; } }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// 启动
init();
