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
STATE_AUTHORITY = {
    "classification": "advisory_diagnostic_cache",
    "trust_baseline": False,
    "completion_authority": False,
    "obligation_authority": "heuristic_context_only",
    "summary": (
        "Persisted Meta state can support drift diagnosis but is not "
        "acceptance evidence, completion authority, or a required task baseline."
    ),
}
REQUIRED_META_LESSONS = ("L013", "L015", "L017", "L019", "L020", "L022")
SHANGHAI_TZ = timezone(timedelta(hours=8))
PLAN_REFERENCE_RE = re.compile(
    r"(?:[\w./-]+\.(?:md|py|js|vue|sh|json|ya?ml|txt):\d+|"
    r"`[^`]*(?:/|\.md|\.py|\.js|\.vue|\.sh|\.json|\.ya?ml|\.txt)[^`]*`)"
)


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
    for line in active_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Only the first table column holds the active document path. The
        # Status/Use columns carry prose (contract ids like `yc-...`, commit
        # ranges like `3688f32..6b1bdd3`) whose backticks must not be mistaken
        # for file paths. Header ("Path") and separator ("---") rows have no
        # backticks, so they contribute nothing.
        cells = stripped.split("|")
        if len(cells) < 2:
            continue
        first_cell = cells[1]
        for match in re.finditer(r"`([^`]+)`", first_cell):
            raw = match.group(1).strip()
            if not raw or raw.startswith("/") or raw.startswith("http"):
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


