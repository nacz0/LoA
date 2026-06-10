# Architecture

LoA is split into small layers so it can run on weak machines and still grow into a LAN orchestrator.

## Goals

- Keep the first usable version dependency-light.
- Use existing LLM runtimes instead of embedding inference logic.
- Make local and remote models look the same to agents.
- Avoid assuming one best runtime. Ollama, llama.cpp server, vLLM, LM Studio, and a second LoA node can all fit behind provider adapters if they expose HTTP APIs.

## Core Components

### Agent Runtime

The runtime owns named agents. An agent is only configuration:

- provider name;
- model id;
- system prompt;
- sampling defaults;
- response token budget.

The runtime builds the chat message list and calls the chosen provider.

### Providers

Provider adapters hide the differences between runtimes:

- `ollama`: native Ollama `/api/chat` and `/api/tags`.
- `openai-compatible`: `/v1/chat/completions` and `/v1/models`.

The OpenAI-compatible adapter is important because many local runtimes expose that API shape, and LoA's own server exposes a minimal version for LAN use.

### Local API

The local server exposes:

- `GET /api/health`
- `GET /api/agents`
- `GET /api/providers`
- `POST /api/chat`
- `GET /v1/models`
- `POST /v1/chat/completions`

By default it binds to `127.0.0.1`. For LAN use, bind to `0.0.0.0` and set `api_token`.

### LAN Nodes

A stronger computer can run LoA or another OpenAI-compatible server. The main LoA instance can then add it as a provider.

Recommended LAN model:

1. Each machine runs its own inference runtime locally.
2. Each machine exposes only a small HTTP API on the home network.
3. The main machine routes specific agents to remote providers.
4. Later, add node health, load metrics, queue depth, model availability, and automatic routing.

## Why Not Start With a Heavy UI

A desktop UI is useful, but it should sit above the API. Starting with the API keeps the first version usable on weak hardware and avoids tying orchestration logic to one frontend framework.

Good next UI choices:

- simple web UI served by the same process;
- Tauri for a light desktop wrapper;
- Electron only if the app needs heavier desktop integration.
