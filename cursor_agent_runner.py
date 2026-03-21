#!/usr/bin/env python3
"""
Run Cursor CLI `agent` in non-interactive (--print) mode and return stdout.

Used to hand off a task to Cursor Agent from a Python "main loop" and collect
the textual result when the agent finishes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def find_cursor_cli() -> str | None:
    return shutil.which("cursor") or shutil.which("cursors")


def run_cursor_agent_task(
    prompt: str,
    *,
    workspace: Path | None = None,
    timeout: float = 600.0,
    output_format: str = "text",
    model: str | None = 'auto',
) -> str:
    """
    Execute: cursor agent --workspace <dir> --print --output-format <fmt> [ --model <m> ] <prompt>

    **Model:** pass ``model=`` or set env **CURSOR_AGENT_MODEL** (e.g. ``auto`` for Auto,
    or ``gpt-5``, ``sonnet-4``, ``sonnet-4-thinking`` per ``cursor agent --help``).
    If unset, Cursor uses its default (which may be a fixed model like Opus in agent mode).

    Returns the agent's stdout (the "result" back to your main loop).
    Raises RuntimeError on missing CLI, non-zero exit, or empty output when failed.
    """
    cursor = find_cursor_cli()
    if not cursor:
        raise RuntimeError(
            'Cursor CLI not found on PATH. Install: Command Palette → '
            '"Shell Command: Install \'cursor\' command in PATH"'
        )

    ws = (workspace or Path.cwd()).resolve()
    if not ws.is_dir():
        raise FileNotFoundError(f"Workspace is not a directory: {ws}")

    cmd: list[str] = [
        cursor,
        "agent",
        "--workspace",
        str(ws),
        "--print",
        "--trust",
        "--output-format",
        output_format,
    ]
    # Headless / scripting: auto-approve tool use when supported (Cursor 2.x+).
    if os.environ.get("CURSOR_AGENT_FORCE", "").strip().lower() in ("1", "true", "yes"):
        cmd.append("--force")

    resolved_model = (model or os.environ.get("CURSOR_AGENT_MODEL", "auto") or "").strip()
    if resolved_model:
        cmd.extend(["--model", resolved_model])

    extra = os.environ.get("CURSOR_AGENT_EXTRA_ARGS", "").strip()
    if extra:
        import shlex

        cmd.extend(shlex.split(extra))

    cmd.append(prompt)

    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
        raise RuntimeError(f"cursor agent failed: {msg}")

    out = (r.stdout or "").strip()
    if not out and r.stderr:
        raise RuntimeError(f"cursor agent returned no stdout: {r.stderr.strip()}")
    return r.stdout or ""
