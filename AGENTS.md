---
title: edu-cloud Agent Entry
owner: liang
last_review_date: "2026-06-28"
expiration_in_days: 30
---

# edu-cloud Agent Entry

This is the active entrypoint for AI-assisted work in edu-cloud.

## Active Document Index

Before reading `docs/**`, read `docs/context/ACTIVE_INDEX.md`. It is the only
canonical index for active, candidate-active, reference, and historical docs.
Do not discover current instructions by scanning old plans or handoffs.

## Current Governance

edu-cloud uses Keel for governed changes:

1. Use one git worktree per parallel task.
2. Add one new scope file under `control/steward/scopes/` for each governed PR.
3. Change only files allowed by that scope.
4. Include `Steward-Scope: <scope_id>` in the PR body.
5. Let GitHub required checks, CODEOWNERS, and human review decide.

The old Yuanqi task-contract workflow is retired from active use. Do not create
or restore `.yuanqi/tasks`, `Yuanqi-Task:` PR markers, Yuanqi task windows, or
Yuanqi registry/scope/overlap gates.

Historical documents may still mention Yuanqi. Treat those references as
history unless a current Keel scope or a current user instruction explicitly
revives a specific fact.

## Roles

Keel keeps the useful 双核治理 responsibility split without the retired Yuanqi
task-contract machinery:

- **Meta Core / 元控核** owns direction, facts, task boundaries, context,
  Claude read-only counter-review, and the completion evidence contract.
- **Guardian Core / 守护核** owns dirty state, truthline, DB/migration gates,
  safety scanning, frontend/backend build-runtime consistency, and environment hygiene.

This is Codex-led and Claude-assisted: Claude may plan, review, or implement
when explicitly used, but GitHub and human review remain the merge authority.

- Codex App: local steward, implementation helper, review assistant, and hygiene
  auditor.
- Claude App: local planner/reviewer or implementation assistant when the user
  explicitly uses it.
- GitHub: hard gate for merge eligibility through required checks, CODEOWNERS,
  and review.

No model accepts its own work as complete. Completion requires concrete evidence:
tests, CI, runtime checks, or file-level inspection.

## Start Here

1. Run `scripts/codex-check` when available.
2. Inspect `git status --short --branch`.
3. Read the relevant current source files before editing.
4. For governed PRs, create a new Keel scope file before changing protected
   governance or high-risk paths.
5. Keep verification focused on the changed behavior.
6. For Meta runtime freshness and task-boundary diagnostics, read
   `docs/context/META_RUNTIME.md` and use `scripts/meta-check`.

## Hard Bans

- Do not run `git reset --hard`, `git checkout -- .`, `git restore .`, `git clean -f`,
  or equivalent destructive cleanup unless the user explicitly asks.
- Do not direct-run `alembic upgrade` or `alembic downgrade` on the project DB.
  Use `scripts/db_migrate`.
- Do not copy active SQLite databases with `cp` or `rsync`; use SQLite backup APIs
  or project migration/backup tools.
- Do not edit `.env` or `.secrets` unless the user explicitly asks.
- Do not commit secrets, API keys, service-account JSON, WAL/SHM files,
  screenshots, local backups, or generated runtime artifacts.
- Do not treat old Windows-era paths, stale handoffs, or historical governance
  documents as current facts.

## Verification

Use the narrowest meaningful verification first, then rely on GitHub required
checks for merge decisions.

Common commands:

```bash
scripts/codex-check
scripts/codex-context --no-network
scripts/codex-verify safety
scripts/codex-verify safety --repo-wide
scripts/codex-verify backend --dry-run
scripts/codex-verify frontend --dry-run
scripts/codex-verify schema --dry-run
```

For runtime isolation, use Docker Compose with a unique project name and ports
for each parallel task. Stop the same Compose project with `docker compose down -v`
when done.
