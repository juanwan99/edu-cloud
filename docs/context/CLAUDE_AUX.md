# Claude Auxiliary Model

This file covers **only** the optional read-only auxiliary review path
(`scripts/codex-consult-claude`): Claude as a Codex-invoked reviewer with full
repository read access and no write or command execution authority.

It does **not** cover governed execution. Per the Q1 ruling
(`docs/reviews/2026-06-12-w1-governance-acceptance.md`), Claude Code is the
project's executor for write operations — but only inside a Yuanqi task window
with an active Yuanqi task contract, where the Yuanqi/GitHub-native gate machine-guards the
write scope, evidence, and closeout. That execution channel and this read-only
auxiliary channel are two different paths; do not conflate them.

## Authority

- Codex/Yuance is the orchestrator at the planning/review/acceptance layer;
  it accepts or rejects findings and completion evidence.
- Write operations belong to the governed Claude Code execution channel
  (active Yuanqi task contract), not to this auxiliary path.
- Claude output in this auxiliary channel is advisory until Codex verifies it.
- Completion claims are accepted by Codex/the user, never declared by Claude.
- `AGENTS.md` is authoritative.
- `docs/context/NOW.md` is the current fact source.
- `docs/context/ACTIVE_INDEX.md` controls whether historical docs are active.
- `CLAUDE.md` is historical/deep reference, not the active entrypoint.

## Entry Point

Use:

```bash
scripts/codex-consult-claude <mode> "<task>"
```

Available modes:

- `review`: implementation, architecture, and governance review.
- `design`: design critique and alternative analysis.
- `history`: historical docs triage.
- `tests`: missing test and regression coverage review.
- `risk`: safety, migration, data, secret, and delivery risk review.
- `question`: repository-aware read-only question answering.

Useful maintenance commands:

```bash
scripts/codex-consult-claude --auth-status
scripts/codex-consult-claude --dry-run review "check the Claude auxiliary wrapper"
scripts/codex-consult-claude --print-system-prompt
```

## Fixed Runtime Boundary

The wrapper invokes Claude with:

```bash
claude -p \
  --no-session-persistence \
  --permission-mode plan \
  --tools Read,Grep,Glob,LS \
  --disallowedTools Bash,Edit,Write,MultiEdit,NotebookEdit \
  --add-dir /home/ops/projects/edu-cloud
```

The wrapper runs Claude from `/tmp/codex-claude-consult`, not the repo root. This reduces accidental activation of historical Claude project state while still granting repository read access through `--add-dir`.

## Claude May (in this auxiliary channel)

- Read `AGENTS.md`, `docs/context/**`, source, tests, and docs.
- Grep, glob, and list files.
- Produce findings, risks, alternatives, and missing-test suggestions.
- Ask Codex for command output when needed.

## Claude Must Not (in this auxiliary channel)

- Edit files.
- Write files.
- Run Bash.
- Run git, migration, database, frontend, backend, or deployment commands.
- Declare completion.
- Treat `CLAUDE.md` as the active project entrypoint.
- Update `docs/context/**` directly.

(Write work belongs to the separate governed execution channel: a Claude Code
window opened via Yuanqi task contract with an active Yuanqi task contract.)

## Codex Must

- Decide whether to accept Claude findings.
- Route accepted code or doc changes into a governed Claude Code execution
  window (active Yuanqi task contract) instead of editing directly.
- Define the contract's required evidence and verify the executor's
  Completion Return Packet against it.
- Ensure `NOW.md` and `ACTIVE_INDEX.md` updates are scheduled (via a governed
  window) when facts change.
- Include command evidence in completion acceptance.

## When To Consult Claude

Use Claude when the second model materially reduces risk:

- Major implementation or governance changes.
- Risky migration, data, secret, or delivery logic.
- Large historical handoff triage.
- AI grading prompt/rubric stability review.
- Missing-test analysis for broad changes.

Do not consult Claude for small edits, routine command output, or final completion claims.
