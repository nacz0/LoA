# LoA

LoA is a lightweight local AI agent orchestrator. The initial target is a weak-to-mid home machine, such as a PC with GTX 1080 and 16 GB RAM, while keeping a path open for using other computers on the LAN as remote inference nodes.

The project starts deliberately small:

- no required Python dependencies;
- local Ollama adapter;
- generic OpenAI-compatible adapter;
- named agents with model, provider, prompt, temperature, and token limits;
- local HTTP API;
- minimal OpenAI-compatible `/v1/models` and `/v1/chat/completions` endpoints so another LoA node can be used over the network.

Official API references used for this direction:

- [Ollama API](https://docs.ollama.com/api/introduction)
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [llama.cpp HTTP server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)

## Quick Start

Create an editable config:

```powershell
python -m loa init-config
```

List configured agents:

```powershell
python -m loa agents
```

Check whether configured providers are reachable:

```powershell
python -m loa doctor
```

List models from local Ollama:

```powershell
python -m loa models --provider local-ollama
```

Chat with the default agent:

```powershell
python -m loa chat "Napisz krótkie streszczenie projektu LoA."
```

Run the local API:

```powershell
python -m loa serve --host 127.0.0.1 --port 8765
```

Open the web UI:

```text
http://127.0.0.1:8765/
```

The UI can chat with agents and manage them. Agent edits are persisted to
`loa.config.json`.

Probe a node:

```powershell
python -m loa node-probe http://127.0.0.1:8765
```

Node metadata endpoints:

```text
GET /api/node/health
GET /api/node/info
GET /api/node/agents
GET /api/node/models
GET /api/nodes/status
```

The web UI can add, edit, delete, and probe LAN nodes. Node entries are
persisted to `loa.config.json`; saved tokens are not returned by the list API.

To route an agent to another LoA computer, add a provider in the web UI:

- type: `openai-compatible`
- base URL: `http://REMOTE_IP:8765/v1`
- API key: the remote node token, if one is configured

Then create or edit an agent and choose that provider. The model field should
match an agent exposed by the remote LoA node, for example `assistant`.

## Troubleshooting

`Config already exists: loa.config.json` means the local config file is already present. Edit it directly, or overwrite it intentionally:

```powershell
python -m loa init-config --force
```

`connection refused` for `http://localhost:11434/api/tags` means LoA cannot reach Ollama. Start Ollama first, then pull or run a model:

```powershell
ollama serve
ollama pull llama3.2
python -m loa models --provider local-ollama
```

On Windows, if Ollama was installed with the desktop installer, opening the Ollama app may already start the background service. The default model in LoA is `llama3.2:latest`, which is a good small-model starting point on weak hardware.

## Configuration

By default LoA looks for `loa.config.json` in the current directory. You can also pass `--config` or set `LOA_CONFIG`.

The default generated config assumes Ollama is running at `http://localhost:11434`:

```json
{
  "providers": {
    "local-ollama": {
      "type": "ollama",
      "base_url": "http://localhost:11434",
      "timeout_seconds": 120
    }
  },
  "agents": {
    "assistant": {
      "provider": "local-ollama",
      "model": "llama3.2:latest",
      "system": "Jestes lokalnym, zwiezlym asystentem AI.",
      "temperature": 0.2,
      "max_tokens": 512
    }
  }
}
```

For a remote LoA node, add an OpenAI-compatible provider pointing at its `/v1` endpoint:

```json
{
  "providers": {
    "garage-pc": {
      "type": "openai-compatible",
      "base_url": "http://192.168.1.40:8765/v1",
      "api_key": "shared-lan-token"
    }
  },
  "agents": {
    "remote-coder": {
      "provider": "garage-pc",
      "model": "coder",
      "system": "Pomagasz przy kodzie, odpowiadasz konkretnie.",
      "temperature": 0.1,
      "max_tokens": 1024
    }
  }
}
```

## Hardware Bias

For GTX 1080 and 16 GB RAM, treat 3B-8B quantized models as the default lane. Prefer Q4/Q5 GGUF variants, modest context windows, and one loaded model at a time. Larger models should run on a stronger LAN node instead of making the main machine unusable.

More detail is in [docs/hardware.md](docs/hardware.md).
