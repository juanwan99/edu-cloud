# Codex Stewardship

Date: 2026-06-11
Purpose: stable planning memory for how Codex leads edu-cloud.

## Authority

- Codex is the project steward: it owns current facts, strategic direction,
  task planning, edits, verification, and completion claims.
- `AGENTS.md` is the active Codex entrypoint.
- `docs/context/ACTIVE_INDEX.md` controls which historical docs may be treated
  as active or candidate-active.
- Claude Code is advisory only through `scripts/codex-consult-claude`; it may
  review and critique, but it does not write, run commands, or declare
  completion.
- `.codex/context/CODEX_CONTEXT.md` is local generated context, not shared
  project truth unless regenerated and cross-checked against active docs.

## Working Memory Contract

- Current facts live in `docs/context/NOW.md`.
- Governance model lives in `docs/context/GOVERNANCE_MODEL.md`.
- Parallel development policy lives in `docs/context/PARALLEL_DEVELOPMENT.md`.
- Long-term module-boundary direction lives in
  `docs/governance/foundation-boundaries.md`.
- Codex should not rely on ignored `.codex/` local state as the shared project
  memory. Durable project memory belongs in tracked `docs/context/**` and
  `docs/governance/**`.

## Strategic Direction

- Stabilize the foundation before broad feature expansion.
- Keep the system on a modular-monolith path while reducing historical coupling.
- Prefer module-owned APIs, service facades, domain events, or explicit
  contracts over direct imports into another module's internals.
- Treat existing cross-module edges and cycles as debt baseline, not precedent
  for new coupling.
- Portal, homepage, workbench, and service-center work should consume backend
  aggregation contracts instead of adding page-level business coupling.
- The end state is safer parallel development: independent task windows should
  be able to work by module or scope with minimal hidden side effects.
- Parallelism is a delivery tactic, not a license to bypass evidence. Use
  `docs/context/PARALLEL_DEVELOPMENT.md` to choose the allowed mode before
  launching extra windows.

## Planning Checklist

Before non-trivial edu-cloud work, Codex should:

1. Run `scripts/codex-check`.
2. Run `scripts/meta-check --task "<current user task>" --write-state`.
3. Read `docs/context/NOW.md` and `docs/context/ACTIVE_INDEX.md`.
4. Identify whether the task changes module boundaries or cross-module calls.
5. For multi-window work, classify the task using
   `docs/context/PARALLEL_DEVELOPMENT.md`.
6. State verification evidence before claiming completion.
