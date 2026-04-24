<!-- legacy-format -->
# S1-A haofenshu-s1-bank Plan Review R1（FAIL）

**Date**: 2026-04-24
**Reviewer**: GPT-5.4 (Codex CLI)
**Reviewed Plan**: [2026-04-24-haofenshu-s1-bank-plan.md](./2026-04-24-haofenshu-s1-bank-plan.md) (commit `1bb95b0`)
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md) (v0.2, commit `9b07b05`)
**Raw Log**: `.codex-plan-review-raw-s1a-20260424_122811.log` (177KB)
**raw_output_hash**: `f4960c98884f42d6ba03554d546db75a5f111d67c9e7052c2f4e4f565f37d3c0`
**subject_hash (plan)**: `8e0bfb2a8e91053ba7baf11516f99f1e4c5bc04f7a1675c8fbf5337a28048935`

---

## 结论：R1 FAIL

**0 HIGH + 6 MED**。F001/F002/F003/F004 独立验证通过；F005/F008 仅部分成立。按 [review-templates.md](~/.claude/rules-t3/review-templates.md#L175) 口径：MED 未处置 → FAIL。

---

## Findings 汇总

| ID | Severity | Category | Type | 概括 |
|----|----------|----------|------|------|
| F-S1A-01 | MED | test-gap | defect_fix | Step 4.2 / G1-S1A-4 命令用 Alembic revision 充当 Git commit 不可执行 |
| F-S1A-02 | MED | test-gap | defect_fix | Task 1 无入口级验证（只做 ORM 属性 round-trip，不走 service/API/CLI） |
| F-S1A-03 | MED | test-gap | defect_fix | `test_existing_columns_unchanged_after_upgrade` 对 bloom_level 用宽松 substring 断言，错误的 VARCHAR(10)/VARCHAR(255) 能漏过 |
| F-S1A-04 | MED | design-concern | defect_fix | Contract Pack 不符合 `~/.claude/config/contract-pack-schema.md` 真源字段名（claim vs statement / verification 非枚举 / risk_modules 字段错 / deadline 格式） |
| F-S1A-05 | MED | test-gap | defect_fix | Gate baseline 双真源冲突（plan `2064 passed` / `22 failed` / `1 error` / `23 skipped` vs CLAUDE.md `2060 passed` / `23 skipped` vs 实测 tests/test_alembic_migration.py 1 fail / 1 pass / 1 error） |
| F-S1A-06 | MED | design-concern | defect_fix | Step 4.3 handoff 模板本身超 15 行但 G1-S1A-6 要求 ≤15 行，执行者必然违反其一 |

独立验证通过项（GPT 亲自跑工具证明）：
- ✅ F001: `alembic heads` = `36e25241e55d (head)`
- ✅ F002: `alembic/env.py:51` + `api/app.py:41` 都已注册
- ✅ F003: Task 3 smoke INSERT 已补必填列
- ✅ F004: Task 1-4 5 字段测试契约 + 3 边界条件齐全
- 🟡 F005: 数量达标但 schema 不符
- 🟡 F008: file:line 有，但负面断言的 Grep 零结果证据不够稳定

Task 3 六个 smoke test 未见逻辑镜像（无 HIGH）。`test_existing_data_preserved_through_migration` 不是"空表也误过"，但只部分锁旧列语义。

Deferred 处置评估：
- #1/#4/#5（bloom_level enum 升级 / source enum / difficulty_level enum）：作为 scope cut 可接受，但意味着对 design §4.1 enum 语义只是延期
- #2（grade_id FK）：合理，grades 表在仓库未出现
- #3（tags 已存在）：合理，`tags` 已是 JSON
- #7（baseline 披露）：披露诚实，但双真源冲突未解决 → 对应 F-S1A-05

---

## 核心 Findings 详述

### F-S1A-01（MED / test-gap）Gate 命令 Alembic revision 混用 Git commit

**Before**: G1-S1A-4 Step 4.2 写 `git diff --stat 36e25241e55d..HEAD -- alembic/env.py src/edu_cloud/api/app.py`，声称验证 ORC-S1A-002 "零改动"。

**After**: `36e25241e55d` 是 Alembic revision ID，不是 Git commit。GPT 实测 `git rev-parse --verify 36e25241e55d^{commit}` 返回 `fatal: Needed a single revision`。命令本身不可执行，Gate 出口失效。

**Evidence**:
- plan.md L797 / L798 / L864
- `git rev-parse --verify 36e25241e55d^{commit}` → fatal

**Impact**: ORC-S1A-002 机械验证降级为"人工看一下"，无客观通过判据。

**Repair 方向**: 绑定到真实 Git 边界。可选：
- `git diff $(git log --format=%H -n 1 -- docs/plans/2026-04-24-haofenshu-s1-bank-plan.md)..HEAD -- alembic/env.py src/edu_cloud/api/app.py` （plan commit 为起点）
- 或 `git diff 1bb95b0..HEAD -- ...` （明确写本 plan commit SHA）
- 禁止继续用 Alembic revision 充当 Git commit

---

### F-S1A-02（MED / test-gap）Task 1 无入口级验证

**Before**: Task 1 的测试契约和示例测试只直接构造 `BankQuestion(...)` 并断言 `q.source == "exam"` 等属性。

**After**: 未经过 bank_service.list_bank_questions / bank API / 或任何现有稳定入口。命中 review-templates.md "无入口级验证 → test-gap MED"。

**Evidence**:
- plan.md L255-274（Task 1 测试契约 + Step 1.1 测试代码）
- review-templates.md L277 / L236

**Impact**: ORM 层之上的集成断裂可能全绿通过。F004 "有 5 字段" 不等于 "入口质量达标"。

**Repair 方向**: 补一个走 `bank_service` 或 API 的集成测试，验证新字段在现有接口下的 serialize/deserialize。例如扩展 `tests/test_services_exam/test_bank_service.py::test_list_bank_questions_with_filter` 加一条 source/difficulty_level 过滤断言。

---

### F-S1A-03（MED / test-gap）bloom_level 类型断言过宽

**Before**: `test_existing_columns_unchanged_after_upgrade` 对 bloom_level 写：
```python
assert '20' in str(cols['bloom_level']['type']) or 'VARCHAR' in str(cols['bloom_level']['type']).upper()
```

**After**: 错误的 `VARCHAR(10)` 或 `VARCHAR(255)` 都能通过（都含 "VARCHAR"）。ORC-S1A-003 "只加不改" 的机械守卫不严。

**Evidence**:
- plan.md L630 (Task 3 Step 3.1 测试代码)
- plan.md L191 (INV-S1A-004 声称"与 initial schema 完全一致")
- models.py:31 (`bloom_level: Mapped[str | None] = mapped_column(String(20), ...)`)
- initial_merged_schema.py:514 (`Column('bloom_level', String(length=20), nullable=True)`)

**Impact**: invariant 文字"完全一致"和可执行断言"包含 20 或 VARCHAR" 强度不匹配。SQLite smoke 漏检。

**Repair 方向**: 让 invariant 文案和断言强度一致。可选：
- 精确断言 `cols['bloom_level']['type'].length == 20`（对 SQLAlchemy VARCHAR type）
- 或跨方言稳定的 `str(cols['bloom_level']['type']) == 'VARCHAR(20)'`
- 禁止保留宽泛 VARCHAR 逃逸口

---

### F-S1A-04（MED / design-concern）Contract Pack schema 不符真源

**Before**: Contract Pack 段（plan.md L179-228）使用自由 prose 字段名。

**After**: 与 `~/.claude/config/contract-pack-schema.md` 真源不符：
- `claim` 应为 `statement`（L7）
- `verification` 应是枚举值 `existing_test / new_test / manual_spike / future_monitor` + `test_ref`（L13）
- `risk_modules` 现在用 `path / risk / mitigation`，真源要别的字段（L31）
- `test_debt.deadline` 现在写 "S1-D 会话"，真源要 `YYYY-MM-DD`（L38）

**Evidence**:
- plan.md L179 / L221
- contract-pack-schema.md L7 / L13 / L31 / L38

**Impact**: F005 仅部分成立（数量达标但不符 schema）。自动校验和 reviewer 复核无法按声明的 schema 消费。

**Repair 方向**: schema 归一化，把 `claim` 改 `statement`、`verification` 改枚举 + test_ref、risk_modules 字段对齐、deadline 改日期格式。禁止并行保留两套字段或通过删字段"过 schema"。

---

### F-S1A-05（MED / test-gap）baseline 双真源冲突

**Before**: plan frontmatter `baseline_count: 2064 passed / 22 failed / 1 error / 23 skipped` + §Deferred #7 披露既有失败，Gate G1-S1A-5 放宽为阈值条件。

**After**: 多真源冲突未消解：
- plan 自己：2064 / 22 / 1 / 23
- CLAUDE.md L85：`2060 passed` / `23 skipped`（旧数字 + 无 failed/error 披露）
- GPT 实测 `tests/test_alembic_migration.py --tb=no -q`：1 fail / 1 pass / 1 error

**Evidence**:
- plan.md L2 / L769 / L909
- CLAUDE.md L85

**Impact**: Gate 阈值不可重复。不同审查者依据不同真源可能得出不同结论。

**Repair 方向**: 把 G1-S1A-5 锚定到不可变 baseline 工件（具体 commit + timestamp + 完整输出 artifact），并同步更新 CLAUDE.md 单一真源。禁止临时挑更宽松数字或让双 baseline 长期并存。

---

### F-S1A-06（MED / design-concern）handoff 模板超 15 行但 Gate 要求 ≤15

**Before**: Step 4.3 的 handoff 模板（plan.md L804 附近）明显超过 15 行（含 frontmatter + 生成块 + 自由备注）。

**After**: G1-S1A-6 (L866) 写 `handoff.md ≤ 15 行`。执行者必须偏离模板或违反 Gate。

**Evidence**:
- plan.md L804（模板）
- plan.md L866（Gate 门槛）

**Impact**: Task 4 内生矛盾。

**Repair 方向**: 统一模板与门槛口径。可选：
- 压缩模板到 ≤15 行
- 或放宽 Gate 到 ≤30 行（与 CLAUDE.md "同 topic handoff ≤1 次、≤15 行硬限" 一致性评估）
- 保留二者之一作为权威

---

## Gate 决策

按 codex-review skill §Gate 条件：

- **R1 FAIL**（6 MED 未处置）
- **是否允许 R2？**
  - Tier = T4？否（T3）
  - topic 含 `remote/deploy/publish`？否
  - 跨模块 ≥2 文件？**是**（plan 声明改动 `modules/bank/models.py` + `alembic/versions/{slug}_s1a_bank_question_extension.py` + `tests/test_alembic_s1a_bank.py` + `tests/test_services_exam/test_bank_service.py` 共 4 文件跨 2+ 模块）
  - **结论：允许 R2**

**建议走 R2**：6 个 finding 全部是机械化可修（改命令 / 补入口测试 / 收紧断言 / Contract Pack schema / baseline 单真源 / handoff 行数），不涉及设计根因，不需再拆 topic。

---

## Raw Evidence

Full Codex output: `docs/plans/.codex-plan-review-raw-s1a-20260424_122811.log`（177KB）
raw_output_hash: `f4960c98884f42d6ba03554d546db75a5f111d67c9e7052c2f4e4f565f37d3c0`
