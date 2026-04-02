#!/usr/bin/env python3
"""
ZB project navigator: reads the zb-projects tree under ``~/zb-projects``, asks what you
want to work on, opens one project in Cursor Agent (seed prompt + workspace) or creates
a multi-root workspace for several. Use --ide-only to open the folder/workspace in the IDE only.
Use --cli-only to skip Cursor and start an interactive shell in the chosen repo (or tmux with one pane per repo when multiple).
Use --noops for read-only exploration (documented intent; the flag is a no-op and does not change the seed prompt or env).
For Jira timesheets use **timesheet-agent** (same directory). The zb-projects root is always
``~/zb-projects`` for discovery, regardless of where this script lives.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any, NoReturn

from zb_orchestrator_launch import open_in_cursor


# zb-projects root: always the user’s ~/zb-projects (not derived from this script’s path).
ROOT = (Path.home() / "zb-projects").resolve()
WORKSPACES_DIR = ROOT / ".zb-workspaces"


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    category: str  # e.g. python-projects

    @property
    def abs_str(self) -> str:
        return str(self.path.resolve())


@dataclass(frozen=True)
class ReasoningConfig:
    """Resolved settings for --reason (OpenAI API or Ollama’s OpenAI-compatible server)."""

    api_key: str | None  # None → skip LLM (OpenAI path only)
    base_url: str
    model: str
    json_mode: bool
    backend: str  # "openai" | "ollama"


def resolve_reasoning_config() -> ReasoningConfig:
    """
    Ollama: OpenAI-compatible base URL is <host>:11434/v1 (see https://github.com/ollama/ollama/blob/main/docs/openai.md).
    Default model qwen2.5:7b — strong instruction-following and JSON-ish output for routing tasks.
    """
    raw = os.environ.get("ZB_AGENT_BACKEND", "openai").strip().lower()
    if raw in ("ollama", "local"):
        explicit = os.environ.get("ZB_AGENT_OPENAI_BASE_URL")
        if explicit:
            base_url = explicit.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"
        else:
            host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
            base_url = host if host.endswith("/v1") else f"{host}/v1"
        model = os.environ.get("ZB_AGENT_MODEL", "qwen2.5:7b")
        api_key = os.environ.get("ZB_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY") or "ollama"
        jm = os.environ.get("ZB_AGENT_JSON_MODE")
        if jm is None:
            json_mode = False
        else:
            json_mode = jm not in ("0", "false", "no")
        return ReasoningConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            json_mode=json_mode,
            backend="ollama",
        )

    api_key = os.environ.get("ZB_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("ZB_AGENT_OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("ZB_AGENT_MODEL", "gpt-4o-mini")
    json_mode = os.environ.get("ZB_AGENT_JSON_MODE", "1") not in ("0", "false", "no")
    return ReasoningConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        json_mode=json_mode,
        backend="openai",
    )


def ollama_api_origin_from_openai_base_url(base_url: str) -> str:
    """Strip OpenAI-compat /v1 suffix → Ollama root (e.g. http://127.0.0.1:11434)."""
    u = base_url.rstrip("/")
    if u.endswith("/v1"):
        u = u[:-3]
    return u.rstrip("/")


def fetch_ollama_model_names(origin: str) -> tuple[set[str] | None, str | None]:
    """
    GET /api/tags. Returns (names, error_message).
    error_message is set when the request fails (e.g. connection refused).
    """
    url = origin.rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return None, f"HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return None, str(e)
    except (TimeoutError, json.JSONDecodeError, OSError) as e:
        return None, str(e)
    names: set[str] = set()
    for m in data.get("models") or []:
        n = m.get("name")
        if isinstance(n, str) and n:
            names.add(n)
    return names, None


def ollama_model_installed(wanted: str, available: set[str]) -> bool:
    """True if `wanted` matches a tag exactly or as an unambiguous prefix (e.g. llama3.2 → llama3.2:latest)."""
    if wanted in available:
        return True
    prefix = wanted + ":"
    return any(n.startswith(prefix) for n in available)


def run_ollama_pull(model: str) -> bool:
    exe = shutil.which("ollama")
    if not exe:
        return False
    r = subprocess.run([exe, "pull", model], check=False)
    return r.returncode == 0


def ensure_ollama_model_ready(
    cfg: ReasoningConfig,
    *,
    interactive: bool,
    auto_pull: bool,
) -> None:
    """
    Verify the configured model exists locally (Ollama /api/tags). If not, suggest
    `ollama pull <model>`, optionally run it (auto_pull or interactive prompt), then re-check.
    Raises RuntimeError if the model is still missing or Ollama is unreachable.
    """
    if cfg.backend != "ollama":
        return
    origin = ollama_api_origin_from_openai_base_url(cfg.base_url)
    names, err = fetch_ollama_model_names(origin)
    if err is not None:
        raise RuntimeError(
            f"Cannot reach Ollama at {origin} ({err}). "
            "Is the Ollama app running (or `ollama serve`)?"
        )
    assert names is not None
    if ollama_model_installed(cfg.model, names):
        return

    pull_cmd = f"ollama pull {cfg.model}"
    exe = shutil.which("ollama")

    def _print_install_hint(*, note_cli: bool) -> None:
        print(f"Ollama model {cfg.model!r} is not installed.", file=sys.stderr)
        print(f"  {pull_cmd}", file=sys.stderr)
        if note_cli and not exe:
            print("  (Install the `ollama` CLI from https://ollama.com to pull models.)", file=sys.stderr)

    if auto_pull and exe:
        print(f"Pulling Ollama model {cfg.model!r} …", file=sys.stderr)
        if not run_ollama_pull(cfg.model):
            _print_install_hint(note_cli=False)
            raise RuntimeError(f"ollama pull failed for {cfg.model!r}")
        names2, err2 = fetch_ollama_model_names(origin)
        if err2 or names2 is None or not ollama_model_installed(cfg.model, names2):
            _print_install_hint(note_cli=False)
            raise RuntimeError(f"Model {cfg.model!r} still not available after pull.")
        return

    if interactive and exe and not auto_pull:
        _print_install_hint(note_cli=False)
        try:
            ans = input(f"Run `{pull_cmd}` now? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans in ("y", "yes"):
            print(f"Pulling Ollama model {cfg.model!r} …", file=sys.stderr)
            if not run_ollama_pull(cfg.model):
                _print_install_hint(note_cli=False)
                raise RuntimeError(f"ollama pull failed for {cfg.model!r}")
            names2, err2 = fetch_ollama_model_names(origin)
            if err2 or names2 is None or not ollama_model_installed(cfg.model, names2):
                _print_install_hint(note_cli=False)
                raise RuntimeError(f"Model {cfg.model!r} still not available after pull.")
            return

    _print_install_hint(note_cli=True)
    raise RuntimeError(f"Ollama model {cfg.model!r} is not available. Install with: {pull_cmd}")


def run_tree() -> str:
    try:
        r = subprocess.run(
            ["tree", "-L", "2", str(ROOT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback if tree is missing
    lines = [str(ROOT)]
    for top in sorted(ROOT.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        lines.append(f"├── {top.name}/")
        try:
            for child in sorted(top.iterdir())[:200]:
                if child.is_dir() and not child.name.startswith("."):
                    lines.append(f"│   ├── {child.name}/")
        except OSError:
            pass
    return "\n".join(lines) + "\n"


def discover_projects() -> list[Project]:
    projects: list[Project] = []
    for category in sorted(ROOT.iterdir()):
        if not category.is_dir() or category.name.startswith("."):
            continue
        if category.name in ("tools",):
            continue
        try:
            for child in sorted(category.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                projects.append(
                    Project(
                        name=child.name,
                        path=child,
                        category=category.name,
                    )
                )
        except OSError:
            continue
    return projects


def index_by_name(projects: list[Project]) -> dict[str, list[Project]]:
    by: dict[str, list[Project]] = {}
    for p in projects:
        by.setdefault(p.name.lower(), []).append(p)
    return by


def split_intent(text: str) -> list[str]:
    # "zenapi and zenscripts", "a, b", "foo / bar"
    parts = re.split(r"\s+(?:and|&|\+|/|,|;)\s+|\s*,\s*", text.strip(), flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _candidates_for_fragment(
    fragment: str,
    projects: list[Project],
    by_lower: dict[str, list[Project]],
) -> list[Project]:
    t = fragment.strip().lower()
    if not t:
        return []
    if t in by_lower:
        return list(by_lower[t])
    names = [p.name for p in projects]
    matches = get_close_matches(fragment, names, n=5, cutoff=0.45)
    if matches:
        out: list[Project] = []
        for m in matches:
            k = m.lower()
            if k in by_lower:
                out.extend(by_lower[k])
        return out
    subs = [p for p in projects if t in p.name.lower()]
    return subs


def _category_alias(part: str) -> str | None:
    p = part.strip().lower().rstrip("/")
    aliases = {
        "ai": "ai-projects",
        "go": "go-projects",
        "js": "javascript-projects",
        "javascript": "javascript-projects",
        "python": "python-projects",
    }
    if p in aliases:
        return aliases[p]
    if p in (
        "ai-projects",
        "go-projects",
        "javascript-projects",
        "python-projects",
    ):
        return p
    return None


def try_qualified_project(token: str, projects: list[Project]) -> Project | None:
    """Match `python-projects/zenapi` or `python/zenapi` (disambiguate duplicates)."""
    raw = token.strip()
    if "/" not in raw:
        return None
    a, b = raw.split("/", 1)
    cat = _category_alias(a)
    if not cat:
        return None
    name = b.strip().strip("/")
    if not name:
        return None
    for p in projects:
        if p.category == cat and p.name == name:
            return p
    return None


def resolve_token(
    token: str,
    projects: list[Project],
    by_lower: dict[str, list[Project]],
) -> Project | list[Project] | None:
    q = try_qualified_project(token, projects)
    if q is not None:
        return q
    t = token.strip().lower()
    if not t:
        return None
    if t in by_lower and len(by_lower[t]) == 1:
        return by_lower[t][0]
    if t in by_lower and len(by_lower[t]) > 1:
        return by_lower[t]
    # Try whole token first
    c = _candidates_for_fragment(token, projects, by_lower)
    if len(c) == 1:
        return c[0]
    if len(c) > 1:
        return c
    # Phrases like "work on zenscripts" — try each word
    words = re.findall(r"[a-z0-9][a-z0-9._-]*", t, flags=re.IGNORECASE)
    for w in words:
        if len(w) < 3:
            continue
        c = _candidates_for_fragment(w, projects, by_lower)
        if len(c) == 1:
            return c[0]
        if len(c) > 1:
            return c
    return None


def pick_disambiguation(cands: list[Project], label: str) -> Project | None:
    print(f"\nMultiple matches for {label!r}:")
    for i, p in enumerate(cands, 1):
        print(f"  {i}. {p.category}/{p.name}")
    try:
        raw = input("Pick number (or Enter to skip): ").strip()
    except EOFError:
        return None
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    if 1 <= n <= len(cands):
        return cands[n - 1]
    return None


def resolve_intent(
    text: str,
    projects: list[Project],
    interactive: bool,
) -> tuple[list[Project], list[str]]:
    by_lower = index_by_name(projects)
    unresolved: list[str] = []
    resolved: list[Project] = []
    seen: set[Path] = set()
    for token in split_intent(text):
        r = resolve_token(token, projects, by_lower)
        p: Project | None = None
        if isinstance(r, Project):
            p = r
        elif isinstance(r, list) and r:
            if len(r) == 1:
                p = r[0]
            elif interactive:
                p = pick_disambiguation(r, token)
            if p is None and isinstance(r, list) and len(r) > 1 and not interactive:
                unresolved.append(
                    f"{token} (ambiguous: {', '.join(f'{x.category}/{x.name}' for x in r)})"
                )
                continue
        if p is None and r is None:
            t = token.strip().lower()
            cands = [x for x in projects if t in x.name.lower()]
            if len(cands) == 1:
                p = cands[0]
        if p is None:
            unresolved.append(token)
            continue
        if p.path not in seen:
            seen.add(p.path)
            resolved.append(p)
    return resolved, unresolved


def _pick_shell_executable() -> str:
    """Return a shell path for exec/spawn (prefer $SHELL if it exists)."""
    s = os.environ.get("SHELL", "").strip()
    if s and Path(s).is_file():
        return s
    for name in ("zsh", "bash", "sh"):
        p = shutil.which(name)
        if p:
            return p
    return "/bin/sh"


def spawn_cli_shell(projects: list[Project]) -> NoReturn:
    """
    Drop into a shell with the resolved repo directories.

    One project: chdir there and replace this process with an interactive shell.
    Several: if ``tmux`` is on PATH, open a new session with one pane per repo
    (tiled); otherwise chdir to the first repo, set ZB_AGENT_REPOS, and spawn a
    shell there (other paths are printed).
    """
    paths = [p.path.resolve() for p in projects]
    repos_env = ":".join(str(p) for p in paths)
    os.environ["ZB_AGENT_REPOS"] = repos_env

    if len(paths) == 1:
        shell = _pick_shell_executable()
        base = os.path.basename(shell)
        try:
            os.chdir(paths[0])
        except OSError as e:
            print(f"Cannot cd to {paths[0]}: {e}", file=sys.stderr)
            sys.exit(1)
        os.execl(shell, base, "-i")

    tmux = shutil.which("tmux")
    if tmux:
        session = f"zb-agent-{uuid.uuid4().hex[:10]}"
        cmd: list[str] = [
            tmux,
            "new-session",
            "-c",
            str(paths[0]),
            "-s",
            session,
        ]
        for p in paths[1:]:
            cmd.extend([";", "split-window", "-c", str(p)])
        cmd.extend([";", "select-layout", "tiled", ";", "attach"])
        r = subprocess.run(cmd)
        if r.returncode == 0:
            sys.exit(0)
        print("tmux failed; falling back to a single shell.", file=sys.stderr)

    # No tmux or tmux failed: first repo + printed list
    print("Repositories (ZB_AGENT_REPOS is set):", file=sys.stderr)
    for p in paths:
        print(f"  {p}", file=sys.stderr)
    print(f"Starting shell in: {paths[0]}", file=sys.stderr)
    shell = _pick_shell_executable()
    base = os.path.basename(shell)
    try:
        os.chdir(paths[0])
    except OSError as e:
        print(f"Cannot cd to {paths[0]}: {e}", file=sys.stderr)
        sys.exit(1)
    os.execl(shell, base, "-i")


def write_workspace(paths: list[Project]) -> Path:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    slug = "-".join(p.name for p in paths)
    out = WORKSPACES_DIR / f"{slug}.code-workspace"
    data = {
        "folders": [{"name": p.name, "path": str(p.path.resolve())} for p in paths],
        "settings": {},
    }
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def project_id(p: Project) -> str:
    return f"{p.category}/{p.name}"


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        out = json.loads(text)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object in model output")


def _openai_compatible_chat(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    base_url: str,
    model: str,
    json_mode: bool,
) -> str:
    from openai import APIError, OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "timeout": 120.0,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = client.chat.completions.create(**kwargs)
    except APIError as e:
        raise RuntimeError(str(e)) from e
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Empty message content from model")
    return content


def reason_select_projects(
    intent: str,
    projects: list[Project],
    *,
    api_key: str,
    base_url: str,
    model: str,
    json_mode: bool,
) -> tuple[list[Project], str]:
    """
    Ask an LLM to pick projects from the catalog. Returns (resolved, reasoning).
    """
    by_pid = {project_id(p): p for p in projects}
    catalog = sorted(by_pid.keys())
    system = (
        "You choose which zb-projects repositories the user needs. "
        'Reply with a single JSON object only: {"reasoning": string, "selections": string[]}. '
        'Each selection MUST be an exact id from the provided catalog (format "category/name"). '
        "If nothing matches, use an empty selections array and explain in reasoning."
    )
    user = json.dumps(
        {"intent": intent, "catalog": catalog},
        indent=2,
    )
    content = _openai_compatible_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        api_key=api_key,
        base_url=base_url,
        model=model,
        json_mode=json_mode,
    )
    parsed = _extract_json_object(content)
    reasoning = str(parsed.get("reasoning", "")).strip()
    raw_sel = parsed.get("selections")
    if not isinstance(raw_sel, list):
        raise ValueError("Model JSON missing 'selections' array")
    out: list[Project] = []
    seen: set[Path] = set()
    for item in raw_sel:
        sid = str(item).strip()
        p = by_pid.get(sid)
        if p is None:
            # allow model to omit category if name is unique
            matches = [x for x in projects if project_id(x).endswith("/" + sid) or x.name == sid]
            if len(matches) == 1:
                p = matches[0]
        if p is None:
            raise ValueError(f"Invalid selection id from model: {item!r}")
        if p.path not in seen:
            seen.add(p.path)
            out.append(p)
    return out, reasoning


def build_cursor_agent_prompt(
    *,
    intent: str,
    ticket: str | None = None,
    reasoning: str | None = None,
) -> str:
    lines: list[str] = []
    if ticket:
        lines.append(f"Work on Jira ticket {ticket}.")
    lines.append(f"Intent: {intent}")
    if reasoning and reasoning.strip():
        lines.append(f"Planning notes: {reasoning.strip()}")
    if ticket:
        lines.append(
            "Workflow: use Cursor skills when relevant — init-local-ticket-branch "
            "(branch from main, push, Jira In Progress if applicable) and "
            "commit-it-then (conventional commits with this ticket in brackets)."
        )
    else:
        lines.append(
            "Workflow: use Cursor skills when relevant. If this work maps to a Jira ticket, "
            "use init-local-ticket-branch and commit-it-then with the ticket in brackets; "
            "otherwise use commit-it-then with [NOTICKET] when committing."
        )
    return "\n".join(lines)


def resolve_ticket_value(
    *,
    raw: str | None,
    interactive: bool,
) -> str | None:
    """
    raw: None = --ticket not passed; use ZB_AGENT_TICKET if set.
    raw == '' = --ticket with no value; prompt when interactive.
    """
    t: str | None
    if raw is None:
        t = os.environ.get("ZB_AGENT_TICKET", "").strip() or None
    elif raw == "":
        if not interactive:
            print(
                "Ticket required: pass --ticket KEY, set ZB_AGENT_TICKET, or run in a TTY.",
                file=sys.stderr,
            )
            sys.exit(1)
        t = input("What ticket do you want to work on? (e.g. ECOMM-2384)\n> ").strip()
    else:
        t = raw.strip()
    return t if t else None


def install_zb_agent_command(*, yes: bool) -> int:
    """
    Symlink this script to ~/.local/bin/zb-agent so it can be run from any directory.
    Returns a process exit code (0 = ok / skipped, 1 = error).
    """
    script = Path(__file__).resolve()
    local_bin = Path.home() / ".local" / "bin"
    link = local_bin / "zb-agent"

    try:
        local_bin.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Cannot create {local_bin}: {e}", file=sys.stderr)
        return 1

    if link.is_symlink():
        try:
            if link.resolve() == script:
                print(f"Already installed: {link} -> {script}")
                return 0
        except OSError:
            pass
    elif link.exists():
        print(
            f"Refusing to overwrite existing file (not a symlink): {link}",
            file=sys.stderr,
        )
        return 1

    if not yes:
        if not sys.stdin.isatty():
            print(
                "Install needs confirmation: run in a terminal, or use: "
                f"{sys.argv[0]} --install -y",
                file=sys.stderr,
            )
            return 1
        try:
            r = input(
                "Install `zb-agent` as a command?\n"
                f"  This creates {link} pointing at this script so you can run "
                "`zb-agent` from anywhere. [y/N] "
            ).strip().lower()
        except EOFError:
            r = ""
        if r not in ("y", "yes"):
            print("Cancelled.")
            return 0

    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(script)
    except OSError as e:
        print(f"Could not create symlink: {e}", file=sys.stderr)
        print(
            f"Fallback: alias zb-agent='{sys.executable} {script}'",
            file=sys.stderr,
        )
        return 1

    print(f"Installed: {link} -> {script}")
    print(
        "Add ~/.local/bin to PATH if needed, e.g. export PATH=\"$HOME/.local/bin:$PATH\""
    )
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Navigate zb-projects and open Cursor workspace(s).")
    ap.add_argument("intent", nargs="*", help='e.g. zenscripts or "zenapi and zenscripts"')
    ap.add_argument("--tree", action="store_true", help="Print tree -L 2 and exit")
    ap.add_argument("--list", action="store_true", help="List discovered projects and exit")
    ap.add_argument("--no-open", action="store_true", help="Do not launch Cursor")
    ap.add_argument(
        "--ide-only",
        action="store_true",
        help="Open folder/workspace with plain `cursor` (no Cursor Agent seed prompt)",
    )
    ap.add_argument(
        "--cli-only",
        action="store_true",
        help="Do not launch Cursor; open a shell in the repo (tmux with one pane per repo if several)",
    )
    ap.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Non-interactive: skip prompts (ambiguous names exit with error; with --install, skip install confirm)",
    )
    ap.add_argument(
        "--install",
        action="store_true",
        help="Offer to install the `zb-agent` command in ~/.local/bin (symlink to this script)",
    )
    ap.add_argument(
        "--reason",
        action="store_true",
        help="Use an LLM to interpret intent (OpenAI or Ollama OpenAI-compatible API); see README",
    )
    ap.add_argument(
        "--no-reason-fallback",
        action="store_true",
        help="With --reason: do not fall back to rule-based matching if the LLM fails",
    )
    ap.add_argument(
        "--ollama",
        action="store_true",
        help="Use local Ollama (OpenAI-compatible API); same as ZB_AGENT_BACKEND=ollama",
    )
    ap.add_argument(
        "--ollama-pull",
        action="store_true",
        help="If the Ollama model is missing, run `ollama pull <model>` automatically",
    )
    ap.add_argument(
        "--ticket",
        nargs="?",
        const="",
        default=None,
        metavar="KEY",
        help="Jira key (e.g. ECOMM-2384). Omit value to be prompted. Env: ZB_AGENT_TICKET",
    )
    ap.add_argument(
        "--noops",
        action="store_true",
        help=(
            "Read-only exploration (documented intent: seed omits branch/commit workflow). "
            "No-op: does not change the seed prompt or behavior."
        ),
    )
    args = ap.parse_args()
    # --noops / ZB_AGENT_NOOPS: no-ops (do not alter seed prompt, env, or runtime behavior).
    # Intended read-only workflow is documented in README and rules.
    _ = args.noops
    if args.ollama:
        os.environ.setdefault("ZB_AGENT_BACKEND", "ollama")

    if args.install:
        sys.exit(install_zb_agent_command(yes=args.yes))

    if args.tree:
        print(run_tree(), end="")
        return

    projects = discover_projects()
    if args.list:
        for p in sorted(projects, key=lambda x: (x.category, x.name)):
            print(f"{p.category}/{p.name}")
        return

    intent: str | None
    if args.intent:
        intent = " ".join(args.intent)
    else:
        print(run_tree(), end="")
        print()
        intent = input("What do you want to work on? (project name(s), e.g. zenscripts or zenapi and zenscripts)\n> ").strip()

    if not intent:
        print("No input.", file=sys.stderr)
        sys.exit(1)

    interactive = sys.stdin.isatty() and not args.yes
    resolved: list[Project] = []
    unresolved: list[str] = []
    reasoning_text: str | None = None

    if args.reason:
        cfg = resolve_reasoning_config()
        if not cfg.api_key:
            msg = "ZB_AGENT_API_KEY or OPENAI_API_KEY must be set for --reason (OpenAI backend)"
            if args.no_reason_fallback:
                print(msg, file=sys.stderr)
                sys.exit(4)
            print(f"Note: {msg}; using rule-based matching.", file=sys.stderr)
            resolved, unresolved = resolve_intent(intent, projects, interactive=interactive)
        else:
            try:
                if cfg.backend == "ollama":
                    auto_pull = args.ollama_pull or os.environ.get(
                        "ZB_AGENT_OLLAMA_PULL", ""
                    ).strip().lower() in ("1", "true", "yes")
                    ensure_ollama_model_ready(
                        cfg,
                        interactive=interactive,
                        auto_pull=auto_pull,
                    )
                resolved, reasoning_text = reason_select_projects(
                    intent,
                    projects,
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                    model=cfg.model,
                    json_mode=cfg.json_mode,
                )
                print("Reasoning:")
                print(reasoning_text or "(none)")
                print()
            except ImportError as e:
                if args.no_reason_fallback:
                    print(
                        "Install the openai package: pip install -r tools/requirements.txt",
                        file=sys.stderr,
                    )
                    sys.exit(6)
                print(
                    f"openai package not available ({e}); falling back to rule-based matching.",
                    file=sys.stderr,
                )
                resolved, unresolved = resolve_intent(intent, projects, interactive=interactive)
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError, KeyError) as e:
                if args.no_reason_fallback:
                    print(f"LLM reasoning failed: {e}", file=sys.stderr)
                    sys.exit(5)
                print(f"LLM reasoning failed ({e}); falling back to rule-based matching.", file=sys.stderr)
                resolved, unresolved = resolve_intent(intent, projects, interactive=interactive)
    else:
        resolved, unresolved = resolve_intent(intent, projects, interactive=interactive)

    if unresolved:
        print("Could not resolve:", ", ".join(unresolved), file=sys.stderr)
        print("Known projects (name → path):", file=sys.stderr)
        for p in sorted(projects, key=lambda x: x.name.lower()):
            if any(u.lower() in p.name.lower() for u in unresolved):
                print(f"  {p.category}/{p.name}", file=sys.stderr)
        sys.exit(2)

    if not resolved:
        print("No projects matched.", file=sys.stderr)
        sys.exit(3)

    if args.cli_only:
        for p in resolved:
            print(f"→ {p.category}/{p.name}")
            print(f"  {p.abs_str}")
        spawn_cli_shell(resolved)

    ticket = resolve_ticket_value(raw=args.ticket, interactive=interactive)
    agent_prompt: str | None = None
    if not args.ide_only:
        agent_prompt = build_cursor_agent_prompt(
            intent=intent,
            ticket=ticket,
            reasoning=reasoning_text,
        )

    if len(resolved) == 1:
        p = resolved[0]
        print(f"→ {p.category}/{p.name}")
        print(f"  {p.abs_str}")
        if not args.no_open:
            open_in_cursor(
                p.path,
                agent_workspace_dir=p.path if agent_prompt else None,
                agent_prompt=agent_prompt,
            )
        elif agent_prompt:
            print()
            print("Cursor Agent prompt (not launched):")
            print(agent_prompt)
        return

    ws = write_workspace(resolved)
    print("Multi-root workspace:")
    for p in resolved:
        print(f"  • {p.category}/{p.name}")
    print(f"→ {ws}")
    if agent_prompt and len(resolved) > 1:
        print(
            "Note: cursor agent --workspace expects a folder; using the first project for Agent.",
            file=sys.stderr,
        )
    if not args.no_open:
        open_in_cursor(
            ws,
            agent_workspace_dir=resolved[0].path if agent_prompt else None,
            agent_prompt=agent_prompt,
        )
    elif agent_prompt:
        print()
        print("Cursor Agent prompt (not launched):")
        print(agent_prompt)
        print(f"Multi-root workspace file: {ws}")


if __name__ == "__main__":
    main()
