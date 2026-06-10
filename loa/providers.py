from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request

from .config import ProviderConfig


class ProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a request."""


@dataclass(frozen=True)
class ChatResult:
    provider: str
    model: str
    content: str
    usage: dict[str, Any]
    raw: dict[str, Any]


class BaseProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    def list_models(self) -> list[str]:
        raise NotImplementedError

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    def list_models(self) -> list[str]:
        response = _request_json(
            _join_url(self.config.base_url, "/api/tags"),
            timeout=self.config.timeout_seconds,
        )
        models = response.get("models", [])
        return sorted(
            str(model.get("name"))
            for model in models
            if isinstance(model, dict) and model.get("name")
        )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        response = _request_json(
            _join_url(self.config.base_url, "/api/chat"),
            method="POST",
            payload=payload,
            timeout=self.config.timeout_seconds,
        )
        message = response.get("message") or {}
        content = str(message.get("content", ""))
        usage = {
            "prompt_tokens": response.get("prompt_eval_count"),
            "completion_tokens": response.get("eval_count"),
            "total_duration_ns": response.get("total_duration"),
        }
        return ChatResult(
            provider=self.name,
            model=model,
            content=content,
            usage=usage,
            raw=response,
        )


class OpenAICompatibleProvider(BaseProvider):
    def list_models(self) -> list[str]:
        response = _request_json(
            _join_url(self.config.base_url, "/models"),
            headers=self._headers(),
            timeout=self.config.timeout_seconds,
        )
        data = response.get("data", [])
        return sorted(
            str(model.get("id"))
            for model in data
            if isinstance(model, dict) and model.get("id")
        )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = _request_json(
            _join_url(self.config.base_url, "/chat/completions"),
            method="POST",
            payload=payload,
            headers=self._headers(),
            timeout=self.config.timeout_seconds,
        )
        choices = response.get("choices") or []
        if not choices:
            raise ProviderError(f"{self.name}: provider returned no choices")
        message = choices[0].get("message") or {}
        usage = response.get("usage") or {}
        return ChatResult(
            provider=self.name,
            model=model,
            content=str(message.get("content", "")),
            usage=usage if isinstance(usage, dict) else {},
            raw=response,
        )

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            return {}
        return {"Authorization": f"Bearer {self.config.api_key}"}


def build_provider(config: ProviderConfig) -> BaseProvider:
    provider_type = config.type.lower().replace("_", "-")
    if provider_type == "ollama":
        return OllamaProvider(config)
    if provider_type in {"openai-compatible", "openai"}:
        return OpenAICompatibleProvider(config)
    raise ProviderError(f"Unsupported provider type {config.type!r} for {config.name!r}")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    body = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"{url}: HTTP {exc.code} {exc.reason}: {details}") from exc
    except error.URLError as exc:
        raise ProviderError(_format_url_error(url, exc.reason)) from exc

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{url}: invalid JSON response") from exc
    if not isinstance(parsed, dict):
        raise ProviderError(f"{url}: expected JSON object response")
    return parsed


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _format_url_error(url: str, reason: object) -> str:
    text = str(reason)
    lowered = text.lower()
    if "10061" in text or "connection refused" in lowered:
        hint = "provider is not reachable"
        if "localhost:11434" in url or "127.0.0.1:11434" in url:
            hint = "Ollama is not running at this address"
        return f"{url}: connection refused ({hint}). Start the provider or update base_url in loa.config.json."
    if "timed out" in lowered or "timeout" in lowered:
        return f"{url}: request timed out. The provider may be busy or the model may still be loading."
    return f"{url}: {text}"
