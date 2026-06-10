from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from loa.config import ProviderConfig
from loa.providers import OllamaProvider, OpenAICompatibleProvider


class ProviderServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "ProviderServer":
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class OllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._json({"models": [{"name": "tiny:latest"}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/chat":
            self._json(
                {
                    "message": {"role": "assistant", "content": "hello"},
                    "prompt_eval_count": 2,
                    "eval_count": 1,
                }
            )
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class OpenAIHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._json({"data": [{"id": "agent"}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/v1/chat/completions":
            self._json(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "remote hello",
                            }
                        }
                    ],
                    "usage": {"completion_tokens": 2},
                }
            )
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ProviderTests(unittest.TestCase):
    def test_ollama_provider(self) -> None:
        with ProviderServer(OllamaHandler) as server:
            provider = OllamaProvider(
                ProviderConfig(
                    name="local",
                    type="ollama",
                    base_url=server.url,
                    timeout_seconds=5,
                )
            )
            self.assertEqual(provider.list_models(), ["tiny:latest"])
            result = provider.chat(
                model="tiny:latest",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                max_tokens=12,
            )

        self.assertEqual(result.content, "hello")
        self.assertEqual(result.usage["completion_tokens"], 1)

    def test_openai_provider(self) -> None:
        with ProviderServer(OpenAIHandler) as server:
            provider = OpenAICompatibleProvider(
                ProviderConfig(
                    name="remote",
                    type="openai-compatible",
                    base_url=server.url + "/v1",
                    api_key="token",
                    timeout_seconds=5,
                )
            )
            self.assertEqual(provider.list_models(), ["agent"])
            result = provider.chat(
                model="agent",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                max_tokens=12,
            )

        self.assertEqual(result.content, "remote hello")
        self.assertEqual(result.usage["completion_tokens"], 2)


if __name__ == "__main__":
    unittest.main()
