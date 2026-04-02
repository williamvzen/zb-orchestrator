# Timesheet agent: calendar from screenshot (Cursor Agent)

[`timesheet-agent`](timesheet-agent) runs **`cursor agent --print`** for **calendar vision** (screenshot → JSON events), then **deterministic** formatting via [`format_calendar_meetings.py`](format_calendar_meetings.py) (weekday headers, ` - Title - Nh` lines). **By default** it also runs the **Jira generate-timesheet** agent in parallel with vision. Pass **`--no-jira`** for calendar-only (one agent + format, no MCP leg).

### Jira + calendar (default)

Use the same **Chrome / screenshot** flow as below. Unless you pass **`--no-jira`**, one command runs **two** `cursor agent --print` subprocesses **in parallel**:

- **Jira leg** — same workflow as [`jira-timesheet-agent`](jira-timesheet-agent): [`generate-timesheet`](.cursor/skills/generate-timesheet/SKILL.md) via Atlassian MCP (`--approve-mcps`).
- **Calendar leg** — vision on the cached screenshot, then formatting.

**Stdout** is two labeled blocks (copy/paste friendly):

---START-OUTPUT-TEXT---
[JIRA_AGENT_OUTPUT]
…Jira timesheet text from the agent…

[TIMESHEET-OUTPUT]
…calendar meetings (default format, or `--json` / `--with-times` shapes)…
---END-OUTPUT-TEXT---

Optional: **`--jira-intent "ECOMM board, last 7 days"`** to steer the Jira agent; otherwise the default matches the standalone Jira launcher. Env: **`CURSOR_AGENT_JIRA_TIMEOUT`**, **`CURSOR_AGENT_JIRA_MODEL`** (overrides **`CURSOR_AGENT_MODEL`** for the Jira run only; vision still uses **`CURSOR_AGENT_VISION_MODEL`**).

**Note:** Two concurrent `cursor agent` runs may contend on some installs; if one leg fails, retry or use **`--no-jira`** and run the Jira leg separately (e.g. [`jira-timesheet-agent`](jira-timesheet-agent)).

**`--json`** skips step 2 on stdout (raw events). **`--with-times`** prints the verbose per-day schedule instead of the meeting list.

**OpenAI is not used** — only the Cursor CLI.

### Model selection (Auto vs fixed model)

Cursor’s CLI accepts **`--model <name>`** (see `cursor agent --help`). To prefer **Auto** instead of a pinned model (e.g. Opus) for scripted runs, set:

```bash
export CURSOR_AGENT_MODEL=auto
```

That is forwarded by `cursor_agent_runner.py` to **`cursor agent`**. Use **`CURSOR_AGENT_VISION_MODEL`** only if the vision step should differ from **`CURSOR_AGENT_MODEL`**.

If **`auto`** fails with **`--print`** in your Cursor version, try another id from **`cursor agent --list-models`**, or pass flags via **`CURSOR_AGENT_EXTRA_ARGS`** (avoid duplicating `--model` if you already set **`CURSOR_AGENT_MODEL`**).

## Prerequisites

