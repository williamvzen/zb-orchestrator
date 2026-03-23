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


def resolve_orchestrator_workspace() -> Path | None:
    """
    Directory for the generate-timesheet skill: prefer the standard zb-projects path,
    else the repo that contains this file if it has `.cursor/skills/generate-timesheet/SKILL.md`.
    """
    skill = Path(".cursor/skills/generate-timesheet/SKILL.md")
    if ORCHESTRATOR_ROOT.is_dir() and (ORCHESTRATOR_ROOT / skill).is_file():
        return ORCHESTRATOR_ROOT.resolve()
    here = Path(__file__).resolve().parent
    if (here / skill).is_file():
        return here
    return None


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
