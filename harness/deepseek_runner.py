#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Drop-in replacement for `claude -p --output-format stream-json` using DeepSeek API.

Installed as /usr/local/bin/claude inside agent containers. Accepts the same
CLI interface as Claude Code headless mode; outputs the same stream-json format
so agent.py requires no changes.

Tool execution (Bash/Read/Write) runs directly in the container process — no
subprocess wrapper needed since this script IS the in-container agent.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("error: openai package not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)


# ── Tool definitions (OpenAI function-calling format) ────────────────────────

_TOOL_DEFS: dict[str, dict] = {
    "Bash": {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": (
                "Execute a shell command. Returns stdout+stderr combined. "
                "Use for compiling, running binaries, file system operations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in ms (default 120000)"},
                },
                "required": ["command"],
            },
        },
    },
    "Read": {
        "type": "function",
        "function": {
            "name": "Read",
            "description": (
                "Read a file. Returns lines prefixed with 1-based line numbers. "
                "Use offset+limit to read a slice of a large file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"},
                    "offset": {"type": "integer", "description": "Line to start from (0-based, default 0)"},
                    "limit": {"type": "integer", "description": "Max lines to return (default 2000)"},
                },
                "required": ["file_path"],
            },
        },
    },
    "Write": {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file, creating parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
}


# ── Tool execution ────────────────────────────────────────────────────────────

def _exec_bash(inp: dict) -> str:
    cmd = inp.get("command", "")
    if not cmd:
        return "Error: no command provided"
    timeout_ms = inp.get("timeout", 120000)
    timeout_s = min(timeout_ms / 1000, 300)
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout_s, errors="replace",
        )
        out = r.stdout
        if r.stderr:
            out += r.stderr
        if r.returncode != 0:
            out += f"\nExit code: {r.returncode}"
        return out[:50000] or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout_s:.0f}s"
    except Exception as e:
        return f"Error: {e}"


def _exec_read(inp: dict) -> str:
    path = inp.get("file_path", "")
    offset = int(inp.get("offset") or 0)
    limit = int(inp.get("limit") or 2000)
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: file not found: {path}"
        if not p.is_file():
            return f"Error: not a regular file: {path}"
        lines = p.read_text(errors="replace").splitlines()
        selected = lines[offset: offset + limit]
        return "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(selected))
    except Exception as e:
        return f"Error: {e}"


def _exec_write(inp: dict) -> str:
    path = inp.get("file_path", "")
    content = inp.get("content", "")
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error: {e}"


_EXECUTORS = {"Bash": _exec_bash, "Read": _exec_read, "Write": _exec_write}


def _execute_tool(name: str, inp: dict) -> str:
    fn = _EXECUTORS.get(name)
    if fn is None:
        return f"Error: unknown tool {name!r}"
    return fn(inp)


# ── stream-json helpers ───────────────────────────────────────────────────────

def _emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


def _emit_assistant(content_blocks: list[dict]) -> None:
    _emit({"type": "assistant", "message": {"content": content_blocks}})


def _emit_tool_result(tool_use_id: str, content: str) -> None:
    _emit({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            }],
        },
    })


def _emit_result(result: str, session_id: str, is_error: bool = False) -> None:
    _emit({
        "type": "result",
        "subtype": "error" if is_error else "success",
        "is_error": is_error,
        "result": result,
        "session_id": session_id,
    })


# ── Main agent loop ───────────────────────────────────────────────────────────

def _run(
    prompt: str,
    model: str,
    max_turns: int,
    active_tools: list[str],
    system_prompt: str | None,
) -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _emit_result("error: DEEPSEEK_API_KEY not set", "none", is_error=True)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    session_id = str(uuid.uuid4())
    _emit({"type": "system", "subtype": "init", "session_id": session_id})

    tool_defs = [_TOOL_DEFS[t] for t in active_tools if t in _TOOL_DEFS]

    oai_messages: list[dict] = []
    if system_prompt:
        oai_messages.append({"role": "system", "content": system_prompt})
    oai_messages.append({"role": "user", "content": prompt})

    for _turn in range(max_turns):
        try:
            kwargs: dict = {
                "model": model,
                "messages": oai_messages,
                "max_tokens": 8192,
            }
            if tool_defs:
                kwargs["tools"] = tool_defs
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            _emit_result(f"API error: {e}", session_id, is_error=True)
            sys.exit(1)

        choice = response.choices[0]
        msg = choice.message

        # Build stream-json content blocks
        content_blocks: list[dict] = []
        if msg.content:
            content_blocks.append({"type": "text", "text": msg.content})

        tool_calls = msg.tool_calls or []
        for tc in tool_calls:
            try:
                inp = json.loads(tc.function.arguments)
            except Exception:
                inp = {}
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": inp,
            })

        _emit_assistant(content_blocks)

        # Append to OpenAI conversation history
        assistant_entry: dict = {"role": "assistant"}
        if msg.content is not None:
            assistant_entry["content"] = msg.content
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        oai_messages.append(assistant_entry)

        # No tool calls → agent is done
        if not tool_calls:
            _emit_result(msg.content or "", session_id)
            return

        # Execute each tool and feed results back
        for tc in tool_calls:
            try:
                inp = json.loads(tc.function.arguments)
            except Exception:
                inp = {}
            tool_result = _execute_tool(tc.function.name, inp)
            _emit_tool_result(tc.id, tool_result)
            oai_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

    _emit_result("Max turns reached", session_id)


# ── CLI argument parsing ──────────────────────────────────────────────────────

def main() -> None:
    # Minimal --version so setup_sandbox.sh verification passes
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "version"):
        print("deepseek-runner 1.0.0 (claude-compatible)")
        sys.exit(0)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-p", action="store_true")
    parser.add_argument("--output-format", default="stream-json")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--tools", default="Read,Write,Bash")
    parser.add_argument("--system-prompt", default=None)
    parser.add_argument("--permission-mode", default="auto")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--strict-mcp-config", action="store_true")
    parser.add_argument("--setting-sources", default=None)
    # resume: ignored — DeepSeek has no built-in session persistence
    parser.add_argument("--resume", default=None)
    parser.add_argument("prompt", nargs="*")

    args = parser.parse_args()

    # Prompt: either positional arg or (on --resume) "continue"
    prompt_parts = [p for p in (args.prompt or []) if p not in ("continue",)]
    if not prompt_parts:
        print("error: no prompt provided", file=sys.stderr)
        sys.exit(1)
    prompt = " ".join(prompt_parts)

    # Tools: comma-separated, may be empty string or literal '""'
    tools_raw = args.tools.strip().strip('"')
    active_tools = [t.strip() for t in tools_raw.split(",") if t.strip()]

    _run(
        prompt=prompt,
        model=args.model,
        max_turns=args.max_turns,
        active_tools=active_tools,
        system_prompt=args.system_prompt,
    )


if __name__ == "__main__":
    main()
