# edu-cloud Codex Entry

This is the active Codex entrypoint. `CLAUDE.md` is historical/deep reference only.

edu-cloud uses **元契治理双核**:

- **Meta Core / 元控核**: owns direction, facts, task boundaries, context,
  Claude read-only counter-review, and the completion evidence contract.
  Its task-bound runtime is `scripts/meta-check`; the contract is documented in
  `docs/context/META_RUNTIME.md`.
- **Guardian Core / 守护核**: owns dirty state, truthline, DB/migration gates,
  safety scanning, frontend/backend build-runtime consistency, and environment hygiene.
  Its realtime runtime is `scripts/guardian-watch`, installed by
  `deploy/systemd/edu-cloud-guardian.service` when continuous monitoring is
  needed.

The working model is the Yuanqi governance division of roles (Q1 ruling 2026-06-12,
`docs/reviews/2026-06-12-w1-governance-acceptance.md`):

- **Codex/Yuance（元策）** plans, reviews, and accepts: evidence gathering,
  root-cause diagnosis, scope freeze, Planner Contract / V2 Task Contract /
  Executor Packet drafting, range review, and acceptance of completion
  evidence. Codex is **not** the default code-writing channel.
- **Claude Code** is the governed executor: it performs the write operations,
  but only inside a Yuanqi task window with an active Yuanqi task contract.
- **Yuanqi governance** guards execution boundaries, evidence coverage, and
  closeout. It does not judge plan quality.
- Completion claims are accepted by Codex/the user from the executor's
  Completion Return Packet; Claude Code does not declare completion on its own.

## Codex Stewardship

Codex is the project steward for edu-cloud at the planning, review, and
acceptance layer. Codex owns current facts, strategic direction, task
planning, contract drafting, range review, and acceptance of completion
evidence. Edits and other write operations are executed by Claude Code inside
active Yuanqi task contract windows; Codex does not edit by default. Claude may
additionally critique through the optional read-only auxiliary path
(`scripts/codex-consult-claude`), which is distinct from the governed
execution channel and does not make Claude the project authority.

Long-term architecture direction: keep edu-cloud on a modular-monolith path
that steadily increases safe parallel development. New work should reduce
direct cross-module coupling, expose behavior through module-owned APIs,
facades, or events where practical, and avoid new direct imports or cycles
unless an explicit governance note justifies the tradeoff.

See `docs/context/CODEX_STEWARD.md` and
`docs/governance/foundation-boundaries.md`.

For multiple Codex/Claude windows, read
`docs/context/PARALLEL_DEVELOPMENT.md` before launching or assigning work.

## Start Here

1. Run `scripts/codex-check`.
2. Run `scripts/meta-check --task "<current user task>" --write-state` for
   non-trivial tasks, especially tasks involving design, evidence, review, or
   multi-step delivery.
3. Read `docs/context/NOW.md`.
4. Read `docs/context/ACTIVE_INDEX.md` before using old plans or handoffs.
5. For multi-window or urgent parallel work, read
   `docs/context/PARALLEL_DEVELOPMENT.md`.
6. Do not clean, stash, overwrite, or revert dirty work unless the user explicitly asks.

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
- Backend completion requires pytest evidence: `scripts/codex-verify backend` (no targets → the single CI-aligned profile, mirrored by the `.github/workflows/test.yml` backend job and gated against `.quality/known-pytest-failures.txt`) or a targeted `scripts/pytest_delta.py` run. The known-failures file is the one source of truth; do not cite hard-coded pass/fail counts as the baseline.
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
scripts/meta-check --json --strict
scripts/codex-context --no-network
scripts/guardian-watch --once --no-network --no-model-review
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

## Claude Channels

Claude has two distinct channels. Do not conflate them:

1. **Governed execution（默认写通道）**: Claude Code executes write work inside
   a Yuanqi task window with an active Yuanqi task contract —
   `allowed_write_scope` / forbidden scope / evidence / closeout are
   machine-enforced by the Yuanqi/GitHub-native gate. The executor returns a Completion
   Return Packet; Codex/the user accepts or rejects it.
2. **Read-only auxiliary review（可选只读辅助审查）**:
   `scripts/codex-consult-claude` invokes Claude as a Codex-invoked read-only
   reviewer.
   - Claude may read the full repository with `Read`, `Grep`, `Glob`, and `LS`.
   - In this channel Claude must not write files, run Bash, run git, run
     migrations, run DB commands, or declare completion.
   - Codex remains responsible for accepting/rejecting findings.
   - See `docs/context/CLAUDE_AUX.md` for the fixed boundary.

## Current Context Files

- `docs/context/GOVERNANCE_MODEL.md`: 元契治理双核 model.
- `docs/context/CODEX_STEWARD.md`: Codex project stewardship and planning memory.
- `docs/context/PARALLEL_DEVELOPMENT.md`: safe parallel development policy.
- `docs/context/META_RUNTIME.md`: Meta Core task-contract runtime.
- `docs/context/GUARDIAN_RUNTIME.md`: Guardian Core realtime runtime contract.
- `docs/context/NOW.md`: current project facts and risks.
- `docs/context/COMMANDS.md`: authoritative commands.
- `docs/context/LESSONS.md`: project-specific lessons migrated from Claude.
- `docs/context/CLAUDE_AUX.md`: Claude read-only auxiliary model protocol.
- `docs/context/SAFETY_MATRIX.md`: rule source to script/CI enforcement map.
- `docs/context/ACTIVE_INDEX.md`: active vs historical document index.
- `docs/context/ARTIFACT_POLICY.md`: data, screenshot, backup, and scratch-script policy.
- `docs/governance/foundation-boundaries.md`: module boundary and coupling-reduction direction.
