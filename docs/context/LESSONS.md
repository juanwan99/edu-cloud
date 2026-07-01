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
| L017: model reviews can drift to local-optimum fixes | Externalize the user intent, oracle, and active assets before asking Claude or GPT to review. | `ACTIVE_INDEX.md`, current scope, and final evidence define the review target; `scripts/codex-consult-claude` remains advisory and read-only. |
| L018: ECS is the only authority | Do not use Windows paths, Windows-era test numbers, or old handoff timelines as current facts. | `AGENTS.md`, `ACTIVE_INDEX.md`; old docs remain historical unless indexed active. |
| L019: repeated fix loops happen when task truth is not live | Keep the current user request, scope, and failing evidence visible during execution; stop and re-anchor after repeated failed fixes. | Final evidence must explain root cause after repeated fixes and cite the current verifier output. |
| L020: concurrent writes can lose updates | Central context files are owned by the main session; do not have parallel workers edit them. Code parallelism requires explicit mode, worktree, scope, and integration owner. | `docs/context/PARALLEL_DEVELOPMENT.md`; for Codex migration, write `AGENTS.md` and `docs/context/**` from one session only. |
| L021: dirty working tree build is a production accident | Do not build production frontend from dirty frontend inputs. | `scripts/codex-verify frontend` refuses dirty frontend inputs by default. |
| L022: multi-step instruction loss and role drift need a hard carrier | Decompose complex user instructions into explicit obligations before execution and after context compaction. | `AGENTS.md`, `ACTIVE_INDEX.md`, the active Keel scope, and the final evidence summary carry obligations. |
| L023: draft PRs are writes, not harmless notes | Draft status prevents accidental merge, but branch/commit/push/PR-body/comment activity still consumes CI, creates queue pressure, and can feel like autonomous execution. | Parallel implementation requires an explicit write license after Dispatch Review; red CI stops workers unless self-fix is explicitly licensed. |
| Migration safety | Do not bypass `scripts/db_migrate`. | `alembic/env.py` guard plus `scripts/codex-verify schema`. |
| Completion truth gate | Do not claim complete without fresh command evidence. | `scripts/codex-verify` is the completion evidence path. |

## Non-Migrated Claude Mechanics

These are intentionally not part of the Codex-native daily workflow:

- Claude session lifecycle.
- Claude compact recovery.
- Claude agent role hierarchy.
- Claude hook runtime governance and L0 manifest signing.
- Historical Windows-era baseline reconciliation.
