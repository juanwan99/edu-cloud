---
title: NOW
owner: liang
last_review_date: "2026-06-30"
expiration_in_days: 7
---

# NOW

Last refreshed: 2026-06-30 21:05 Asia/Shanghai

## Current Goal

Use `docs/context/REQUIREMENTS_BASELINE.md` as the current requirements and task
baseline. Old session reports and old plan documents are historical evidence
only unless `ACTIVE_INDEX.md` or the baseline promotes them.

## Fresh State

- Current master: `c6e8d8f4f710d84409952f68e1ff3a544a57bac0`.
- Current open PRs: none.
- Recent merged work: #71/#73 OCR review-needed fail-visible hardening,
  #75 grading details-count fail-closed, #77 token revocation explicit-env
  fail-closed, #79 AI chat persistence warning localization, #81 independent
  review evidence hardening, and #82 scope closeout.
- Latest master GitHub run `28445858249` is green.
- Module dependency gate is clean: `0 edges, 0 cycles`.
- Keel scope registry is closed: 34 closed scopes, 0 active scopes.

## Next Work Queue

1. Fix CRITICAL silent degradation in AI `DataScopeBuilder` failure handling:
   never fall back to a wider AI tool scope when class/grade visibility cannot
   be built.
2. Fix HIGH AI daily-limit fail-open behavior: quota storage/check failures
   must become visible and conservative.
3. Fix HIGH grading LLM slot lookup fallback: DB lookup exceptions must not
   silently use `.env`/default grading credentials.
4. Investigate and then fix HIGH scan identity fallback: barcode failure or
   unmatched student identity must not silently write official `StudentAnswer`
   rows.
5. Refresh active-doc hygiene as needed; do not let stale plan facts become task
   baselines.
6. Keep module decoupling as a guardrail, not a broad refactor, until a concrete
   product task exposes a boundary problem.

## Keel Baseline

Current governed PR flow:

1. create one task branch/worktree;
2. add one fresh scope file under `control/steward/scopes/`;
3. change only paths allowed by that scope;
4. include `Steward-Scope: <scope_id>` and real dispatch-review evidence in the
   PR body;
5. let GitHub required checks, CODEOWNERS, and human review decide merge.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create `.yuanqi/tasks`, `Yuanqi-Task:` PR markers, Yuanqi task windows, or
Yuanqi registry/scope/overlap gates for current work.

## Live Verification Commands

Use live commands for volatile facts. Do not trust old timestamps in historical
handoffs.

```bash
git status --short --branch
git rev-parse HEAD
gh pr list --repo juanwan99/edu-cloud --state open
gh run list --repo juanwan99/edu-cloud --branch master --limit 5
python scripts/governance/check_module_dependencies.py --check
```

Runtime, ECS services, DB state, and public URL facts were not reverified in
this baseline pass. Recheck them with project runtime commands before any
runtime, deploy, migration, or production claim.
