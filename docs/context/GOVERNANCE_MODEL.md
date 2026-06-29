---
title: Dual-Core Governance
owner: liang
last_review_date: "2026-06-28"
expiration_in_days: 30
---

# Dual-Core Governance / 双核治理

edu-cloud uses Keel to keep AI-assisted work fast, bounded, and reviewable.
The two responsibility centers are Meta Core and Guardian Core.
This is Codex-led and Claude-assisted, with GitHub as the hard merge authority.

## Current Authority

- Codex leads planning, implementation help, review, hygiene, and acceptance
  evidence.
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

Primary files and tools:

- `AGENTS.md`
- `docs/context/CODEX_STEWARD.md`
- `docs/context/PARALLEL_DEVELOPMENT.md`
- `docs/context/NOW.md`
- `docs/context/ACTIVE_INDEX.md`
- `docs/context/COMMANDS.md`
- `docs/context/LESSONS.md`
- `docs/context/CLAUDE_AUX.md`
- `docs/context/META_RUNTIME.md`
- `docs/governance/foundation-boundaries.md`
- `scripts/codex-context`
- `scripts/meta-check`
- `scripts/meta_runtime.py`
- `scripts/codex-consult-claude`

## Meta Runtime

`scripts/meta-check` is the synchronous Meta Core diagnostic runtime. It may
observe, classify, write advisory state, and flag blockers. It must not edit
files automatically, replace user instructions, or declare completion.

It checks that:

- active context documents exist and are indexed;
- `docs/context/NOW.md` is fresh;
- Meta runtime remains registered in active entrypoint docs;
- Claude auxiliary review remains read-only and Codex-led;
- changed or recent plan/design docs include evidence or delivery-path
  references;
- current user task text can be decomposed into explicit obligations.

## Guardian Core

Guardian Core prevents operational accidents. It owns:

- dirty state and risky artifact checks;
- source/build/nginx/backend truthline;
- DB/migration gates;
- safety scanning;
- frontend/backend build-runtime consistency;
- process, port, and environment hygiene;
- no-new-failure regression discipline.

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
- `.github/workflows/test.yml`

## Guardian Runtime

`scripts/guardian-watch` is advisory runtime monitoring. It can run once for
local inspection or continuously under systemd. It may observe, classify, and
alert. It must not kill processes, delete files, run migrations, deploy, build,
or clean git state automatically.

## Completion Rule

Completion requires concrete evidence: local focused checks where useful,
GitHub required checks, CODEOWNER/human review for protected areas, and any
runtime evidence required by the task. The executor does not self-declare
completion.

## Non-Goals

Do not recreate retired Claude hook or Yuanqi task-contract machinery inside
Keel. Keel keeps the useful rules, evidence discipline, scope boundaries, and
health checks while relying on GitHub for hard merge enforcement.
