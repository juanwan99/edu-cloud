---
title: Active Document Index
owner: liang
last_review_date: "2026-06-29"
expiration_in_days: 30
---

# Active Document Index

Read this file before reading `docs/**`. Anything not listed here is candidate,
reference, or historical context and must not be treated as current instruction.
The active governance model is Keel, with GitHub as merge authority.

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | Primary AI entrypoint and hard rules |
| `CLAUDE.md` | active | Claude app entry shim pointing back to AGENTS and this index |
| `docs/context/ACTIVE_INDEX.md` | active | Canonical current-doc index |
| `docs/context/NOW.md` | active | Current volatile facts and near-term work |
| `docs/context/CODEX_STEWARD.md` | active | Codex stewardship and completion discipline |
| `docs/context/GOVERNANCE_MODEL.md` | active | Keel dual-core governance model |
| `docs/context/PARALLEL_DEVELOPMENT.md` | active | Safe parallel work modes and exclusive scopes |
| `docs/context/COMMANDS.md` | active | Command reference |
| `docs/context/SAFETY_MATRIX.md` | active | Risk-to-enforcement map |
| `docs/context/ARTIFACT_POLICY.md` | active | Local artifact and backup policy |
| `docs/context/CLAUDE_AUX.md` | active | Optional read-only Claude review protocol |
| `docs/context/LESSONS.md` | active | Project-specific lessons that still affect current behavior |

## Candidate Active Work

Candidate docs may be read only after the task explicitly needs them. Before an
agent uses one as current truth, it must confirm the related source files and
either promote it here or cite it as historical evidence.

| Path | Status | Notes |
|---|---|---|
| `docs/essay-scoring-handoff.md` | candidate-active | AI essay scoring and grading context; verify current code and data before use |
| `docs/scan-calibration-handoff.md` | candidate-active | OMR calibration context; verify DB/templates/files before use |
| `docs/archive/plans/2026-06-10-db-migration-design.md` | candidate-active | DB migration design; live DB/service state must be reverified before execution |
| `docs/archive/plans/2026-06-10-runtime-foundation-recovery.md` | candidate-active | Runtime recovery investigation; volatile runtime facts are historical snapshots |

## Reference

Reference docs can explain background, but they do not override `AGENTS.md`,
this index, source code, tests, CI, or current user instruction.

| Path | Status | Notes |
|---|---|---|
| `docs/governance/foundation-boundaries.md` | reference | Long-term module boundary direction |
| `docs/governance/debt-ledger.md` | reference | Historical and current debt ledger; verify facts before acting |
| `docs/reviews/2026-06-22-portal-c3-online-verification.md` | reference | Portal online verification evidence |
| `docs/reviews/2026-06-22-portal-d08d-runtime-closeout.md` | reference | Portal runtime closeout evidence |
| `docs/reviews/2026-06-22-rh1-worker-runtime-fingerprint-closeout.md` | reference | Worker freshness evidence |
| `docs/reviews/2026-06-22-rh3-frontend-gating-regression-closeout.md` | reference | Frontend gating regression evidence |
| `.github/workflows/test.yml` | reference | Main CI workflow |
| `.github/workflows/steward-hard-gates.yml` | reference | Keel hard-gate workflow |
| `.github/workflows/doc-stale-sweep.yml` | reference | Scheduled Tier A active-doc stale issue workflow |

## Historical

- `docs/context/META_RUNTIME.md` and `docs/context/GUARDIAN_RUNTIME.md` are
  historical runtime-contract documents. Do not load them as current Keel
  requirements unless a current scope explicitly names them.
- `scripts/meta-check` and `scripts/guardian-watch` are historical/advisory
  local runtime tools. They are not GitHub merge authority and are not default
  startup commands.
- Removed `docs/archive/plans/archived/**` material is historical evidence only; use git
  history when explicit evidence is needed.
- Removed `docs/superpowers/**` material is historical evidence only.
- Old Windows-era handoffs, old review logs, and Yuanqi task-contract references
  are not current instructions.
- If a task cites an old plan or handoff, first add it here with status
  `candidate-active` or `reference`, including why it is safe to read.
