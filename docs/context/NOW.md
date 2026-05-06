# NOW

Last refreshed: 2026-05-06 21:03 Asia/Shanghai

Command used:

```bash
scripts/codex-context --no-network
scripts/truth-status.sh /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q
scripts/codex-verify safety
scripts/truth doctor --json
```

## Current Facts

- Branch: `master`
- Upstream: `origin/master`
- HEAD: `9646269`
- Ahead: 7 commits
- Git status entries: 92 after Guardian doctor JSON and context integration
- Frontend dist hash: `0e97e5c`
- Frontend dist source_dirty: `false`
- Frontend dist build time: `2026-05-06T05:23:28.419Z`
- Backend `/api/v1/version`: `9646269`, pid `2108103`
- Known pytest baseline entries: 27 in `.quality/known-pytest-failures.txt`
- DB doctor: ok, alembic `ed1f8408241c`, hard=0, warn=0

## Dirty State

Current tracked `src/` dirty area is AI grading. `truth-status` reports 14 tracked backend dirty files:

- `src/edu_cloud/modules/grading/detail_flatten.py`
- `src/edu_cloud/modules/grading/equivalence_guard.py`
- `src/edu_cloud/modules/grading/ocr_validator.py`
- `src/edu_cloud/modules/grading/prompts/base.py`
- `src/edu_cloud/modules/grading/prompts/biology.py`
- `src/edu_cloud/modules/grading/prompts/chemistry.py`
- `src/edu_cloud/modules/grading/prompts/chinese.py`
- `src/edu_cloud/modules/grading/prompts/english.py`
- `src/edu_cloud/modules/grading/prompts/geography.py`
- `src/edu_cloud/modules/grading/prompts/history.py`
- `src/edu_cloud/modules/grading/prompts/math.py`
- `src/edu_cloud/modules/grading/prompts/physics.py`
- `src/edu_cloud/modules/grading/prompts/politics.py`
- `src/edu_cloud/modules/grading/rubric_formatter.py`

Additional untracked `src/` item. `scripts/codex-context --no-network` counts this as backend dirty, so its backend dirty count is 15:

- `src/edu_cloud/data/import_jingyan_yuwen.py`

Frontend build input dirty:

- `frontend/src/pages/ai-grading/QuestionList.vue`

Other notable local artifacts:

- `test_output/tql_yuwen_a3.pdf`
- `edu_cloud.db-wal`
- `edu_cloud.db-shm`
- `data/.db_migrate.lock`
- `.codex`
- `frontend/.codex`
- `backups/**`
- `screenshots/**`
- `data/essay_*.json`
- `scripts/essay_*.py`

## Truthline

`scripts/truth-status.sh /home/ops/projects/edu-cloud` reports:

- exit code `1`
- frontend build inputs dirty
- `frontend/dist` is built from `0e97e5c`, while current source is `9646269`
- `https://mcu.asia/` returns 200
- nginx serves `version.json` git_hash `0e97e5c`
- backend git hash matches source hash `9646269`
- diagnosis: broken at source because backend has uncommitted changes

## Doctor Risks

`scripts/truth doctor --json` reports:

- overall: `red`
- issue_count: 5
- red: `PORT_DANGER` because port 8080 Vite dev server is bound to `0.0.0.0`
- yellow: two `GHOST_PROCESS` issues
- yellow: `SERVICE_BYPASS` because `edu-cloud.service` is inactive while uvicorn `:9000` is running manually
- yellow: `CLAUDE_SESSION_RISK` because 9 Claude processes are active
- DB schema aligned

## Codex Migration State

Codex-native migration layer is now present in the working tree:

- `AGENTS.md`: active Codex entrypoint.
- `docs/context/GOVERNANCE_MODEL.md`: EduCloud Dual-Core Control Plane model.
- `docs/context/**`: current facts, commands, lessons, safety matrix, active index, artifact policy.
- `scripts/codex-context`: current project summary.
- `scripts/codex-check`: read-only start-of-work preflight.
- `scripts/codex-consult-claude`: read-only Claude Code auxiliary reviewer wrapper.
- `scripts/codex-verify`: completion verification wrapper with `safety`, `frontend`, `backend`, `schema`, and `full` modes.
- `scripts/truth-status.sh`: exits non-zero on `BROKEN AT` diagnosis.
- `scripts/truth doctor --json`: emits `guardian.doctor.v1` issue/action data.
- `scripts/codex-context`: consumes Guardian doctor JSON and prints Guardian Health.
- `scripts/codex-verify frontend`: includes local/remote `version.json` alignment checks.
- `docs/context/CLAUDE_AUX.md`: fixed protocol for Claude as full-repo read-only auxiliary model.
- Claude Code auth: verified via `scripts/codex-consult-claude --auth-status` with a Claude.ai Max subscription. Do not commit credentials or tokens.
- `.github/workflows/test.yml`: lightweight governance job for Codex script smoke tests and safety dry-runs; backend/frontend jobs now include Alembic smoke and frontend build.
- `CLAUDE.md`: preserved as historical/deep reference and no longer the active entrypoint.

These files are not committed yet. Review them as the Codex governance migration change set, separate from the existing AI grading dirty work.

## Dual-Core State

- Meta Core is documented in `docs/context/GOVERNANCE_MODEL.md` and surfaced by `scripts/codex-context`.
- Guardian Core now has hard gates for truthline diagnosis exit code and frontend version alignment.
- `docs/context/SAFETY_MATRIX.md` has stable rule IDs `S-001` through `S-013`.
- Remaining Guardian hardening candidates: repo-wide secret scan and optional event/fix-loop counters.

## Do Not Do

- Do not clean untracked files yet.
- Do not overwrite the AI grading dirty source changes.
- Do not run direct Alembic migration commands.
- Do not copy active SQLite DB files.
- Do not use old Windows-era docs as current facts.
