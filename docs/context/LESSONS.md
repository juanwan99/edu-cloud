# Migrated Lessons

Project-specific lessons migrated from the Claude system. This file records only lessons that affect current Codex behavior.

| Lesson | Rule | Codex Enforcement |
|---|---|---|
| L013: correct code is not equal to user-visible delivery | Verify source -> build -> nginx -> browser before frontend completion. | `scripts/codex-verify frontend`, `scripts/truth-status.sh`, `https://mcu.asia/version.json` |
| L015: visual and offline evaluation tasks cannot be fully autonomous | Use small batches and user-visible evidence for visual/AI grading changes. | `ACTIVE_INDEX.md` must mark active handoffs; completion notes must list covered and not-covered paths. |
| L016: active SQLite copy caused data loss | Never copy active SQLite DB with `cp` or `rsync`; use SQLite backup or `scripts/db_migrate`. | `SAFETY_MATRIX.md`, `ARTIFACT_POLICY.md`, future CI grep for dangerous DB copy commands. |
| L018: ECS is the only authority | Do not use Windows paths, Windows-era test numbers, or old handoff timelines as current facts. | `AGENTS.md`, `ACTIVE_INDEX.md`; old docs remain historical unless indexed active. |
| L020: concurrent writes can lose updates | Central context files are owned by the main session; do not have parallel workers edit them. | For Codex migration, write `AGENTS.md` and `docs/context/**` from one session only. |
| L021: dirty working tree build is a production accident | Do not build production frontend from dirty frontend inputs. | `scripts/codex-verify frontend` refuses dirty frontend inputs by default. |
| Migration safety | Do not bypass `scripts/db_migrate`. | `alembic/env.py` guard plus `scripts/codex-verify schema`. |
| Completion truth gate | Do not claim complete without fresh command evidence. | `scripts/codex-verify` is the completion evidence path. |

## Non-Migrated Claude Mechanics

These are intentionally not part of the Codex-native daily workflow:

- Claude session lifecycle.
- Claude compact recovery.
- Claude agent role hierarchy.
- Claude hook runtime governance and L0 manifest signing.
- Historical Windows-era baseline reconciliation.
