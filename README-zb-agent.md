# zb-agent

Install (for `--reason` LLM support):

```bash
pip install -r requirements.txt
```

## Run `zb-agent` from anywhere

After cloning, you can install a short command so you don’t need the `./tools/zb-agent.py` path:

```bash
./tools/zb-agent.py --install
```

You’ll be asked whether to add `zb-agent` under `~/.local/bin` (a symlink to this script). To skip the prompt in scripts or CI:

```bash
./tools/zb-agent.py --install -y
```

Ensure `~/.local/bin` is on your `PATH` (many shells include it by default on macOS/Linux).

## timesheet-agent (Jira / generate-timesheet)

Use **`./timesheet-agent.py`** (same directory as `zb-agent.py`) to open **zb-orchestrator** with the **generate-timesheet** Cursor workflow — separate from project navigation. It shares `zb_orchestrator_launch.py` with zb-agent for launching `cursor agent`. See usage examples under [Usage](#usage).

---

Small helper that mirrors `tree -L 2` under `zb-projects`, asks what you want to work on (or accepts names on the CLI), then:

- **One project** — prints the path and starts **Cursor Agent** with a seed prompt for your intent (`cursor agent --workspace <folder> "<prompt>"`). Use **`--ide-only`** to open the folder with plain `cursor` (no Agent).
- **Several projects** — writes a multi-root `.code-workspace` under `.zb-workspaces/` and starts Agent the same way, using the **first** resolved project as `--workspace` (Cursor’s CLI requires a directory, not a `.code-workspace` file); a short note is printed to stderr. **`--ide-only`** opens the `.code-workspace` file only.

## Usage

```bash
# Interactive: shows the tree, then prompts
./tools/zb-agent.py
# After --install, from any directory:
zb-agent

# One project
./tools/zb-agent.py zenscripts

# Multiple (use quotes if your shell splits on spaces)
./tools/zb-agent.py zenapi and zenscripts

# List all leaf projects (category/name)
./tools/zb-agent.py --list

# Tree only
./tools/zb-agent.py --tree

# Create workspace / print paths without launching Cursor
./tools/zb-agent.py --no-open zenapi and zenscripts

# Open in the IDE only (no Cursor Agent seed prompt)
./tools/zb-agent.py --ide-only zenscripts

# Jira timesheet / weekly report (dedicated script; opens zb-orchestrator)
./timesheet-agent.py
./timesheet-agent.py "ECOMM board, last 7 days"
./timesheet-agent.py --no-open   # print Agent prompt only
```

## Cursor CLI

Install once: **Command Palette → “Shell Command: Install 'cursor' command in PATH”**.

## Cursor Agent (default)

Every successful run **starts Cursor Agent** (unless **`--ide-only`** or **`--no-open`**). The seed prompt includes your intent and, with **`--reason`**, the model’s planning text. Pass **`--ticket`** for Jira context and branch/commit workflow, or **`--noops`** for read-only exploration (see below). This uses the `cursor agent` subcommand, **not** the main IDE Composer — there is no supported `cursor` flag to pre-fill the in-editor chat from the shell.

## Jira ticket (`--ticket`) and investigation (`--noops`)

Optional **`--ticket`** adds the Jira key and the branch/commit workflow in the seed prompt (see [Cursor skills](#cursor-skills-branch--commits)).

**`--noops`** switches to read-only exploration: the seed prompt omits **init-local-ticket-branch** and committing. Combine **`--noops --ticket`** when you still want ticket context (e.g. “what does ECOMM-XXXX touch?”) without implying you are starting implementation. Env: **`ZB_AGENT_NOOPS=1`** (same semantics as the flag).

**Flag behavior:** **`--noops`** and **`ZB_AGENT_NOOPS`** are currently **no-ops** — they do not change the seed prompt, exported env, or runtime behavior. The paragraphs above describe the intended investigation workflow for reference.

```bash
# Prompt for ticket after choosing work (interactive)
./tools/zb-agent.py --ticket --ollama --reason "zenapi and zenscripts"

# Ticket on the command line
./tools/zb-agent.py --ticket ECOMM-2384 zenscripts

# Investigation: no branch workflow (optional ticket for context)
./tools/zb-agent.py --noops zenscripts
./tools/zb-agent.py --noops --ticket ECOMM-2384 zenapi

# Non-interactive: env or explicit key (do not use bare `--ticket` without a TTY)
ZB_AGENT_TICKET=ECOMM-2384 ./tools/zb-agent.py -y --no-open zenapi
ZB_AGENT_NOOPS=1 ZB_AGENT_TICKET=ECOMM-2384 ./tools/zb-agent.py -y --no-open zenapi
```

With **`--no-open`**, the script prints the Agent prompt text instead of launching Cursor. With **`--ide-only`**, it opens the IDE only and does not run `cursor agent`.

If `cursor agent` fails (e.g. auth), zb-agent falls back to opening the folder or workspace file with `cursor` and prints the prompt on stderr for pasting.

## Cursor skills (branch + commits)

This repo includes a rule ([`.cursor/rules/zb-agent-workflow.mdc`](.cursor/rules/zb-agent-workflow.mdc)) so the AI applies your skills when they fit:

| Skill | When |
|--------|------|
| **init-local-ticket-branch** | When the work has a Jira key (e.g. after opening with **`--ticket`**) and **not** **`--noops`** — create/push the ticket branch from `main`, naming and Jira steps per the skill. |
| **commit-it-then** | When committing changes — subject format, `[TICKET]` or `[NOTICKET]`, 50-character cap. |
| **generate-timesheet** | After **`timesheet-agent`**, or when you need a Jira timesheet / status summary — Atlassian MCP + JQL; see [`.cursor/skills/generate-timesheet/SKILL.md`](.cursor/skills/generate-timesheet/SKILL.md). |

The initial Agent prompt reminds the model to use these skills (with ticket-specific wording when **`--ticket`** is set). Ensure **init-local-ticket-branch** and **commit-it-then** exist in your Cursor user skills (or equivalent paths) so `/` commands or Skills pick them up.

## Duplicate names

Some folders exist under more than one category (e.g. `graphql-commons` in both `javascript-projects` and `python-projects`). Use a qualified path:

```bash
./tools/zb-agent.py python/graphql-commons
./tools/zb-agent.py javascript/graphql-commons
```

Aliases: `python` → `python-projects`, `js` / `javascript` → `javascript-projects`, `go` → `go-projects`, `ai` → `ai-projects`.

## Non-interactive ambiguity

If a name is ambiguous and stdin is not a TTY, the script exits with an error. Use qualified paths or run in a terminal. With `-y` / `--yes`, ambiguous names never open an interactive picker.

## LLM reasoning (`--reason`)

Optional **agentic** step: an OpenAI-compatible chat model reads your free-form intent and the full project catalog, returns a short **reasoning** string plus **which** `category/name` ids to open. Selections are validated against disk; invalid ids cause a fallback unless `--no-reason-fallback`.

### OpenAI (cloud)

```bash
export OPENAI_API_KEY=sk-...
./tools/zb-agent.py --reason --no-open "the Python API and the scripts repo"
```

### Ollama (local)

Ollama exposes an [OpenAI-compatible HTTP API](https://github.com/ollama/ollama/blob/main/docs/openai.md) at `http://127.0.0.1:11434/v1`. No cloud API key is required; the client sends a dummy key.

```bash
ollama pull qwen2.5:7b   # recommended default for this script (see below)
./tools/zb-agent.py --ollama --reason --no-open "zenapi and zenscripts"
# equivalent: ZB_AGENT_BACKEND=ollama ./tools/zb-agent.py --reason ...
```

**Suggested models (pick one, pull before use):**

| Model | Notes |
|-------|--------|
| **`qwen2.5:7b`** (default) | Best balance for this task: follows instructions, stays close to valid JSON, reasonable speed on CPU/GPU. |
| **`qwen2.5:3b`** | Lighter / faster if `7b` is slow; slightly less reliable on messy phrasing. |
| **`llama3.2`** | Common small default in Ollama; fine for simple intents; JSON can be noisier than Qwen. |

This use case is **small structured output** (a JSON object with `reasoning` + `selections`), not long coding — you do **not** need the largest models; **7B-class** is enough.

Ollama defaults **`ZB_AGENT_JSON_MODE` off** (no `response_format: json_object`), because many local setups handle it inconsistently; the prompt still asks for JSON and the parser tolerates minor formatting. Set `ZB_AGENT_JSON_MODE=1` if your Ollama build supports JSON mode and you want stricter output.

Before calling the model, the script **checks `/api/tags`** on your Ollama host. If the model is not installed, it prints `ollama pull <model>`. If the `ollama` CLI is on `PATH`, you can:

- Run **`--ollama-pull`**, or set **`ZB_AGENT_OLLAMA_PULL=1`**, to run `ollama pull` automatically; or
- In an interactive terminal, confirm when prompted.

If the Ollama daemon is not reachable, you’ll get a short error (start the Ollama app or `ollama serve`).

### Environment reference

| Variable | Default | Meaning |
|----------|---------|---------|
| `ZB_AGENT_BACKEND` | `openai` | Set to `ollama` or `local` for Ollama (or use `--ollama`). |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama base URL; `/v1` is appended if missing. Ignored if `ZB_AGENT_OPENAI_BASE_URL` is set. |
| `ZB_AGENT_OPENAI_BASE_URL` | `https://api.openai.com/v1` (OpenAI only) | **OpenAI:** API base (Azure, Groq, etc.). **Ollama:** optional; if set, overrides `OLLAMA_HOST` (same `/v1` rule). |
| `OPENAI_API_KEY` or `ZB_AGENT_API_KEY` | — | **OpenAI backend:** required. **Ollama backend:** optional; defaults to placeholder `ollama`. |
| `ZB_AGENT_MODEL` | `gpt-4o-mini` (OpenAI) / `qwen2.5:7b` (Ollama) | Chat model name as known to the server. |
| `ZB_AGENT_JSON_MODE` | `1` (OpenAI) / off unless set (Ollama) | `response_format: json_object` when supported. |
| `ZB_AGENT_OLLAMA_PULL` | off | Set to `1` / `true` / `yes` to auto-run `ollama pull` when the model is missing (same as `--ollama-pull`). |
| `ZB_AGENT_TICKET` | — | Optional Jira key when `--ticket` is not passed (non-interactive scripts). |

If the key is missing (OpenAI only) or the call fails, the script uses the usual rule-based matcher unless `--no-reason-fallback` is set.
