from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_SCRIPTS = REPO_ROOT / "scripts" / "governance"
sys.path.insert(0, str(GOVERNANCE_SCRIPTS))

import check_doc_pollution as guard  # noqa: E402


def write_active_index(repo: Path, rel_path: str) -> None:
    active_index = repo / "docs" / "context" / "ACTIVE_INDEX.md"
    active_index.parent.mkdir(parents=True, exist_ok=True)
    active_index.write_text(
        "\n".join(
            [
                "| Path | Status | Notes |",
                "|---|---|---|",
                f"| `{rel_path}` | active | test fixture |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_active_doc(repo: Path, rel_path: str, text: str) -> Path:
    doc = repo / rel_path
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(text, encoding="utf-8")
    write_active_index(repo, rel_path)
    return doc


def test_debt_ledger_known_pollution_and_burn_down_examples() -> None:
    debt_ledger = REPO_ROOT / "docs" / "governance" / "debt-ledger.md"
    lines = debt_ledger.read_text(encoding="utf-8").splitlines()

    burn_down_line = next(line for line in lines if "D-03A 30/55" in line)
    assert (
        guard.scan_lines(
            Path("docs/governance/debt-ledger.md"),
            [burn_down_line],
            source_counts=(0, 0),
            start_line=20,
        )
        == []
    )

    known_bad_heading = "### D-03 跨模块耦合 53 edges / 13 cycles（R-H4）— HIGH · 结构"
    failures = guard.scan_lines(
        Path("docs/governance/debt-ledger.md"),
        [known_bad_heading],
        source_counts=(0, 0),
        start_line=70,
    )

    assert any("known stale pollution" in failure.message for failure in failures)


def test_active_doc_current_55_edges_fails(tmp_path: Path) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/current.md",
        "D-03 当前事实：55 edges / 30 cycles。\n",
    )

    failures = guard.check_docs(tmp_path, source_counts=(0, 0))

    assert any("known stale pollution" in failure.message for failure in failures)
    assert any(failure.line == 1 for failure in failures)


def test_active_doc_date_adjacent_current_55_edges_fails(tmp_path: Path) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/current.md",
        "更新时间:2026-06-24 / D-03 当前事实:55 edges / 30 cycles。\n",
    )

    failures = guard.check_docs(tmp_path, source_counts=(0, 0))

    assert any("known stale pollution" in failure.message for failure in failures)
    assert any("current fact disagrees with source truth" in failure.message for failure in failures)


def test_active_doc_historical_55_edges_passes(tmp_path: Path) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/history.md",
        "D-03 historical burn-down: 55 edges / 30 cycles -> 0 edges / 0 cycles。\n",
    )

    assert guard.check_docs(tmp_path, source_counts=(0, 0)) == []


def test_active_doc_date_adjacent_historical_55_edges_passes(tmp_path: Path) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/history.md",
        "更新时间:2026-06-24 / D-03 历史峰值：55 edges / 30 cycles -> 0 edges / 0 cycles。\n",
    )

    assert guard.check_docs(tmp_path, source_counts=(0, 0)) == []


def test_current_fact_count_mismatch_fails(tmp_path: Path) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/current.md",
        "D-03 当前事实：1 edges / 2 cycles。\n",
    )

    failures = guard.check_docs(tmp_path, source_counts=(0, 0))

    assert any("current fact disagrees with source truth" in failure.message for failure in failures)


def test_source_command_failure_fails(tmp_path: Path, monkeypatch) -> None:
    write_active_doc(
        tmp_path,
        "docs/context/current.md",
        "D-03 当前事实：0 edges / 0 cycles。\n",
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="boom")

    monkeypatch.setattr(guard.subprocess, "run", fake_run)

    failures = guard.check_docs(tmp_path)

    assert any("source command failed" in failure.message for failure in failures)
