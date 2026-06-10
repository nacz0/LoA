from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from . import __version__
from .agents import AgentError, AgentRuntime
from .config import AppConfig, ConfigError, load_config, read_config_data, write_config_data
from .providers import ProviderError


def run_server(
    config: AppConfig,
    runtime: AgentRuntime | None = None,
    config_path: Path | None = None,
) -> None:
    runtime = runtime or AgentRuntime(config)
    handler = make_handler(config, runtime, config_path=config_path)
    server = ThreadingHTTPServer((config.bind_host, config.bind_port), handler)
    try:
        print(f"LoA server listening on http://{config.bind_host}:{config.bind_port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping LoA server")
    finally:
        server.server_close()


def make_handler(
    config: AppConfig,
    runtime: AgentRuntime,
    config_path: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    web_root = Path(__file__).with_name("web")
    state: dict[str, Any] = {"config": config, "runtime": runtime}

    class LoARequestHandler(BaseHTTPRequestHandler):
        server_version = "LoA/0.1"

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            path = urlparse(self.path).path

            if path == "/":
                self._send_static(web_root / "index.html", "text/html; charset=utf-8")
                return

            if path == "/app.js":
                self._send_static(web_root / "app.js", "text/javascript; charset=utf-8")
                return

            if path == "/style.css":
                self._send_static(web_root / "style.css", "text/css; charset=utf-8")
                return

            if path == "/api/health":
                self._send_json(
                    {
                        "ok": True,
                        "app": "loa",
                        "agents": self._runtime().agent_names(),
                        "providers": self._runtime().provider_names(),
                        "config_writable": config_path is not None,
                    }
                )
                return

            if path == "/api/node/health":
                if not self._authorized():
                    return
                self._send_json(self._node_health())
                return

            if path == "/api/node/info":
                if not self._authorized():
                    return
                self._send_json(self._node_info())
                return

            if path == "/api/node/agents":
                if not self._authorized():
                    return
                self._send_json({"agents": self._agent_rows()})
                return

            if path == "/api/node/models":
                if not self._authorized():
                    return
                self._send_json({"providers": self._provider_model_report()})
                return

            if path == "/api/agents":
                if not self._authorized():
                    return
                self._send_json({"agents": self._agent_rows()})
                return

            if path == "/api/providers":
                if not self._authorized():
                    return
                self._send_json({"providers": self._provider_rows()})
                return

            if path == "/api/nodes":
                if not self._authorized():
                    return
                self._send_json({"nodes": self._node_rows()})
                return

            if path == "/api/nodes/status":
                if not self._authorized():
                    return
                self._send_json({"nodes": self._node_status_report()})
                return

            if path == "/api/provider-models":
                if not self._authorized():
                    return
                self._send_json({"providers": self._provider_model_report()})
                return

            if path == "/v1/models":
                if not self._authorized():
                    return
                self._send_json(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": name,
                                "object": "model",
                                "owned_by": "loa",
                            }
                            for name in self._runtime().agent_names()
                        ],
                    }
                )
                return

            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if not self._authorized():
                return

            if path == "/api/chat":
                self._handle_api_chat()
                return

            if path == "/api/agents":
                self._handle_save_agent()
                return

            if path == "/api/providers":
                self._handle_save_provider()
                return

            if path == "/api/nodes":
                self._handle_save_node()
                return

            if path == "/v1/chat/completions":
                self._handle_openai_chat()
                return

            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            if not self._authorized():
                return
            if path.startswith("/api/agents/"):
                name = path.rsplit("/", 1)[-1]
                self._handle_delete_agent(name)
                return
            if path.startswith("/api/providers/"):
                name = path.rsplit("/", 1)[-1]
                self._handle_delete_provider(name)
                return
            if path.startswith("/api/nodes/"):
                name = path.rsplit("/", 1)[-1]
                self._handle_delete_node(name)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _handle_api_chat(self) -> None:
            body = self._read_json()
            if body is None:
                return

            try:
                agent_name = body.get("agent")
                if "messages" in body:
                    result = self._runtime().chat_messages(
                        agent_name=agent_name,
                        messages=body["messages"],
                    )
                else:
                    message = body.get("message")
                    if not isinstance(message, str) or not message.strip():
                        self._send_error(HTTPStatus.BAD_REQUEST, "message is required")
                        return
                    history = body.get("history") or []
                    result = self._runtime().chat(
                        agent_name=agent_name,
                        message=message,
                        history=history,
                    )
            except (AgentError, ProviderError) as exc:
                self._send_error(HTTPStatus.BAD_GATEWAY, str(exc))
                return

            self._send_json(
                {
                    "agent": result.agent,
                    "provider": result.provider,
                    "model": result.model,
                    "message": result.content,
                    "usage": result.usage,
                }
            )

        def _handle_openai_chat(self) -> None:
            body = self._read_json()
            if body is None:
                return
            model = body.get("model")
            messages = body.get("messages")
            if not isinstance(model, str) or not model:
                self._send_error(HTTPStatus.BAD_REQUEST, "model is required")
                return
            if not isinstance(messages, list):
                self._send_error(HTTPStatus.BAD_REQUEST, "messages must be an array")
                return

            try:
                result = self._runtime().chat_messages(agent_name=model, messages=messages)
            except (AgentError, ProviderError) as exc:
                self._send_error(HTTPStatus.BAD_GATEWAY, str(exc))
                return

            self._send_json(
                {
                    "id": f"loa-{result.agent}",
                    "object": "chat.completion",
                    "model": result.agent,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": result.content,
                            },
                        }
                    ],
                    "usage": result.usage,
                }
            )

        def _handle_save_agent(self) -> None:
            body = self._read_json()
            if body is None:
                return
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return

            try:
                raw = read_config_data(config_path)
                agents = raw.setdefault("agents", {})
                if not isinstance(agents, dict):
                    raise ConfigError("agents must be an object")
                name = _clean_agent_name(body.get("name"))
                provider = str(body.get("provider", "")).strip()
                model = str(body.get("model", "")).strip()
                if provider not in self._config().providers:
                    raise ConfigError(f"provider {provider!r} is not configured")
                if not model:
                    raise ConfigError("model is required")
                agents[name] = {
                    "provider": provider,
                    "model": model,
                    "system": str(body.get("system", "")),
                    "temperature": float(body.get("temperature", 0.2)),
                    "max_tokens": _optional_int(body.get("max_tokens", 512)),
                }
                if "default_agent" not in raw:
                    raw["default_agent"] = name
                write_config_data(config_path, raw)
                self._reload_config()
            except (ConfigError, TypeError, ValueError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True, "agent": name})

        def _handle_save_provider(self) -> None:
            body = self._read_json()
            if body is None:
                return
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return

            try:
                raw = read_config_data(config_path)
                providers = raw.setdefault("providers", {})
                if not isinstance(providers, dict):
                    raise ConfigError("providers must be an object")
                name = _clean_config_name(body.get("name"), "provider")
                provider_type = str(body.get("type", "")).strip()
                base_url = str(body.get("base_url", "")).strip().rstrip("/")
                if provider_type not in {"ollama", "openai-compatible", "openai"}:
                    raise ConfigError("provider type must be ollama or openai-compatible")
                if not base_url:
                    raise ConfigError("provider base_url is required")
                existing = providers.get(name)
                if not isinstance(existing, dict):
                    existing = {}
                api_key = body.get("api_key")
                if api_key is None or api_key == "":
                    api_key = existing.get("api_key")
                providers[name] = {
                    "type": provider_type,
                    "base_url": base_url,
                    "api_key": str(api_key) if api_key else None,
                    "timeout_seconds": float(body.get("timeout_seconds", 120)),
                }
                write_config_data(config_path, raw)
                self._reload_config()
            except (ConfigError, ProviderError, TypeError, ValueError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True, "provider": name})

        def _handle_delete_provider(self, raw_name: str) -> None:
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return
            name = raw_name.strip()
            try:
                raw = read_config_data(config_path)
                providers = raw.get("providers")
                agents = raw.get("agents")
                if not isinstance(providers, dict) or name not in providers:
                    self._send_error(HTTPStatus.NOT_FOUND, "provider not found")
                    return
                if len(providers) == 1:
                    raise ConfigError("cannot delete the last provider")
                if isinstance(agents, dict):
                    users = [
                        agent_name
                        for agent_name, agent in agents.items()
                        if isinstance(agent, dict) and agent.get("provider") == name
                    ]
                    if users:
                        raise ConfigError(
                            f"provider is used by agents: {', '.join(sorted(users))}"
                        )
                del providers[name]
                write_config_data(config_path, raw)
                self._reload_config()
            except (ConfigError, ProviderError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True})

        def _handle_delete_agent(self, raw_name: str) -> None:
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return
            name = raw_name.strip()
            try:
                raw = read_config_data(config_path)
                agents = raw.get("agents")
                if not isinstance(agents, dict) or name not in agents:
                    self._send_error(HTTPStatus.NOT_FOUND, "agent not found")
                    return
                if len(agents) == 1:
                    raise ConfigError("cannot delete the last agent")
                del agents[name]
                if raw.get("default_agent") == name:
                    raw["default_agent"] = sorted(agents)[0]
                write_config_data(config_path, raw)
                self._reload_config()
            except ConfigError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True})

        def _handle_save_node(self) -> None:
            body = self._read_json()
            if body is None:
                return
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return

            try:
                raw = read_config_data(config_path)
                nodes = raw.setdefault("nodes", {})
                if not isinstance(nodes, dict):
                    raise ConfigError("nodes must be an object")
                name = _clean_config_name(body.get("name"), "node")
                url = str(body.get("url", "")).strip().rstrip("/")
                if not url:
                    raise ConfigError("node url is required")
                existing = nodes.get(name)
                if not isinstance(existing, dict):
                    existing = {}
                token = body.get("token")
                if token is None or token == "":
                    token = existing.get("token")
                roles = _parse_roles(body.get("roles", ["chat"]))
                nodes[name] = {
                    "url": url,
                    "enabled": bool(body.get("enabled", True)),
                    "token": str(token) if token else None,
                    "weight": int(body.get("weight", 1)),
                    "roles": roles,
                }
                write_config_data(config_path, raw)
                self._reload_config()
            except (ConfigError, TypeError, ValueError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True, "node": name})

        def _handle_delete_node(self, raw_name: str) -> None:
            if config_path is None:
                self._send_error(HTTPStatus.CONFLICT, "config file is not writable")
                return
            name = raw_name.strip()
            try:
                raw = read_config_data(config_path)
                nodes = raw.get("nodes")
                if not isinstance(nodes, dict) or name not in nodes:
                    self._send_error(HTTPStatus.NOT_FOUND, "node not found")
                    return
                del nodes[name]
                write_config_data(config_path, raw)
                self._reload_config()
            except ConfigError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json({"ok": True})

        def _authorized(self) -> bool:
            current_token = self._config().api_token
            if not current_token:
                return True
            header = self.headers.get("Authorization", "")
            if header == f"Bearer {current_token}":
                return True
            self._send_error(HTTPStatus.UNAUTHORIZED, "missing or invalid token")
            return False

        def _node_health(self) -> dict[str, Any]:
            return {
                "ok": True,
                "app": "loa",
                "version": __version__,
                "agents": self._runtime().agent_names(),
                "providers": self._runtime().provider_names(),
                "auth_enabled": bool(self._config().api_token),
            }

        def _node_info(self) -> dict[str, Any]:
            config = self._config()
            return {
                **self._node_health(),
                "server": {
                    "bind_host": config.bind_host,
                    "bind_port": config.bind_port,
                },
                "agents_detail": self._agent_rows(),
                "providers_detail": self._provider_rows(),
                "nodes": self._node_rows(),
                "endpoints": [
                    "/api/node/health",
                    "/api/node/info",
                    "/api/node/agents",
                    "/api/node/models",
                    "/api/chat",
                    "/v1/chat/completions",
                ],
            }

        def _agent_rows(self) -> list[dict[str, Any]]:
            return [
                {
                    "name": agent.name,
                    "provider": agent.provider,
                    "model": agent.model,
                    "system": agent.system,
                    "temperature": agent.temperature,
                    "max_tokens": agent.max_tokens,
                }
                for agent in self._config().agents.values()
            ]

        def _provider_rows(self) -> list[dict[str, Any]]:
            return [
                {
                    "name": provider.name,
                    "type": provider.type,
                    "base_url": provider.base_url,
                    "has_api_key": bool(provider.api_key),
                    "timeout_seconds": provider.timeout_seconds,
                }
                for provider in self._config().providers.values()
            ]

        def _node_rows(self) -> list[dict[str, Any]]:
            return [
                {
                    "name": node.name,
                    "url": node.url,
                    "enabled": node.enabled,
                    "has_token": bool(node.token),
                    "weight": node.weight,
                    "roles": list(node.roles),
                }
                for node in self._config().nodes.values()
            ]

        def _node_status_report(self) -> list[dict[str, Any]]:
            return [_probe_node(node) for node in self._config().nodes.values()]

        def _provider_model_report(self) -> list[dict[str, Any]]:
            providers: list[dict[str, Any]] = []
            runtime = self._runtime()
            for name in runtime.provider_names():
                provider = runtime.providers[name]
                try:
                    models = provider.list_models()
                    providers.append(
                        {
                            "name": name,
                            "ok": True,
                            "models": models,
                            "model_count": len(models),
                        }
                    )
                except ProviderError as exc:
                    providers.append(
                        {
                            "name": name,
                            "ok": False,
                            "error": str(exc),
                            "models": [],
                            "model_count": 0,
                        }
                    )
            return providers

        def _config(self) -> AppConfig:
            return state["config"]

        def _runtime(self) -> AgentRuntime:
            return state["runtime"]

        def _reload_config(self) -> None:
            if config_path is None:
                return
            new_config = load_config(config_path)
            state["config"] = new_config
            state["runtime"] = AgentRuntime(new_config)

        def _read_json(self) -> dict[str, Any] | None:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid content length")
                return None
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid JSON")
                return None
            if not isinstance(body, dict):
                self._send_error(HTTPStatus.BAD_REQUEST, "expected JSON object")
                return None
            return body

        def _send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.end_headers()
            self.wfile.write(data)

        def _send_static(self, path: Path, content_type: str) -> None:
            try:
                data = path.read_bytes()
            except OSError:
                self._send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"ok": False, "error": message}, status=status)

    return LoARequestHandler


