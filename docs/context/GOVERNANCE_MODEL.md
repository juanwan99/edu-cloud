# EduCloud Dual-Core Control Plane

The edu-cloud governance model is the **EduCloud Dual-Core Control Plane**
(`ECP-DualCore`).
It is Codex-led and Claude-assisted: Codex is the operator, editor, verifier,
and source of completion claims; Claude is a full-repository read-only reviewer.

## Purpose

The control plane keeps daily work aligned with the user's goal and prevents
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
- `scripts/codex-context`
- `scripts/codex-consult-claude`

Core capabilities:

- Current-fact control
- Active-document indexing
- Scope and task-boundary discipline
- Evidence requirements for decisions and completion claims
- Asset inventory before new design or architecture work
- Claude read-only counter-review

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
- `scripts/codex-check`
- `scripts/codex-verify`
- `scripts/truth-status.sh`
- `scripts/truth doctor`
- `scripts/db_doctor.py`
- `scripts/db_migrate`
- `scripts/pytest_delta.py`
- `.github/workflows/test.yml`

Core capabilities:

- Start-of-work preflight
- Completion verification gates
- Dirty-build refusal
- Source/build/nginx/backend truthline checks
- Migration and SQLite guardrails
- Changed-script safety scanning and repo-wide secret/SQLite-copy scanning
- Structured rule mapping through Safety Matrix IDs

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
