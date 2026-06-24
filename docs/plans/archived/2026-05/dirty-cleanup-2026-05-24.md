# Dirty Artifact Cleanup - 2026-05-24

Backup before cleanup: `/home/ops/backups/edu-cloud/dirty-cleanup/20260524T124228Z/dirty-artifacts.tar.gz`

Decisions:

- `pyproject.toml` / `uv.lock`: keep and commit. Current tracked AI engine imports `pydantic_ai`; the dependency declaration was missing from HEAD.
- `src/editor_layouts/66d695f2-b9a6-4557-9f72-665c5c9f5e97_be86745a-67e4-4077-9132-409599350b54.json`: keep and commit. It is CardEditor business data for Jingyan school / Chinese subject and matches the existing `editor_layouts/<school_id>_<subject_id>.json` storage contract.
- `.claude/**`: local Claude/Codex runtime state. Backed up, removed from the worktree, and ignored.
- `legacy receipt log`: local review receipt/waiver state. Backed up, removed, and ignored.
- Historical agent/exam-import plan drafts: archived under `docs/plans/archived/2026-05/` rather than left as active-looking untracked docs.
- `docs/scan-calibration-handoff.md`, `scripts/calibrate_scan.py`, `scripts/calibrate_universal.py`, `scripts/bench_llm_concurrency.py`: kept as intentional operational/calibration references.
- `scripts/calibrate_bio_geo.py`: superseded by `calibrate_universal.py`; archived under `scripts/archived/2026-05-24-scan-calibration/`.

Do not use `git clean` for future cleanup. Classify first, back up, then either commit, archive, or ignore.
