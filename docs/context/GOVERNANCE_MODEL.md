# 元守双核心

The edu-cloud governance model is **元守双核心**.
The name means a two-core system: 元 for Meta Core / 元控核, and 守 for
Guardian Core / 守护核.
It is Codex-led and Claude-assisted: Codex is the operator, editor, verifier,
and source of completion claims; Claude is a full-repository read-only reviewer.

## Purpose

The governance layer keeps daily work aligned with the user's goal and prevents
operational accidents. It is explicit, script-backed, and reviewable in git.

## Meta Core / 元控核

Meta Core prevents task drift and execution drift. It owns direction, facts,
task boundaries, context, Claude read-only counter-review, and the completion evidence contract.

It answers:

- What facts and documents are active now?
- What is the task boundary?
- Which historical docs are safe to read?
- Does this task need Claude read-only counter-review?
- What evidence is required before a completion claim?
- Is this change following existing project assets instead of creating a parallel system?

Primary files and tools:

- `AGENTS.md`
- `docs/context/NOW.md`
- `docs/context/ACTIVE_INDEX.md`
- `docs/context/COMMANDS.md`
- `docs/context/LESSONS.md`
- `docs/context/CLAUDE_AUX.md`
- `docs/context/META_RUNTIME.md`
- `scripts/codex-context`
- `scripts/meta-check`
- `scripts/meta_runtime.py`
- `scripts/codex-consult-claude`

Core capabilities:

- Current-fact control
- Active-document indexing
- Scope and task-boundary discipline
- Evidence requirements for decisions and completion claims
- Asset inventory before new design or architecture work
- Claude read-only counter-review

## Meta Runtime / 元控运行时

`scripts/meta-check` is the executable Meta Core runtime. It is synchronous and
task-bound: run it at task start, before broad design decisions, and before
completion claims. It writes an optional latest state file at
`logs/meta-state.json`.

It guards:

- active context documents exist and are indexed
- `docs/context/NOW.md` has a fresh current-facts timestamp
- project lessons include structural Meta risks from past failures
- Meta runtime remains registered in active entrypoint docs
- Claude auxiliary review remains read-only and Codex-led
- changed plan/design/handoff documents include evidence, existing-asset
  inventory, or delivery-path sections
- current user task text is decomposed into obligations such as evidence
  mining, read-only model review, implementation verification, autonomy, and
  multi-step instruction handling

Authority boundaries:

- It may observe, classify, write a task-contract snapshot, and block a
  completion claim when red issues are present.
- It must not edit files automatically, replace user instructions, or declare
  completion.
- It must not replace Guardian's continuous environment monitoring.

## Guardian Core / 守护核

Guardian Core prevents operational accidents. It owns dirty state, truthline,
DB/migration gates, safety scanning, frontend/backend build-runtime consistency, and environment hygiene.

It answers:

- Is the working tree safe to build from?
- Are source, dist, nginx, backend, and browser evidence aligned?
- Are migration and SQLite rules being followed?
- Are risky local artifacts present?
- Are known pytest failures stable?
- Is a fix-loop or repeated patch pattern emerging?

Primary files and tools:

- `docs/context/SAFETY_MATRIX.md`
- `docs/context/ARTIFACT_POLICY.md`
- `docs/context/GUARDIAN_RUNTIME.md`
- `scripts/codex-check`
- `scripts/codex-verify`
- `scripts/guardian-watch`
- `scripts/guardian_runtime.py`
- `scripts/truth-status.sh`
- `scripts/truth doctor`
- `scripts/db_doctor.py`
- `scripts/db_migrate`
- `scripts/pytest_delta.py`
- `deploy/systemd/edu-cloud-guardian.service`
- `.github/workflows/test.yml`

Core capabilities:

- Start-of-work preflight
- Completion verification gates
- Dirty-build refusal
- Source/build/nginx/backend truthline checks
- Migration and SQLite guardrails
- Changed-script safety scanning and repo-wide secret/SQLite-copy scanning
- Structured rule mapping through Safety Matrix IDs
- Realtime advisory snapshots in `logs/guardian-state.json`
- Rate-limited read-only Claude risk review when the runtime sees persistent
  yellow/red health

## Guardian Runtime / 守护运行时

`scripts/guardian-watch` is the realtime Guardian Core runtime. It can run once
for local inspection or continuously under systemd.

It monitors:

- git dirty/ahead state
- truth doctor health: ports, public binds, ghost processes, systemd state,
  Claude process count, dist permissions, and DB schema drift
- frontend/backend truthline data from local dist, nginx, and backend version
  endpoints when network checks are enabled
- risky local artifacts vs active SQLite WAL/SHM runtime files
- read-only model review state

It writes:

- latest state: `logs/guardian-state.json`
- append-only event stream: `logs/guardian-watch.jsonl`
- read-only model review reports: `logs/guardian-model-review-*.txt`

Authority boundaries:

- It may observe, classify, alert, and schedule read-only model review.
- Claude review uses `scripts/codex-consult-claude`; GPT review requires an
  explicit read-only command wrapper passed with `--model-review-command`.
- It must not kill ARQ workers, backend services, Claude sessions, or port
  listeners automatically.
- It must not delete active SQLite DB/WAL/SHM files, dirty source files,
  experiment data, backups, screenshots, `.env`, or `.secrets`.
- It must not run git cleanup, migrations, builds, or deployment commands.

The systemd template is `deploy/systemd/edu-cloud-guardian.service`. It runs the
watcher every 15 seconds and enables rate-limited Claude review through
`scripts/codex-consult-claude`.

## Authority

- Codex leads and edits.
- Claude may read the full repository through `scripts/codex-consult-claude`.
- Claude may critique Meta Core decisions and Guardian Core gaps.
- Claude may not write files, run Bash, run migrations, or declare completion.
- Completion claims require Codex-run verification evidence.

## Non-Goals

Do not recreate the Claude hook runtime inside Codex. The following Claude-era
mechanics stay historical unless a specific Codex-native need appears:

- PreToolUse/PostToolUse/Stop hook lifecycle
- Claude session compact/recovery machinery
- L0 hook manifest signing
- Hook budget management
- Claude teams/inboxes

Codex absorbs the useful rules, evidence discipline, and health checks, not the
Claude runtime.
