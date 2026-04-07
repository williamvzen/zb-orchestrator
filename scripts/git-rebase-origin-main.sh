#!/usr/bin/env bash
# Stash WIP, fetch main, rebase onto origin/main, restore stash.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STASH_MSG="cursor: rebase onto origin/main"
STASHED=0
if git status --porcelain | grep -q .; then
  git stash push -u -m "$STASH_MSG"
  STASHED=1
fi

git fetch origin main
if git rebase origin/main; then
  if [[ "$STASHED" -eq 1 ]]; then
    git stash pop
  fi
else
  echo >&2 "Rebase stopped (conflicts or error). Fix and run: git rebase --continue"
  if [[ "$STASHED" -eq 1 ]]; then
    echo >&2 "Your stash is still saved. After the rebase finishes: git stash pop"
  fi
  exit 1
fi
