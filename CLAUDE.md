---
title: Claude Entry
owner: liang
last_review_date: "2026-06-29"
expiration_in_days: 30
---

# Claude Entry

Use `AGENTS.md` as the active project entrypoint.

Before reading project docs, use `docs/context/ACTIVE_INDEX.md` as the canonical
document index. Do not discover active instructions by scanning historical
plans, retired handoffs, or deleted governance systems.

## Current Governance

edu-cloud uses Keel:

1. One git worktree per parallel task.
2. One new scope file under `control/steward/scopes/` per governed PR.
3. `Steward-Scope: <scope_id>` in the PR body.
4. GitHub required checks, CODEOWNERS, and human review decide merge readiness.

Before starting multi-worker, deletion/retirement, governance, central-context,
or protected-path work, request Codex Dispatch Review. Do not split or launch
mutating workers until that review defines task order, scope ids, allowed paths,
forbidden paths, and verification commands.

When a governed PR is opened, include both `Steward-Scope: <scope_id>` and
`Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>`. Claude/worker sessions
must not invent CDR evidence or self-attest that Codex review happened.

GitHub enforces this through `steward/dispatch-review`: governed PRs must use a
fresh `keel/` branch based on latest `origin/master`, include non-placeholder
CDR evidence, and include a completed Dispatch Review checklist.

## Retired Material

The old Yuanqi task-contract layer, superpowers plans/specs, archived plan tree,
and gate JSON files are no longer active working material.

Historical facts may be recovered from git history when explicitly needed, but
deleted historical documents must not be treated as current instructions.

## Working Rule

Read current source files and current indexed docs before acting. Do not revive
retired paths, old Windows-era handoffs, or deleted planning systems as active
policy.

Do not open a PR with `Steward-Scope: REQUIRED`; replace it with the exact active
scope id. Do not open a PR with `Codex-Dispatch-Review: REQUIRED`; replace it
with review evidence issued before implementation. Include the matching fresh
scope file in the PR diff.
