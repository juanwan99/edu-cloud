import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTEST_DELTA = PROJECT_ROOT / "scripts" / "pytest_delta.py"


def load_pytest_delta():
    spec = importlib.util.spec_from_file_location("pytest_delta_under_test", PYTEST_DELTA)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_full_run_does_not_update_baseline_by_default(tmp_path, monkeypatch, capsys):
    module = load_pytest_delta()
    baseline = tmp_path / "known-pytest-failures.txt"
    known_failure = "tests/test_example.py::test_old_failure"
    original = (
        "# Known pytest failures\n"
        "# Last updated: 2026-01-01\n"
        f"{known_failure}\n"
    )
    baseline.write_text(original)

    monkeypatch.setattr(module, "BASELINE_FILE", str(baseline))
    monkeypatch.setattr(sys, "argv", ["pytest_delta.py"])
    monkeypatch.setattr(module, "run_pytest", lambda extra_args: ("1 passed in 0.01s\n", "", 0))

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 0
    assert baseline.read_text() == original
    output = capsys.readouterr().out
    assert "baseline unchanged" in output
    assert "--update-baseline" in output


@pytest.mark.parametrize("flag", ["--update-baseline", "--prune-baseline"])
def test_explicit_update_flag_prunes_fixed_known_failures(tmp_path, monkeypatch, flag):
    module = load_pytest_delta()
    baseline = tmp_path / "known-pytest-failures.txt"
    fixed_failure = "tests/test_example.py::test_fixed_failure"
    still_failing = "tests/test_example.py::test_still_failing"
    baseline.write_text(
        "# Known pytest failures\n"
        "# Last updated: 2026-01-01\n"
        f"{fixed_failure}\n"
        f"{still_failing}\n"
    )
    seen_extra_args = []

    def fake_run_pytest(extra_args):
        seen_extra_args.extend(extra_args)
        return (f"FAILED {still_failing} - AssertionError\n", "", 1)

    monkeypatch.setattr(module, "BASELINE_FILE", str(baseline))
    monkeypatch.setattr(sys, "argv", ["pytest_delta.py", flag])
    monkeypatch.setattr(module, "run_pytest", fake_run_pytest)

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 0
    assert seen_extra_args == []
    updated = baseline.read_text()
    assert fixed_failure not in updated
    assert still_failing in updated
    assert "# Last updated:" in updated
