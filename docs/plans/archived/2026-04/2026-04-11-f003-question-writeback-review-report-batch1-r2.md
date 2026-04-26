<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-12 12:37:38
## 审查报告: Task 0-4 (Batch 1) — Round 2
结论: FAIL

GPT 原始输出: `docs/plans/.codex-code-review-batch1-r2-raw.log`
GPT 原始输出 SHA256: `9dd30bff153ed52e4e0c72a53009d1f933d70b9a55417d71800fff095642f175`
GPT token 消耗: 73,047

### R1 Finding 状态

| Finding | R1 Severity | R2 GPT 判定 | Claude 三态 | 说明 |
|---------|-------------|-------------|-------------|------|
| F001 | HIGH code-bug | resolved | verified-resolved | GPT 独立复现确认：双面 skeleton → `A ['obj-A','essay-A']` `B ['obj-B','essay-B']` 正确分面 |
| F002 | HIGH test-gap | residual | verified | S5 已升级精确集合断言，但 S5b 仍为成员断言 `assert "essay-13" in a_region_ids`，未达到 "exact set equality" 要求 |
| F003 | MED test-gap | residual | verified | test_INV001_empty_skeleton 已正确实现，但 plan.md:371 INV-001 test_ref 仍指向旧 test_S2 |

### 第一段：测试充分性（Test Adequacy）

- F001 的代码修复已通过 GPT 独立复现验证（构造 obj-A/B + essay-A/B 双面 skeleton，输出正确分面）
- S5 断言已升级为精确集合断言（`== {"essay-13"}` / `== {"essay-14"}`），删除分面逻辑后断言失败 → 有效
- S5b 仍使用成员断言（`"essay-13" in a_region_ids`），不是精确集合断言 → 残留 test-gap
- test_INV001_empty_skeleton 正确实现空输入测试 → 有效

### 第二段：行为正确性（Behavioral Correctness）

**变更理解（GPT 描述）：** Round 2 修复 commit `74fbe5b` 在 `upsert_template_both_sides()` 中新增 `side_region_ids` 集合，用其过滤 `slots.sub_regions` 和 `objective_groups`，确保每面 Template 只含对应面的题区。S5 断言从存在性升级到 region id 精确集合。新增 test_INV001_empty_skeleton 独立覆盖空输入边界。

**Executor 自审抽检：**
- 抽检 1: R2 交接单声称"S5 确认 A={essay-13} B={essay-14} 精确分面"→ 读 test_publish_service.py:178-179 确认 `assert a_region_ids == {"essay-13"}` 和 `assert b_region_ids == {"essay-14"}` → 属实
- 抽检 2: R2 交接单声称"S5b 补齐 slots fixture + 追加 essay-13 in a_region_ids"→ 读 test_publish_service.py:220 确认只有成员断言，未达到精确集合 → **部分不实**（声称"追加"暗示已充分，实际仍为弱断言）

**对抗性审查：**
- GPT 独立复现 F001 修复效果：构造含 `obj-A/obj-B` + `essay-A/essay-B` 的双面 skeleton → 当前实现 `A ['obj-A','essay-A']` `B ['obj-B','essay-B']`（正确），对照旧行为两面都含全部 4 个 region（错误）→ F001 confirmed resolved
- GPT 验证 S5b 反证强度：去掉核心过滤逻辑后 S5 精确集合断言失败（有效），但 S5b 成员断言仍通过（无效）→ F002 残留 confirmed

### 第三段：未测试风险（Non-tested Risks）

- 无新增未测试风险（Round 2 范围仅为 R1 finding 修复，未引入新行为）
- plan.md INV-001 test_ref 映射未更新，不影响运行时行为，影响审计可追溯性

### 发现清单

#### F002-R2（残留）
| 字段 | 值 |
|------|-----|
| ID | F002-R2 |
| Severity | HIGH |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | S5b 使用成员断言 `assert "essay-13" in a_region_ids`，A 面混入额外 region 时测试仍通过 |
| After-behavior | S5b 应使用精确集合断言 `assert a_region_ids == {"essay-13"}`，确保 A 面只含对应 region |
| Inv-conflict | none |
| Evidence | test_publish_service.py:220 |
| Impact | S5b 无法捕获"A 面混入 B 面 region"的错误实现 |
| Repair hypothesis | 改一行：`assert "essay-13" in a_region_ids` → `assert a_region_ids == {"essay-13"}` |
| Status | verified |

#### F003-R2（残留，Planner 归类 design-concern）
| 字段 | 值 |
|------|-----|
| ID | F003-R2 |
| Severity | MED |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | plan.md:371 INV-001 test_ref 指向 test_S2（不覆盖空输入） |
| After-behavior | test_ref 应指向 test_INV001_empty_skeleton |
| Inv-conflict | none |
| Evidence | plan.md:371 |
| Impact | 审计可追溯性缺口，不影响运行时行为 |
| Repair hypothesis | plan.md:371 更新 test_ref |
| Status | verified |
| Planner 处置 | **design-concern — 不阻塞**。核心测试已存在且通过；plan.md 在 Gate 1 后保持稳定；test_ref 映射修正延期到 batch1 收尾 |

### 回归检查

- 定点: 7 tests PASS
- 前端全量: 184 tests PASS
- 后端全量: 1729 passed / 4 failed / 1 error（与既有 baseline 一致，无新增回归）

### Planner 分类处置（2 轮后介入）

**F002 残留 → code-bug（Round 3 修复）:**
S5b 断言从 `assert "essay-13" in a_region_ids` 改为 `assert a_region_ids == {"essay-13"}`。一行改动，test_publish_service.py:220。

**F003 残留 → design-concern（记入 design.md §待处置，不阻塞）:**
plan.md:371 INV-001 test_ref 未更新到 test_INV001_empty_skeleton。核心测试已存在且通过。plan.md 在 Gate 1 后保持稳定（锚点段字节级冻结），Contract Pack 段虽不在锚点保护范围但属于计划文档的一部分。test_ref 映射修正延期到 batch1 收尾。

**Round 3 scope:** 仅审 F002 残留的 S5b 断言修复（test_publish_service.py:220 一行改动）。F003 design-concern 不阻塞。
