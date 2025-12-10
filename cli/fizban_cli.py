#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_cli.py
Minimal OpenAI client for Termux / Fizban.

Features:
- Chat mode:    /v1/chat/completions   (good for gpt-4.1-mini, etc)
- Responses mode: /v1/responses        (good for gpt-5, gpt-5-mini, gpt-5-nano)
- Flags:
    --mode {chat,responses}
    --model NAME
    --temperature FLOAT
    --reasoning {minimal,low,medium,high}   (responses mode only)
    --max-output-tokens INT                 (responses mode only)
    --prompt-file PATH                      (read user prompt from file)
"""

import os
import sys
import json
import datetime as _dt
from pathlib import Path
from typing import List, Dict, Any, Optional

import argparse
import requests
import yaml

# ---------- Paths & Config ----------

FIZBAN_DIR = Path.home() / "fizban"
CONFIG_DIR = FIZBAN_DIR           # keep it simple: all under ~/fizban
LOG_DIR = FIZBAN_DIR / "logs"
PROMPTS_DIR = FIZBAN_DIR / "prompts"

DEFAULT_MODEL = os.environ.get("FIZBAN_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")

SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_fizban.yaml"
DEFAULT_TEMPERATURE = 0.7  # override with --temperature


# ---------- Helpers ----------

def load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        sys.stderr.write(
            "[error] OPENAI_API_KEY is not set. Export it in your shell, e.g.\n"
            "        export OPENAI_API_KEY='sk-...'\n"
        )
        sys.exit(1)
    return key


def load_system_prompt() -> str:
    """
    Try to load a YAML prompt file; fall back to a simple system prompt.
    """
    if SYSTEM_PROMPT_FILE.is_file():
        try:
            data = yaml.safe_load(SYSTEM_PROMPT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "prompt" in data:
                return str(data["prompt"])
            if isinstance(data, str):
                return data
        except Exception as e:
            sys.stderr.write(f"[warn] Failed to parse {SYSTEM_PROMPT_FILE}: {e}\n")

    # Fallback: lightweight fizban dev persona
    return (
        "You are Fizban, a direct, plainspoken AI co-developer running in a Termux "
        "environment on Android. Help the user with code, build scripts, and game/"
        "emotion-engine design. Be concise but technically precise."
    )


def log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d")
    return LOG_DIR / f"session_{stamp}.log"


def append_log(entry: Dict[str, Any]) -> None:
    try:
        lp = log_path()
        with lp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Logging must not kill the CLI
        pass


# ---------- API Wrappers ----------

def call_openai_chat(
    api_key: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_output_tokens: Optional[int] = None,
) -> str:
    url = f"{OPENAI_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "top_p": 1.0,
    }
    if max_output_tokens is not None:
        payload["max_tokens"] = int(max_output_tokens)

    append_log({"ts": _dt.datetime.now().isoformat(), "direction": "out", "endpoint": "chat", "payload": payload})

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response: {resp.status_code} {resp.text[:500]}")

    append_log(
        {
            "ts": _dt.datetime.now().isoformat(),
            "direction": "in",
            "endpoint": "chat",
            "status": resp.status_code,
            "data": data,
        }
    )

    if resp.status_code != 200:
        msg = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(f"OpenAI error {resp.status_code}: {msg or str(data)[:500]}")

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected chat response schema: {e}\n{data}")


def _extract_text_from_responses(data: Dict[str, Any]) -> str:
    """
    Try to pull plain text out of /v1/responses schema.
    """
    # Preferred: look at output blocks
    for block in data.get("output", []):
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "") or ""
    # Fallback: some wrappers put text here
    if "output_text" in data and isinstance(data["output_text"], dict):
        return data["output_text"].get("text", "") or ""
    raise RuntimeError(f"Could not find text in responses payload: {data}")


def call_openai_responses(
    api_key: str,
    prompt_text: str,
    model: str,
    temperature: float,
    reasoning_effort: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> str:
    url = f"{OPENAI_BASE_URL.rstrip('/')}/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "input": prompt_text,
        "temperature": float(temperature),
        "top_p": 1.0,
        "store": False,
        "text": {"format": {"type": "text"}},
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    if max_output_tokens is not None:
        payload["max_output_tokens"] = int(max_output_tokens)

    append_log({"ts": _dt.datetime.now().isoformat(), "direction": "out", "endpoint": "responses", "payload": payload})

    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response: {resp.status_code} {resp.text[:500]}")

    append_log(
        {
            "ts": _dt.datetime.now().isoformat(),
            "direction": "in",
            "endpoint": "responses",
            "status": resp.status_code,
            "data": data,
        }
    )

    if resp.status_code != 200:
        msg = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(f"OpenAI error {resp.status_code}: {msg or str(data)[:500]}")

    return _extract_text_from_responses(data)


# ---------- CLI Logic ----------

def run_one_shot_chat(
    prompt: str,
    model: str,
    temperature: float,
    max_output_tokens: Optional[int],
) -> int:
    api_key = load_api_key()
    system_prompt = load_system_prompt()

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        reply = call_openai_chat(api_key, messages, model=model, temperature=temperature, max_output_tokens=max_output_tokens)
    except Exception as e:
        sys.stderr.write(f"[error] {e}\n")
        return 1

    print(reply)
    return 0


def run_one_shot_responses(
    prompt: str,
    model: str,
    temperature: float,
    reasoning_effort: Optional[str],
    max_output_tokens: Optional[int],
) -> int:
    api_key = load_api_key()
    # Note: responses endpoint takes a flat input string; we can still embed the system prompt manually if desired.
    system_prompt = load_system_prompt()
    full_prompt = f"{system_prompt}\n\nUser:\n{prompt}"

    try:
        reply = call_openai_responses(
            api_key,
            full_prompt,
            model=model,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        )
    except Exception as e:
        sys.stderr.write(f"[error] {e}\n")
        return 1

    print(reply)
    return 0


def repl_chat(model: str, temperature: float) -> int:
    api_key = load_api_key()
    system_prompt = load_system_prompt()

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    sys.stderr.write(
        f"[fizban] Interactive chat mode. Model={model}, temperature={temperature}\n"
        "[fizban] Ctrl-D (EOF) or /quit to exit.\n"
    )

    while True:
        try:
            user = input("\nYou> ")
        except EOFError:
            sys.stderr.write("\n[fizban] EOF, exiting.\n")
            break

        user = user.strip()
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break

        messages.append({"role": "user", "content": user})

        try:
            reply = call_openai_chat(
                api_key,
                messages,
                model=model,
                temperature=temperature,
                max_output_tokens=None,
            )
        except Exception as e:
            sys.stderr.write(f"[error] {e}\n")
            # don’t kill history; allow retry
            continue

        messages.append({"role": "assistant", "content": reply})
        print(f"\nFizban> {reply}")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fizban CLI for OpenAI")
    p.add_argument(
        "--mode",
        choices=["chat", "responses"],
        default="chat",
        help="API mode: 'chat' uses /v1/chat/completions, 'responses' uses /v1/responses",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override model name (default from $FIZBAN_MODEL or gpt-4.1-mini)",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (0.0–2.0). Default 0.7 if not set.",
    )
    p.add_argument(
        "--reasoning",
        type=str,
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Reasoning effort (responses mode only). Ignored in chat mode.",
    )
    p.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Hard cap on output tokens (chat: max_tokens, responses: max_output_tokens).",
    )
    p.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        help="Read user prompt from a file instead of CLI args.",
    )
    p.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text (if not using --prompt-file).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    model = args.model or DEFAULT_MODEL
    temperature = args.temperature if args.temperature is not None else DEFAULT_TEMPERATURE

    # Determine user prompt (if any)
    prompt_text: Optional[str] = None
    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_file():
            sys.stderr.write(f"[error] --prompt-file not found: {path}\n")
            return 1
        prompt_text = path.read_text(encoding="utf-8")
    elif args.prompt:
        prompt_text = " ".join(args.prompt).strip()

    if args.mode == "chat":
        # REPL if no prompt was given
        if prompt_text is None:
            return repl_chat(model=model, temperature=temperature)
        else:
            return run_one_shot_chat(
                prompt=prompt_text,
                model=model,
                temperature=temperature,
                max_output_tokens=args.max_output_tokens,
            )
    else:
        # responses mode always expects a one-shot prompt
        if prompt_text is None:
            sys.stderr.write("[error] responses mode requires a prompt or --prompt-file.\n")
            return 1
        return run_one_shot_responses(
            prompt=prompt_text,
            model=model,
            temperature=temperature,
            reasoning_effort=args.reasoning,
            max_output_tokens=args.max_output_tokens,
        )


if __name__ == "__main__":
    raise SystemExit(main())

