#!/usr/bin/env bash
# Stop and remove Docker containers associated with zb-agent.
#
# Matches either:
#   - Container name contains the substring "zb-agent" (docker name filter)
#   - Label zb-agent=true (set e.g. docker run --label zb-agent=true ...)
#
# Set DRY_RUN=1 to print IDs that would be removed without removing them.
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker: command not found" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker: daemon not reachable (is Docker running?)" >&2
  exit 1
fi

ids=$(
  {
    docker ps -aq --filter "name=zb-agent" 2>/dev/null || true
    docker ps -aq --filter "label=zb-agent=true" 2>/dev/null || true
  } | sort -u | grep -v '^$' || true
)

if [[ -z "${ids}" ]]; then
  echo "No zb-agent Docker containers found (name contains 'zb-agent' or label zb-agent=true)."
  exit 0
fi

# Single line for display / xargs
id_line=$(echo "${ids}" | paste -sd' ' -)

echo "Matching containers:"
echo "${ids}" | xargs docker inspect --format '{{.Id}} {{.Name}} {{.State.Status}} {{.Config.Image}}'

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN=1: would run: docker rm -f ${id_line}"
  exit 0
fi

echo "Removing: ${id_line}"
# shellcheck disable=SC2086
docker rm -f ${id_line}
echo "Done."
