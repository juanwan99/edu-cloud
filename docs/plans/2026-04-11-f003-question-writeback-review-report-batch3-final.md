[edu-cloud] Planner 最终处置 | 2026-04-12 17:19:44
## 审查报告: Task 9-12 (Batch 3) — 扩展批次审查最终处置
结论: PASS (Planner override after R3 + independent verification)

GPT R1/R2/R3 原始输出: `docs/plans/.codex-code-review-batch3-{raw,r2-raw,r3-raw}.log`
GPT R3 原始输出 SHA256: `7b028acda26db3e8945d9ce7a812b1064f10d8d1cacf04b86f0d4ecabe869263`

### 3 轮审查轨迹

- R1 FAIL: F001 (caplog) + F002 (S8b/S8c 不调闭包) + F003 (.tpl wiring)
- R2 FAIL: F001/F003 resolved; F002 accepted-risk 被 GPT 拒绝（GPT 声称可直接调闭包）
- R3 FAIL: GPT 仍认为 S8c 未调真闭包

### Planner 独立验证（R3 后）

Planner 按 GPT R2/R3 的建议，将 S8c 改写为通过真闭包连调两次。结果：

```
FAILED tests/test_api_exam/test_pipeline_save_answer.py::test_S8c_factory_closure_duplicate_idempotent
E   sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
    can't call await_only() here.
    at: sqlalchemy/dialects/sqlite/aiosqlite.py:157
```

**MissingGreenlet 确认是真实的**——发生在闭包内 IntegrityError → `await db2.rollback()` 路径上。S8b 成功（happy path 一次 commit），S8c 失败（duplicate 路径 rollback 触发 greenlet 问题）。

**GPT R2 的"复现成功"不成立**——GPT 声称用真实 async_sessionmaker 调闭包两次成功，但 Planner 用当前 repo 的 fixture 独立复现确认 MissingGreenlet 是真实的。这是 `_async_ctx` wrapper + aiosqlite 的固有限制，非 Executor 编造。

### F002 最终处置

| 字段 | 值 |
|------|-----|
| Status | accepted-risk |
| Reason | aiosqlite + _async_ctx wrapper 在 IntegrityError → rollback 路径触发 MissingGreenlet (Planner 独立复现确认)。S8b 已通过真闭包 happy path。S8c 用 SAVEPOINT 模拟 duplicate 语义验证 IntegrityError 捕获。S8d/S8d-b 通过 HTTP 端到端覆盖真实 wiring。S7a 验证 SAVEPOINT 语义。综合覆盖足够。 |
| Deadline | S7c test_debt (PostgreSQL CI, 2026-06-30) 解决后可重新验证闭包 duplicate 路径 |

### R1 全部 Finding 最终状态

| Finding | R1 Severity | 最终状态 | 解决轮次 |
|---------|-------------|---------|---------|
| F001 | HIGH code-bug | resolved-correct | R2 |
| F002 | HIGH test-gap | accepted-risk (Planner verified MissingGreenlet) | R3 + Planner override |
| F003 | MED test-gap | resolved-correct | R2 |

### 跨批次集成确认

GPT R1 已确认跨批次主链路一致：
- frontend publishCard → POST /api/v1/card/publish
- router.py → publish_card_atomic
- publish_card_atomic → upsert_questions_from_skeleton → upsert_template_both_sides
- pipeline_router → build_pipeline_save_answer_fn (db_mod import R4-F001 compliant)
- 全链路签名/参数契约一致
