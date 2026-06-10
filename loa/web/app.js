const state = {
  agents: [],
  providers: [],
  nodes: [],
  selectedAgent: "",
  selectedProvider: "",
  selectedNode: "",
  messages: [],
  busy: false,
};

const els = {
  statusBadge: document.querySelector("#statusBadge"),
  serverLine: document.querySelector("#serverLine"),
  agentList: document.querySelector("#agentList"),
  providerList: document.querySelector("#providerList"),
  providerForm: document.querySelector("#providerForm"),
  providerNameInput: document.querySelector("#providerNameInput"),
  providerTypeInput: document.querySelector("#providerTypeInput"),
  providerBaseUrlInput: document.querySelector("#providerBaseUrlInput"),
  providerApiKeyInput: document.querySelector("#providerApiKeyInput"),
  providerTimeoutInput: document.querySelector("#providerTimeoutInput"),
  deleteProviderButton: document.querySelector("#deleteProviderButton"),
  newProviderButton: document.querySelector("#newProviderButton"),
  nodeList: document.querySelector("#nodeList"),
  agentSelect: document.querySelector("#agentSelect"),
  agentForm: document.querySelector("#agentForm"),
  agentNameInput: document.querySelector("#agentNameInput"),
  providerSelect: document.querySelector("#providerSelect"),
  modelInput: document.querySelector("#modelInput"),
  modelOptions: document.querySelector("#modelOptions"),
  systemInput: document.querySelector("#systemInput"),
  temperatureInput: document.querySelector("#temperatureInput"),
  maxTokensInput: document.querySelector("#maxTokensInput"),
  deleteAgentButton: document.querySelector("#deleteAgentButton"),
  newAgentButton: document.querySelector("#newAgentButton"),
  nodeForm: document.querySelector("#nodeForm"),
  nodeNameInput: document.querySelector("#nodeNameInput"),
  nodeUrlInput: document.querySelector("#nodeUrlInput"),
  nodeTokenInput: document.querySelector("#nodeTokenInput"),
  nodeWeightInput: document.querySelector("#nodeWeightInput"),
  nodeEnabledInput: document.querySelector("#nodeEnabledInput"),
  nodeRolesInput: document.querySelector("#nodeRolesInput"),
  deleteNodeButton: document.querySelector("#deleteNodeButton"),
  newNodeButton: document.querySelector("#newNodeButton"),
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
      <span class="meta">${escapeHtml(agent.provider)} - temp ${agent.temperature}</span>
    `;
    row.addEventListener("click", () => {
      selectAgent(agent.name);
    });
    els.agentList.append(row);
  }

  if (!state.selectedAgent && state.agents.length) {
    state.selectedAgent = state.agents[0].name;
  }
  if (state.selectedAgent) {
    els.agentSelect.value = state.selectedAgent;
  }
  updateActiveAgent();
  fillAgentForm();
}

function updateActiveAgent() {
  const selected = els.agentSelect.value;
  state.selectedAgent = selected;
  document.querySelectorAll("[data-agent]").forEach((row) => {
    row.classList.toggle("active", row.dataset.agent === selected);
  });
}

function selectAgent(name) {
  state.selectedAgent = name;
  els.agentSelect.value = name;
  updateActiveAgent();
  fillAgentForm();
}

function renderProviderSelect() {
  els.providerSelect.innerHTML = "";
  for (const provider of state.providers) {
    const option = document.createElement("option");
    option.value = provider.name;
    option.textContent = provider.name;
    els.providerSelect.append(option);
  }
  fillModelOptions();
}

function fillModelOptions() {
  const providerName = els.providerSelect.value;
  const provider = state.providers.find((item) => item.name === providerName);
  els.modelOptions.innerHTML = "";
  for (const model of provider?.models || []) {
    const option = document.createElement("option");
    option.value = model;
    els.modelOptions.append(option);
  }
}

function fillAgentForm() {
  const agent = state.agents.find((item) => item.name === state.selectedAgent);
  els.deleteAgentButton.disabled = !agent || state.agents.length <= 1;
  if (!agent) {
    els.agentNameInput.value = "";
    els.modelInput.value = "";
    els.systemInput.value = "";
    els.temperatureInput.value = "0.2";
    els.maxTokensInput.value = "512";
    return;
  }
  els.agentNameInput.value = agent.name;
  els.providerSelect.value = agent.provider;
  fillModelOptions();
  els.modelInput.value = agent.model;
  els.systemInput.value = agent.system || "";
  els.temperatureInput.value = agent.temperature;
  els.maxTokensInput.value = agent.max_tokens ?? "";
}

function renderProviders() {
  els.providerList.innerHTML = "";
  for (const provider of state.providers) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "row";
    row.dataset.provider = provider.name;
    const models = provider.models || [];
    const detail = provider.ok
      ? `${provider.model_count} modeli`
      : provider.error || "Blad providera";
    row.innerHTML = `
      <span class="row-title">
        <span>${escapeHtml(provider.name)}</span>
        <span class="pill ${provider.ok ? "ok" : "error"}">${provider.ok ? "OK" : "ERR"}</span>
      </span>
      <span class="meta">${escapeHtml(provider.type || "")} - ${escapeHtml(detail)}</span>
      ${models.length ? `<span class="muted">${escapeHtml(models.slice(0, 4).join(", "))}</span>` : ""}
    `;
    row.addEventListener("click", () => {
      selectProvider(provider.name);
    });
    els.providerList.append(row);
  }

  if (!state.selectedProvider && state.providers.length) {
    state.selectedProvider = state.providers[0].name;
  }
  updateActiveProvider();
  fillProviderForm();
}

function updateActiveProvider() {
  document.querySelectorAll("[data-provider]").forEach((row) => {
    row.classList.toggle("active", row.dataset.provider === state.selectedProvider);
  });
}

function selectProvider(name) {
  state.selectedProvider = name;
  updateActiveProvider();
  fillProviderForm();
}

function fillProviderForm() {
  const provider = state.providers.find((item) => item.name === state.selectedProvider);
  const usedByAgent = state.agents.some((agent) => agent.provider === provider?.name);
  els.deleteProviderButton.disabled = !provider || state.providers.length <= 1 || usedByAgent;
  if (!provider) {
    els.providerNameInput.value = "";
    els.providerTypeInput.value = "openai-compatible";
    els.providerBaseUrlInput.value = "";
    els.providerApiKeyInput.value = "";
    els.providerApiKeyInput.placeholder = "opcjonalnie";
    els.providerTimeoutInput.value = "120";
    return;
  }
  els.providerNameInput.value = provider.name;
  els.providerTypeInput.value = provider.type || "openai-compatible";
  els.providerBaseUrlInput.value = provider.base_url || "";
  els.providerApiKeyInput.value = "";
  els.providerApiKeyInput.placeholder = provider.has_api_key
    ? "klucz zapisany, zostaw puste aby zachowac"
    : "opcjonalnie";
  els.providerTimeoutInput.value = provider.timeout_seconds || 120;
}

function renderNodes() {
  els.nodeList.innerHTML = "";

  for (const node of state.nodes) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "row";
    row.dataset.node = node.name;
    const status = node.enabled ? (node.status || "unknown") : "disabled";
    const ok = node.ok && node.enabled;
    const latency = Number.isFinite(node.latency_ms) ? ` - ${node.latency_ms} ms` : "";
    const roles = (node.roles || []).join(", ");
    row.innerHTML = `
      <span class="row-title">
        <span>${escapeHtml(node.name)}</span>
        <span class="pill ${ok ? "ok" : "error"}">${escapeHtml(status)}</span>
      </span>
      <span class="meta">${escapeHtml(node.url)}${latency}</span>
      <span class="muted">${escapeHtml(roles || "chat")}</span>
    `;
    row.addEventListener("click", () => {
      selectNode(node.name);
    });
    els.nodeList.append(row);
  }

  if (!state.selectedNode && state.nodes.length) {
    state.selectedNode = state.nodes[0].name;
  }
  updateActiveNode();
  fillNodeForm();
}

function updateActiveNode() {
  document.querySelectorAll("[data-node]").forEach((row) => {
    row.classList.toggle("active", row.dataset.node === state.selectedNode);
  });
}

function selectNode(name) {
  state.selectedNode = name;
  updateActiveNode();
  fillNodeForm();
}

function fillNodeForm() {
  const node = state.nodes.find((item) => item.name === state.selectedNode);
  els.deleteNodeButton.disabled = !node;
  if (!node) {
    els.nodeNameInput.value = "";
    els.nodeUrlInput.value = "";
    els.nodeTokenInput.value = "";
    els.nodeTokenInput.placeholder = "opcjonalnie";
    els.nodeWeightInput.value = "1";
    els.nodeEnabledInput.checked = true;
    els.nodeRolesInput.value = "chat";
    return;
  }
  els.nodeNameInput.value = node.name;
  els.nodeUrlInput.value = node.url;
  els.nodeTokenInput.value = "";
  els.nodeTokenInput.placeholder = node.has_token
    ? "token zapisany, zostaw puste aby zachowac"
    : "opcjonalnie";
  els.nodeWeightInput.value = node.weight || 1;
  els.nodeEnabledInput.checked = Boolean(node.enabled);
  els.nodeRolesInput.value = (node.roles || ["chat"]).join(", ");
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
    const [health, agents, providers, providerModels, nodes, nodeStatuses] = await Promise.all([
      api("/api/health"),
      api("/api/agents"),
      api("/api/providers"),
      api("/api/provider-models"),
      api("/api/nodes"),
      api("/api/nodes/status"),
    ]);
    state.agents = agents.agents;
    const detailByName = new Map(providers.providers.map((provider) => [provider.name, provider]));
    state.providers = providerModels.providers.map((provider) => ({
      ...(detailByName.get(provider.name) || {}),
      ...provider,
    }));
    const statusByName = new Map(nodeStatuses.nodes.map((node) => [node.name, node]));
    state.nodes = nodes.nodes.map((node) => ({
      ...node,
      ...(statusByName.get(node.name) || {}),
    }));
    els.serverLine.textContent = `${health.providers.length} providerow - ${health.agents.length} agentow - ${state.nodes.length} node'ow`;
    renderProviderSelect();
    renderAgents();
    renderProviders();
    renderNodes();
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

async function saveProvider(event) {
  event.preventDefault();
  const payload = {
    name: els.providerNameInput.value.trim(),
    type: els.providerTypeInput.value,
    base_url: els.providerBaseUrlInput.value.trim(),
    api_key: els.providerApiKeyInput.value.trim() || undefined,
    timeout_seconds: Number(els.providerTimeoutInput.value || 120),
  };
  try {
    const result = await api("/api/providers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedProvider = result.provider;
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Zapisano provider ${result.provider}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

async function deleteProvider() {
  const name = els.providerNameInput.value.trim();
  if (!name) {
    return;
  }
  try {
    await api(`/api/providers/${encodeURIComponent(name)}`, { method: "DELETE" });
    state.selectedProvider = "";
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Usunieto provider ${name}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

function newProvider() {
  state.selectedProvider = "";
  updateActiveProvider();
  els.providerNameInput.value = "remote-loa";
  els.providerTypeInput.value = "openai-compatible";
  els.providerBaseUrlInput.value = "";
  els.providerApiKeyInput.value = "";
  els.providerApiKeyInput.placeholder = "opcjonalnie";
  els.providerTimeoutInput.value = "120";
  els.deleteProviderButton.disabled = true;
  els.providerNameInput.focus();
}

async function saveNode(event) {
  event.preventDefault();
  const payload = {
    name: els.nodeNameInput.value.trim(),
    url: els.nodeUrlInput.value.trim(),
    token: els.nodeTokenInput.value.trim() || undefined,
    enabled: els.nodeEnabledInput.checked,
    weight: Number(els.nodeWeightInput.value || 1),
    roles: els.nodeRolesInput.value
      .split(",")
      .map((role) => role.trim())
      .filter(Boolean),
  };
  try {
    const result = await api("/api/nodes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedNode = result.node;
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Zapisano node ${result.node}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

async function deleteNode() {
  const name = els.nodeNameInput.value.trim();
  if (!name) {
    return;
  }
  try {
    await api(`/api/nodes/${encodeURIComponent(name)}`, { method: "DELETE" });
    state.selectedNode = "";
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Usunieto node ${name}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

function newNode() {
  state.selectedNode = "";
  updateActiveNode();
  els.nodeNameInput.value = "node-" + String(state.nodes.length + 1);
  els.nodeUrlInput.value = "";
  els.nodeTokenInput.value = "";
  els.nodeTokenInput.placeholder = "opcjonalnie";
  els.nodeWeightInput.value = "1";
  els.nodeEnabledInput.checked = true;
  els.nodeRolesInput.value = "chat";
  els.deleteNodeButton.disabled = true;
  els.nodeNameInput.focus();
}

async function saveAgent(event) {
  event.preventDefault();
  const payload = {
    name: els.agentNameInput.value.trim(),
    provider: els.providerSelect.value,
    model: els.modelInput.value.trim(),
    system: els.systemInput.value,
    temperature: Number(els.temperatureInput.value || 0.2),
    max_tokens: els.maxTokensInput.value ? Number(els.maxTokensInput.value) : null,
  };
  try {
    const result = await api("/api/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedAgent = result.agent;
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Zapisano agenta ${result.agent}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

async function deleteAgent() {
  const name = els.agentNameInput.value.trim();
  if (!name || state.agents.length <= 1) {
    return;
  }
  try {
    await api(`/api/agents/${encodeURIComponent(name)}`, { method: "DELETE" });
    state.selectedAgent = "";
    await refresh();
    state.messages.push({
      role: "assistant",
      label: "LoA",
      content: `Usunieto agenta ${name}.`,
    });
    renderMessages();
  } catch (error) {
    state.messages.push({
      role: "error",
      label: "Blad",
      content: error.message,
    });
    renderMessages();
  }
}

function newAgent() {
  state.selectedAgent = "";
  updateActiveAgent();
  els.agentNameInput.value = "agent-" + String(state.agents.length + 1);
  els.providerSelect.value = state.providers[0]?.name || "";
  fillModelOptions();
  els.modelInput.value = state.providers[0]?.models?.[0] || "";
  els.systemInput.value = "";
  els.temperatureInput.value = "0.2";
  els.maxTokensInput.value = "512";
  els.deleteAgentButton.disabled = true;
  els.agentNameInput.focus();
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
      label: `${result.agent} - ${result.model}`,
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
els.agentForm.addEventListener("submit", saveAgent);
els.deleteAgentButton.addEventListener("click", deleteAgent);
els.newAgentButton.addEventListener("click", newAgent);
els.providerForm.addEventListener("submit", saveProvider);
els.deleteProviderButton.addEventListener("click", deleteProvider);
els.newProviderButton.addEventListener("click", newProvider);
els.nodeForm.addEventListener("submit", saveNode);
els.deleteNodeButton.addEventListener("click", deleteNode);
els.newNodeButton.addEventListener("click", newNode);
els.providerSelect.addEventListener("change", fillModelOptions);
els.agentSelect.addEventListener("change", () => {
  updateActiveAgent();
  fillAgentForm();
});
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
