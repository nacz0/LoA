from __future__ import annotations

import unittest

from loa.agents import AgentRuntime
from loa.config import AgentConfig, AppConfig, ProviderConfig
from loa.providers import BaseProvider, ChatResult


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
            content=messages[0]["content"] + " / " + messages[-1]["content"],
            usage={"messages": len(messages)},
            raw={},
        )


class AgentRuntimeTests(unittest.TestCase):
    def test_runtime_prepends_system_prompt(self) -> None:
        config = AppConfig(
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
                    system="system prompt",
                )
            },
            default_agent="assistant",
        )
        runtime = AgentRuntime(config, providers={"fake": FakeProvider(config.providers["fake"])})

        result = runtime.chat(message="hello")

        self.assertEqual(result.content, "system prompt / hello")
        self.assertEqual(result.usage["messages"], 2)


if __name__ == "__main__":
    unittest.main()
