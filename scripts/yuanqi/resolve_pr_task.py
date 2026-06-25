"""Resolve the Yuanqi task id declared by a pull request body."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


TASK_DECLARATION = re.compile(r"^\s*Yuanqi-Task:\s*(yq-[A-Za-z0-9._-]+)\s*$")
MISSING_TASK_MESSAGE = "PR 必须声明 Yuanqi-Task: <id>"


def resolve_task_id(event_path: str) -> str | None:
    """Return the Yuanqi task id declared in the pull request body."""
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    body = event.get("pull_request", {}).get("body") or ""
    if not isinstance(body, str):
        return None

    for line in body.splitlines():
        match = TASK_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve Yuanqi task id from a GitHub pull request event."
    )
    parser.add_argument("--event", required=True, help="Path to GITHUB_EVENT_PATH.")
    parser.add_argument("--head-ref", required=True, help="Pull request head ref.")
    args = parser.parse_args(argv)

    try:
        task_id = resolve_task_id(args.event)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{MISSING_TASK_MESSAGE}: {exc}", file=sys.stderr)
        return 1

    if not task_id:
        print(MISSING_TASK_MESSAGE, file=sys.stderr)
        return 1

    print(task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
