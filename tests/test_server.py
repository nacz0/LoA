from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib import request

from loa.agents import AgentRuntime
from loa.config import AgentConfig, AppConfig, ProviderConfig
from loa.providers import BaseProvider, ChatResult
from loa.server import make_handler


class FakeProvider(BaseProvider):
    def list_models(self) -> list[str]:
        return ["fake-model"]

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult:
        return ChatResult(
            provider=self.name,
            model=model,
            content="pong",
            usage={},
            raw={},
        )


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig(
            providers={
                "fake": ProviderConfig(
                    name="fake",
                    type="fake",
                    base_url="http://fake",
                )
            },
            agents={
                "assistant": AgentConfig(
                    name="assistant",
                    provider="fake",
                    model="fake-model",
                )
            },
            default_agent="assistant",
        )
        self.runtime = AgentRuntime(
            self.config,
            providers={"fake": FakeProvider(self.config.providers["fake"])},
        )
        handler = make_handler(self.config, self.runtime)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def test_serves_web_ui(self) -> None:
        with request.urlopen(self.base_url + "/", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("<title>LoA</title>", body)

    def test_provider_model_report(self) -> None:
        with request.urlopen(self.base_url + "/api/provider-models", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["providers"][0]["name"], "fake")
        self.assertEqual(payload["providers"][0]["models"], ["fake-model"])


if __name__ == "__main__":
    unittest.main()
