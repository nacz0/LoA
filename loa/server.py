from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
from typing import Any
from urllib.parse import urlparse

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
    api_token = config.api_token
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

            if path == "/api/agents":
                if not self._authorized():
                    return
                self._send_json(
                    {
                        "agents": [
                            {
                                "name": agent.name,
                                "provider": agent.provider,
                                "model": agent.model,
                                "temperature": agent.temperature,
                                "max_tokens": agent.max_tokens,
                            }
                            for agent in self._config().agents.values()
                        ]
                    }
                )
                return

            if path == "/api/providers":
                if not self._authorized():
                    return
                self._send_json(
                    {
                        "providers": [
                            {
                                "name": provider.name,
                                "type": provider.type,
                                "base_url": provider.base_url,
                            }
                            for provider in self._config().providers.values()
                        ]
                    }
                )
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

        def _authorized(self) -> bool:
            if not api_token:
                return True
            header = self.headers.get("Authorization", "")
            if header == f"Bearer {api_token}":
                return True
            self._send_error(HTTPStatus.UNAUTHORIZED, "missing or invalid token")
            return False

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
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
    name = str(value or "").strip()
    if not name:
        raise ConfigError("agent name is required")
    if not all(char.isalnum() or char in {"_", "-"} for char in name):
        raise ConfigError("agent name may only contain letters, digits, _ and -")
    return name


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
