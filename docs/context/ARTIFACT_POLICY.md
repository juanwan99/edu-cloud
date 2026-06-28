---
title: Artifact Policy
owner: liang
last_review_date: "2026-06-28"
expiration_in_days: 30
---

# Artifact Policy

This policy prevents experimental files from polluting current engineering decisions.

## Do Not Clean Blindly

The current workspace contains active source changes, experiments, backups,
screenshots, WAL/SHM files, and zero-byte Codex noise. Do not delete or move
them without explicit user approval. The user approved classification on
2026-05-06; current local experiment outputs are ignored rather than committed.

## Categories

| Category | Examples | Policy |
|---|---|---|
| Active source | `src/**`, `frontend/src/**`, `tests/**`, `docs/context/**` | Review and commit intentionally. Never discard blindly. |
| Experiment data | `data/essay_*.json`, `data/deepseek_*.json`, `scripts/essay_*.py` | Keep local and ignored unless a reviewed baseline task explicitly promotes it. |
| Local backup | `backups/**`, `*.db`, `*.db.bak*` | Do not commit. Keep local or archive outside repo after approval. |
| SQLite runtime | `*.db-wal`, `*.db-shm`, `data/.db_migrate.lock` | Do not commit. Ignore. Active WAL/SHM files are runtime state, not strict blockers. Do not copy active DB with `cp` or `rsync`. |
| Screenshots | `screenshots/**` | Commit only named verification screenshots required by a task. |
| Scratch patch scripts | `patch_*.py`, `convert_*.py` | Keep local and ignored unless reusable enough to promote into `scripts/`. |
| External symlink | `edu-knowledge-base` | Treat as external read-only context unless task explicitly targets it. |
| Empty Codex noise | `.codex`, `frontend/.codex` zero-byte files | Ignore or delete only after approval. |

## Initial Cleanup Order

1. Classify source changes first.
2. Confirm whether experiment data is a production baseline.
3. Add ignore rules for runtime noise.
4. Only then delete or archive disposable files.

## Recommended Ignore Additions

```gitignore
.codex
frontend/.codex
*.db-wal
*.db-shm
data/.db_migrate.lock
backups/
screenshots/
```

Do not add broad ignores for `docs/*.json` or `data/*.json` until the user decides which experiment results are baselines.

## Current Local Ignore Classification

These local AI grading artifacts are intentionally not versioned:

- `data/deepseek_*.json`
- `data/essay_*.json`
- `data/regrade_results.json`
- `docs/ai-grading-baseline*.json`
- `docs/anchor-essays*`
- `docs/anchor-samples.md`
- `scripts/deepseek_grading_eval.py`
- `scripts/essay_*.py`
- `patch_*.py`
- `convert_*.py`
- `src/edu_cloud/data/import_jingyan_yuwen.py`
