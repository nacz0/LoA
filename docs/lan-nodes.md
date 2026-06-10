# LAN Nodes

LoA can use another home computer by treating it as an OpenAI-compatible provider.

## Run a Node

On the remote computer:

```powershell
$env:LOA_API_TOKEN = "shared-lan-token"
python -m loa serve --host 0.0.0.0 --port 8765
```

On the main computer, test it:

```powershell
python -m loa node-probe http://192.168.1.40:8765 --token shared-lan-token
```

Then configure it as a provider:

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

In that example, `coder` is an agent name configured on the remote node.

## Security Rules

- Bind to `127.0.0.1` unless you intentionally expose the node to LAN.
- Always use `api_token` for LAN.
- Do not expose this server directly to the internet.
- Prefer a firewall rule limited to your private subnet.

## Future Routing

The next layer should add:

- node health polling;
- queue depth;
- loaded model list;
- estimated tokens per second;
- RAM/VRAM pressure;
- routing policies such as local-first, fastest-node, cheapest-node, or pinned-agent.
