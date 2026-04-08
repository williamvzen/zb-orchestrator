#!/usr/bin/env bash
# Stop and remove every running Docker container on this host (docker rm -f).
#
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker: command not found" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker: daemon not reachable (is Docker running?)" >&2
  exit 1
fi

ids=$(docker ps -q 2>/dev/null | grep -v '^$' || true)

if [[ -z "${ids}" ]]; then
  echo "No running Docker containers found."
  exit 0
fi

id_line=$(echo "${ids}" | paste -sd' ' -)

echo "Running containers to stop and remove:"
echo "${ids}" | xargs docker inspect --format '{{.Id}} {{.Name}} {{.State.Status}} {{.Config.Image}}'

echo "Removing: ${id_line}"
# shellcheck disable=SC2086
docker rm -f ${id_line}
echo "Done."
