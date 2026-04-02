"""
Local-only web UI for ./timesheet-agent: upload a calendar screenshot, set Jira intent,
run the same CLI in a background thread, poll for completion.

Bind: 127.0.0.1 only. No authentication — use on your machine only.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from flask import Flask, jsonify, render_template, request

REPO_ROOT = Path(__file__).resolve().parent.parent
TIMESHEET_SCRIPT = REPO_ROOT / "timesheet-agent"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # screenshots

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _split_combined_output(stdout: str) -> tuple[str | None, str | None, bool]:
    """
    If stdout contains JIRA/TIMESHEET markers, return (jira_block, calendar_block, True).
    Else (None, full_stdout, False).
    """
    if "[JIRA_AGENT_OUTPUT]" not in stdout or "[TIMESHEET-OUTPUT]" not in stdout:
        return None, stdout.strip() or None, False
    jira_m = re.search(
        r"\[JIRA_AGENT_OUTPUT\]\s*(.*?)\s*\[TIMESHEET-OUTPUT\]",
        stdout,
        re.DOTALL,
    )
    cal_m = re.search(r"\[TIMESHEET-OUTPUT\]\s*(.*)\Z", stdout, re.DOTALL)
    jira_block = (jira_m.group(1).strip() if jira_m else "") or None
    cal_block = (cal_m.group(1).strip() if cal_m else "") or None
    return jira_block, cal_block, True


def _run_job(
    job_id: str,
    image_path: Path,
    *,
    jira_intent: str,
    no_jira: bool,
    as_json: bool,
    with_times: bool,
) -> None:
    cmd: list[str] = [
        str(TIMESHEET_SCRIPT),
        "-i",
        str(image_path),
        "--cursor-workspace",
        str(REPO_ROOT),
        "--no-browser-prompt",
    ]
    if no_jira:
        cmd.append("--no-jira")
    if as_json:
        cmd.append("--json")
    if with_times:
        cmd.append("--with-times")
    intent = (jira_intent or "").strip()
    if intent:
        cmd.extend(["--jira-intent", intent])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=None,
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
        jira_b, cal_b, combined = _split_combined_output(out)
        with _lock:
            _jobs[job_id] = {
                "status": "done" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "stdout": out,
                "stderr": err,
                "jira_block": jira_b,
                "calendar_block": cal_b,
                "combined": combined,
            }
    except OSError as e:
        with _lock:
            _jobs[job_id] = {
                "status": "error",
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "jira_block": None,
                "calendar_block": None,
                "combined": False,
            }
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/run")
def api_run() -> Any:
    if "image" not in request.files or not request.files["image"].filename:
        return jsonify({"error": "Missing image file"}), 400

    jira_intent = request.form.get("jira_intent", "") or ""
    no_jira = request.form.get("no_jira") == "1"
    as_json = request.form.get("as_json") == "1"
    with_times = request.form.get("with_times") == "1"

    f = request.files["image"]
    suffix = Path(f.filename or "shot").suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ".png"

    tmp = NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    try:
        f.save(tmp_path)
    except OSError as e:
        tmp_path.unlink(missing_ok=True)
        return jsonify({"error": f"Could not save upload: {e}"}), 500
    finally:
        tmp.close()

    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {"status": "running", "returncode": None}

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, tmp_path),
        kwargs={
            "jira_intent": jira_intent,
            "no_jira": no_jira,
            "as_json": as_json,
            "with_times": with_times,
        },
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id})


@app.get("/api/job/<job_id>")
def api_job(job_id: str) -> Any:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify(job)


def main() -> None:
    ap = argparse.ArgumentParser(description="Local web UI for timesheet-agent.")
    ap.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=int(__import__("os").environ.get("TIMESHEET_UI_PORT", "8765")),
        help="Port (default: 8765 or TIMESHEET_UI_PORT)",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Flask debug mode (not for untrusted networks)",
    )
    args = ap.parse_args()

    if not TIMESHEET_SCRIPT.is_file():
        print(f"timesheet-ui: missing script: {TIMESHEET_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    print(f"timesheet-ui → http://{args.host}:{args.port}/", file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
