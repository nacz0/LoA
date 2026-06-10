from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib import error, request

from .agents import AgentError, AgentRuntime
from .config import ConfigError, find_config_path, load_config, write_default_config
from .providers import ProviderError
from .server import run_server


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except (ConfigError, AgentError, ProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loa")
    parser.add_argument("--config", help="Path to loa.config.json")
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init-config", help="Write example config")
    init_parser.add_argument("--path", default="loa.config.json")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_init_config)

    agents_parser = subparsers.add_parser("agents", help="List configured agents")
    agents_parser.set_defaults(func=cmd_agents)

    doctor_parser = subparsers.add_parser("doctor", help="Check config and providers")
    doctor_parser.add_argument("--json", action="store_true", help="Print JSON report")
    doctor_parser.set_defaults(func=cmd_doctor)

    models_parser = subparsers.add_parser("models", help="List provider models")
    models_parser.add_argument("--provider", help="Provider name")
    models_parser.set_defaults(func=cmd_models)

    chat_parser = subparsers.add_parser("chat", help="Send one chat message")
    chat_parser.add_argument("message", nargs="?", help="Message text. Reads stdin if omitted.")
    chat_parser.add_argument("--agent", help="Agent name")
    chat_parser.add_argument("--json", action="store_true", help="Print full JSON result")
    chat_parser.set_defaults(func=cmd_chat)

    serve_parser = subparsers.add_parser("serve", help="Run local HTTP API")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.set_defaults(func=cmd_serve)

    probe_parser = subparsers.add_parser("node-probe", help="Probe a LoA node")
    probe_parser.add_argument("url")
    probe_parser.add_argument("--token")
    probe_parser.set_defaults(func=cmd_node_probe)

    return parser


def cmd_init_config(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if target.exists() and not args.force:
        print(f"Config already exists: {target}")
        print("Edit it directly or rerun with --force to overwrite it.")
        return 0
    path = write_default_config(args.path, force=args.force)
    print(f"Wrote {path}")
    return 0


def cmd_agents(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    rows = [
        {
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
        }
        for agent in config.agents.values()
    ]
    _print_json({"agents": rows})
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    runtime = AgentRuntime(config)
    providers: list[dict[str, Any]] = []
    exit_code = 0

    for provider_name in runtime.provider_names():
        provider = runtime.providers[provider_name]
        try:
            models = provider.list_models()
            providers.append(
                {
                    "name": provider_name,
                    "ok": True,
                    "models": models,
                    "model_count": len(models),
                }
            )
        except ProviderError as exc:
            providers.append(
                {
                    "name": provider_name,
                    "ok": False,
                    "error": str(exc),
                }
            )
            exit_code = 1

    report = {
        "ok": exit_code == 0,
        "default_agent": config.default_agent,
        "agents": runtime.agent_names(),
        "providers": providers,
        "server": {
            "bind_host": config.bind_host,
            "bind_port": config.bind_port,
            "auth_enabled": bool(config.api_token),
        },
    }

    if args.json:
        _print_json(report)
    else:
        print(f"default agent: {config.default_agent}")
        print(f"agents: {', '.join(runtime.agent_names())}")
        for provider in providers:
            if provider["ok"]:
                print(
                    f"provider {provider['name']}: ok "
                    f"({provider['model_count']} models)"
                )
            else:
                print(f"provider {provider['name']}: error: {provider['error']}")
    return exit_code


def cmd_models(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    runtime = AgentRuntime(config)
    provider_names = [args.provider] if args.provider else runtime.provider_names()
    result: dict[str, Any] = {}
    for provider_name in provider_names:
        provider = runtime.providers.get(provider_name)
        if provider is None:
            raise ProviderError(f"provider {provider_name!r} is not configured")
        result[provider_name] = provider.list_models()
    _print_json({"models": result})
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    runtime = AgentRuntime(config)
    message = args.message if args.message is not None else sys.stdin.read()
    if not message.strip():
        raise AgentError("message is empty")
    result = runtime.chat(agent_name=args.agent, message=message)
    if args.json:
        _print_json(
            {
                "agent": result.agent,
                "provider": result.provider,
                "model": result.model,
                "message": result.content,
                "usage": result.usage,
            }
        )
    else:
        print(result.content)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    config_path = find_config_path(args.config)
    if args.host or args.port:
        from dataclasses import replace

        config = replace(
            config,
            bind_host=args.host or config.bind_host,
            bind_port=args.port or config.bind_port,
        )
    run_server(config, config_path=config_path)
    return 0


def cmd_node_probe(args: argparse.Namespace) -> int:
    url = args.url.rstrip("/") + "/api/node/health"
    headers = {"Accept": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_json(body)
    return 0


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
