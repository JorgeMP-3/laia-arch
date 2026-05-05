#!/usr/bin/env python3
"""
Command Center Tool — PTY terminal management for the Hermes multi-agent UI.

Gives Hermes first-class tools to spawn, inspect, inject into, and kill PTY
terminal sessions displayed in the Command Center UI (workspace-ui).

REST API lives at http://localhost:8077/api/terminals (workspace-ui backend).

Tools:
  command_center_list    — List all terminal sessions (alive and dead)
  command_center_spawn   — Spawn a new PTY terminal with an agent
  command_center_inject  — Send text/commands to a running terminal
  command_center_kill    — Kill a terminal session
"""

import json
import logging
import os
from typing import Any, Optional

import urllib.request
import urllib.error

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8077"


def _base_url() -> str:
    return os.environ.get("WORKSPACE_UI_URL", _DEFAULT_BASE_URL)


def _req(method: str, path: str, body: Optional[dict] = None) -> Any:
    url = f"{_base_url()}/api{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Command Center backend at {_base_url()}. "
            "Is workspace-ui running? Start with: cd ~/.hermes/workspace-ui/backend && uvicorn main:app --port 8077"
        ) from e


# ---------------------------------------------------------------------------
# command_center_list
# ---------------------------------------------------------------------------

def _handle_list(args, **_kw):
    try:
        terminals = _req("GET", "/terminals")
        alive = [t for t in terminals if t.get("alive")]
        dead = [t for t in terminals if not t.get("alive")]
        return tool_result(
            terminals=terminals,
            alive_count=len(alive),
            dead_count=len(dead),
            summary=[
                f"[{t['id'][:8]}] {t['agent_type']} — {'ALIVE' if t['alive'] else 'DEAD'} | cwd: {t['cwd']}"
                for t in terminals
            ],
        )
    except RuntimeError as e:
        return tool_error(str(e))


registry.register(
    name="command_center_list",
    toolset="command_center",
    schema={
        "name": "command_center_list",
        "description": (
            "List all PTY terminal sessions in the Command Center UI. "
            "Returns each session's id, agent_type, cwd, alive status, pid, and exit_code. "
            "Use this to find terminal IDs before injecting or killing."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    handler=_handle_list,
    emoji="📋",
)


# ---------------------------------------------------------------------------
# command_center_spawn
# ---------------------------------------------------------------------------

def _handle_spawn(args, **_kw):
    agent_type = args.get("agent_type", "bash")
    payload: dict = {"agent_type": agent_type}
    if args.get("cwd"):
        payload["cwd"] = args["cwd"]
    if args.get("prompt"):
        payload["prompt"] = args["prompt"]
    if args.get("cols"):
        payload["cols"] = int(args["cols"])
    if args.get("rows"):
        payload["rows"] = int(args["rows"])
    try:
        terminal = _req("POST", "/terminals", payload)
        return tool_result(
            terminal=terminal,
            id=terminal["id"],
            message=(
                f"Spawned {agent_type} terminal (id: {terminal['id'][:8]}). "
                "It is now visible in the Command Center UI. "
                "Use command_center_inject to send it a prompt."
            ),
        )
    except RuntimeError as e:
        return tool_error(str(e))


registry.register(
    name="command_center_spawn",
    toolset="command_center",
    schema={
        "name": "command_center_spawn",
        "description": (
            "Spawn a new PTY agent terminal in the Command Center UI. "
            "The terminal opens instantly and is visible to the user. "
            "After spawning, use command_center_inject to send it work. "
            "Available agent_types: bash, claude-code-planner, codex-worker, opencode-worker."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["bash", "claude-code-planner", "codex-worker", "opencode-worker"],
                    "description": (
                        "Type of agent to spawn. "
                        "'bash' = raw interactive shell. "
                        "'claude-code-planner' = Claude Code CLI (strong planner, uses host account). "
                        "'codex-worker' = Codex CLI (OpenAI, requires or auto-creates a git repo). "
                        "'opencode-worker' = OpenCode CLI (MiniMax or other cheap model)."
                    ),
                    "default": "bash",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the terminal (absolute path). Defaults to ~/.hermes.",
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "Initial prompt/command to inject after the shell is ready (0.8s delay). "
                        "For claude-code/codex/opencode, this is the task description."
                    ),
                },
                "cols": {
                    "type": "integer",
                    "description": "Terminal width in columns (default: 220).",
                    "default": 220,
                },
                "rows": {
                    "type": "integer",
                    "description": "Terminal height in rows (default: 50).",
                    "default": 50,
                },
            },
            "required": ["agent_type"],
        },
    },
    handler=_handle_spawn,
    emoji="🚀",
)


