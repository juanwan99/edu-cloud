#!/usr/bin/env python3
"""Guard active governance docs against known D-03 pollution regressions."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ACTIVE_INDEX_REL = Path("docs/context/ACTIVE_INDEX.md")
SOURCE_COMMAND = ("python3", "scripts/governance/check_module_dependencies.py")

SOURCE_COUNTS_RE = re.compile(
    r"(?P<edges>\d+)\s+edges?\s*,\s*(?P<cycles>\d+)\s+cycles?",
    re.IGNORECASE,
)
EDGE_CYCLE_PAIR_RE = re.compile(
    r"(?P<edges>\d+)\s+edges?\s*/\s*(?P<cycles>\d+)\s+cycles?",
    re.IGNORECASE,
)
EDGE_THEN_CYCLE_RE = re.compile(
    r"(?P<edges>\d+)\s+edges?\b.{0,48}?\b(?P<cycles>\d+)\s+cycles?",
    re.IGNORECASE,
)

STALE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b53\s+edges?\s*/\s*13\s+cycles?\b", re.IGNORECASE),
    re.compile(r"\b55\s+edges?\b", re.IGNORECASE),
    re.compile(r"\b55\s*/\s*30\b"),
    re.compile(r"\b53\s*/\s*13\b"),
)
HISTORICAL_MARKERS = (
    "历史",
    "已清零",
    "burn-down",
    "峰值",
    "合同快照",
    "superseded",
    "historical",
    "cleared",
    "→",
    "->",
)
TOPIC_MARKERS = ("D-03", "跨模块依赖", "跨模块耦合", "edges", "cycles")


@dataclass(frozen=True)
class Failure:
    path: Path | str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.message}"


def resolve_repo(repo_arg: str | None = None) -> Path:
    if repo_arg:
        return Path(repo_arg).resolve()
    return Path(__file__).resolve().parents[2]


def parse_source_counts(output: str) -> tuple[int, int] | None:
    match = SOURCE_COUNTS_RE.search(output)
    if not match:
        return None
    return int(match.group("edges")), int(match.group("cycles"))


def load_source_counts(repo: Path) -> tuple[tuple[int, int] | None, list[Failure]]:
    result = subprocess.run(
        SOURCE_COMMAND,
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = f"source command failed with exit {result.returncode}: {result.stderr.strip()}"
        return None, [Failure(SOURCE_COMMAND[1], 1, message)]

    counts = parse_source_counts(result.stdout)
    if counts is None:
        message = "source command output is unparsable; expected 'N edges, M cycles'"
        return None, [Failure(SOURCE_COMMAND[1], 1, message)]
    return counts, []


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def normalize_path_cell(cell: str) -> Path:
    return Path(cell.strip().strip("`"))


def parse_active_paths(active_index: Path) -> tuple[list[Path], list[Failure]]:
    failures: list[Failure] = []
    try:
        lines = active_index.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [Failure(active_index, 1, f"cannot read ACTIVE_INDEX: {exc}")]

    active_paths: list[Path] = []
    path_idx: int | None = None
    status_idx: int | None = None

    for line_no, line in enumerate(lines, start=1):
        if not line.lstrip().startswith("|"):
            continue

        cells = split_markdown_row(line)
        lowered = [cell.lower() for cell in cells]

        if "path" in lowered and "status" in lowered:
            path_idx = lowered.index("path")
            status_idx = lowered.index("status")
            continue
        if set("".join(cells)) <= {"-", ":"}:
            continue
        if path_idx is None or status_idx is None:
            continue
        if len(cells) <= max(path_idx, status_idx):
            failures.append(Failure(active_index, line_no, "ACTIVE_INDEX row has too few columns"))
            continue

        if cells[status_idx].strip().lower() == "active":
            active_paths.append(normalize_path_cell(cells[path_idx]))

    return active_paths, failures


def has_topic_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in TOPIC_MARKERS)


def has_historical_semantics(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in HISTORICAL_MARKERS)


def line_context(lines: Sequence[str], index: int) -> str:
    return "\n".join(lines[max(0, index - 1) : min(len(lines), index + 2)])


def scan_lines(rel_path: Path, lines: Sequence[str], source_counts: tuple[int, int], *, start_line: int = 1) -> list[Failure]:
    failures: list[Failure] = []
    seen: set[tuple[int, str]] = set()

    def add_failure(line_no: int, message: str) -> None:
        key = (line_no, message)
        if key not in seen:
            seen.add(key)
            failures.append(Failure(rel_path, line_no, message))

    for index, line in enumerate(lines):
        line_no = start_line + index
        context = line_context(lines, index)
        historical = has_historical_semantics(context)

        for pattern in STALE_PATTERNS:
            if pattern.search(line) and not historical:
                add_failure(line_no, f"known stale pollution lacks historical semantics: {pattern.pattern}")

        if not has_topic_marker(context) or historical:
            continue

        for regex in (EDGE_CYCLE_PAIR_RE, EDGE_THEN_CYCLE_RE):
            for match in regex.finditer(line):
                counts = int(match.group("edges")), int(match.group("cycles"))
                if counts != source_counts:
                    message = (
                        "current fact disagrees with source truth: "
                        f"{counts[0]} edges / {counts[1]} cycles vs "
                        f"{source_counts[0]} edges / {source_counts[1]} cycles"
                    )
                    add_failure(line_no, message)

    return failures


def check_docs(repo: Path, source_counts: tuple[int, int] | None = None) -> list[Failure]:
    repo = repo.resolve()
    failures: list[Failure] = []

    if source_counts is None:
        source_counts, source_failures = load_source_counts(repo)
        if source_failures:
            return source_failures
    assert source_counts is not None

    active_paths, index_failures = parse_active_paths(repo / ACTIVE_INDEX_REL)
    failures.extend(index_failures)

    for rel_path in active_paths:
        doc_path = repo / rel_path
        try:
            lines = doc_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            failures.append(Failure(rel_path, 1, f"active path is missing or unreadable: {exc}"))
            continue
        failures.extend(scan_lines(rel_path, lines, source_counts))

    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Repository root. Defaults to this script's repo.")
    parser.add_argument("--check", action="store_true", help="Run the regression guard.")
    args = parser.parse_args(argv)

    repo = resolve_repo(args.repo)
    failures = check_docs(repo)
    if failures:
        for failure in failures:
            print(failure.format())
        return 1

    print("Doc pollution guard clean: active docs match source truth and known D-03 pollution is historical only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
