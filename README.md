# zb-orchestrator

Personal tooling around **Cursor** and **Jira**: pick projects under `~/zb-projects`, run **Cursor Agent** with seeded prompts, and produce **timesheets** from Jira (MCP) and/or **Google Calendar** screenshots.

## Contents

| Item | Role |
|------|------|
| [`zb-agent.py`](zb-agent.py) | Interactive navigator over `~/zb-projects`; opens one project or a multi-root workspace in **Cursor Agent** (or IDE only), or **`--cli-only`** for a shell in the repo. Optional `--ticket`, `--reason` (OpenAI), `--noops`. |
| [`jira-timesheet-agent`](jira-timesheet-agent) | Opens this repo in Cursor with a seed for the **generate-timesheet** skill (Atlassian MCP). |
| [`timesheet-agent`](timesheet-agent) | Headless **calendar vision** (`cursor agent --print`) + deterministic [`format_calendar_meetings.py`](format_calendar_meetings.py). **By default** also runs **Jira** generate-timesheet in parallel; stdout is `[JIRA_AGENT_OUTPUT]` / `[TIMESHEET-OUTPUT]`. **`--no-jira`** for calendar-only. |
| [`timesheet-ui`](timesheet-ui) | Local web UI (Flask) on **127.0.0.1** — upload screenshot, optional calendar-only; runs **`timesheet-agent`** in the background. See [README-timesheet-agent.md](README-timesheet-agent.md#web-ui-optional). |
| [`cursor_agent_runner.py`](cursor_agent_runner.py) | Subprocess helper for `cursor agent --print` (models, timeouts, `--approve-mcps` for MCP workflows). |
| [`zb_orchestrator_launch.py`](zb_orchestrator_launch.py) | Resolves the orchestrator workspace, builds timesheet prompts, **`cursor agent`** / `cursor` launch. |
| [`.cursor/skills/generate-timesheet/SKILL.md`](.cursor/skills/generate-timesheet/SKILL.md) | Jira timesheet workflow (MCP steps, output format). |
| [`.cursor/skills/clean-up-current-branch/SKILL.md`](.cursor/skills/clean-up-current-branch/SKILL.md) | Stash, checkout `main`, delete current branch. |
| [`.cursor/rules/`](.cursor/rules/) | Cursor rules: zb-agent ticket workflow, timesheet capture hints, etc. |

## Installation

### 1. Clone

```bash
git clone git@github.com:williamvzen/zb-orchestrator.git
cd zb-orchestrator
```

### 2. Python dependencies

Requires **Python 3** with `pip`. Install packages used by `zb-agent` (e.g. `--reason` / OpenAI) and shared helpers:

```bash
pip install -r requirements.txt
```

(`requirements.txt` currently pulls in `openai` and `Pillow`.)

### 3. Cursor CLI

Scripts call **`cursor`** and **`cursor agent`**. Install the shell command once from Cursor: **Command Palette → “Shell Command: Install 'cursor' command in PATH”**.

### 4. Optional: `zb-agent` on your PATH

From the repo root, install a **`zb-agent`** symlink under `~/.local/bin` pointing at [`zb-agent.py`](zb-agent.py):

```bash
./zb-agent.py --install
```

Non-interactive (CI or scripts):

```bash
./zb-agent.py --install -y
```

Ensure **`~/.local/bin`** is on your `PATH` (common on macOS/Linux):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

After that you can run **`zb-agent`** from any directory. Otherwise invoke **`./zb-agent.py`** with the path to this clone.

### 5. API keys (only if you use them)

| Use case | Variable |
|----------|----------|
| **zb-agent** `--reason` with OpenAI | `OPENAI_API_KEY` or `ZB_AGENT_API_KEY` |
| Ollama / other backends | See [README-zb-agent.md](README-zb-agent.md) |

Calendar / Jira flows use the **Cursor** CLI only unless you opt into `--reason`.

### 6. Jira MCP (timesheet from Jira)

For [`jira-timesheet-agent`](jira-timesheet-agent) or **`timesheet-agent`** (default Jira leg), configure the **Atlassian / Jira** MCP in Cursor and ensure this repo (or your orchestrator checkout) is the **`cursor agent --workspace`** target so [`.cursor/mcp.json`](.cursor/mcp.json) loads.

## Documentation

- **[README-zb-agent.md](README-zb-agent.md)** — `zb-agent` usage, flags, Cursor skills for branches/commits. Examples there may say `./tools/zb-agent.py`; in **this** repo use **`./zb-agent.py`** or the installed **`zb-agent`** command.
- **[README-timesheet-agent.md](README-timesheet-agent.md)** — Calendar screenshot flow, `--capture`, default Jira + `--no-jira`, env vars (`CURSOR_AGENT_*`).

## Remote

Default remote: `git@github.com:williamvzen/zb-orchestrator.git`
