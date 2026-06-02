---
name: zenapi-pr-dependency-safety
description: >-
  Assesses whether a zenapi GitHub pull request is safe to merge from a Python
  dependency and breaking-change perspective for a large Django + DRF
  monolith in production. Expects a PR URL; fetches PR metadata and docs for
  touched versions, checks out the PR head branch locally, maps breaking
  upgrades to in-repo usage, and returns a written verdict and optional
  upgrade plan only (no installs, no merges, no pushes). Use when the user
  pastes a zenapi PR link, asks if a zenapi dependency PR is merge-safe, or
  wants a production-impact review before merging library upgrades.
---

# ZenAPI PR dependency merge safety

## Goal

Give a **cautious, evidence-based** answer: is this PR **safe to merge** from the angle of **Python dependency changes** and **documented breaking changes**, for **production** code that is a **large Django + DRF monolith** (“big elephant”). Treat unknown impact as **risk**, not “probably fine.”

**Primary input:** a **full GitHub pull request URL** (e.g. `https://github.com/<org>/zenapi/pull/<n>`).

**Hard scope:** **analyze and plan only**. Do **not** merge the PR, **not** run `pip install` / `poetry update` / lockfile regeneration to “fix” things, **not** push branches, **not** change production config. If an upgrade path is obvious, describe it in a **plan** section for humans to execute later.

## Preconditions (resolve before deep analysis)

1. **Repository identity:** From the PR URL, obtain `owner`, `repo`, and `pullNumber`. Confirm `repo` is **zenapi** (or the org’s canonical zenapi name); if the URL is another repo, stop and say so.
2. **Local zenapi clone:** You need a **local path** to the zenapi checkout (sibling to other worktrees is common, e.g. `../zenapi` or `python-projects/zenapi`). If missing, clone once into a path the user names; do not guess secrets or remotes beyond what `git` / the user provides.
3. **GitHub access:** Use **GitHub MCP** (preferred) or `gh` CLI with auth to read PR title, body, files, and optionally diff.

## Workflow checklist (copy and tick in the reply)

```text
- [ ] Parsed PR URL → owner, repo, pullNumber
- [ ] Fetched PR: title, body, base ref, head ref, head SHA
- [ ] Listed changed files; identified dependency manifests / lockfiles
- [ ] Compared base vs head dependency versions (direct deps first)
- [ ] Flagged semver-major or known-breaking upgrades; pulled upstream notes
- [ ] For each risky dep: searched zenapi for imports / Django integration points
- [ ] Summarized merge risk + optional non-executed upgrade plan
```

## Step 1 — Parse the PR URL

Accept common forms:

- `https://github.com/<owner>/<repo>/pull/<n>`
- `https://github.com/<owner>/<repo>/pull/<n>/files`
- Same with `www.` or enterprise hosts if the user’s org uses them (adjust parsing).

Extract `owner`, `repo`, `pullNumber`.

## Step 2 — Load PR metadata and narrative

Using **`mcp_github_pull_request_read`** (or equivalent):

- `method: get` → title, body, `baseRefName`, `headRefName`, `headRefOid`, state, labels.
- `method: get_files` → paths and change types; note **lockfiles** and **`pyproject.toml` / `requirements*.txt` / `constraints*.txt`**.

Read the **title and body first**: they often name the **target versions** and motivation. Cross-check against file list.

## Step 3 — Pull the right branch locally

In the **local zenapi** directory:

1. `git fetch origin` (and other remotes if the PR is from a fork—use `head` repo/branch from GitHub).
2. Check out the **PR head** exactly (prefer detached HEAD at **`headRefOid`** for reproducibility, or `origin/<headRefName>` if that matches the PR).
3. Record **commit SHA** you analyzed.

If the PR is from a **fork**, fetch the fork ref GitHub exposes for that PR (`pull/<n>/head` on the canonical remote, or add the fork remote). Do not merge `main` into the branch for this review unless the user explicitly wants a merge preview; default is **review the PR as proposed**.

## Step 4 — Identify dependency deltas

Compare **base** vs **head** for:

- `pyproject.toml` / `setup.cfg` / `setup.py` (if present)
- `requirements*.txt`, `constraints*.txt`
- **`poetry.lock` / `Pipfile.lock` / `uv.lock`** (treat lockfile changes as **first-class** evidence)

