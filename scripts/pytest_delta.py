#!/usr/bin/env python3
"""pytest_delta.py — No-new-failures regression gate (P1-A, audit consensus 2026-05-04).

Runs pytest, compares against known-failures baseline.
- New failures → exit 1 (block)
- Known failures disappearing (fixed) → auto-remove from baseline
- All known failures still failing → exit 0 (pass)

Usage:
    python scripts/pytest_delta.py [--update-only] [pytest-args...]
    --update-only: skip pytest run, just update baseline from last junit xml
"""
import subprocess
import sys
import os

BASELINE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.quality', 'known-pytest-failures.txt',
)


def load_baseline():
    if not os.path.exists(BASELINE_FILE):
        return set()
    known = set()
    with open(BASELINE_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                known.add(line)
    return known


def save_baseline(known, removed=None):
    header_lines = []
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE) as f:
            for line in f:
                if line.startswith('#'):
                    header_lines.append(line.rstrip())
                else:
                    break

    from datetime import datetime
    for i, h in enumerate(header_lines):
        if h.startswith('# Last updated:'):
            header_lines[i] = f'# Last updated: {datetime.now().strftime("%Y-%m-%d")}'
            break

    with open(BASELINE_FILE, 'w') as f:
        for h in header_lines:
            f.write(h + '\n')
        for test_id in sorted(known):
            f.write(test_id + '\n')

    if removed:
        print(f"\n✅ {len(removed)} known failure(s) fixed — removed from baseline:")
        for t in sorted(removed):
            print(f"  - {t}")


def run_pytest(extra_args):
    cmd = [
        sys.executable, '-m', 'pytest',
        '--tb=no', '-q', '--no-header',
    ] + extra_args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return r.stdout, r.stderr, r.returncode


def parse_failures(stdout):
    failures = set()
    for line in stdout.splitlines():
        if line.startswith('FAILED '):
            test_id = line[7:].strip()
            if '::' in test_id:
                test_id = test_id.split(' ')[0]
            failures.add(test_id)
    return failures


def _detect_collection_errors(stdout, stderr, rc):
    """Detect pytest collection/import errors that don't produce FAILED lines."""
    if rc in (2, 3, 4):
        return True
    error_markers = ('ERRORS', 'collection error', 'ImportError', 'ModuleNotFoundError')
    combined = (stdout or '') + (stderr or '')
    return any(m in combined for m in error_markers)


def main():
    extra_args = [a for a in sys.argv[1:] if a != '--update-only']
    is_full_run = not extra_args or all(a.startswith('-') for a in extra_args)

    print("Running pytest...")
    stdout, stderr, rc = run_pytest(extra_args)

    if _detect_collection_errors(stdout, stderr, rc):
        print(f"\n❌ pytest collection/import error detected (exit code {rc}).")
        print("Fix collection errors before checking regression baseline.")
        if stderr:
            for line in stderr.splitlines()[-10:]:
                print(f"  {line}")
        sys.exit(1)

    actual_failures = parse_failures(stdout)
    known = load_baseline()

    new_failures = actual_failures - known
    fixed = (known - actual_failures) if is_full_run else set()

    if fixed:
        known -= fixed
        save_baseline(known, removed=fixed)

    if new_failures:
        print(f"\n❌ {len(new_failures)} NEW failure(s) detected (not in baseline):")
        for t in sorted(new_failures):
            print(f"  {t}")
        print(f"\nKnown failures: {len(known & actual_failures)}")
        print(f"New failures:   {len(new_failures)}")
        print("\nTo add to baseline (if intentional): edit .quality/known-pytest-failures.txt")
        sys.exit(1)

    print(f"\n✅ No new failures.")
    print(f"   Known failures still present: {len(known & actual_failures)}")
    if fixed:
        print(f"   Known failures fixed: {len(fixed)}")
    if not is_full_run:
        print(f"   (partial run — known failures not auto-removed)")
    passed_line = [l for l in stdout.splitlines() if 'passed' in l]
    if passed_line:
        print(f"   {passed_line[-1].strip()}")
    sys.exit(0)


if __name__ == '__main__':
    main()
