import subprocess
import sys

from scripts.governance.check_legacy_quarantine import check_files


def test_legacy_quarantine_flags_retired_consult_in_active_ci(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("run: scripts/codex-consult-claude --dry-run review CI smoke\n", encoding="utf-8")

    findings = check_files(tmp_path, (".github/workflows/test.yml",))

    assert len(findings) == 1
    assert findings[0].token == "codex-consult-claude"


def test_legacy_quarantine_allows_retired_term_outside_active_execution_files(tmp_path):
    docs = tmp_path / "docs" / "context" / "CLAUDE_AUX.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("historical reference to scripts/codex-consult-claude\n", encoding="utf-8")

    assert check_files(tmp_path, (".github/workflows/test.yml", "scripts/guardian_runtime.py")) == []


def test_legacy_quarantine_cli_passes_current_tree():
    result = subprocess.run(
        [sys.executable, "scripts/governance/check_legacy_quarantine.py", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "legacy quarantine clean" in result.stdout
