"""Fail when retired Claude auxiliary paths return to active execution surfaces."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_EXECUTION_FILES = (
    ".github/workflows/test.yml",
    "scripts/guardian_runtime.py",
    "deploy/systemd/edu-cloud-guardian.service",
)
FORBIDDEN_TOKENS = ("codex-consult-claude", "--model-review claude")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    token: str
    text: str


def check_files(root: Path = PROJECT_ROOT, files: tuple[str, ...] = ACTIVE_EXECUTION_FILES) -> list[Finding]:
    findings: list[Finding] = []
    for rel in files:
        path = root / rel
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for token in FORBIDDEN_TOKENS:
                if token in line:
                    findings.append(Finding(rel, line_no, token, line.strip()))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block retired Claude auxiliary active execution references.")
    parser.add_argument("--check", action="store_true", help="Fail if retired references are active.")
    args = parser.parse_args(argv)

    findings = check_files()
    if findings:
        print("retired Claude auxiliary active references detected:")
        for item in findings:
            print(f"{item.path}:{item.line}: {item.token}: {item.text}")
        return 1
    if args.check:
        print("legacy quarantine clean: no retired Claude auxiliary active execution references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
