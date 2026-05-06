# Meta Runtime

This is the active runtime contract for Meta Core / 元控核 inside 元守双核心.

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

## Completion Evidence

For Meta runtime changes, use:

```bash
.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q
scripts/meta-check --json --strict
scripts/codex-context --no-network
scripts/codex-verify safety --repo-wide
```
