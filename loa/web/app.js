const state = {
  agents: [],
  providers: [],
  messages: [],
  busy: false,
};

const els = {
  statusBadge: document.querySelector("#statusBadge"),
  serverLine: document.querySelector("#serverLine"),
  agentList: document.querySelector("#agentList"),
  providerList: document.querySelector("#providerList"),
  agentSelect: document.querySelector("#agentSelect"),
  messages: document.querySelector("#messages"),
  form: document.querySelector("#chatForm"),
  input: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  clearButton: document.querySelector("#clearButton"),
  refreshButton: document.querySelector("#refreshButton"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function setStatus(kind, text) {
  els.statusBadge.className = `status ${kind}`;
  els.statusBadge.textContent = text;
}

function renderAgents() {
  els.agentSelect.innerHTML = "";
  els.agentList.innerHTML = "";

  for (const agent of state.agents) {
    const option = document.createElement("option");
    option.value = agent.name;
    option.textContent = agent.name;
    els.agentSelect.append(option);

    const row = document.createElement("button");
    row.type = "button";
    row.className = "row";
    row.dataset.agent = agent.name;
    row.innerHTML = `
      <span class="row-title">
        <span>${escapeHtml(agent.name)}</span>
        <span class="pill">${escapeHtml(agent.model)}</span>
      </span>
      <span class="meta">${escapeHtml(agent.provider)} · temp ${agent.temperature}</span>
    `;
    row.addEventListener("click", () => {
      els.agentSelect.value = agent.name;
      updateActiveAgent();
    });
    els.agentList.append(row);
  }

  updateActiveAgent();
}

function updateActiveAgent() {
  const selected = els.agentSelect.value;
  document.querySelectorAll("[data-agent]").forEach((row) => {
    row.classList.toggle("active", row.dataset.agent === selected);
  });
}

function renderProviders() {
  els.providerList.innerHTML = "";
  for (const provider of state.providers) {
    const row = document.createElement("div");
    row.className = "row";
    const models = provider.models || [];
    const detail = provider.ok
      ? `${provider.model_count} modeli`
      : provider.error || "Blad providera";
    row.innerHTML = `
      <span class="row-title">
        <span>${escapeHtml(provider.name)}</span>
        <span class="pill ${provider.ok ? "ok" : "error"}">${provider.ok ? "OK" : "ERR"}</span>
      </span>
      <span class="meta">${escapeHtml(detail)}</span>
      ${models.length ? `<span class="muted">${escapeHtml(models.slice(0, 4).join(", "))}</span>` : ""}
    `;
    els.providerList.append(row);
  }
}

function renderMessages() {
  els.messages.innerHTML = "";
  if (!state.messages.length) {
    const empty = document.createElement("div");
    empty.className = "message assistant";
    empty.innerHTML = `<span class="message-role">LoA</span><span>Gotowe.</span>`;
    els.messages.append(empty);
    return;
  }

  for (const message of state.messages) {
    const item = document.createElement("div");
    item.className = `message ${message.role}`;
    item.innerHTML = `
      <span class="message-role">${escapeHtml(message.label)}</span>
      <span>${escapeHtml(message.content)}</span>
    `;
    els.messages.append(item);
  }
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function refresh() {
  setStatus("", "Sprawdzanie");
  try {
    const [health, agents, providerModels] = await Promise.all([
      api("/api/health"),
      api("/api/agents"),
      api("/api/provider-models"),
    ]);
    state.agents = agents.agents;
    state.providers = providerModels.providers;
    els.serverLine.textContent = `${health.providers.length} providerow · ${health.agents.length} agentow`;
    renderAgents();
    renderProviders();
    setStatus("ok", "Online");
  } catch (error) {
    setStatus("error", "Blad");
    state.messages.push({
      role: "error",
      label: "System",
      content: error.message,
    });
    renderMessages();
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const content = els.input.value.trim();
  if (!content || state.busy) {
    return;
  }

  const agent = els.agentSelect.value;
  state.messages.push({ role: "user", label: "Ty", content });
  renderMessages();
  els.input.value = "";
  setBusy(true);

  const history = state.messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .slice(0, -1)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));

  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ agent, message: content, history }),
    });
    state.messages.push({
      role: "assistant",
      label: `${result.agent} · ${result.model}`,
      content: result.message,
    });
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
  } finally {
    setBusy(false);
    renderMessages();
  }
}

function setBusy(busy) {
  state.busy = busy;
  els.sendButton.disabled = busy;
  els.sendButton.textContent = busy ? "Czekaj" : "Wyslij";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

els.form.addEventListener("submit", sendMessage);
els.agentSelect.addEventListener("change", updateActiveAgent);
els.clearButton.addEventListener("click", () => {
  state.messages = [];
  renderMessages();
});
els.refreshButton.addEventListener("click", refresh);
els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    els.form.requestSubmit();
  }
});

renderMessages();
refresh();
