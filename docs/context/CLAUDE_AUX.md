# Claude Auxiliary Model

Claude Code may be used as a Codex-invoked auxiliary model with full repository read access and no write or command execution authority.

## Authority

- Codex is the orchestrator, editor, verifier, and source of completion claims.
- Claude output is advisory until Codex verifies it.
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

## Claude May

- Read `AGENTS.md`, `docs/context/**`, source, tests, and docs.
- Grep, glob, and list files.
- Produce findings, risks, alternatives, and missing-test suggestions.
- Ask Codex for command output when needed.

## Claude Must Not

- Edit files.
- Write files.
- Run Bash.
- Run git, migration, database, frontend, backend, or deployment commands.
- Declare completion.
- Treat `CLAUDE.md` as the active project entrypoint.
- Update `docs/context/**` directly.

## Codex Must

- Decide whether to accept Claude findings.
- Apply any code or doc changes itself.
- Run verification commands itself.
- Update `NOW.md` and `ACTIVE_INDEX.md` when facts change.
- Include command evidence in completion claims.

## When To Consult Claude

Use Claude when the second model materially reduces risk:

- Major implementation or governance changes.
- Risky migration, data, secret, or delivery logic.
- Large historical handoff triage.
- AI grading prompt/rubric stability review.
- Missing-test analysis for broad changes.

Do not consult Claude for small edits, routine command output, or final completion claims.
