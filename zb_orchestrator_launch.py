"""
Shared helpers for launching Cursor against ``~/zb-projects/ai-projects/zb-orchestrator``
(generate-timesheet and related workflows).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Standard layout under the user’s zb-projects checkout.
ROOT = (Path.home() / "zb-projects").resolve()
ORCHESTRATOR_ROOT = ROOT / "ai-projects" / "zb-orchestrator"

# Relative to repo root — used with ``resolve_orchestrator_workspace(...)``.
CLEANUP_ZB_AGENT_DOCKER_SKILL = ".cursor/skills/cleanup-zb-agent-docker/SKILL.md"


def resolve_orchestrator_workspace(
    skill_relative: str = ".cursor/skills/generate-timesheet/SKILL.md",
) -> Path | None:
    """
    Directory for orchestrator workflows: prefer the standard zb-projects path,
    else the repo that contains this file if it has the given skill file
    (default: generate-timesheet).
    """
    skill = Path(skill_relative)
    if ORCHESTRATOR_ROOT.is_dir() and (ORCHESTRATOR_ROOT / skill).is_file():
        return ORCHESTRATOR_ROOT.resolve()
    here = Path(__file__).resolve().parent
    if (here / skill).is_file():
        return here
    return None


def build_cleanup_zb_agent_docker_prompt(*, intent: str = "") -> str:
    """Seed prompt for Cursor Agent: Docker cleanup via ``cleanup-zb-agent-docker`` skill."""
    focus = intent.strip()
    intent_line = focus if focus else "Stop and remove all running Docker containers on this machine."
    return "\n".join(
        [
            f"Intent: {intent_line}",
            "",
            "Follow `.cursor/skills/cleanup-zb-agent-docker/SKILL.md` — especially **Execution rules (mandatory)**.",
            "",
            "From this workspace root, the canonical command is:",
            "  bash scripts/cleanup-zb-agent-docker.sh",
            "",
            "Use the terminal tool to run the script when appropriate. Do not reply with only a summary "
            "of what the script would do without running it, unless the user explicitly asked for an "
            "explanation only or Docker is unavailable.",
            "",
            "This session is operational cleanup only: do not run **init-local-ticket-branch** or create "
            "git branches unless the user explicitly asks to change this repository.",
        ]
    )


def run_cleanup_zb_agent_docker_sh(
    orchestrator: Path | None = None,
) -> int:
    """
    Run ``scripts/cleanup-zb-agent-docker.sh`` in the orchestrator repo (stop/remove all running containers).
    Resolves workspace via the default generate-timesheet skill path when ``orchestrator`` is None.
    Returns the shell script exit code.
    """
    root = orchestrator if orchestrator is not None else resolve_orchestrator_workspace()
    if root is None:
        print(
            "cleanup-zb-agent-docker: could not resolve zb-orchestrator (expected "
            f"{ORCHESTRATOR_ROOT} or a clone with .cursor/skills/generate-timesheet/SKILL.md).",
            file=sys.stderr,
        )
        return 7
    script = root / "scripts" / "cleanup-zb-agent-docker.sh"
    if not script.is_file():
        print(f"Missing script: {script}", file=sys.stderr)
        return 6
    r = subprocess.run(["bash", str(script)], cwd=str(root), check=False)
    return int(r.returncode)


def build_timesheet_prompt(*, intent: str) -> str:
    """Seed prompt for Cursor Agent: Jira timesheet via the generate-timesheet skill in this repo."""
    return "\n".join(
        [
            f"Intent: {intent}",
            "",
            "Follow `.cursor/skills/generate-timesheet/SKILL.md` — especially **Execution rules (mandatory)**.",
            "",
            "You must **execute the workflow step by step** with real tool calls when available:",
            "1) getAccessibleAtlassianResources → cloudId",
            "2) atlassianUserInfo → accountId",
            "3) build JQL, then searchJiraIssuesUsingJql",
            "4) format issues from the API result (or handle empty/errors per the skill).",
            "",
            "Do not answer with only a summary of the skill or hypothetical steps. Do not claim MCP "
            "is unavailable before attempting those calls. Use each tool’s output in the next step.",
            "",
            "This session is read-only for Jira reporting: do not run **init-local-ticket-branch** or "
            "create git branches unless the user explicitly asks to change this repository.",
        ]
    )


def open_in_cursor(
    ide_target: Path,
    *,
    agent_workspace_dir: Path | None = None,
    agent_prompt: str | None = None,
    mcp: str | None = None,
) -> None:
    """When ``mcp`` is set, append ``--approve-mcps`` so workspace MCP servers load without approval prompts."""
    cursor = shutil.which("cursor") or shutil.which("cursors")  # rare alias
    if not cursor:
        print("Cursor CLI not found on PATH. Install shell command from Cursor:", file=sys.stderr)
        print('  Command Palette → "Shell Command: Install \'cursor\' command in PATH"', file=sys.stderr)
        print(f"Or open manually: {ide_target}", file=sys.stderr)
        return

    if agent_prompt and agent_workspace_dir:
        cmd = [cursor, "agent"]
        # Cursor Agent loads MCP from .cursor/mcp.json for the workspace. There is no --mcp <name>
        # flag; use --approve-mcps so configured servers (e.g. "jira") are approved without prompts.
        if mcp:
            cmd.append("--approve-mcps")
        cmd.extend(["--workspace", str(agent_workspace_dir), agent_prompt])
        r = subprocess.run(cmd, check=False)
        if r.returncode != 0 and mcp:
            print(
                f"cursor agent with --approve-mcps exited {r.returncode}; retrying without it.",
                file=sys.stderr,
            )
            r = subprocess.run(
                [cursor, "agent", "--workspace", str(agent_workspace_dir), agent_prompt],
                check=False,
            )
        if r.returncode != 0:
            print(
                "cursor agent failed; opening the IDE only. Paste this into Cursor Agent if needed:",
                file=sys.stderr,
            )
            print(agent_prompt, file=sys.stderr)
            subprocess.run([cursor, str(ide_target)], check=False)
        return

    subprocess.run([cursor, str(ide_target)], check=False)
