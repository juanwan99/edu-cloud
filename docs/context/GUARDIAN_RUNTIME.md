# Guardian Runtime

This is the active runtime contract for Guardian Core / 守护核 inside
元守双核心.

## Evidence Basis

The runtime watchlist comes from current Codex context plus historical failure
evidence:

- `docs/context/LESSONS.md`: user-visible delivery requires source -> build ->
  nginx -> browser proof; active SQLite copy is forbidden; dirty frontend builds
  are production incidents; completion needs command evidence.
- `~/.claude/LESSONS.md`: L013 records delivery-pipeline blindness; L016 records
  SQLite WAL copy data loss; L019 records repeated fix-loop drift; L021 records
  dirty working tree builds.
- `docs/superpowers/plans/2026-04-29-guardian-meta-boundary-design.md`: Guardian
  is a hygiene ledger, not an action-deny system; shared state should flow
  through files, not hidden runtime coupling.
- `scripts/truth-status.sh` and `scripts/truth-doctor.sh`: current truthline,
  ports, ghosts, systemd, Claude session, dist, and DB checks.

## What It Guards

High-frequency checks:

- worktree dirty/ahead state
- frontend/backend dirty risk
- risky local artifacts vs active SQLite WAL/SHM runtime files
- truth doctor health: ports, public binds, ghost processes, systemd state,
  Claude process count, dist permissions, and DB drift
- current `guardian.watch.v1` state freshness

Network-backed checks, when enabled:

- local `frontend/dist/version.json`
- remote `https://mcu.asia/version.json`
- backend `http://127.0.0.1:9000/api/v1/version`

Model checks:

- Claude review is scheduled through `scripts/codex-consult-claude`.
- GPT review is supported only through an explicit read-only
  `--model-review-command` wrapper.
- Reviews are rate-limited by issue fingerprint and interval.

## What It Must Not Do

The runtime must never automatically:

- kill ARQ workers, backend services, llm-proxy, port listeners, or Claude
  sessions
- delete active SQLite DB/WAL/SHM files
- delete dirty source, tests, docs, backups, screenshots, experiment data,
  `.env`, or `.secrets`
- run `git reset`, `git clean`, stash, revert, migrations, builds, deploys, or
  database copy commands
- declare work complete

## Runtime Files

- executable: `scripts/guardian-watch`
- implementation: `scripts/guardian_runtime.py`
- service template: `deploy/systemd/edu-cloud-guardian.service`
- latest state: `logs/guardian-state.json`
- event stream: `logs/guardian-watch.jsonl`
- model reports: `logs/guardian-model-review-*.txt`

`logs/**` is ignored by git.
The JSONL stream rotates at 10MB with five retained backups. The systemd unit
sets a modest CPU quota, memory cap, and `NoNewPrivileges=true`.

## Completion Evidence

For Guardian runtime changes, use:

```bash
.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q
scripts/guardian-watch --once --json --no-network --no-model-review
systemctl is-active edu-cloud-guardian.service
scripts/codex-context --no-network
scripts/codex-verify safety --repo-wide
```
