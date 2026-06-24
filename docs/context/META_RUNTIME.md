# Meta Runtime

This is the active runtime contract for Meta Core / 元控核 inside 双核治理.

## Evidence Basis

The Meta watchlist comes from historical behavior failures and current Codex
governance gaps:

- `~/.claude/LESSONS.md` L013: negative claims and self-audits failed when not
  backed by grep/read/log evidence.
- `~/.claude/LESSONS.md` L015: visual/offline tasks produced false completion
  claims because the model tried to be its own judge.
- `~/.claude/LESSONS.md` L017: model reviews drifted toward local design
  fixes when the global intent was not externalized.
- `~/.claude/LESSONS.md` L019: repeated fix loops happened because task truth
  was not live during execution.
- `~/.claude/LESSONS.md` L022: multi-step instruction skipping, role drift,
  shallow depth, and compact-related forgetting had no hard runtime carrier.
- `docs/meta-reviews/2026-05-04-behavior-quality-audit.md`: planning evidence
  and completion honesty were weak points even when output volume was high.

## What It Guards

`scripts/meta-check` emits `meta.core.v1` snapshots for the synchronous
task-contract plane. It checks:

- active context documents exist and are indexed
- `docs/context/NOW.md` has a fresh `Last refreshed` timestamp
- migrated lessons cover structural Meta risks
- Meta runtime is registered in entrypoint docs
- Claude auxiliary review remains read-only
- changed plan/design/handoff files include evidence, asset inventory, or
  delivery-path sections
- optional recent committed plan/design files include evidence and a concrete
  file or asset reference
- optional drift checks compare current obligations against advisory diagnostic
  obligations from `logs/meta-state.json`
- current task text implies explicit obligations such as evidence mining,
  Claude review, implementation verification, autonomy, and instruction
  decomposition

## What It Must Not Do

Meta runtime must not:

- edit files automatically
- declare completion
- override user instructions
- let Claude or GPT become the source of completion claims
- replace Guardian runtime environment checks

## Runtime Files

- executable: `scripts/meta-check`
- implementation: `scripts/meta_runtime.py`
- optional latest state: `logs/meta-state.json`

Meta is synchronous and task-bound. It is intentionally not a systemd watcher:
Guardian monitors the environment continuously; Meta should run at task start,
before broad design decisions, and before completion claims.

## Deep Checks

Use these when the task is long-running, design-heavy, or follows a model
review that found structural risk:

```bash
scripts/meta-check --task "current user task" --write-state
scripts/meta-check --task "current user task" --check-drift --baseline-state logs/meta-state.json
scripts/meta-check --check-recent-plans
```

`--check-drift` compares current obligations to the advisory state cache
(the `--baseline-state` flag name is retained for compatibility) and reports
`TASK_CONTRACT_DRIFT` if an obligation disappears from current task text. This
is a diagnostic warning, not a trusted baseline or completion authority.
`--check-recent-plans` checks recently committed `docs/plans/**` and
`docs/superpowers/plans/**` files for evidence sections that include a concrete
file, file-line, or asset reference. If the git range cannot be resolved, it
reports `PLAN_SCAN_INCONCLUSIVE` instead of silently skipping the check.

Task-obligation extraction is heuristic. Use stable task text when refreshing
the advisory cache for drift diagnostics. If the user materially changes the
task, refresh the advisory cache rather than treating the drift warning as a
trusted baseline failure.

## Exit Modes

`scripts/meta-check` has two non-zero exit gates; without either flag it always
exits zero (report-only).

- `--strict` (legacy, local/dev): exit non-zero for **any** non-green snapshot —
  red issues OR a non-blocking yellow (e.g. `STALE_FACTS` in the 24-72h window).
  Use it interactively when you want the full signal.
- `--fail-on-blocking` (CI-safe): exit non-zero **only** when `red_count > 0` or
  any issue carries `blocks_completion=true`; a non-blocking yellow exits zero.
  Use it in deterministic pipelines so a stale-but-recent `NOW.md` does not fail
  CI on a clock. `NOW.md` past the 72h red threshold is blocking and still fails.

CI (`.github/workflows/test.yml` `governance` job) and `scripts/codex-verify
full` both use `--fail-on-blocking`. The flags are independent; passing both
applies the stricter result.

## Completion Authority

Completion is accepted from the external/current authority chain:

- GitHub CI required check / governance gate
- CODEOWNERS approval
- live doctor current output (`scripts/truth-doctor.sh` and
  `scripts/db_doctor.py --strict` when DB/schema is in scope)

`scripts/meta-check --write-state` and `logs/meta-state.json` are task-state
diagnostics. They can carry obligations and drift context, but persisted state is
not a trust baseline and is not sufficient completion authority.

`scripts/meta-check --fail-on-blocking` remains a CI-safe local/CI signal for
blocking Meta issues; it does not replace the required check plus CODEOWNERS
approval chain.

For Meta runtime changes, attach current diagnostic output such as:

```bash
.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q
scripts/meta-check --json --fail-on-blocking   # CI-safe gate (or --strict locally for full signal)
scripts/codex-context --no-network
scripts/codex-verify safety --repo-wide
```
