---
name: clean-up-current-branch
description: >-
  Stashes work, checks out main, and force-deletes the branch that was checked
  out. Use when the user invokes /clean-up-current-branch, asks to clean up or
  remove the current branch after switching to main, or wants to drop the local
  feature branch they were on.
---

# Clean up current branch

## When to use

- User runs **/clean-up-current-branch** or asks to clean up the current branch and return to **main**
- User wants to **stash**, **checkout main**, and **delete** the previous branch locally

## Safety

- **Do not** run if the current branch is **`main`** (or **`master`** if that is the default). Tell the user to switch to a feature branch first, or confirm they meant something else.
- Warn if **uncommitted changes** will be stashed; the stash remains on **main** after checkout.

## Steps (run in the repo root)

Execute these shell commands in order. **Capture the branch name before** any checkout.

```bash
BRANCH_TO_REMOVE=$(git branch --show-current)
```

If `BRANCH_TO_REMOVE` is `main` or `master`, **stop** and explain.

Otherwise run:

```bash
git stash && git checkout main && git branch -D "$BRANCH_TO_REMOVE"
```

## Aftermath

- Confirm **main** is checked out and **`$BRANCH_TO_REMOVE`** was deleted.
- Mention that **`git stash list`** still holds the stash if `git stash` ran; user can **`git stash pop`** or **`git stash drop`** as needed.

## Edge cases

- If **`git checkout main`** fails (no local `main`, wrong default branch name), report the error and suggest **`git checkout master`** or creating **`main`**—do not force-delete the old branch until checkout succeeds.
- If **`git branch -D`** fails (branch not fully merged, etc.), report; user may prefer **`git branch -d`** for a safe delete.
