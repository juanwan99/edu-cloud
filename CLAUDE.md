---
title: Claude Entry
owner: liang
last_review_date: "2026-06-28"
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

## Retired Material

The old Yuanqi task-contract layer, superpowers plans/specs, archived plan tree,
and gate JSON files are no longer active working material.

Historical facts may be recovered from git history when explicitly needed, but
deleted historical documents must not be treated as current instructions.

## Working Rule

Read current source files and current indexed docs before acting. Do not revive
retired paths, old Windows-era handoffs, or deleted planning systems as active
policy.
