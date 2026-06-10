from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_FILE = "loa.config.json"


class ConfigError(ValueError):
    """Raised when the LoA configuration is invalid."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    type: str
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class AgentConfig:
    name: str
    provider: str
    model: str
    system: str = ""
    temperature: float = 0.2
    max_tokens: int | None = 512


@dataclass(frozen=True)
class NodeConfig:
    name: str
    url: str
    enabled: bool = True
    weight: int = 1
    roles: tuple[str, ...] = ("chat",)


@dataclass(frozen=True)
class AppConfig:
    providers: dict[str, ProviderConfig]
    agents: dict[str, AgentConfig]
    nodes: dict[str, NodeConfig] = field(default_factory=dict)
    default_agent: str = "assistant"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    api_token: str | None = None


DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "bind_host": "127.0.0.1",
        "bind_port": 8765,
        "api_token": None,
    },
    "providers": {
        "local-ollama": {
            "type": "ollama",
            "base_url": "http://localhost:11434",
            "timeout_seconds": 120,
        }
    },
    "agents": {
        "assistant": {
            "provider": "local-ollama",
            "model": "llama3.2:latest",
            "system": "Jestes lokalnym, zwiezlym asystentem AI.",
            "temperature": 0.2,
            "max_tokens": 512,
        }
    },
    "nodes": {
        "local": {
            "url": "http://127.0.0.1:8765",
            "enabled": True,
            "weight": 1,
            "roles": ["chat"],
        }
    },
    "default_agent": "assistant",
}


def find_config_path(path: str | Path | None = None) -> Path | None:
    if path:
        return Path(path)

    env_path = os.environ.get("LOA_CONFIG")
    if env_path:
        return Path(env_path)

    cwd_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if cwd_path.exists():
        return cwd_path

    return None


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = find_config_path(path)
    if config_path is None:
        data = DEFAULT_CONFIG
    else:
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc

    return parse_config(data)


def parse_config(data: dict[str, Any]) -> AppConfig:
    providers_data = _require_mapping(data, "providers")
    agents_data = _require_mapping(data, "agents")
    server_data = data.get("server", {})
    if server_data is None:
        server_data = {}
    if not isinstance(server_data, dict):
        raise ConfigError("server must be an object")

    providers = {
        name: _parse_provider(name, value)
        for name, value in providers_data.items()
    }
    agents = {
        name: _parse_agent(name, value)
        for name, value in agents_data.items()
    }
    nodes = {
        name: _parse_node(name, value)
        for name, value in data.get("nodes", {}).items()
    }

    default_agent = str(data.get("default_agent", next(iter(agents), "assistant")))
    if default_agent not in agents:
        raise ConfigError(f"default_agent {default_agent!r} is not configured")

    for agent in agents.values():
        if agent.provider not in providers:
            raise ConfigError(
                f"agent {agent.name!r} references missing provider {agent.provider!r}"
            )

    api_token = server_data.get("api_token")
    env_token = os.environ.get("LOA_API_TOKEN")
    if env_token:
        api_token = env_token

    return AppConfig(
        providers=providers,
        agents=agents,
        nodes=nodes,
        default_agent=default_agent,
        bind_host=str(server_data.get("bind_host", "127.0.0.1")),
        bind_port=int(server_data.get("bind_port", 8765)),
        api_token=str(api_token) if api_token else None,
    )


def write_default_config(path: str | Path = DEFAULT_CONFIG_FILE, force: bool = False) -> Path:
    target = Path(path)
    if target.exists() and not force:
        raise ConfigError(f"Config already exists: {target}")
    target.write_text(
        json.dumps(DEFAULT_CONFIG, indent= two_space_indent(), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return target


def two_space_indent() -> int:
    return 2


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"{key} must be a non-empty object")
    return value


def _parse_provider(name: str, value: Any) -> ProviderConfig:
    if not isinstance(value, dict):
        raise ConfigError(f"provider {name!r} must be an object")
    provider_type = str(value.get("type", "")).strip()
    base_url = str(value.get("base_url", "")).strip()
    if not provider_type:
        raise ConfigError(f"provider {name!r} is missing type")
    if not base_url:
        raise ConfigError(f"provider {name!r} is missing base_url")
    api_key = value.get("api_key")
    return ProviderConfig(
        name=name,
        type=provider_type,
        base_url=base_url,
        api_key=str(api_key) if api_key else None,
        timeout_seconds=float(value.get("timeout_seconds", 120)),
    )


def _parse_agent(name: str, value: Any) -> AgentConfig:
    if not isinstance(value, dict):
        raise ConfigError(f"agent {name!r} must be an object")
    provider = str(value.get("provider", "")).strip()
    model = str(value.get("model", "")).strip()
    if not provider:
        raise ConfigError(f"agent {name!r} is missing provider")
    if not model:
        raise ConfigError(f"agent {name!r} is missing model")
    max_tokens = value.get("max_tokens", 512)
    return AgentConfig(
        name=name,
        provider=provider,
        model=model,
        system=str(value.get("system", "")),
        temperature=float(value.get("temperature", 0.2)),
        max_tokens=int(max_tokens) if max_tokens is not None else None,
    )


def _parse_node(name: str, value: Any) -> NodeConfig:
    if not isinstance(value, dict):
        raise ConfigError(f"node {name!r} must be an object")
    roles = value.get("roles", ["chat"])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ConfigError(f"node {name!r} roles must be a list of strings")
    return NodeConfig(
        name=name,
        url=str(value.get("url", "")).rstrip("/"),
        enabled=bool(value.get("enabled", True)),
        weight=int(value.get("weight", 1)),
        roles=tuple(roles),
    )
