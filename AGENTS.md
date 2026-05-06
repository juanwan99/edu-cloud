# edu-cloud Codex Entry

This is the active Codex entrypoint. `CLAUDE.md` is historical/deep reference only.

edu-cloud uses **元守双核心**:

- **Meta Core / 元控核**: owns direction, facts, task boundaries, context,
  Claude read-only counter-review, and the completion evidence contract.
- **Guardian Core / 守护核**: owns dirty state, truthline, DB/migration gates,
  safety scanning, frontend/backend build-runtime consistency, and environment hygiene.

The model is Codex-led and Claude-assisted.

## Start Here

1. Run `scripts/codex-check`.
2. Read `docs/context/NOW.md`.
3. Read `docs/context/ACTIVE_INDEX.md` before using old plans or handoffs.
4. Do not clean, stash, overwrite, or revert dirty work unless the user explicitly asks.

## Project

- Root: `/home/ops/projects/edu-cloud`
- Knowledge base symlink: `edu-knowledge-base -> /home/ops/projects/edu-knowledge-base`
- Production URL: `https://mcu.asia`
- Backend API: `127.0.0.1:9000`
- Frontend source: `frontend/src/`
- Frontend production artifact: `frontend/dist/`

## Delivery Contract

- User-visible frontend evidence must come from `https://mcu.asia`, not `localhost`.
- Frontend source changes require `npm run lint`, `npm run build`, and `scripts/truth-status.sh`.
- `localhost:8080` and `localhost:5173` are debug-only.
- Backend completion requires pytest evidence: targeted pytest or `scripts/pytest_delta.py`.
- Schema work requires `scripts/db_migrate` and `scripts/db_doctor.py --strict`.
- Completion claims must include the exact verification command and result.

## Hard Bans

- Do not run `git reset --hard`, `git checkout -- .`, `git restore .`, `git clean -f`, or equivalent destructive cleanup without explicit user approval.
- Do not direct-run `alembic upgrade` or `alembic downgrade` on the project DB. Use `scripts/db_migrate`.
- Do not copy active SQLite databases with `cp` or `rsync`. Use SQLite backup APIs or `scripts/db_migrate`.
- Do not edit `.env` or `.secrets` unless the user explicitly asks.
- Do not commit real secrets, API keys, service-account JSON, WAL/SHM files, screenshots, or local backups.
- Do not use Windows-era baselines, paths, or historic handoff numbers as current facts.
- Do not treat historical `docs/plans/**` as active unless listed in `docs/context/ACTIVE_INDEX.md`.

## Verification Commands

```bash
scripts/codex-check
scripts/codex-context --no-network
scripts/codex-consult-claude --dry-run review "check read-only boundary"
scripts/codex-verify safety
scripts/codex-verify safety --repo-wide
scripts/codex-verify backend --dry-run
scripts/codex-verify frontend --dry-run
scripts/codex-verify schema --dry-run
```

Use real verification before completion:

```bash
scripts/codex-verify safety
scripts/codex-verify safety --repo-wide
scripts/codex-verify backend
scripts/codex-verify frontend
scripts/codex-verify full --schema
```

`scripts/codex-verify frontend` refuses dirty frontend build inputs unless `--allow-dirty-build` is passed. Dirty builds are debug evidence only, not completion evidence.

## Claude Auxiliary Model

Claude Code may be used only through `scripts/codex-consult-claude` as a Codex-invoked read-only auxiliary reviewer.

- Claude may read the full repository with `Read`, `Grep`, `Glob`, and `LS`.
- Claude must not write files, run Bash, run git, run migrations, run DB commands, or declare completion.
- Codex remains responsible for accepting/rejecting findings, editing files, running verification, and updating `docs/context/**`.
- See `docs/context/CLAUDE_AUX.md` for the fixed boundary.

## Current Context Files

- `docs/context/GOVERNANCE_MODEL.md`: 元守双核心 model.
- `docs/context/NOW.md`: current project facts and risks.
- `docs/context/COMMANDS.md`: authoritative commands.
- `docs/context/LESSONS.md`: project-specific lessons migrated from Claude.
- `docs/context/CLAUDE_AUX.md`: Claude read-only auxiliary model protocol.
- `docs/context/SAFETY_MATRIX.md`: rule source to script/CI enforcement map.
- `docs/context/ACTIVE_INDEX.md`: active vs historical document index.
- `docs/context/ARTIFACT_POLICY.md`: data, screenshot, backup, and scratch-script policy.