- **`cursor`** on your PATH ([install shell command](https://cursor.com) from Cursor).
- Logged-in / authenticated Cursor Agent if your install requires it.

## Env (optional)

| Variable | Meaning |
|----------|---------|
| `CURSOR_AGENT_WORKSPACE` | Workspace root for `cursor agent` (default: directory containing `timesheet-agent`) |
| `CURSOR_AGENT_MODEL` | Model for **`cursor agent`** (vision step). Use **`auto`** for Auto mode — passed as `--model auto` (see `cursor agent --help` and `--list-models`). |
| `CURSOR_AGENT_VISION_MODEL` | Optional: overrides **`CURSOR_AGENT_MODEL`** for the **vision** step only |
| `CURSOR_AGENT_TIMEOUT` | Seconds for the agent run (default `600`) |
| `CURSOR_AGENT_FORCE=1` | Passes `--force` to the CLI when supported |
| `CURSOR_AGENT_EXTRA_ARGS` | Extra args (shell-split) appended before the prompt |
| `CALENDAR_VISION_NO_BROWSER_PROMPT=1` | With `--capture`: skip the “open Google Calendar?” prompt; only print the URL on stderr |

Override workspace on the CLI: **`--cursor-workspace DIR`**.  
**`--no-browser-prompt`**: same as the env var (non-interactive / CI friendly).

## Web UI (optional)

Local browser UI for the same flow as **`./timesheet-agent -i FILE`**: upload a calendar screenshot, set Jira intent and flags, then run the CLI in the background (polls until Cursor Agent finishes).

1. Install UI dependencies: `pip install -r requirements-timesheet-ui.txt`
2. From the repo root: **`./timesheet-ui`** (or `python -m timesheet_ui`)
3. Open the URL printed on stderr (default **http://127.0.0.1:8765/**).

Upload a screenshot and optionally turn off **Include Jira** for calendar-only; Jira range and formatting match the CLI defaults (same as `./timesheet-agent -i FILE` without extra flags).

The server binds to **127.0.0.1** only (no auth). Options: **`--port`**, **`TIMESHEET_UI_PORT`**, **`--host`** (avoid exposing on a LAN).

macOS **`screencapture`** is not available in the browser — capture the calendar to a file, then upload it. The UI does not replace **`--capture`**; use the terminal for interactive capture if you prefer.

## Install command (optional)

From the repo root, install a **`timesheet-agent`** symlink under `~/.local/bin` pointing at [`timesheet-agent`](timesheet-agent):

```bash
./timesheet-agent --install
./timesheet-agent --install -y
```

After `--install`, ensure `~/.local/bin` is on your `PATH` (same pattern as installing **`zb-agent`**; see [README.md](README.md)).

## Usage

```bash
./timesheet-agent
./timesheet-agent --capture
./timesheet-agent --image ~/Desktop/cal.png           # vision agent → Python formatter → stdout
./timesheet-agent -i shot.png --json                    # raw events JSON
./timesheet-agent -i shot.png --with-times              # per-day times + durations (verbose)
./timesheet-agent --capture                             # default: parallel Jira MCP + calendar → labeled stdout
./timesheet-agent -i shot.png --jira-intent "ECOMM last 7 days"
./timesheet-agent -i shot.png --no-jira                 # calendar vision only (no Jira leg)
```

## Agentic workflow (sequence)

End-to-end flow (default): **screenshot → two parallel Cursor Agent runs (Jira MCP + vision) → normalize → `format_calendar_meetings.py` → labeled stdout** (`[JIRA_AGENT_OUTPUT]` / `[TIMESHEET-OUTPUT]`). With **`--no-jira`**: **screenshot → vision only → normalize → format → markdown stdout**.

| Step | What happens | Command / artifact |
|------|----------------|---------------------|
| **1. Open Calendar** | In the browser, go to **Google Calendar** (sign in if needed) so the week/view you need is on screen. | [calendar.google.com/calendar/u/0/r](https://calendar.google.com/calendar/u/0/r) |
| **2. Prepare** | (Optional if you use the prompt below.) Leave the right week in view. | — |
| **3. Capture** | **`--capture`** (macOS): the terminal asks *Open Google Calendar in your default browser now (new tab)? [Y/n]* — **Yes** opens [the calendar URL](https://calendar.google.com/calendar/u/0/r) via the system browser (usually a **new tab**). Then select the window/region to screenshot. **`--image`**: use a file; no browser prompt. | `--capture` or `--image path.png` |
| **4. Run agents** | **Default:** `timesheet-agent` starts **two** **`cursor agent --print`** runs (Jira MCP + vision) in parallel. The vision agent reads **`.calendar_vision_cache/calendar_input.*`**, extracts events, and prints **one JSON object** on stdout; the script parses it. **`--no-jira`:** vision only. | `./timesheet-agent --image shot.png` |
| **5. Normalize** | Script sorts events, normalizes fields (`date_iso`, `title`, `duration_hours`, …). | Internal (`normalize_events`) |
| **6. Format meetings** | Deterministic **`format_calendar_meetings.py`** → markdown on stdout. | *(default)* |
| **7a. Raw JSON** | Emit `events` + `assumptions` only — **skips** step 6 on stdout. | `--json` |
| **7b. Verbose schedule** | Per-day lines with duration and time ranges instead of step 6. | `--with-times` / `-v` |

**Agent chat (Cursor):** You can ask: *“Want to open Google Calendar in the browser before we capture?”* If they say **yes**, have them run **`./timesheet-agent --capture`** in the integrated terminal and answer **`Y`** at the prompt — that opens the calendar from the console in a **new tab** (Python `webbrowser`, default browser). If they prefer to open it themselves, they can say **no** and open the link manually. For automation/CI, use **`--no-browser-prompt`**.

**One-liner examples**

```bash
# After step 1–2: open Calendar in the browser, then e.g.:

# Steps 1–6: default — Jira + vision in parallel; labeled stdout with meeting list in [TIMESHEET-OUTPUT]
./timesheet-agent --image ~/Desktop/cal.png

# Calendar only (no Jira MCP run)
./timesheet-agent --image ~/Desktop/cal.png --no-jira

# JSON only (for piping or saving); still runs Jira leg unless --no-jira
./timesheet-agent --image ~/Desktop/cal.png --json > events.json

# Pipe JSON through the formatter explicitly (same rules as default stdout)
./timesheet-agent --image ~/Desktop/cal.png --json | ./format_calendar_meetings.py

# Verbose schedule with times (skip default format step)
./timesheet-agent --image ~/Desktop/cal.png --with-times
```

Formatting rules live in **[`format_calendar_meetings.py`](format_calendar_meetings.py)** (source of truth).

## Quick run (minimal)

1. Run **`./timesheet-agent --capture`** (macOS). When asked, press **Enter** or **y** to open Google Calendar in a new tab, then select the calendar window/region for the screenshot. Or use **`--image`** with a file you already saved.
2. Wait for the **vision** agent; stderr shows that phase.
3. Treat output as **draft** — small text can be misread.

## Output

- **Default (with Jira):** stdout is **`[JIRA_AGENT_OUTPUT]`** (Jira text) then **`[TIMESHEET-OUTPUT]`** (calendar). The calendar block is a day-grouped list from **`format_calendar_meetings.py`** — `**Monday**:` / ` - Title - 1h` lines unless you change shape below.
- **`--no-jira`:** same calendar formatting as before, single stream (no Jira block).
- **`--json`**: inside **`[TIMESHEET-OUTPUT]`** when Jira is on; with **`--no-jira`**, `events` + `assumptions` only (no formatted list on stdout).
- **`--with-times` / `-v`**: per **day**, lines like `• [1h]  9:00 – 10:00  Standup` (calendar section).
- **`--format-meetings`** is accepted for compatibility (legacy; no extra effect).
- **`--python-format-only`** is accepted for compatibility (legacy; formatting is always Python).
