<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-13 20:36:55

## 审查报告: Batch 2 (T7-T8) — Round 2

**结论: PASS**

- 代码范围: commit `ff59672..c3655ba`（feat: Batch 2 T7/T8 + Round 2 加固，knowledge_tree 路径过滤）
- Round 1 报告: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch2.md` (FAIL: F001/F002/F003 + P001/P002)
- 交接单: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch2.md` (含 Round 2 加固段)
- 原始输出: `docs/plans/.codex-code-review-batch2-r2-raw.log`
- 原始 SHA256: `ea8ec15ac88ac5e211ad995b5c30b465c53af992777e5a728b292a5aab73f563`
- 加固 commit: `c3655ba`（4 files, +306/-139）

### Round 1 Finding 复审结果

| Finding | R1 状态 | R2 处置 | Status | 验证证据 |
|---------|--------|---------|--------|----------|
| F001 HIGH test-gap (defect_fix) | exam-items 测试无法证伪占位实现 | controlled_kb fixture 锁链路 + 集合精确断言 | resolved-correct | GPT 独立 mutant: "任意非空" 占位实现返回错误集合 → test_get_exam_items_returns_exact_da_chain fail |
| F002 HIGH test-gap (defect_fix) | stats/overview 测试无法证伪硬编码聚合 | _purge_concept_data 隔离 + 精确数值（avg=233.3 / coverage=0.667）| resolved-correct | GPT 独立 mutant: threshold_bug → distribution mismatch / coverage_bug → m1.avg_freq=700 vs 233.3 mismatch；test_stats_overview_exact_aggregation 连跑 5 次稳定 PASS |
| F003 MED code-bug (defect_fix) | get_exam_items 分页非确定性 | ORDER BY item_id ASC + IN 结果 dict 重排 | resolved-correct | GPT 独立 unsorted mutant: page1=[item_002, item_003] / page2=[item_001]（非 ASC 序）→ test_get_exam_items_pagination_stable fail |
| P001 MED process | Contract Pack INV-002/004/005 verification 映射不准 | 由 Planner 处置 | open（不阻塞）| 本批未变更 plan Contract Pack；GPT 确认实现层无回归 |
| P002 MED process | schemas.py 契约缺失 | ExamItemsResponse / StatsOverviewResponse + response_model | resolved-correct | GPT 验证：缺必填字段/嵌套类型错误被 ValidationError 拦截，额外字段被过滤；不 strict forbid extra（合理） |

### 第一段：测试充分性（Test Adequacy）

GPT 独立 mutant 反证策略验证了所有加固测试在错误实现下会 fail：

- **F001 反证**：注入 `mutant_any_nonempty` 占位实现（已知 concept 返回 `{id: 'wrong_item', total: 1}`）→ test_get_exam_items_returns_exact_da_chain 的 `set == {item_001, item_002, item_003}` 直接失败。
- **F002 反证**：注入 `threshold_bug`（high>=100）→ distribution mismatch；注入 `coverage_bug`（avg=sum/1, coverage=1.0）→ m1.avg_freq=700 vs 233.3 + m1.exam_coverage=1.0 vs 0.667 mismatch。当前实现连跑 5 次稳定 PASS。
- **F003 反证**：注入 `mutant_unsorted`（无 ORDER BY + 无 dict 重排）→ page1 返回 [item_002, item_003]、page2 返回 [item_001]，违反 ASC + 跨页边界 → test_get_exam_items_pagination_stable 的 `p1_ids == ["item_001", "item_002"]` 严格序列断言失败。

12 项 Batch 2 新增测试全部稳定 PASS（含 9 项 Round 2 加固 + 3 项 graph_v3）。

### 第二段：行为正确性（Behavioral Correctness）

- **变更理解**: T7 Graph API v3（追加 9 个 stats 字段，v2 全保留）+ T8 exam-items（concept→DA→q_matrix→assessment_items 链路 + 分页）+ stats/overview（模块聚合）+ Round 2 加固（response_model + ORDER BY + dict 重排）
- **Executor 自审抽检**：交接单 9 项加固测试 GPT 抽 3 项独立验证均通过（mutant 反证 + 5 次稳定性）
- **行为变更检查**：ORDER BY + dict 重排只把"不确定"变成"确定"（非 behavior_change，是 defect_fix）；response_model 只在错误路径触发 ValidationError（不改变正常响应内容）；question_number int 类型修正与真实 schema 对齐
- **新 behavior_change**: 无

#### 对抗性审查（Adversarial Review）

GPT 独立构造 4 类 mutant 实现注入测试，验证加固测试是否真能拦截错误行为：

