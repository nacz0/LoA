from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from loa.config import ConfigError, load_config, parse_config, write_default_config


class ConfigTests(unittest.TestCase):
    def test_parse_default_shape(self) -> None:
        config = parse_config(
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
                        "model": "llama3.2:3b",
                    }
                },
                "default_agent": "assistant",
            }
        )

        self.assertEqual(config.default_agent, "assistant")
        self.assertEqual(config.providers["local"].type, "ollama")
        self.assertEqual(config.agents["assistant"].provider, "local")

    def test_parse_nodes_with_token(self) -> None:
        config = parse_config(
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
                        "model": "llama3.2:3b",
                    }
                },
                "nodes": {
                    "desktop": {
                        "url": "http://192.168.1.40:8765/",
                        "token": "secret",
                        "enabled": True,
                        "weight": 3,
                        "roles": ["chat", "code"],
                    }
                },
                "default_agent": "assistant",
            }
        )

        node = config.nodes["desktop"]
        self.assertEqual(node.url, "http://192.168.1.40:8765")
        self.assertEqual(node.token, "secret")
        self.assertEqual(node.roles, ("chat", "code"))

    def test_missing_provider_is_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            parse_config(
                {
                    "providers": {
                        "local": {
                            "type": "ollama",
                            "base_url": "http://localhost:11434",
                        }
                    },
                    "agents": {
                        "assistant": {
                            "provider": "missing",
                            "model": "llama3.2:3b",
                        }
                    },
                }
            )

    def test_write_and_load_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loa.config.json"
            write_default_config(path)
            loaded = load_config(path)

        self.assertIn("local-ollama", loaded.providers)
        self.assertIn("assistant", loaded.agents)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
