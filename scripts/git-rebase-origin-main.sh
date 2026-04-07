#!/usr/bin/env bash
# Stash WIP, fetch main, rebase onto origin/main, restore stash.
# Usage: git-rebase-origin-main.sh [REPO_DIR]
# If REPO_DIR is omitted, uses the parent of this script's directory (zb-orchestrator root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -ge 1 ]]; then
  ROOT="$(cd "$1" && pwd)"
else
  ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi
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
