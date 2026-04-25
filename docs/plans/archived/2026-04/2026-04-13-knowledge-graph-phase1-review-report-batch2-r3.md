[edu-cloud] GPT Reviewer | 2026-04-13 20:49:37

## 审查报告: Batch 2 (T7-T8) — Round 3

**结论: PASS**

- 代码范围: commit `d300263`（fix R3：N001 INNER JOIN total/items 一致性）
- 交接单: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch2.md`
- 原始输出: `docs/plans/.codex-raw-code_review_batch2_r3-20260413T204937.log`
- 原始 SHA256: `d3a3ff4f25642ece55c66a275776b96e3f8e50e8856bf0f485d78dd351c53433`

### 多轮审查链 audit trail

| Round | Commit | 结论 | 关键 finding |
|-------|--------|------|------|
| R1 | ff59672 | FAIL | F001/F002 HIGH test-gap + F003 MED code-bug + P001/P002 process |
| R2 | c3655ba | FAIL | F001/F002/F003/P002 resolved-correct, P001 deferred (INV-002/004), N001 NEW MED code-bug |
| R3 | d300263 | **PASS** | N001 resolved-correct, 边界路径无新 bug |

### Round 3 审查范围

按 FAIL 升级规则 R3 仅审 code-bug 和 test-gap 修复。

### 变更理解（GPT 独立复述）

R3 commit `d300263` 单一目的修复 R2 N001（total/items 不一致 phantom bug）：
- `exam_items_service.py:64-69` SELECT 改为 `SELECT DISTINCT q.item_id FROM q_matrix q INNER JOIN assessment_items a ON q.item_id = a.id WHERE q.attribute_id IN (...) ORDER BY q.item_id ASC`
- INNER JOIN 在分页前过滤掉 q_matrix 引用但 assessment_items 缺失的 phantom id
- 结果：`total = len(item_ids)` 现在等于真实可返回的 item 总数；分页元数据与实际 items 数一致
- 防御性 `row is None` 分支保留（`exam_items_service.py:101`）作为 fail-safe

测试新增 `test_get_exam_items_total_consistent_with_actual_items`（`tests/test_knowledge_tree/test_exam_items_service.py:140`）：临时 SQLite 构造 `q_matrix` 引用 3 个 id（其中 `item_MISSING` 不在 `assessment_items`），断言 `total==2 / page2 空 / page1_size2 装满`。

### 对抗性审查

GPT 在临时 worktree 中执行 mutant 测试：
- **Mutant 1**: 删除 `INNER JOIN assessment_items` 子句 → `test_get_exam_items_total_consistent_with_actual_items` 实际 fail，报 `total=3`（phantom 3 而非 2）→ 测试有效抓住 mutant
- **边界 1**: 全部 phantom id 场景（assessment_items 完全无对应行）→ 返回 `{total:0, items:[], page:1, page_size:10}` ✓ INNER JOIN 没破坏空集合路径
- **边界 2**: 无关联 DA 场景 → 仍走早退 `return {"total": 0, "items": [], ...}` ✓ INNER JOIN 不影响 DA 早退路径
- **边界 3**: 防御性 continue 分支理论上不可达，但保留作为 defense-in-depth；GPT 未发现可触发路径

### 第一段：N001 resolved-correct

GPT 实测复盘：
- 修复点 `exam_items_service.py:61-67` SELECT 改为 `INNER JOIN assessment_items`，分页前过滤 phantom id
- `total / page_ids / items` 三者口径现在一致
- 防御性 `row is None` 分支保留为 fail-safe（理论不再触发）
- 测试 `test_get_exam_items_total_consistent_with_actual_items` 同时锁定 3 个角度：第一页 `total==2` + 第二页空但 `total` 仍为 2 + page_size=2 时第一页装满
- GPT 临时 worktree 删除 `INNER JOIN` 后该测试 fail（`total=3`），mutant 验证有效

### 第二段：边界路径无新 bug

GPT 额外构造测试场景：
- 全部 phantom id（assessment_items 完全无对应）→ `{total:0, items:[], page:1, page_size:10}` ✓
- 无关联 DA → 仍走早退路径返回空 ✓
- INNER JOIN 没破坏空集合/无关联路径

### 发现清单

无新 finding。

### Round 1/2 finding 终态汇总

| ID | Severity | Category | Type | R3 终态 | Evidence |
|----|----------|----------|------|---------|----------|
| F001 | HIGH | test-gap | defect_fix | resolved-correct (R2) | test_exam_items_service.py 受控 KB 9 测试 |
| F002 | HIGH | test-gap | defect_fix | resolved-correct (R2) | test_stats_overview_exact_aggregation 精确数值 |
| F003 | MED | code-bug | defect_fix | resolved-correct (R2) | exam_items_service.py:66 ORDER BY |
| P001 | MED | process | defect_fix | partial-deferred (R2) | INV-005 已修，INV-002/004 deferred 到下一 Task |
| P002 | MED | process | defect_fix | resolved-correct (R2) | router.py response_model + schemas.py |
| N001 | MED | code-bug | defect_fix | resolved-correct (R3) | exam_items_service.py:61-67 INNER JOIN |

### PASS 判定

按 `~/.claude/rules-t3/review-templates.md <!-- anchor: pass-fail -->`：
- N001 (R2 唯一阻塞 finding) resolved-correct ✓
- 无新 HIGH/MED code-bug 或 test-gap finding ✓
- → **PASS**

### 行为变更审批记录

R3 commit d300263 仅修 N001（INNER JOIN 过滤 phantom id），属 defect_fix（修复 total/items 不一致 bug），无 behavior_change，无需用户单独批准。

### 后续

- P001 INV-002/004 verification 映射 deferred 给下一 Task / Phase 1 收尾时 Planner 处置
- Batch 2 关闭，可推进 Batch 3（T9-T13 前端 + T14 收尾）