Build a table: **package → version on base → version on head → bump type** (major / minor / patch / pre-release). Flag **major** and any **explicit deprecations** called out in upstream release notes.

**Transitive deps:** If only the lockfile moves, name the **top-level** change that pulled them; call out **large transitive churn** as extra risk for a monolith.

## Step 5 — Breaking changes and documentation (mandatory for flagged bumps)

For each **non-patch** or **suspected breaking** upgrade:

1. Open **upstream** release notes: GitHub **Releases** / **CHANGELOG** / PyPI “Project description” links.
2. Extract **actionable** breaking items (removed APIs, renamed kwargs, dropped Python/Django support, stricter validation, default behavior changes).
3. Note **Django** and **DRF** compatibility if the bump touches the stack or middleware/session/auth layers.

Do **not** trust the PR description alone; **corroborate** with the official changelog for the **exact** version range.

## Step 6 — Map breaking items to **our** code (zenapi)

ZenAPI is assumed to be a **Django + DRF** monolith. Search **systematically** (e.g. `rg`), not randomly:

| Area | Why it breaks on upgrades |
|------|---------------------------|
| `INSTALLED_APPS` / third-party Django apps | App init, signals, template tags, admin |
| `MIDDLEWARE` / ASGI/WSGI | Order-sensitive, deprecated hooks |
| `settings.py` / split settings | Renamed settings, stricter checks |
| DRF: `ViewSet`, `APIView`, serializers, pagination, throttling, renderers, parsers | Behavior and validation changes |
| URLs / routers | Namespace or schema changes |
| ORM: managers, `QuerySet`, raw SQL, `JSONField`, constraints | DB-backend and validation differences |
| Management commands, Celery/async tasks, lifecycle hooks | Import side effects |
| Tests | Often first signal; note if PR only updates tests |

For each **risky library**, search:

- **Imports:** `import <pkg>`, `from <pkg>` (include common submodule paths).
- **String references:** settings values, entry points, Django app labels if relevant.

If the changelog says “X removed,” prove **“we don’t call X”** with **grep hits or absence**, and cite file paths.

## Step 7 — Verdict and merge recommendation

Use calibrated language:

- **Low risk:** narrow bump, no major semver, no code paths found, changelog clean for our usage.
- **Medium:** major bump but breaking surface clearly unused, or mitigations in PR.
- **High:** major bump + used APIs changed, or insufficient docs / churn too large to reason about in one pass.
- **Unknown:** treat as **high** until disproven.

**Never** imply production sign-off beyond “dependency merge-safety review”; security and product risk are separate.

## Step 8 — Optional upgrade plan (documentation only)

If a **clear** sequence exists (e.g. “upgrade A to x.y first, then B”), outline:

1. Ordered steps  
2. What to re-grep / re-test after each step  
3. What could block (Django LTS, Python pin, conflicting pins)

**Do not execute** this plan in the same run unless the user explicitly asks for implementation.

## Output format (use this structure in the final message)

```markdown
# ZenAPI PR dependency review: <title>

- **PR:** <url>
- **Head SHA analyzed:** `<sha>`
- **Base:** `<base>` → **Head:** `<head>`

## Dependency deltas (summary table)
| Package | Base | Head | Risk flag |
|---------|------|------|-----------|

## Breaking changes (from upstream docs)
- ...

## Usage in our codebase (evidence)
- Package P: used in `path:line` … / not found (cite search pattern)

## Django / DRF impact
- ...

## Merge safety verdict
**<merge-safe | merge-risky | needs-more-info>** — one short paragraph why.

## Suggested upgrade plan (do not execute)
1. ...
```

## Edge cases

- **Docs-only or CI-only PR:** Say so; dependency verdict may be N/A.
- **Huge diff:** Prioritize manifest + lockfile + changelog; sample large mechanical diffs only if tied to runtime behavior.
- **Fork PR out of date with base:** Mention **merge skew**; recommend rebase/merge base before production merge (still analysis-only here).

## Related skills

- **`open-github-pr`:** for creating PRs, not this review.
- **`init-local-ticket-branch` / `commit-it-then`:** only if the user later asks for repo work in **this** orchestrator repo with a ticket; this skill does not require a Jira branch by default.
