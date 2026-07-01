---
title: NOW
owner: liang
last_review_date: "2026-07-01"
expiration_in_days: 7
---

# NOW

Last refreshed: 2026-07-01 11:26 Asia/Shanghai

## Current Goal

Use `docs/context/REQUIREMENTS_BASELINE.md` as the current requirements and task
baseline. Old session reports and old plan documents are historical evidence
only unless `ACTIVE_INDEX.md` or the baseline promotes them.

## Fresh State

- Current master: `227137c2aec5b779667176edc730de818bae751e`.
- Current open PRs: none.
- Recently closed stale PR: #83 was closed because its baseline was based on
  `c6e8d8f4` and was superseded by #84-#89.
- Recent merged work:
  - #92 made skipped workflow steps visible.
  - #91 refreshed active context after #90.
  - #90 refreshed the mainline baseline after #84-#89.
  - #89 clarified Keel steward/task window role boundaries.
  - #84 made grading LLM config lookup errors fail closed.
  - #85 made AI chat DataScope build failure fail closed.
  - #86 made scan persistence fail closed on unknown student identity.
  - #87 canonicalized adaptive mastery student identity.
  - #88 made answer-standardizer text-LLM fallback visible.
- Latest master `Tests` run for #92 merge commit is `in_progress`:
  run `28491163509`, head `227137c2aec5b779667176edc730de818bae751e`.
- Module dependency gate is clean: `0 edges, 0 cycles`.
- Current Keel scopes on `origin/master`: 34 closed, 9 active. This PR branch
  adds one active scope for its own review, so branch-local scope count is
  34 closed and 10 active until merge. Master active scope files:
  `keel-grading-llm-config-fail-closed-2026-06-30.yml`;
  `keel-ai-datascope-fail-closed-2026-06-30.yml`;
  `keel-scan-identity-fail-closed-2026-06-30.yml`;
  `keel-adaptive-canonical-student-identity-2026-06-30.yml`;
  `keel-answer-standardizer-fail-visible-2026-06-30.yml`;
  `keel-refresh-active-context-after-pr90-2026-07-01.yml`;
  `keel-refresh-mainline-baseline-2026-07-01.yml`;
  `keel-workflow-skipped-steps-visible-2026-07-01.yml`;
  `keel-window-role-boundary-2026-07-01.yml`.

## Next Work Queue

1. Close or retire the nine merged active Keel scopes in a separate scoped
   closeout PR if the team wants active-scope count back to zero.
2. Continue P1 silent-degradation work, but reverify each old candidate against
   current master before dispatch. Do not dispatch from stale baseline text.
3. Start the document lifecycle cleanup lane with a fresh scope: keep
   `ACTIVE_INDEX.md` small, update active-doc frontmatter, and avoid broad
   historical-doc deletion without CODEOWNER review.
4. Keep module decoupling as a guardrail, not a broad refactor, until a concrete
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
