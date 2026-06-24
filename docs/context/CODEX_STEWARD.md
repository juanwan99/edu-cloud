# Codex Stewardship

Date: 2026-06-12 (revised per Q1 ruling,
`docs/reviews/2026-06-12-w1-governance-acceptance.md`; original 2026-06-11
steward definition in `d981e52` is superseded)
Purpose: stable planning memory for how Codex leads edu-cloud.

## Authority

- Codex/Yuance（元策）is the project steward at the **planning, review, and
  acceptance layer**: it owns current facts, strategic direction, evidence
  gathering, root-cause diagnosis, scope freeze, contract drafting (Planner
  Contract / V2 Task Contract / Executor Packet), range review, and acceptance
  of completion evidence. Codex is **not** the default code-writing channel.
- **Claude Code is the executor**: all write operations (code and docs) are
  executed by Claude Code, and only inside a Yuanqi task window with an active
  Yuanqi Yuanqi task contract. The Yuanqi/GitHub-native gate machine-guards the write boundary,
  evidence coverage, and closeout; it does not judge plan quality.
- Completion claims are accepted by Codex/the user from the executor's
  Completion Return Packet; the executor does not self-declare completion.
- `AGENTS.md` is the active Codex entrypoint.
- `docs/context/ACTIVE_INDEX.md` controls which historical docs may be treated
  as active or candidate-active.
- `scripts/codex-consult-claude` remains available as an **optional read-only
  auxiliary review path** (Codex-invoked reviewer: critique only, no writes,
  no commands, no completion claims). It is distinct from — and must not be
  conflated with — the governed Claude Code execution channel above.
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
6. For mutating work, draft the V2 Task Contract + Executor Packet and
   dispatch a governed Claude Code window (Yuanqi task contract + contract) instead of
   editing directly.
7. Accept or reject the executor's Completion Return Packet against the
   contract's required evidence before declaring the task complete.
