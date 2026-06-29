---
title: Safety Matrix
owner: liang
last_review_date: "2026-06-29"
expiration_in_days: 30
---

# Safety Matrix

Each row maps an active risk to current Keel enforcement. Historical Meta
Runtime and Guardian Runtime references are not current hard gates.

| ID | Risk | Current Defense | Completion Evidence | Gap |
|---|---|---|---|---|
| S-001 | Governed PR changes files outside scope | `steward_scope_gate.py`, Conftest, PR `Steward-Scope` marker | GitHub required checks pass for exact PR | None for merge-gated paths |
| S-002 | AI silently weakens governance gates | Semgrep governance rules, CODEOWNERS, required checks | `steward-hard-gates` and `semgrep` pass; CODEOWNER approval | Requires human review of intentional policy changes |
| S-003 | Dirty or audit-red frontend ships | `scripts/codex-verify frontend`, CI frontend job | Frontend gate output; GitHub Tests run | CI does not prove live `https://mcu.asia`; live evidence is task-dependent |
| S-004 | Source/build/nginx/backend drift | `scripts/truth-status.sh`, `scripts/codex-verify frontend` | Truthline output when runtime evidence is required | Runtime checks are local/task evidence, not universal CI gates |
| S-005 | Direct Alembic mutation | `scripts/db_migrate`, safety scan, DB doctor | `scripts/codex-verify schema` when schema is touched | None for scoped DB work if verifier is run |
| S-006 | Active SQLite copy | AGENTS hard ban, artifact policy, safety scan | `scripts/codex-verify safety --repo-wide` | Scan covers shell-level copies, not arbitrary external tools |
| S-007 | Secret leakage | `.gitignore`, Gitleaks, safety scan | Gitleaks required check; safety scan output | Historical leaked secrets require rotation, not just tree cleanup |
| S-008 | Destructive git cleanup | AGENTS hard ban, safety scan | Safety scan has no destructive command hits; user approval for real cleanup | Human discipline still required for manual shell commands |
| S-009 | Retired Yuanqi/Claude hook returns as active policy | Legacy quarantine check, ACTIVE_INDEX, AGENTS | CI governance job runs quarantine; active docs do not point to retired paths | Historical docs may mention old systems as evidence |
| S-010 | Historical docs pollute current work | `ACTIVE_INDEX.md`, doc frontmatter gate, stale sweep | Active docs are indexed and non-stale | Candidate/reference docs still require human judgment |
| S-011 | Completion without evidence | `scripts/codex-verify`, CI, CODEOWNER review | Final answer cites commands/results; GitHub checks pass | Codex has no automatic stop hook |
| S-012 | Artifact noise or backups tracked | `ARTIFACT_POLICY.md`, `.gitignore`, hygiene review | `git status` clean except intended files | Periodic cleanup still useful |
| S-013 | Parallel work conflicts | Separate worktrees, fresh scope per PR, allowed paths | Distinct branches/scopes; no overlapping changed protected files | Human scheduling still needed for same module edits |
| S-014 | Process/port collisions in local dev | Docker Compose project-name/port isolation; manual process checks when runtime is touched | Task-specific runtime evidence and cleanup command | No always-on local process registry by design |
| S-015 | Multi-step instruction loss or compaction drift | AGENTS, ACTIVE_INDEX, current user instruction, scoped PRs | Work summary maps changes to the current request and scope | No model memory is authority |
| S-016 | Independent review optimizes the wrong problem | Read-only Claude auxiliary protocol, GitHub PR review, human approval | Review comments or user approval tied to the same PR/scope | External model review remains advisory |
| S-017 | Push accepted while GitHub Actions is red or pending | `scripts/codex-verify github-ci --wait`; GitHub required checks | CI run bound to current HEAD is success | Private branch protection limitations remain outside local repo |
| S-018 | Document lifecycle decays | Active frontmatter, ACTIVE_INDEX, `doc-stale-sweep.yml` scheduled issue | Doc stale sweep issue absent/closed; active docs have review metadata | Deterministic stale checks do not judge semantic correctness |

## Enforcement Strength

- Hard GitHub gate: required check or CODEOWNER review blocks merge.
- Hard local verifier: command exits non-zero and blocks completion claims.
- Advisory local verifier: command reports risk for human judgment.
- Documentation rule: active instruction, enforced by review and hygiene checks.

## Historical Issue Codes

Older documents may mention Meta/Guardian issue codes such as `BUILD_DRIFT`,
`BACKEND_DRIFT`, `META_RUNTIME_UNREGISTERED`, or `TASK_CONTRACT_DRIFT`. Treat
them as historical labels unless a current Keel scope explicitly reactivates the
specific tool that emits them.