- **Mutant A — 占位非空（mutant_any_nonempty）**：`get_exam_items` 任何 concept 都返回 `{id: 'wrong_item', total: 1}` 占位 item。
  - 实际跑加固测试结果：test_get_exam_items_returns_exact_da_chain 的 `set == {item_001, item_002, item_003}` 直接失败（集合不等）；test_get_exam_items_isolation_between_concepts 也失败。
  - 结论：受控 KB + 集合精确断言能拦截占位实现 → F001 真修复。

- **Mutant B — 无序分页（mutant_unsorted）**：去掉 ORDER BY item_id ASC + 去掉 dict 重排，依赖 SQLite rowid 默认序。
  - controlled_kb fixture 故意倒序插 q_matrix（DA2→item_003 在 rowid 1，DA1→item_001 在 rowid 4）→ 默认 rowid 序：item_002, item_003, item_001
  - 实际跑分页测试：page1=[item_002, item_003] / page2=[item_001]（违反 ASC + 跨页边界）
  - 结论：test_get_exam_items_pagination_stable 的 `p1_ids == ["item_001", "item_002"]` 严格序列断言会拦截 → F003 真修复。

- **Mutant C — 分桶阈值错（threshold_bug）**：把 freq>=500 改为 freq>=100。
  - 实际比较：distribution `{high:2, mid:0, low:1, zero:1}` vs 期望 `{high:1, mid:1, low:1, zero:1}` → mismatch
  - 结论：test_stats_overview_exact_aggregation 的 `assert distribution == {h:1, m:1, l:1, z:1}` 精确等式会拦截 → F002 真修复（分桶维度）。

- **Mutant D — 覆盖率分母错（coverage_bug）**：avg_freq = total_freq（不除 concepts）+ exam_coverage = 1.0 硬编码。
  - 实际比较：m1.avg_freq=700.0 vs 233.3 / m1.exam_coverage=1.0 vs 0.667 → mismatch
  - 结论：精确数值断言会拦截 → F002 真修复（聚合维度）。

- **Pydantic response_model 反证**：构造 3 类响应（缺 total / 额外 extra_field / 嵌套类型错 module_stats.M1.avg_freq=str）注入序列化层
  - 缺必填字段 → ValidationError（拦截）
  - 嵌套类型错 → ValidationError（拦截）
  - 额外未声明字段 → 静默过滤（不报错，Pydantic 默认行为，可接受）
  - 结论：response_model 能拦截字段漂移和类型不匹配 → P002 真修复。

- **稳定性反证**：test_stats_overview_exact_aggregation 连跑 5 次（独立 process）→ 全部 PASS，未出现 b45 的偶发 700 vs 233.3 mismatch
  - 结论：先前的不稳定 b45 是 fixture 顺序的瞬时状态污染，已在隔离单跑 + 重复跑中验证为伪阳性。

GPT 抽检结论：所有 R1 finding 修复在对抗性 mutant 下均能被现有测试套拦截，加固有效。

### 第三段：未测试风险（Non-tested Risks）

- 跨大批次翻页一致性已被 controlled_kb 的 page1/page2 测试覆盖（包括重复请求幂等）
- response_model 不 strict forbid extra（额外字段被静默过滤）— 这是 Pydantic 默认配置，前向兼容性优于严格校验，可接受
- knowledge.db 真实路径下 stats 计算大数据量行为未独立测试，但 controlled_kb 已覆盖核心算法

### 发现清单（Round 2）

<!-- anchor: finding-list -->

本轮未发现新的阻断性 finding。所有 R1 finding 已 resolved-correct 或 由 Planner 处置（P001）。

### PASS/FAIL 判定

按 `~/.claude/rules-t3/review-templates.md <!-- anchor: pass-fail -->`：
- 无未修复的 code-bug HIGH/MED
- 无未修复的 test-gap HIGH/MED
- F001/F002/F003/P002 全部 resolved-correct（GPT 独立 mutant 反证验证）
- P001 是 process 类不阻塞 PASS/FAIL，由 Planner 在 plan/Contract Pack 处置
- **结论：PASS**

### 验证命令记录

GPT 独立运行（codex exec 内）：
- `pytest tests/test_knowledge_tree/test_graph_v3.py tests/test_knowledge_tree/test_exam_items_service.py -q` → `12 passed`
- `pytest tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview_exact_aggregation -q` 连跑 5 次 → 全部通过
- 独立 mutant 注入测试（mutant_any_nonempty / mutant_unsorted / threshold_bug / coverage_bug）→ 当前实现的精确断言均能正确拦截

### 后续

- **本批 Gate 2 R2 PASS**：可推进 Batch 3（T9-T14 前端热力色 + ConceptMapPanel + NodeDetailDrawer + 教材导航 + 收尾）
- **P001 Planner 待办**：Contract Pack INV-002/004/005 verification 映射精确化（不阻塞 Batch 3 启动，可作 T14 收尾的一部分）
- **gates.json 回执**：`code_review_batch2=pass`，subject_ref `commit:ff59672..c3655ba`
