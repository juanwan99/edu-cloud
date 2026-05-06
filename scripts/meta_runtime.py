"""Meta Core runtime checks for edu-cloud.

Meta Core is the synchronous task-contract plane: it keeps work aligned with
the user's instruction, current facts, active context, evidence requirements,
and read-only model-review boundaries.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from codex_support import PROJECT_ROOT


SCHEMA = "meta.core.v1"
STATE_SCHEMA = "meta.state.v1"
REQUIRED_META_LESSONS = ("L013", "L015", "L017", "L019", "L020", "L022")
SHANGHAI_TZ = timezone(timedelta(hours=8))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def issue(
    code: str,
    severity: str,
    summary: str,
    command_hint: str,
    *,
    blocks_completion: bool = False,
    required_before: str = "completion",
    source: str = "meta-check",
) -> dict[str, Any]:
    return {
        "issue_code": code,
        "severity": severity,
        "summary": summary,
        "blocks_completion": blocks_completion,
        "required_before": required_before,
        "command_hint": command_hint,
        "source": source,
    }


def active_index_paths(text: str) -> list[str]:
    if "## Active" not in text:
        return []
    active_text = text.split("## Active", 1)[1].split("## Candidate Active Work", 1)[0]
    paths: list[str] = []
    for match in re.finditer(r"`([^`]+)`", active_text):
        raw = match.group(1)
        if raw.startswith("/") or raw.startswith("http"):
            continue
        paths.append(raw)
    return paths


def check_active_docs(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    index = project_root / "docs" / "context" / "ACTIVE_INDEX.md"
    if not index.exists():
        return [
            issue(
                "ACTIVE_INDEX_MISSING",
                "red",
                "docs/context/ACTIVE_INDEX.md is missing",
                "restore docs/context/ACTIVE_INDEX.md",
                blocks_completion=True,
                source="active-index",
            )
        ]
    text = index.read_text(encoding="utf-8")
    issues: list[dict[str, Any]] = []
    for rel in active_index_paths(text):
        if not (project_root / rel).exists():
            issues.append(
                issue(
                    "ACTIVE_DOC_MISSING",
                    "red",
                    f"active document is missing: {rel}",
                    f"restore {rel} or remove it from docs/context/ACTIVE_INDEX.md",
                    blocks_completion=True,
                    source="active-index",
                )
            )
    return issues


def check_lesson_coverage(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    lessons = project_root / "docs" / "context" / "LESSONS.md"
    if not lessons.exists():
        return [
            issue(
                "META_LESSON_GAP",
                "yellow",
                "docs/context/LESSONS.md is missing",
                "restore docs/context/LESSONS.md",
                required_before="handoff",
                source="lessons",
            )
        ]
    text = lessons.read_text(encoding="utf-8")
    missing = [lesson for lesson in REQUIRED_META_LESSONS if lesson not in text]
    if not missing:
        return []
    return [
        issue(
            "META_LESSON_GAP",
            "yellow",
            "migrated lessons missing structural Meta risks: " + ", ".join(missing),
            "update docs/context/LESSONS.md from ~/.claude/LESSONS.md evidence",
            required_before="handoff",
            source="lessons",
        )
    ]


def check_now_freshness(
    project_root: Path = PROJECT_ROOT,
    *,
    now: datetime | None = None,
    yellow_hours: int = 24,
    red_hours: int = 72,
) -> list[dict[str, Any]]:
    now_doc = project_root / "docs" / "context" / "NOW.md"
    if not now_doc.exists():
        return [
            issue(
                "STALE_FACTS",
                "yellow",
                "docs/context/NOW.md is missing, so current facts cannot be trusted",
                "restore docs/context/NOW.md and refresh live facts",
                required_before="handoff",
                source="now-freshness",
            )
        ]
    text = now_doc.read_text(encoding="utf-8")
    match = re.search(r"Last refreshed:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+Asia/Shanghai", text)
    if not match:
        return [
            issue(
                "STALE_FACTS",
                "yellow",
                "docs/context/NOW.md has no parseable Last refreshed timestamp",
                "update docs/context/NOW.md with 'Last refreshed: YYYY-MM-DD HH:MM Asia/Shanghai'",
                required_before="handoff",
                source="now-freshness",
            )
        ]
    refreshed = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=SHANGHAI_TZ)
    current = (now or datetime.now(timezone.utc)).astimezone(SHANGHAI_TZ)
    age_hours = (current - refreshed).total_seconds() / 3600
    if age_hours <= yellow_hours:
        return []
    if age_hours > red_hours:
        return [
            issue(
                "STALE_FACTS",
                "red",
                f"docs/context/NOW.md is stale by {age_hours:.1f} hours",
                "refresh docs/context/NOW.md from live commands before completion",
                blocks_completion=True,
                source="now-freshness",
            )
        ]
    return [
        issue(
            "STALE_FACTS",
            "yellow",
            f"docs/context/NOW.md is stale by {age_hours:.1f} hours",
            "refresh docs/context/NOW.md before broad design or handoff",
            required_before="broad_design",
            source="now-freshness",
        )
    ]


def check_meta_registration(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    checks = {
        "docs/context/GOVERNANCE_MODEL.md": ("Meta Runtime", "scripts/meta-check"),
        "docs/context/COMMANDS.md": ("scripts/meta-check",),
        "AGENTS.md": ("docs/context/META_RUNTIME.md", "scripts/meta-check"),
    }
    issues: list[dict[str, Any]] = []
    for rel, terms in checks.items():
        path = project_root / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [term for term in terms if term not in text]
        if missing:
            issues.append(
                issue(
                    "META_RUNTIME_UNREGISTERED",
                    "yellow",
                    f"{rel} missing Meta runtime reference(s): {', '.join(missing)}",
                    f"update {rel}",
                    required_before="handoff",
                    source="meta-registration",
                )
            )
    return issues


def check_claude_boundary(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    wrapper = project_root / "scripts" / "codex-consult-claude"
    if not wrapper.exists():
        return [
            issue(
                "CLAUDE_BOUNDARY_GAP",
                "red",
                "scripts/codex-consult-claude is missing",
                "restore scripts/codex-consult-claude",
                blocks_completion=True,
                source="claude-boundary",
            )
        ]
    text = wrapper.read_text(encoding="utf-8")
    required = ("--no-session-persistence", "--permission-mode", "Read,Grep,Glob,LS", "Bash,Edit,Write")
    missing = [term for term in required if term not in text]
    if not missing:
        return []
    return [
        issue(
            "CLAUDE_BOUNDARY_GAP",
            "red",
            "Claude wrapper no longer proves read-only boundary: " + ", ".join(missing),
            "scripts/codex-consult-claude --dry-run review boundary",
            blocks_completion=True,
            source="claude-boundary",
        )
    ]


def run_git_status(project_root: Path = PROJECT_ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) >= 4:
            raw = line[3:]
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1]
            paths.append(raw)
    return paths


def check_plan_contract(path: Path, text: str) -> list[dict[str, Any]]:
    rel = str(path)
    if not (rel.startswith("docs/plans/") or rel.startswith("docs/superpowers/plans/")):
        return []
    if rel.endswith(".log") or "/archived/" in rel:
        return []
    lower = text.lower()
    evidence_terms = ("evidence", "现有资产盘点", "实证", "evidence_refs", "交付路径")
    if any(term.lower() in lower for term in evidence_terms):
        return []
    return [
        issue(
            "PLAN_EVIDENCE_GAP",
            "yellow",
            f"plan/design document lacks an evidence or asset-inventory section: {rel}",
            f"add Evidence / 现有资产盘点 / 交付路径 to {rel}",
            required_before="handoff",
            source="plan-contract",
        )
    ]


def check_changed_plan_contracts(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for rel in run_git_status(project_root):
        path = project_root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        issues.extend(check_plan_contract(Path(rel), text))
    return issues


def task_obligations(task: str | None) -> list[dict[str, str]]:
    if not task:
        return []
    obligations: list[dict[str, str]] = []
    if re.search(r"实证|证据|深度|挖掘|evidence", task):
        obligations.append({"code": "EVIDENCE_MATRIX", "summary": "produce evidence-backed findings, not impressions"})
    if re.search(r"双模型|Claude|GPT|反审|审查|review", task, re.I):
        obligations.append({"code": "CLAUDE_REVIEW", "summary": "run read-only auxiliary model review and keep Codex authority"})
    if re.search(r"升级|建设|实现|完成|强化|upgrade|implement", task, re.I):
        obligations.append({"code": "IMPLEMENT_AND_VERIFY", "summary": "implement with tests and fresh verification evidence"})
    if re.search(r"不要停|全部完成|主导|直至", task):
        obligations.append({"code": "AUTONOMY_REQUESTED", "summary": "continue autonomously, but preserve safety and evidence gates"})
    if task.count("，") + task.count(",") + task.count("；") + task.count(";") >= 2:
        obligations.append({"code": "INSTRUCTION_DECOMPOSITION", "summary": "decompose multi-step instruction before execution"})
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in obligations:
        if item["code"] not in seen:
            deduped.append(item)
            seen.add(item["code"])
    return deduped


def build_snapshot(
    *,
    project_root: Path = PROJECT_ROOT,
    task: str | None = None,
    include_git: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []
    for name, func in (
        ("active_docs", check_active_docs),
        ("lesson_coverage", check_lesson_coverage),
        ("now_freshness", check_now_freshness),
        ("meta_registration", check_meta_registration),
        ("claude_boundary", check_claude_boundary),
    ):
        issues = func(project_root)
        checks.append({"name": name, "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)
    if include_git:
        issues = check_changed_plan_contracts(project_root)
        checks.append({"name": "changed_plan_contracts", "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)

    red_count = sum(1 for item in all_issues if item["severity"] == "red" or item.get("blocks_completion"))
    yellow_count = sum(1 for item in all_issues if item["severity"] == "yellow" and not item.get("blocks_completion"))
    overall = "red" if red_count else "yellow" if yellow_count else "green"
    obligations = task_obligations(task)
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "project": str(project_root),
        "overall": overall,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "task_contract": {
            "task": task or "",
            "obligations": obligations,
            "obligation_count": len(obligations),
        },
        "checks": checks,
        "issues": all_issues,
        "actions": [
            {
                "issue_code": item["issue_code"],
                "required_before": item["required_before"],
                "command_hint": item["command_hint"],
                "blocks_completion": item["blocks_completion"],
            }
            for item in all_issues
        ],
        "policy": {
            "plane": "synchronous task-contract",
            "auto_edit": False,
            "auto_complete": False,
            "model_review_read_only": True,
        },
    }


def write_state(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": STATE_SCHEMA, "updated_at": utc_now(), "latest_snapshot": snapshot}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def print_human(snapshot: dict[str, Any]) -> None:
    print(f"Meta Check {snapshot['generated_at']} overall={snapshot['overall']}")
    obligations = snapshot["task_contract"]["obligations"]
    if obligations:
        print("task obligations:")
        for item in obligations:
            print(f"- {item['code']}: {item['summary']}")
    else:
        print("task obligations: none")
    if not snapshot["issues"]:
        print("issues: none")
        return
    print("issues:")
    for item in snapshot["issues"]:
        flag = " blocks_completion" if item["blocks_completion"] else ""
        print(f"- {item['issue_code']} {item['severity']}{flag}: {item['summary']}")
        print(f"  hint: {item['command_hint']}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Meta Core task-contract checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero for red or yellow issues.")
    parser.add_argument("--task", help="Current user task text for task-contract extraction.")
    parser.add_argument("--no-git", action="store_true", help="Skip changed plan/design evidence checks.")
    parser.add_argument("--state-file", type=Path, default=PROJECT_ROOT / "logs" / "meta-state.json")
    parser.add_argument("--write-state", action="store_true", help="Write latest state to logs/meta-state.json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = build_snapshot(task=args.task, include_git=not args.no_git)
    if args.write_state:
        write_state(args.state_file, snapshot)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print_human(snapshot)
    if args.strict and snapshot["overall"] != "green":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