def _clean_agent_name(value: object) -> str:
    return _clean_config_name(value, "agent")


def _clean_config_name(value: object, label: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise ConfigError(f"{label} name is required")
    if not all(char.isalnum() or char in {"_", "-"} for char in name):
        raise ConfigError(f"{label} name may only contain letters, digits, _ and -")
    return name


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _parse_roles(value: object) -> list[str]:
    if isinstance(value, str):
        roles = [role.strip() for role in value.split(",")]
    elif isinstance(value, list):
        roles = [str(role).strip() for role in value]
    else:
        raise ConfigError("node roles must be a list or comma-separated string")
    roles = [role for role in roles if role]
    if not roles:
        raise ConfigError("node roles must not be empty")
    return roles


def _probe_node(node: Any) -> dict[str, Any]:
    started = time.monotonic()
    base = {
        "name": node.name,
        "url": node.url,
        "enabled": node.enabled,
        "weight": node.weight,
        "roles": list(node.roles),
    }
    if not node.enabled:
        return {**base, "ok": False, "status": "disabled", "latency_ms": None}

    headers = {"Accept": "application/json"}
    if node.token:
        headers["Authorization"] = f"Bearer {node.token}"
    req = request.Request(
        node.url.rstrip("/") + "/api/node/health",
        headers=headers,
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        return {
            **base,
            "ok": False,
            "status": "error",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": f"HTTP {exc.code} {exc.reason}",
        }
    except error.URLError as exc:
        return {
            **base,
            "ok": False,
            "status": "offline",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": str(exc.reason),
        }
    except (json.JSONDecodeError, OSError) as exc:
        return {
            **base,
            "ok": False,
            "status": "error",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": str(exc),
        }
    if not isinstance(body, dict):
        body = {}
    return {
        **base,
        "ok": bool(body.get("ok")),
        "status": "online" if body.get("ok") else "error",
        "latency_ms": round((time.monotonic() - started) * 1000),
        "app": body.get("app"),
        "version": body.get("version"),
        "agents": body.get("agents", []),
        "providers": body.get("providers", []),
        "auth_enabled": bool(body.get("auth_enabled")),
    }
