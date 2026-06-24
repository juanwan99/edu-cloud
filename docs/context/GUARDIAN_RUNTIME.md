# Guardian Runtime

This is the active runtime contract for Guardian Core / 守护核 inside
双核治理.

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
  real Claude CLI session count, dist permissions, and DB drift
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
- `PARALLEL_FRONTEND_DEV_SERVER`: an edu-cloud Vite dev server is running
  outside canonical port 8080.
- `PARALLEL_VERSION_DRIFT`: a backend listener reports a git hash different
  from source HEAD **and** the commits between them touch real runtime paths
  (blocking red). A docs/governance-only trail downgrades to the non-blocking
  `PARALLEL_VERSION_DRIFT_DOCS` instead (see Drift Classification below).
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

## Drift Classification (docs/governance vs runtime)

A deployed git hash that merely *trails* source HEAD is not automatically a
runtime failure. `codex_support.classify_hash_drift(base, head)` diffs the two
commits and classifies the gap:

- `runtime` — at least one path under `RUNTIME_DRIFT_PREFIXES` (source,
  frontend build inputs, dependencies, `deploy/`, the worker entrypoint) changed.
  The deployed bundle/backend is genuinely stale; the drift stays a blocking red
  `BUILD_DRIFT` / `NGINX_DRIFT` / `BACKEND_DRIFT` / `PARALLEL_VERSION_DRIFT`.
- `docs_only` — the commits only changed documentation, governance, CI,
  tests, or the observability scripts themselves. The deployed artifact is
  functionally current, so Guardian emits the non-blocking yellow
  `*_DOCS` variant (`BUILD_DRIFT_DOCS`, `NGINX_DRIFT_DOCS`, `BACKEND_DRIFT_DOCS`,
  `PARALLEL_VERSION_DRIFT_DOCS`) instead of a red.
- `unknown` — a hash is not resolvable in the local repo or the diff failed.
  Classification cannot prove the gap is benign, so the drift stays red
  (fail-safe; real drift detection is never weakened by the unknown branch).

`scripts/truth-status.sh` applies the identical rule (its `RUNTIME_PREFIXES`
array mirrors `RUNTIME_DRIFT_PREFIXES`): a docs-only trail at Build/Nginx/Backend
prints a yellow warning and reports a `FUNCTIONALLY ALIGNED — deployed runtime
trails HEAD only by docs/governance/test/observability commits` diagnosis
(exit 0). The literal `ALL ALIGNED — ... versions match` line is reserved for an
exact hash match, so the diagnosis never falsely claims equality. A real or
unknown gap prints a red `BROKEN AT:` and exits non-zero.

## Claude Session Counting

`CLAUDE_SESSION_RISK` counts only genuine Claude Code CLI sessions.
`codex_support.is_claude_cli_process` requires the command's `argv[0]` basename
to be `claude` (an npm bin shim/symlink) or a `node`/`bun` launch of the
claude-code `cli.js`. Commands that merely reference a `.claude` config path, the
`claude-meta` git repo, or wrapper scripts such as `legacy_governance_claude` /
`codex-consult-claude` are not sessions and never inflate the count; stateless
`--no-session-persistence` consult reviewers are also excluded.

## Stale Meta Snapshot Labelling

`scripts/codex-context` reads the persisted `logs/meta-state.json` snapshot. It
is a point-in-time record, not a live daemon, so codex-context labels it with
its age and a freshness verdict via `codex_support.snapshot_freshness`
(`META_STATE_FRESH_SECONDS = 3600`). A snapshot older than the window — or one
whose timestamp cannot be parsed — is marked `STALE — point-in-time snapshot, not
current truth`, and its `overall` is annotated `run scripts/meta-check to refresh`
so a stale red is never presented as the current verdict.

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

## Completion Authority

Completion is accepted from the external/current authority chain:

- GitHub CI required check / governance gate
- CODEOWNERS approval
- live doctor current output (`scripts/truth-doctor.sh` and
  `scripts/db_doctor.py --strict` when DB/schema is in scope)

`scripts/guardian-watch`, `systemctl is-active edu-cloud-guardian.service`, and
`logs/guardian-state.json` are operational diagnostics. They are useful PR
evidence, but they are not a trust baseline and are not sufficient completion
authority.

For Guardian runtime changes, attach current diagnostic output such as:

```bash
.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q
scripts/guardian-watch --once --json --no-network --no-model-review
systemctl is-active edu-cloud-guardian.service
scripts/codex-context --no-network
scripts/codex-verify safety --repo-wide
```
