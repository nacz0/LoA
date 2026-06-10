from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib import request

from loa.agents import AgentRuntime
from loa.config import AgentConfig, AppConfig, NodeConfig, ProviderConfig
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

    def test_node_health_and_info(self) -> None:
        with request.urlopen(self.base_url + "/api/node/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))
        with request.urlopen(self.base_url + "/api/node/info", timeout=5) as response:
            info = json.loads(response.read().decode("utf-8"))

        self.assertTrue(health["ok"])
        self.assertEqual(health["app"], "loa")
        self.assertEqual(info["agents_detail"][0]["name"], "assistant")
        self.assertIn("/api/node/health", info["endpoints"])

    def test_disabled_node_status_is_reported_without_probe(self) -> None:
        config = AppConfig(
            providers=self.config.providers,
            agents=self.config.agents,
            nodes={
                "remote": NodeConfig(
                    name="remote",
                    url="http://127.0.0.1:1",
                    enabled=False,
                    weight=2,
                    roles=("chat",),
                )
            },
            default_agent="assistant",
        )
        handler = make_handler(
            config,
            AgentRuntime(config, providers=self.runtime.providers),
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with request.urlopen(
                f"http://{host}:{port}/api/nodes/status",
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(payload["nodes"][0]["name"], "remote")
        self.assertEqual(payload["nodes"][0]["status"], "disabled")


class WritableServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "loa.config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "providers": {
                        "local": {
                            "type": "ollama",
                            "base_url": "http://localhost:11434",
                        }
                    },
                    "agents": {
                        "assistant": {
                            "provider": "local",
                            "model": "llama3.2:latest",
                        }
                    },
                    "default_agent": "assistant",
                }
            ),
            encoding="utf-8",
        )
        self.config = AppConfig(
            providers={
                "local": ProviderConfig(
                    name="local",
                    type="ollama",
                    base_url="http://localhost:11434",
                )
            },
            agents={
                "assistant": AgentConfig(
                    name="assistant",
                    provider="local",
                    model="llama3.2:latest",
                )
            },
            default_agent="assistant",
        )
        self.runtime = AgentRuntime(
            self.config,
            providers={"local": FakeProvider(self.config.providers["local"])},
        )
        handler = make_handler(self.config, self.runtime, config_path=self.config_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def test_save_agent_updates_config_file(self) -> None:
        payload = {
            "name": "coder",
            "provider": "local",
            "model": "llama3.2:latest",
            "system": "code helper",
            "temperature": 0.1,
            "max_tokens": 256,
        }
        req = request.Request(
            self.base_url + "/api/agents",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(saved["agents"]["coder"]["system"], "code helper")

    def test_delete_agent_updates_config_file(self) -> None:
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        saved["agents"]["coder"] = {
            "provider": "local",
            "model": "llama3.2:latest",
        }
        self.config_path.write_text(json.dumps(saved), encoding="utf-8")
        req = request.Request(
            self.base_url + "/api/agents/coder",
            method="DELETE",
        )

        with request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertNotIn("coder", saved["agents"])

    def test_save_node_updates_config_file_without_listing_token(self) -> None:
        payload = {
            "name": "desktop",
            "url": "http://192.168.1.40:8765",
            "token": "shared-token",
            "enabled": True,
            "weight": 3,
            "roles": ["chat", "code"],
        }
        req = request.Request(
            self.base_url + "/api/nodes",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
        with request.urlopen(self.base_url + "/api/nodes", timeout=5) as response:
            listed = json.loads(response.read().decode("utf-8"))

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(saved["nodes"]["desktop"]["token"], "shared-token")
        self.assertTrue(listed["nodes"][0]["has_token"])
        self.assertNotIn("token", listed["nodes"][0])

    def test_delete_node_updates_config_file(self) -> None:
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        saved["nodes"] = {
            "desktop": {
                "url": "http://192.168.1.40:8765",
                "enabled": True,
                "weight": 1,
                "roles": ["chat"],
            }
        }
        self.config_path.write_text(json.dumps(saved), encoding="utf-8")
        req = request.Request(
            self.base_url + "/api/nodes/desktop",
            method="DELETE",
        )

        with request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertNotIn("desktop", saved["nodes"])


if __name__ == "__main__":
    unittest.main()
