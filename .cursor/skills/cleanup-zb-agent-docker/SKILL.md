---
name: cleanup-zb-agent-docker
description: Stops and removes all running Docker containers (docker ps -q, docker rm -f). Runs scripts/cleanup-zb-agent-docker.sh. Use when the user wants to clear every running container (e.g. free disk on a runner, reset local Docker), or invokes cleanup-zb-agent-docker / zb-agent --cleanup-zb-agent-docker.
---

# Cleanup Docker (all running containers)

The script **`scripts/cleanup-zb-agent-docker.sh`** lists **`docker ps -q`** (running containers only) and runs **`docker rm -f`** on each ID. It does **not** remove stopped containers unless you start them first.

**Warning:** This affects **every** running container on the machine, not only zb-agent.

## Execution rules (mandatory)

1. Prefer running the **bundled script** from the **workspace root** (the folder passed to `cursor agent --workspace`):

   ```bash
   bash scripts/cleanup-zb-agent-docker.sh
   ```

2. If `docker` is missing or the daemon is not running, report the error from the script or from `docker info` and stop — do not invent container IDs.

3. After a successful run, confirm removal briefly (the script prints `Done.`).

4. **Do not** replace the script with ad-hoc `docker rm` unless the script is missing or fails in a way that requires manual intervention; if so, mirror the same behavior (`docker ps -q` then `docker rm -f` on those IDs).

## When to use

- Free disk or reset Docker on a **self-hosted runner** or dev machine
- User explicitly asks to run **cleanup-zb-agent-docker** or **`zb-agent --cleanup-zb-agent-docker`**

## Edge cases

- **No running containers:** The script exits 0 and prints a short message — relay that to the user.
- **Permission denied / Docker socket:** Tell the user to fix Docker permissions or start Docker Desktop.