# ---------------------------------------------------------------------------
# command_center_inject
# ---------------------------------------------------------------------------

def _handle_inject(args, **_kw):
    terminal_id = args.get("terminal_id", "").strip()
    text = args.get("text", "")
    press_enter = args.get("press_enter", True)
    if not terminal_id:
        return tool_error("terminal_id is required")
    if not text:
        return tool_error("text is required")
    try:
        resp = _req("POST", f"/terminals/{terminal_id}/inject", {
            "text": text,
            "press_enter": press_enter,
        })
        return tool_result(
            ok=resp.get("ok", True),
            injected=resp.get("injected", len(text.encode())),
            terminal_id=terminal_id,
            message=f"Injected {resp.get('injected', '?')} bytes into terminal {terminal_id[:8]}.",
        )
    except RuntimeError as e:
        return tool_error(str(e))


registry.register(
    name="command_center_inject",
    toolset="command_center",
    schema={
        "name": "command_center_inject",
        "description": (
            "Inject text or a command into a running PTY terminal in the Command Center UI. "
            "Use this to send tasks to sub-agents (claude-code, codex, opencode, bash). "
            "The text appears in the terminal exactly as typed; press_enter=true sends it. "
            "Use command_center_list to find the terminal id first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "terminal_id": {
                    "type": "string",
                    "description": "Full terminal UUID returned by command_center_spawn or command_center_list.",
                },
                "text": {
                    "type": "string",
                    "description": (
                        "Text or command to inject. For agents (claude-code, codex, opencode), "
                        "this is the task description or follow-up prompt."
                    ),
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Whether to press Enter after the text (sends the command). Default: true.",
                    "default": True,
                },
            },
            "required": ["terminal_id", "text"],
        },
    },
    handler=_handle_inject,
    emoji="⌨️",
)


# ---------------------------------------------------------------------------
# command_center_kill
# ---------------------------------------------------------------------------

def _handle_kill(args, **_kw):
    terminal_id = args.get("terminal_id", "").strip()
    if not terminal_id:
        return tool_error("terminal_id is required")
    try:
        resp = _req("DELETE", f"/terminals/{terminal_id}")
        return tool_result(
            ok=resp.get("ok", True),
            terminal_id=terminal_id,
            message=f"Terminal {terminal_id[:8]} killed and removed from the UI.",
        )
    except RuntimeError as e:
        return tool_error(str(e))


registry.register(
    name="command_center_kill",
    toolset="command_center",
    schema={
        "name": "command_center_kill",
        "description": (
            "Kill a PTY terminal session and remove it from the Command Center UI. "
            "Use this when a sub-agent has finished its task or is stuck. "
            "Use command_center_list to find the terminal id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "terminal_id": {
                    "type": "string",
                    "description": "Full terminal UUID to kill.",
                },
            },
            "required": ["terminal_id"],
        },
    },
    handler=_handle_kill,
    emoji="🗑️",
)


# ---------------------------------------------------------------------------
# command_center_read
# ---------------------------------------------------------------------------

def _handle_read(args, **_kw):
    terminal_id = args.get("terminal_id", "").strip()
    tail_bytes = int(args.get("tail_bytes", 8192))
    if not terminal_id:
        return tool_error("terminal_id is required")
    try:
        resp = _req("GET", f"/terminals/{terminal_id}/output?tail_bytes={tail_bytes}")
        output = resp.get("output", "")
        lines = output.splitlines()
        # Return last 120 lines to keep context manageable
        visible = "\n".join(lines[-120:]) if len(lines) > 120 else output
        return tool_result(
            terminal_id=terminal_id,
            agent_type=resp.get("agent_type"),
            alive=resp.get("alive"),
            output=visible,
            total_lines=len(lines),
            message=f"Output of terminal {terminal_id[:8]} ({resp.get('agent_type')}):",
        )
    except RuntimeError as e:
        return tool_error(str(e))


registry.register(
    name="command_center_read",
    toolset="command_center",
    schema={
        "name": "command_center_read",
        "description": (
            "Read the recent output of a PTY terminal in the Command Center UI. "
            "Returns the last N bytes of terminal output as clean text (ANSI stripped). "
            "Use this to check what a sub-agent is doing, whether it finished, or if it's stuck. "
            "Call command_center_list first to get the terminal id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "terminal_id": {
                    "type": "string",
                    "description": "Full terminal UUID returned by command_center_spawn or command_center_list.",
                },
                "tail_bytes": {
                    "type": "integer",
                    "description": "How many bytes of recent output to return (default: 8192, max: 65536).",
                    "default": 8192,
                },
            },
            "required": ["terminal_id"],
        },
    },
    handler=_handle_read,
    emoji="👁️",
)
