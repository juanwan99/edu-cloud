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
- port inventory for canonical API/dev/proxy ports and parallel backend binds
- process inventory for systemd-owned services, duplicate workers, and extra
  Guardian/watch processes
- risky local artifacts vs active SQLite WAL/SHM runtime files
- truth doctor health: ports, public binds, ghost processes, systemd state,
  Claude process count, dist permissions, and DB drift
- current `guardian.watch.v1` state freshness

Network-backed checks, when enabled:

- local `frontend/dist/version.json`
- remote `https://mcu.asia/version.json`
- backend `http://127.0.0.1:9000/api/v1/version`
- non-canonical edu-cloud backend listeners, when reachable on localhost, so a
  debug backend on another port can be compared with the current source hash

## Parallel Version Guardrails

Guardian treats these as first-class inventory, not just log text:

- `ports`: listening TCP ports from `ss -tlnp`, enriched with pid, command,
  systemd owner, and edu-cloud `/api/v1/version` when applicable.
- `processes`: project-related API, worker, Guardian, and llm-proxy processes,
  enriched with systemd ownership.
- `versions`: source HEAD, local dist, nginx, backend, and runtime dirty flags.

Stable issue codes for parallel-version accidents:

- `PARALLEL_BACKEND_PROCESS`: an edu-cloud backend is running outside canonical
  port 9000.
- `PARALLEL_VERSION_DRIFT`: a backend listener reports a git hash different
  from source HEAD.
- `PARALLEL_RUNTIME_DIRTY`: a backend listener reports `source_dirty=true`.
- `DUPLICATE_WORKER_PROCESS`: more than one ARQ worker is present, or a worker
  is not owned by `edu-cloud-worker.service`.
- `PORT_CONFLICT`: a guarded port has multiple listeners.
- `PORT_PUBLIC_BIND`: a guarded port is bound publicly.
- `PORT_OWNER_MISMATCH`: a canonical port is owned by the wrong systemd service.
- `BACKEND_HOT_RELOAD`: watch state saw the same backend PID report a different
  hash or boot time, indicating a reload that needs human context.

In watch mode, Guardian also persists `backend_runtimes` in
`logs/guardian-state.json` so it can compare the current API listener PID,
reported hash, and boot time with the previous sample. This catches reload-style
version changes that a single `--once` snapshot cannot prove by itself.

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
