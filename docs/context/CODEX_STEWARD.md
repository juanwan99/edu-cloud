# Codex Stewardship

Date: 2026-06-28
Purpose: stable planning memory for how Codex leads edu-cloud under Keel.

## Authority

- Codex is the local steward for planning, implementation help, review,
  hygiene, scope discipline, and acceptance evidence.
- Claude may be used by the user as planner, reviewer, or executor, but no
  model accepts its own work as complete.
- GitHub is the merge authority: required checks, CODEOWNERS, and human review
  decide whether a PR may merge.
- `AGENTS.md` is the active project entrypoint.
- `docs/context/ACTIVE_INDEX.md` controls which docs are active,
  candidate-active, reference, or historical.

## Keel Working Contract

For governed PRs:

1. Use a separate git worktree for parallel or risky work.
2. Add one new scope file under `control/steward/scopes/`.
3. Keep edits inside the declared `allowed_paths` and outside
   `forbidden_paths`.
4. Put `Steward-Scope: <scope_id>` in the PR body.
5. Let GitHub required checks and CODEOWNER review decide merge readiness.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create Yuanqi task windows, `.yuanqi/tasks`, or `Yuanqi-Task:` PR markers unless
the user explicitly revives a specific historical fact for analysis.

## Working Memory

- Current facts live in `docs/context/NOW.md`.
- Governance model lives in `docs/context/GOVERNANCE_MODEL.md`.
- Parallel development policy lives in `docs/context/PARALLEL_DEVELOPMENT.md`.
- Long-term module-boundary direction lives in
  `docs/governance/foundation-boundaries.md`.

Durable project memory belongs in tracked `docs/context/**` and
`docs/governance/**`, not ignored local `.codex/` state.

## Planning Checklist

Before non-trivial edu-cloud work:

1. Run `scripts/codex-check` when available.
2. Inspect `git status --short --branch`.
3. Read `docs/context/NOW.md` and `docs/context/ACTIVE_INDEX.md`.
4. Identify module-boundary, runtime, DB, auth, workflow, or deployment risk.
5. For multi-window work, classify the task using
   `docs/context/PARALLEL_DEVELOPMENT.md`.
6. For governed PRs, create the Keel scope file before protected edits.
7. Verify with focused local checks, then rely on GitHub required checks and
   human review for merge authority.
