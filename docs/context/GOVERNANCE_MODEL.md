---
title: Keel Governance Model
owner: liang
last_review_date: "2026-06-29"
expiration_in_days: 30
---

# Keel Governance Model

edu-cloud uses Keel to keep AI-assisted work fast, bounded, and reviewable.
Keel keeps a dual-core responsibility split, but GitHub is the hard merge
authority.

## Current Authority

- Codex leads local stewardship, implementation help, review, hygiene, and
  acceptance evidence.
- Claude may assist as a planner, reviewer, or executor when explicitly used,
  but no model accepts its own work as complete.
- GitHub is the hard merge authority through required checks, CODEOWNERS, and
  human approval.
- Governed PRs declare `Steward-Scope: <scope_id>` and add one fresh scope file
  under `control/steward/scopes/`.

The retired Yuanqi task-contract workflow is historical evidence only. Current
work must not create Yuanqi task windows, `.yuanqi/tasks`, or `Yuanqi-Task:`
markers.

## Meta Core

Meta Core prevents task drift and context drift. It owns:

- direction;
- active facts and document indexing;
- task boundaries and scope discipline;
- context discipline;
- Claude read-only counter-review;
- completion evidence contract;
- long-term module-boundary direction and coupling-reduction discipline;
- parallel-work classification before launching extra windows.

Primary current files and tools:

- `AGENTS.md`
- `docs/context/ACTIVE_INDEX.md`
- `docs/context/CODEX_STEWARD.md`
- `docs/context/PARALLEL_DEVELOPMENT.md`
- `docs/context/NOW.md`
- `docs/context/COMMANDS.md`
- `docs/context/LESSONS.md`
- `docs/context/CLAUDE_AUX.md`
- `docs/governance/foundation-boundaries.md`
- `scripts/codex-check`
- `scripts/codex-context`
- `scripts/codex-consult-claude`

## Guardian Core

Guardian Core prevents operational accidents. It owns:

- dirty state and risky artifact checks;
- source/build/nginx/backend truthline;
- DB/migration gates;
- safety scanning;
- frontend/backend build-runtime consistency;
- process, port, and environment hygiene;
- no-new-failure regression discipline.

Primary current files and tools:

- `docs/context/SAFETY_MATRIX.md`
- `docs/context/ARTIFACT_POLICY.md`
- `scripts/codex-verify`
- `scripts/db_doctor.py`
- `scripts/db_migrate`
- `scripts/truth-status.sh`
- `scripts/truth-doctor.sh`
- `.github/workflows/test.yml`
- `.github/workflows/steward-hard-gates.yml`
- `.github/workflows/doc-stale-sweep.yml`

## Completion Rule

Completion requires concrete evidence: local focused checks where useful,
GitHub required checks, CODEOWNER/human review for protected areas, and any
runtime evidence required by the task. The executor does not self-declare
completion.

## Non-Goals

Do not recreate retired Claude hook or Yuanqi task-contract machinery inside
Keel. Keel keeps the useful rules, evidence discipline, scope boundaries, and
health checks while relying on GitHub for hard merge enforcement.
