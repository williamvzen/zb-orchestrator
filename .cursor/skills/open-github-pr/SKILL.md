---
name: open-github-pr
description: Opens GitHub pull requests via MCP using each repository’s PR template body, conventional-commit titles with ticket suffixes, and a filled checklist. Use when creating a PR, opening a pull request, or when the user asks to raise a PR with Jira/ECOMM context or team workflow.
---

# Open GitHub PR (MCP)

## When to use

- User wants a PR opened using **GitHub MCP** (`mcp_github_create_pull_request` or equivalent).
- Work should follow the **current workspace** repo’s **`.github/pull_request_template.md`** (or the closest match under `.github/`).

## PR title

- Use only **`feat`**, **`fix`**, or **`chore`** (imperative mood).
- Append the ticket in square brackets **with no space** before `[`:
  - With a Jira-style key: `feat: implement fallback for orders[ECOMM-8989]`
  - Without a ticket: `chore: update security issues[NOTICKET]`
- Match the branch/work; keep the first line within team limits if the template or hooks require it.

## Body: template first

1. Read **`.github/pull_request_template.md`** from the **active repo root** (paths may differ; search under `.github/` if needed).
2. Build the PR **body** by starting from that file’s structure and filling:
   - **Ticket:** Link to the Jira issue when a key exists (e.g. `https://counsl.atlassian.net/browse/ECOMM-XXXX`). Replace placeholder ticket links with the real key. If there is no ticket, state that clearly and use `[NOTICKET]` consistently with the title.
   - **Description:** Short summary of changes and motivation.
   - **Back-out Procedures:** Leave the section present per template; do not imply rollback steps are “done” in the checklist (see below).

## Checklist: what to check

- Set checklist lines to **`[x]`** for every item **except** the following—leave these as **`[ ]`**:
  1. **Security:** Any item about **Code Review for Security**, **OWASP**, or self-review for security impact.
  2. **Code review / standards:** Any item about **reviewing team or project code policies** (e.g. ZenAPI Code Policies in zenapi) or equivalent “author has reviewed policies/standards” wording.
  3. **Back-out / rollback:** Any checklist line about **back-out**, **rollback**, or **backoff** procedures (if the template adds one; a markdown subsection under Description is not a checkbox—leave unchecked only if there is an explicit checklist item).

All other template checklist items should be **`[x]`** by default for this workflow.

## MCP steps

1. Resolve **owner** and **repo** (e.g. from `git remote get-url origin` or user input).
2. Resolve **head** branch (current branch or the branch the user specifies) and **base** (usually `main`; confirm if different).
3. Call **`mcp_github_create_pull_request`** with:
   - `title`: per **PR title** above.
   - `body`: filled template from **Body** above.
   - `head`, `base`, `owner`, `repo`.

4. Return the PR URL to the user.

## Edge cases

- If the template changes, follow the file in the repo; apply the same **checked vs unchecked** rules by matching meaning (security, policy/code review, back-out checklist), not only line numbers.
- If unsure whether an item is “security” vs “general quality,” leave **security-related** items unchecked and prefer checking only non-security items that clearly apply.
