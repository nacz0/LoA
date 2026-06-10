from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AgentConfig, AppConfig
from .providers import BaseProvider, ChatResult, build_provider


class AgentError(RuntimeError):
    """Raised when an agent cannot be resolved or run."""


@dataclass(frozen=True)
class AgentRunResult:
    agent: str
    provider: str
    model: str
    content: str
    usage: dict[str, Any]
    raw: dict[str, Any]


class AgentRuntime:
    def __init__(
        self,
        config: AppConfig,
        providers: dict[str, BaseProvider] | None = None,
    ) -> None:
        self.config = config
        self.providers = providers or {
            name: build_provider(provider_config)
            for name, provider_config in config.providers.items()
        }

    def agent_names(self) -> list[str]:
        return sorted(self.config.agents)

    def provider_names(self) -> list[str]:
        return sorted(self.providers)

    def chat(
        self,
        *,
        message: str,
        agent_name: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AgentRunResult:
        agent = self._agent(agent_name)
        messages: list[dict[str, str]] = []
        if history:
            messages.extend(_normalize_messages(history))
        messages.append({"role": "user", "content": message})
        return self.chat_messages(agent_name=agent.name, messages=messages)

    def chat_messages(
        self,
        *,
        agent_name: str | None = None,
        messages: list[dict[str, str]],
    ) -> AgentRunResult:
        agent = self._agent(agent_name)
        provider = self.providers.get(agent.provider)
        if provider is None:
            raise AgentError(f"provider {agent.provider!r} is not available")

        normalized = _normalize_messages(messages)
        if agent.system:
            normalized = [{"role": "system", "content": agent.system}] + normalized

        result = provider.chat(
            model=agent.model,
            messages=normalized,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
        )
        return _to_agent_result(agent, result)

    def _agent(self, agent_name: str | None) -> AgentConfig:
        name = agent_name or self.config.default_agent
        agent = self.config.agents.get(name)
        if agent is None:
            raise AgentError(f"agent {name!r} is not configured")
        return agent


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    allowed_roles = {"system", "user", "assistant", "tool"}
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise AgentError(f"message {index} must be an object")
        role = str(message.get("role", "")).strip()
        content = message.get("content", "")
        if role not in allowed_roles:
            raise AgentError(f"message {index} has unsupported role {role!r}")
        if not isinstance(content, str):
            raise AgentError(f"message {index} content must be a string")
        normalized.append({"role": role, "content": content})
    return normalized


def _to_agent_result(agent: AgentConfig, result: ChatResult) -> AgentRunResult:
    return AgentRunResult(
        agent=agent.name,
        provider=result.provider,
        model=result.model,
        content=result.content,
        usage=result.usage,
        raw=result.raw,
    )
