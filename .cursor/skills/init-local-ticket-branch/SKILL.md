---
name: init-local-ticket-branch
description: Checks out main, pulls, creates a branch named ECOMM-XXXX-slug or wa.fix-NOTICKET-slug under 50 characters, pushes to origin, and transitions Jira to In Progress with verification when an issue key exists. Use when initializing a ticket locally, starting work from ECOMM-XXXX, NOTICKET fixes, or setting up a feature branch from main.
---

# Initialize local ticket branch

## When to use

Apply when the user wants to start work from a Jira ticket, create a branch from `main`, or follow ECOMM / `wa.fix-NOTICKET` branch naming.

**Defaults:** remote `origin`, base branch `main`. Override if the user specifies another remote or base.

## Git workflow

Run from the repo root in order:

1. `git checkout main`
2. `git pull origin main`
3. `git checkout -b <branch>`
4. `git push origin <branch>`

If checkout or pull fails (uncommitted changes, merge conflicts), stop and report; do not force destructive git operations unless the user explicitly asks.

## Branch naming

### With a Jira key (e.g. `ECOMM-2300`)

- Pattern: `ECOMM-XXXX-description-from-ticket`
- **Description:** Prefer the Jira issue **summary** via `getJiraIssue` (slugified). If unavailable, use a short description from the user.

### Without a ticket (informal)

- Pattern: `wa.fix-NOTICKET-description-from-input`
- **Description:** From user input, slugified.

### Slug rules

- Lowercase, hyphen-separated, alphanumeric; drop unsafe characters; collapse repeated hyphens; no leading/trailing hyphens.

## Length: under 50 characters (hard)

The full branch name must be **fewer than 50 characters** (target at most **49**).

1. Build a candidate from the pattern above.
2. If the length is **≥ 50**, **do not** only chop characters. **Regenerate** a shorter name:
   - Shorten the semantic slug: fewer words, abbreviations that stay readable (e.g. `checkout` → `co`, `payment` → `pay` only when meaning stays clear).
   - Prefer re-slugifying from the same ticket summary / user intent until under the limit.
3. If still too long after one or two regeneration passes, truncate **only the slug portion** (never drop `ECOMM-XXXX` or the `wa.fix-NOTICKET` prefix), preferring word-boundary cuts, then strip trailing hyphens.

**Prefix lengths (for planning shorter slugs):**

- `ECOMM-` + four digits + `-` → 10 characters + slug.
- `wa.fix-NOTICKET-` → 15 characters + slug.

## Branch push

After `git push origin <branch>`, confirm the branch exists on the remote and matches local:

1. **Push succeeded:** The command exited cleanly and the output shows the branch updated on `origin` (no auth/network errors).
2. **Remote branch present:** e.g. `git ls-remote --heads origin <branch>` returns a commit SHA (not empty).
3. **Same commit as local:** Compare `git rev-parse HEAD` with the SHA from `git ls-remote --heads origin <branch>`; they must match.

If verification fails, do not run Jira “In Progress” steps until push is fixed.

## Examples (illustrative)

- Ticket key + summary: `ECOMM-2300-render-payment-errors-in-checkout` — if over 49 chars, regenerate to something like `ECOMM-2300-render-pay-errors-checkout` or shorter until valid.
- No ticket: `wa.fix-NOTICKET-include-variants-null-adornment` — shorten the slug part if needed.

## Jira: move to In Progress (only with ticket context)

Skip this section if there is **no** issue key (e.g. `ECOMM-1234`) or no Jira access.

After a successful push:

1. **cloudId:** If the user gave a Jira URL, try the site hostname (e.g. `company.atlassian.net`) as `cloudId`; if that fails, use `getAccessibleAtlassianResources` to resolve it.
2. **Transitions:** `getTransitionsForJiraIssue` for the issue key. Pick the transition whose destination is **In Progress** (workflow labels vary; match the intended “started work” status).
3. **Transition:** `transitionJiraIssue` with that transition `id`.
4. **Verify:** `getJiraIssue` and confirm `fields.status.name` (or equivalent) reflects In Progress / the expected post-transition status.

If no suitable transition exists (permissions, workflow), report that clearly instead of guessing.

## Additional resources

None required; keep instructions in this file unless a separate reference is needed for a specific team’s Jira workflow names.
