# Calendar from screenshot (Cursor Agent)

[`calendar_vision.py`](calendar_vision.py) runs **one** Cursor Agent step, then **deterministic** formatting:

1. **Vision** — `cursor agent --print` reads **`.calendar_vision_cache/`** and returns **JSON** events from the screenshot.
2. **Format** — the script calls [`format_calendar_meetings.py`](format_calendar_meetings.py) on those events (weekday headers, ` - Title - Nh` lines). No second agent.

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
| `CURSOR_AGENT_WORKSPACE` | Workspace root for `cursor agent` (default: directory containing `calendar_vision.py`) |
| `CURSOR_AGENT_MODEL` | Model for **`cursor agent`** (vision step). Use **`auto`** for Auto mode — passed as `--model auto` (see `cursor agent --help` and `--list-models`). |
| `CURSOR_AGENT_VISION_MODEL` | Optional: overrides **`CURSOR_AGENT_MODEL`** for the **vision** step only |
| `CURSOR_AGENT_TIMEOUT` | Seconds for the agent run (default `600`) |
| `CURSOR_AGENT_FORCE=1` | Passes `--force` to the CLI when supported |
| `CURSOR_AGENT_EXTRA_ARGS` | Extra args (shell-split) appended before the prompt |
| `CALENDAR_VISION_NO_BROWSER_PROMPT=1` | With `--capture`: skip the “open Google Calendar?” prompt; only print the URL on stderr |

Override workspace on the CLI: **`--cursor-workspace DIR`**.  
**`--no-browser-prompt`**: same as the env var (non-interactive / CI friendly).

## Usage

```bash
./calendar_vision.py
./calendar_vision.py --capture
./calendar_vision.py --image ~/Desktop/cal.png           # vision agent → Python formatter → stdout
./calendar_vision.py -i shot.png --json                    # raw events JSON
./calendar_vision.py -i shot.png --with-times              # per-day times + durations (verbose)
```

## Agentic workflow (sequence)

End-to-end flow: **screenshot → Cursor Agent (vision) → normalize → `format_calendar_meetings.py` → markdown stdout**.

| Step | What happens | Command / artifact |
|------|----------------|----------------------|
| **1. Open Calendar** | In the browser, go to **Google Calendar** (sign in if needed) so the week/view you need is on screen. | [calendar.google.com/calendar/u/0/r](https://calendar.google.com/calendar/u/0/r) |
| **2. Prepare** | (Optional if you use the prompt below.) Leave the right week in view. | — |
| **3. Capture** | **`--capture`** (macOS): the terminal asks *Open Google Calendar in your default browser now (new tab)? [Y/n]* — **Yes** opens [the calendar URL](https://calendar.google.com/calendar/u/0/r) via the system browser (usually a **new tab**). Then select the window/region to screenshot. **`--image`**: use a file; no browser prompt. | `--capture` or `--image path.png` |
| **4. Run vision agent** | `calendar_vision.py` calls **`cursor agent --print`** in the chosen workspace. The agent reads **`.calendar_vision_cache/calendar_input.*`**, extracts events, and prints **one JSON object** on stdout. The script parses it. | `./calendar_vision.py --image shot.png` |
| **5. Normalize** | Script sorts events, normalizes fields (`date_iso`, `title`, `duration_hours`, …). | Internal (`normalize_events`) |
| **6. Format meetings** | Deterministic **`format_calendar_meetings.py`** → markdown on stdout. | *(default)* |
| **7a. Raw JSON** | Emit `events` + `assumptions` only — **skips** step 6 on stdout. | `--json` |
| **7b. Verbose schedule** | Per-day lines with duration and time ranges instead of step 6. | `--with-times` / `-v` |

**Agent chat (Cursor):** You can ask: *“Want to open Google Calendar in the browser before we capture?”* If they say **yes**, have them run **`./calendar_vision.py --capture`** in the integrated terminal and answer **`Y`** at the prompt — that opens the calendar from the console in a **new tab** (Python `webbrowser`, default browser). If they prefer to open it themselves, they can say **no** and open the link manually. For automation/CI, use **`--no-browser-prompt`**.

**One-liner examples**

```bash
# After step 1–2: open Calendar in the browser, then e.g.:

# Steps 1–6: default — meeting list on stdout
./calendar_vision.py --image ~/Desktop/cal.png

# JSON only (for piping or saving)
./calendar_vision.py --image ~/Desktop/cal.png --json > events.json

# Pipe JSON through the formatter explicitly (same rules as default stdout)
./calendar_vision.py --image ~/Desktop/cal.png --json | ./format_calendar_meetings.py

# Verbose schedule with times (skip default format step)
./calendar_vision.py --image ~/Desktop/cal.png --with-times
```

Formatting rules live in **[`format_calendar_meetings.py`](format_calendar_meetings.py)** (source of truth).

## Quick run (minimal)

1. Run **`./calendar_vision.py --capture`** (macOS). When asked, press **Enter** or **y** to open Google Calendar in a new tab, then select the calendar window/region for the screenshot. Or use **`--image`** with a file you already saved.
2. Wait for the **vision** agent; stderr shows that phase.
3. Treat output as **draft** — small text can be misread.

## Output

- **Default:** day-grouped list from **`format_calendar_meetings.py`** — `**Monday**:` / ` - Title - 1h` lines.
- **`--json`**: `events` + `assumptions` (no formatted list on stdout).
- **`--with-times` / `-v`**: per **day**, lines like `• [1h]  9:00 – 10:00  Standup`.
- **`--format-meetings`** is accepted for compatibility (legacy; no extra effect).
- **`--python-format-only`** is accepted for compatibility (legacy; formatting is always Python).
