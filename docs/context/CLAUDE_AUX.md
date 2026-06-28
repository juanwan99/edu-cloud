# Claude Auxiliary Model

This file covers the optional read-only Claude review path
(`scripts/codex-consult-claude`). It is advisory only.

## Boundary

- Claude auxiliary review may read the repository and produce findings.
- It must not edit files, run Bash, run git, run migrations, deploy, or declare
  completion.
- Accepted findings are implemented through normal Keel work: separate
  worktree when useful, fresh scope file, PR body `Steward-Scope: <scope_id>`,
  required checks, CODEOWNER review, and human approval.
- `AGENTS.md` is authoritative. `CLAUDE.md` is only a lightweight Claude entry
  shim and not a replacement for `AGENTS.md`.

The retired Yuanqi task-contract execution channel is historical. Do not route
new work through Yuanqi task windows or Yuanqi task markers.

## Entry Point

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

Maintenance commands:

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

The wrapper runs Claude from `/tmp/codex-claude-consult`, not the repo root.
That reduces accidental activation of historical Claude project state while
still granting repository read access through `--add-dir`.

## Codex Must

- Decide whether to accept Claude findings.
- Convert accepted work into a normal Keel-scoped PR.
- Verify the implementation with concrete evidence.
- Keep `NOW.md` and `ACTIVE_INDEX.md` current when facts change.
