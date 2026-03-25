#!/usr/bin/env python3
"""
Calendar JSON (calendar_vision schema) → day-grouped markdown: titles with `[brackets]`
removed; each line is `` - {title} - {formatted duration}`` where duration comes from
``duration_hours``.

**Input shape** — root object ``{"events": [...]}``. Each event object:

```json
{
  "date_iso": "2026-03-26",
  "day_hint": null,
  "title": "Zenbusiness Tech Talk Series",
  "start_time": "11:00 AM",
  "end_time": "11:50 AM",
  "duration_hours": 0.8333333333333334
}
```

- **date_iso**: `YYYY-MM-DD` when known; drives weekday grouping and day order.
- **day_hint**: optional string when `date_iso` is missing.
- **title**: event name (`[brackets]` removed in output).
- **start_time** / **end_time**: optional strings as shown in the UI; sort within a day.
- **duration_hours**: number (hours); formatted with `format_duration_hours(ev)` and appended as
  `f"{title} - {…}"` on each bullet line.

Standalone: pipe JSON into stdin or pass a file path. Used by ``timesheet-agent`` after vision.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from typing import Any

def strip_brackets(title: str) -> str:
    """Remove square-bracket groups and their contents, including nested `[` `]`."""
    out: list[str] = []
    depth = 0
    for ch in title:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def format_duration_hours(ev: dict[str, Any]) -> str:
    """
    Format ``ev["duration_hours"]`` for the title suffix (e.g. ``1h``, ``1.5h``, ``2h``).
    Snaps to the nearest **0.5h** step (0.5, 1, 1.5, 2, …). Missing, invalid, or non-positive → ``?h``.
    """
    try:
        d = float(ev.get("duration_hours") or 0.0)
    except (TypeError, ValueError):
        return "0.5h"
    if d <= 0:
        return "0.5h"
    snapped = round(d * 2.0) / 2.0
    if snapped <= 0:
        snapped = 0.5
    if snapped > 8:
        return "8h"
    if abs(snapped - round(snapped)) < 1e-9:
        return f"{int(round(snapped))}h"
    s = f"{snapped:.1f}".rstrip("0").rstrip(".")
    return f"{s}h"


def should_drop_title(title: str) -> bool:
    raw = title.strip()
    if not raw:
        return True
    low = raw.lower()
    if low == "google calendar" or raw.startswith("Google Calendar"):
        return True
    if "all-day home" in low or low.replace(" ", "") == "alldayhome":
        return True
    if re.search(r"\booo\b", raw, re.IGNORECASE):
        return True
    return False


def weekday_from_iso(ds: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
        try:
            return date.fromisoformat(ds).strftime("%A")
        except ValueError:
            pass
    return ""


def day_group_key(ev: dict[str, Any]) -> str:
    ds = str(ev.get("date_iso") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
        return ds
    h = ev.get("day_hint")
    if isinstance(h, str) and h.strip():
        return f"__hint__:{h.strip()}"
    return "__unknown__"


def day_sort_key_for_group(k: str) -> tuple:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k):
        return (0, k)
    return (1, k)


def weekday_header_for_group(group_key: str, sample_ev: dict[str, Any]) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", group_key):
        w = weekday_from_iso(group_key)
        if w:
            return w
    h = sample_ev.get("day_hint")
    if isinstance(h, str) and h.strip():
        return h.strip()
    return "Unknown day"


def normalize_events_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("JSON must contain an 'events' array")
    out: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or "").strip()
        if should_drop_title(title):
            continue
        title = strip_brackets(title)
        if should_drop_title(title) or not title:
            continue
        row = dict(ev)
        row["title"] = title
        out.append(row)
    return out


def format_meetings_markdown(events: list[dict[str, Any]]) -> str:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        by_day[day_group_key(ev)].append(ev)

    blocks: list[str] = []
    for gkey in sorted(by_day.keys(), key=day_sort_key_for_group):
        lst = by_day[gkey]
        if not lst:
            continue
        ordered = sorted(lst, key=lambda e: str(e.get("start_time") or ""))
        wk = weekday_header_for_group(gkey, ordered[0])
        lines = [f"**{wk}**:"]
        seen: set[tuple[str, str]] = set()
        for ev in ordered:
            t = strip_brackets(str(ev.get("title") or "").strip())
            if not t:
                continue
            dur = format_duration_hours(ev)
            title_with_duration = f"{t} - {dur}"
            key = (t, dur)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f" - {title_with_duration}")
        if len(lines) <= 1:
            continue
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks).rstrip() + ("\n" if blocks else "")


def load_json_stdin_or_file(path: str | None) -> dict[str, Any]:
    if path:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Root JSON must be an object")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(
        description='Convert calendar JSON (events[]) to day-grouped lines: " - {title} - {Nh}".',
    )
    ap.add_argument(
        "file",
        nargs="?",
        help="JSON file (default: stdin)",
    )
    args = ap.parse_args()
    try:
        data = load_json_stdin_or_file(args.file)
        events = normalize_events_payload(data)
        sys.stdout.write(format_meetings_markdown(events))
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
