"""Keel dispatch review gate for governed pull requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


SCOPE_DECLARATION = re.compile(r"^\ufeff?\s*Steward-Scope:\s*([A-Za-z0-9._-]+)\s*$")
SECTION_HEADING = re.compile(r"^##\s+Dispatch Review\s*$", re.MULTILINE)
NEXT_HEADING = re.compile(r"^##\s+", re.MULTILINE)
UNCHECKED_BOX = re.compile(r"(?m)^\s*[-*]\s+\[\s\]\s+")


def validate_event(event: dict[str, Any]) -> list[str]:
    pr = event.get("pull_request") or {}
    body_value = pr.get("body") or ""
    body = body_value if isinstance(body_value, str) else ""
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    head_ref = head.get("ref") or ""
    scope_id = _resolve_scope_id(body)
    errors: list[str] = []

    if not scope_id:
        errors.append("PR body must declare Steward-Scope: <scope_id>")
    if head_ref.startswith("batch/"):
        errors.append("governed PR branches must not use retired batch/* names")
    if scope_id and not head_ref.startswith("keel/"):
        errors.append("governed PR branches must use keel/<purpose>-<date>")

    section = _dispatch_section(body)
    if section is None:
        errors.append("PR body must include a ## Dispatch Review section")
        return errors

    unchecked = [line.strip() for line in section.splitlines() if UNCHECKED_BOX.match(line)]
    if unchecked:
        errors.append("all Dispatch Review checklist items must be checked")

    required_phrases = [
        "Codex Dispatch Review completed",
        "latest `origin/master`",
        "fresh scope file",
        "forbidden_paths",
        "reachability was checked",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in section]
    if missing:
        errors.append(f"Dispatch Review is missing required evidence: {', '.join(missing)}")

    return errors


def _resolve_scope_id(body: str) -> str | None:
    for line in body.splitlines():
        match = SCOPE_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def _dispatch_section(body: str) -> str | None:
    match = SECTION_HEADING.search(body)
    if not match:
        return None
    start = match.end()
    next_match = NEXT_HEADING.search(body, start)
    end = next_match.start() if next_match else len(body)
    return body[start:end]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="Path to the GitHub event JSON")
    args = parser.parse_args(argv)

    event = json.loads(Path(args.event).read_text(encoding="utf-8-sig"))
    errors = validate_event(event)
    if errors:
        for error in errors:
            print(f"dispatch review error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
