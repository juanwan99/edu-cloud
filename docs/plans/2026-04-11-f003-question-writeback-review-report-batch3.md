<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-12 16:46:24
## 审查报告: Task 9-12 (Batch 3) — 扩展批次审查 Round 1
结论: FAIL

GPT 原始输出: `docs/plans/.codex-code-review-batch3-raw.log`
GPT 原始输出 SHA256: `6a82bc68e7a8ed743824ef91d73d9d749b1740edbb522a979ff49fa53752f304`
GPT token 消耗: 266,193

### 第一段：测试充分性（Test Adequacy）

- V2/V2b (publishCard) 有效——恢复三步走后 fetch count 断言失败
- V3/V3b (ExamDetailPage) 有效——恢复 2-arg 后 callArgs[1] undefined
- S8d-a (DB Template wiring) 有效——tracked_factory + identity 断言
- **S8a caplog 失败**：`test_S8a_factory_orphan_logs_warning` 用 `caplog.set_level(logging.WARNING)` 但未绑定模块 logger，GPT 实跑 21 passed / 1 failed
- **S8b/S8c 不调闭包**：手工重建 region_map + 直接 db.add，未测试工厂闭包本身
- **S8d-b 缺失**：`.tpl` 分支 wiring 无测试覆盖

### 第二段：行为正确性（Behavioral Correctness）

**变更理解（GPT 描述）：** Batch 3 完成前端 publishCard 单次 POST 重写（T9）、ExamDetailPage 3-arg 签名 + data-testid（T10）、pipeline_router build_pipeline_save_answer_fn 工厂 + 统一装配（T11）、E2E 回归 + design.md 标记（T12）。

**对抗性审查：** GPT 确认跨批次主链路一致——前端 → router → publish_card_atomic → upsert_questions → upsert_template，R4-F001 compliance ok。pipeline_router L16 `import edu_cloud.database as db_mod` 确认。

### 第三段：未测试风险（Non-tested Risks）

- `.tpl` 分支漏调工厂 / 漏传 save_answer_fn 不会被发现（S8d-b 缺失）
- 闭包内 IntegrityError 捕获未被真实测试（S8c 手工 db.add 而非调闭包）

### 跨批次集成确认（Integration Review）

| 检查项 | 状态 |
|--------|------|
| publish_service.py upsert → publish_card_atomic → router 调用链 | 一致 |
| 前端 publishCard POST /api/v1/card/publish 参数契约 | 一致 |
| pipeline_router db_mod import (R4-F001) | 一致 |
| 前端 vitest 4 新测试 | 4 passed |

### 发现清单

#### F001
| 字段 | 值 |
|------|-----|
| ID | F001 |
| Severity | HIGH |
| Category | code-bug |
| Type | defect_fix |
| Before-behavior | `test_S8a_factory_orphan_logs_warning` caplog 未绑定模块 logger → 测试实际失败 |
| After-behavior | caplog 显式绑定 `edu_cloud.modules.scan.pipeline_router` logger |
| Evidence | test_pipeline_save_answer.py:66; GPT 实跑 21 passed 1 failed |
| Status | verified |

#### F002
| 字段 | 值 |
|------|-----|
| ID | F002 |
| Severity | HIGH |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | S8b/S8c 手工 db.add 测试 region_map → 闭包核心行为（工厂构建 + db_mod.async_session + IntegrityError catch）未被覆盖 |
| After-behavior | 通过工厂拿闭包、真实调用闭包、在 DB 上断言结果 |
| Evidence | test_pipeline_save_answer.py:99-153 |
| Impact | 闭包不写库 / 错误映射 question_id / 不吞重复异常 → 测试仍绿 |
| Status | verified |
| 注 | Executor 偏差记录说 aiosqlite + greenlet MissingGreenlet 限制导致改为手工测试。如果 greenlet 限制确实不可绕过（通过 _session_factory 注入也不行），可 Planner 归类 design-concern + accepted-risk，但需要提供复现证据 |

#### F003 (Integration)
| 字段 | 值 |
|------|-----|
| ID | F003 |
| Severity | MED |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | `.tpl` 分支 wiring 无测试（只有 DB Template 分支 S8d-a） |
| After-behavior | 补 S8d-b：tpl_path 分支 tracked_factory + identity 断言 |
| Evidence | pipeline_router.py:173-176; test_pipeline_router_wiring.py 只有 S8d-a |
| Status | verified |

### Planner 处置

全部 defect_fix，无 behavior_change。Executor 修复后提交 Round 2。