def check_legacy_claude_auxiliary_retired(project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    active_files = (
        ".github/workflows/test.yml",
        "scripts/guardian_runtime.py",
        "deploy/systemd/edu-cloud-guardian.service",
    )
    forbidden = ("codex-consult-claude", "--model-review claude")
    issues: list[dict[str, Any]] = []
    for rel in active_files:
        path = project_root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for token in forbidden:
                if token in line:
                    issues.append(
                        issue(
                            "LEGACY_CLAUDE_AUX_ACTIVE",
                            "red",
                            f"retired Claude auxiliary path remains active in {rel}:{lineno}: {token}",
                            "remove the retired auxiliary invocation or route review through Yuanqi evidence + human/GitHub review",
                            blocks_completion=True,
                            source="legacy-claude-auxiliary",
                        )
                    )
    return issues


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
    if path.suffix != ".md":
        return []
    if rel.endswith(".log") or "/archived/" in rel:
        return []
    lower = text.lower()
    evidence_terms = ("evidence", "现有资产盘点", "实证", "evidence_refs", "交付路径")
    has_evidence_marker = any(term.lower() in lower for term in evidence_terms)
    has_reference = bool(PLAN_REFERENCE_RE.search(text))
    if has_evidence_marker and has_reference:
        return []
    summary = (
        f"plan/design document lacks concrete evidence reference: {rel}"
        if has_evidence_marker
        else f"plan/design document lacks an evidence or asset-inventory section: {rel}"
    )
    hint = (
        f"add at least one file:line or backticked asset path reference to {rel}"
        if has_evidence_marker
        else f"add Evidence / 现有资产盘点 / 交付路径 to {rel}"
    )
    return [
        issue(
            "PLAN_EVIDENCE_GAP",
            "yellow",
            summary,
            hint,
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


def recent_plan_paths(project_root: Path = PROJECT_ROOT, limit: int = 20) -> list[str]:
    paths, _error = recent_plan_paths_with_error(project_root, limit=limit)
    return paths


def recent_plan_paths_with_error(project_root: Path = PROJECT_ROOT, limit: int = 20) -> tuple[list[str], str | None]:
    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if upstream.returncode == 0 and upstream.stdout.strip():
        range_spec = f"{upstream.stdout.strip()}...HEAD"
    else:
        range_spec = f"HEAD~{limit}..HEAD"
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            range_spec,
            "--",
            "docs/plans/*.md",
            "docs/superpowers/plans/*.md",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git diff failed"
        return [], detail
    seen: set[str] = set()
    paths: list[str] = []
    for raw in result.stdout.splitlines():
        rel = raw.strip()
        if not rel or rel in seen:
            continue
        seen.add(rel)
        paths.append(rel)
    return paths, None


def check_recent_plan_contracts(
    project_root: Path = PROJECT_ROOT,
    *,
    recent_paths: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if recent_paths is None:
        paths, error = recent_plan_paths_with_error(project_root, limit=limit)
        if error:
            return [
                issue(
                    "PLAN_SCAN_INCONCLUSIVE",
                    "yellow",
                    "recent committed plan scan could not determine git range: " + error,
                    "run scripts/meta-check --check-recent-plans from a branch with an upstream, or inspect recent plan docs manually",
                    required_before="handoff",
                    source="plan-contract",
                )
            ]
    else:
        paths = recent_paths
    for rel in paths:
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
        obligations.append({"code": "INDEPENDENT_REVIEW_EVIDENCE", "summary": "capture independent review evidence without invoking retired Claude auxiliary runtime"})
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


def obligation_codes(obligations: list[dict[str, str]]) -> set[str]:
    return {str(item.get("code")) for item in obligations if item.get("code")}


def advisory_state_obligations(path: Path) -> list[dict[str, str]]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    latest = parsed.get("latest_snapshot") if isinstance(parsed, dict) else {}
    contract = latest.get("task_contract") if isinstance(latest, dict) else {}
    obligations = contract.get("obligations") if isinstance(contract, dict) else []
    if not isinstance(obligations, list):
        return []
    return [item for item in obligations if isinstance(item, dict)]


def check_task_contract_drift(
    state_path: Path,
    *,
    current_obligations: list[dict[str, str]],
) -> list[dict[str, Any]]:
    advisory_codes = obligation_codes(advisory_state_obligations(state_path))
    current_codes = obligation_codes(current_obligations)
    if not advisory_codes:
        return [
            issue(
                "TASK_CONTRACT_DRIFT",
                "yellow",
                f"advisory state cache is missing or has no task obligations: {state_path}",
                'run scripts/meta-check --task "..." --write-state to refresh advisory diagnostics when useful',
                required_before="handoff",
                source="task-drift",
            )
        ]
    missing = sorted(advisory_codes - current_codes)
    if not missing:
        return []
    return [
        issue(
            "TASK_CONTRACT_DRIFT",
            "yellow",
            "current task text no longer includes advisory state obligation(s): " + ", ".join(missing),
            "re-run scripts/meta-check with the full current user task or refresh the advisory state cache",
            required_before="completion",
            source="task-drift",
        )
    ]


def build_snapshot(
    *,
    project_root: Path = PROJECT_ROOT,
    task: str | None = None,
    include_git: bool = True,
    check_recent_plans: bool = False,
    check_drift: bool = False,
    baseline_state: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []
    obligations = task_obligations(task)
    for name, func in (
        ("active_docs", check_active_docs),
        ("lesson_coverage", check_lesson_coverage),
        ("now_freshness", check_now_freshness),
        ("meta_registration", check_meta_registration),
        ("legacy_claude_auxiliary", check_legacy_claude_auxiliary_retired),
    ):
        issues = func(project_root)
        checks.append({"name": name, "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)
    if include_git:
        issues = check_changed_plan_contracts(project_root)
        checks.append({"name": "changed_plan_contracts", "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)
    if check_recent_plans:
        issues = check_recent_plan_contracts(project_root)
        checks.append({"name": "recent_plan_contracts", "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)
    if check_drift:
        issues = check_task_contract_drift(
            baseline_state or project_root / "logs" / "meta-state.json",
            current_obligations=obligations,
        )
        checks.append({"name": "task_contract_drift", "status": "ok" if not issues else "issue", "issue_count": len(issues)})
        all_issues.extend(issues)

    red_count = sum(1 for item in all_issues if item["severity"] == "red" or item.get("blocks_completion"))
    yellow_count = sum(1 for item in all_issues if item["severity"] == "yellow" and not item.get("blocks_completion"))
    overall = "red" if red_count else "yellow" if yellow_count else "green"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "project": str(project_root),
        "state_authority": STATE_AUTHORITY,
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
    payload = {
        "schema": STATE_SCHEMA,
        "updated_at": utc_now(),
        "state_authority": STATE_AUTHORITY,
        "latest_snapshot": snapshot,
    }
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


def has_blocking_issue(snapshot: dict[str, Any]) -> bool:
    """Return True when the snapshot carries a completion-blocking signal.

    Blocking means either a red-counted issue or any issue flagged
    ``blocks_completion``. ``build_snapshot`` already folds ``blocks_completion``
    into ``red_count``, but we also scan the raw issues so the predicate stays
    correct for hand-built snapshots and future severities.
    """
    if snapshot.get("red_count"):
        return True
    return any(item.get("blocks_completion") for item in snapshot.get("issues", []))


def decide_exit_code(snapshot: dict[str, Any], *, strict: bool, fail_on_blocking: bool) -> int:
    """Resolve the process exit code from a snapshot and the gate flags.

    ``--strict`` keeps the legacy behavior: any non-green snapshot (red OR a
    non-blocking yellow) exits non-zero. ``--fail-on-blocking`` is CI-safe: only
    red or ``blocks_completion`` issues exit non-zero, so a stale-but-non-blocking
    yellow (e.g. a ``STALE_FACTS`` warning inside the 24-72h window) does not fail
    a deterministic pipeline. Flags are independent; either may trip exit 1.
    """
    if strict and snapshot.get("overall") != "green":
        return 1
    if fail_on_blocking and has_blocking_issue(snapshot):
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Meta Core task-contract checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero for any non-green snapshot (red or non-blocking yellow). Legacy local/dev gate.")
    parser.add_argument(
        "--fail-on-blocking",
        action="store_true",
        help="CI-safe gate: exit non-zero only for red or blocks_completion issues; non-blocking yellow exits zero.",
    )
    parser.add_argument("--task", help="Current user task text for task-contract extraction.")
    parser.add_argument("--no-git", action="store_true", help="Skip changed plan/design evidence checks.")
    parser.add_argument("--check-recent-plans", action="store_true", help="Also check recent committed plan/design files.")
    parser.add_argument("--check-drift", action="store_true", help="Compare current task obligations with an advisory state cache.")
    parser.add_argument("--baseline-state", type=Path, help="Advisory meta-state file for --check-drift (legacy flag name).")
    parser.add_argument("--state-file", type=Path, default=PROJECT_ROOT / "logs" / "meta-state.json")
    parser.add_argument("--write-state", action="store_true", help="Write advisory diagnostic state to logs/meta-state.json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = build_snapshot(
        task=args.task,
        include_git=not args.no_git,
        check_recent_plans=args.check_recent_plans,
        check_drift=args.check_drift,
        baseline_state=args.baseline_state,
    )
    if args.write_state:
        write_state(args.state_file, snapshot)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print_human(snapshot)
    return decide_exit_code(snapshot, strict=args.strict, fail_on_blocking=args.fail_on_blocking)


if __name__ == "__main__":
    raise SystemExit(main())
