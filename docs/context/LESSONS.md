---
title: Migrated Lessons
owner: liang
last_review_date: "2026-06-28"
expiration_in_days: 30
---

# Migrated Lessons

Project-specific lessons migrated from the Claude system. This file records only lessons that affect current Codex behavior.

| Lesson | Rule | Codex Enforcement |
|---|---|---|
| L013: correct code is not equal to user-visible delivery | Verify source -> build -> nginx -> browser before frontend completion. | `scripts/codex-verify frontend`, `scripts/truth-status.sh`, `https://mcu.asia/version.json` |
| L015: visual and offline evaluation tasks cannot be fully autonomous | Use small batches and user-visible evidence for visual/AI grading changes. | `ACTIVE_INDEX.md` must mark active handoffs; completion notes must list covered and not-covered paths. |
| L016: active SQLite copy caused data loss | Never copy active SQLite DB with `cp` or `rsync`; use SQLite backup or `scripts/db_migrate`. | `SAFETY_MATRIX.md`, `ARTIFACT_POLICY.md`, future CI grep for dangerous DB copy commands. |
| L017: model reviews can drift to local-optimum fixes | Externalize the user intent, oracle, and active assets before asking Claude or GPT to review. | `scripts/meta-check` extracts review/evidence obligations; `scripts/codex-consult-claude` remains advisory and read-only. |
| L018: ECS is the only authority | Do not use Windows paths, Windows-era test numbers, or old handoff timelines as current facts. | `AGENTS.md`, `ACTIVE_INDEX.md`; old docs remain historical unless indexed active. |
| L019: repeated fix loops happen when task truth is not live | Keep a live task contract during execution; stop and re-anchor after repeated failed fixes. | `scripts/meta-check --task ... --write-state`; final evidence must explain root cause after repeated fixes. |
| L020: concurrent writes can lose updates | Central context files are owned by the main session; do not have parallel workers edit them. Code parallelism requires explicit mode, worktree, scope, and integration owner. | `docs/context/PARALLEL_DEVELOPMENT.md`; for Codex migration, write `AGENTS.md` and `docs/context/**` from one session only. |
| L021: dirty working tree build is a production accident | Do not build production frontend from dirty frontend inputs. | `scripts/codex-verify frontend` refuses dirty frontend inputs by default. |
| L022: multi-step instruction loss and role drift need a hard carrier | Decompose complex user instructions into explicit obligations before execution and after context compaction. | `scripts/meta-check` emits `task_contract.obligations`; `scripts/codex-context` exposes the latest Meta runtime state. |
| Migration safety | Do not bypass `scripts/db_migrate`. | `alembic/env.py` guard plus `scripts/codex-verify schema`. |
| Completion truth gate | Do not claim complete without fresh command evidence. | `scripts/codex-verify` is the completion evidence path. |

## Non-Migrated Claude Mechanics

These are intentionally not part of the Codex-native daily workflow:

- Claude session lifecycle.
- Claude compact recovery.
- Claude agent role hierarchy.
- Claude hook runtime governance and L0 manifest signing.
- Historical Windows-era baseline reconciliation.
