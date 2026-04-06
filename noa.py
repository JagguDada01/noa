#!/usr/bin/env python3
"""Offline terminal chat app backed by a local Ollama model."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator


APP_NAME = "Noa"
APP_ACCENT = "1;38;5;203"
APP_ASCII_ART = textwrap.dedent(
    r"""
     _   _    ___      _
    | \ | |  / _ \    / \
    |  \| | | | | |  / _ \
    | . ` | | | | | / ___ \
    | |\  | | |_| |/ /   \ \
    |_| \_|  \___//_/     \_\
    """
).strip("\n")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_SYSTEM_PROMPT = (
    "You are Noa, a helpful AI assistant running in a terminal. "
    "Be accurate, concise, and say when you are unsure."
)

HELP_TEXT = textwrap.dedent(
    """
    Commands:
      /help               Show this help
      /models             List locally installed models
      /model NAME         Switch to a different installed model
      /clear              Clear chat history
      /system TEXT        Replace the system prompt
      /status             Show current settings
      /exit               Quit
    """
).strip()

_SERVER_PROCESS: subprocess.Popen[bytes] | None = None


class OllamaError(RuntimeError):
    """Raised when Ollama returns an error or is unavailable."""


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def style(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def info(message: str) -> None:
    print(style(message, "36"))


def warn(message: str) -> None:
    print(style(message, "33"), file=sys.stderr)


def error(message: str) -> None:
    print(style(message, "31"), file=sys.stderr)


def installed_models() -> list[str]:
    manifests_root = Path.home() / ".ollama" / "models" / "manifests"
    if not manifests_root.exists():
        return []

    models: set[str] = set()
    for manifest in manifests_root.rglob("*"):
        if not manifest.is_file():
            continue

        parts = manifest.relative_to(manifests_root).parts
        if len(parts) < 4:
            continue

        _, namespace, model_name, tag = parts[:4]
        name = model_name if namespace == "library" else f"{namespace}/{model_name}"
        models.add(f"{name}:{tag}")

    return sorted(models)


def is_server_alive(host: str, timeout: float = 1.0) -> bool:
    request = urllib.request.Request(f"{host}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def cleanup_server() -> None:
    global _SERVER_PROCESS
    if _SERVER_PROCESS and _SERVER_PROCESS.poll() is None:
        _SERVER_PROCESS.terminate()
        try:
            _SERVER_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _SERVER_PROCESS.kill()
    _SERVER_PROCESS = None


def ensure_server(host: str, auto_start: bool) -> None:
    global _SERVER_PROCESS

    if is_server_alive(host):
        return

    if not auto_start:
        raise OllamaError(
            f"Ollama is not reachable at {host}. Start it with: ollama serve"
        )

    if shutil.which("ollama") is None:
        raise OllamaError(
            "Ollama is not installed. Install it first, then add a local model."
        )

    info("Starting local Ollama server...")
    _SERVER_PROCESS = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(cleanup_server)

    for _ in range(50):
        if is_server_alive(host):
            return
        time.sleep(0.2)

    raise OllamaError(
        "Started Ollama, but the server did not become ready in time."
    )


def api_request(
    host: str,
    path: str,
    payload: dict,
    *,
    timeout: float = 300.0,
) -> urllib.request.addinfourl:
    request = urllib.request.Request(
        f"{host}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            message = body or str(exc)
        raise OllamaError(message) from exc
    except urllib.error.URLError as exc:
        raise OllamaError(str(exc.reason)) from exc


def stream_chat(
    host: str,
    model: str,
    messages: list[dict[str, str]],
) -> Iterator[str]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    with api_request(host, "/api/chat", payload) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue

            chunk = json.loads(line)
            if "error" in chunk:
                raise OllamaError(chunk["error"])

            content = chunk.get("message", {}).get("content")
            if content:
                yield content

            if chunk.get("done"):
                break


def run_once(host: str, model: str, system_prompt: str, prompt: str) -> int:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        for token in stream_chat(host, model, messages):
            print(token, end="", flush=True)
        print()
        return 0
    except OllamaError as exc:
        error(f"Request failed: {exc}")
        return 1


def print_banner(model: str, host: str, system_prompt: str) -> None:
    width = shutil.get_terminal_size((80, 20)).columns
    print(style("=" * min(width, 80), "2"))
    print(style(APP_ASCII_ART, APP_ACCENT))
    print(style("Hello JagguDada", "1;32"))
    print(f"Model: {model}")
    print(f"Host:  {host}")
    print("Type /help for commands.")
    print(style("=" * min(width, 80), "2"))


def chat_loop(host: str, model: str, system_prompt: str) -> int:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    print_banner(model, host, system_prompt)

    while True:
        try:
            user_input = input(style("\nyou> ", "1;34"))
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\nExiting.")
            return 0

        prompt = user_input.strip()
        if not prompt:
            continue

        if prompt in {"/exit", "/quit"}:
            return 0

        if prompt == "/help":
            print(HELP_TEXT)
            continue

        if prompt == "/models":
            models = installed_models()
            if not models:
                print("No local models found in ~/.ollama/models.")
            else:
                print("\n".join(models))
            continue

        if prompt == "/clear":
            messages = [{"role": "system", "content": system_prompt}]
            info("Chat history cleared.")
            continue

        if prompt == "/status":
            print(f"Model: {model}")
            print(f"Host: {host}")
            print(f"Messages in context: {len(messages) - 1}")
            continue

        if prompt.startswith("/model "):
            requested_model = prompt.split(maxsplit=1)[1].strip()
            if not requested_model:
                warn("Usage: /model NAME")
                continue

            local_models = installed_models()
            if local_models and requested_model not in local_models:
                warn(
                    "Model not found locally. Use /models to see installed models."
                )
                continue

            model = requested_model
            messages = [{"role": "system", "content": system_prompt}]
            info(f"Switched to {model}. Chat history cleared.")
            continue

        if prompt.startswith("/system "):
            system_prompt = prompt.split(maxsplit=1)[1].strip()
            if not system_prompt:
                warn("Usage: /system TEXT")
                continue
            messages = [{"role": "system", "content": system_prompt}]
            info("System prompt updated. Chat history cleared.")
            continue

        messages.append({"role": "user", "content": prompt})

        print(style(f"{APP_NAME}> ", APP_ACCENT), end="", flush=True)
        chunks: list[str] = []
        try:
            for token in stream_chat(host, model, messages):
                chunks.append(token)
                print(token, end="", flush=True)
            print()
        except KeyboardInterrupt:
            print("\nRequest interrupted.")
            messages.pop()
            continue
        except OllamaError as exc:
            print()
            error(f"Request failed: {exc}")
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": "".join(chunks)})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline terminal AI chat backed by a local Ollama model."
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Ollama host URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--model",
        help="Model to use. Defaults to the first locally installed model.",
    )
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM_PROMPT,
        help="System prompt for the assistant.",
    )
    parser.add_argument(
        "--once",
        metavar="PROMPT",
        help="Ask one question and exit.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print locally installed models and exit.",
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Do not auto-start `ollama serve` when the server is not running.",
    )
    return parser.parse_args()


def pick_model(user_selected: str | None) -> str:
    models = installed_models()
    if user_selected:
        return user_selected
    if models:
        return models[0]
    raise OllamaError(
        "No local Ollama models were found. Add one with: ollama pull llama3.2:3b"
    )


def main() -> int:
    args = parse_args()

    if args.list_models:
        models = installed_models()
        if models:
            print("\n".join(models))
            return 0
        warn("No local models found in ~/.ollama/models.")
        return 1

    try:
        model = pick_model(args.model)
        ensure_server(args.host, auto_start=not args.no_auto_start)
    except OllamaError as exc:
        error(str(exc))
        return 1

    if args.once:
        return run_once(args.host, model, args.system, args.once)

    return chat_loop(args.host, model, args.system)


if __name__ == "__main__":
    raise SystemExit(main())
