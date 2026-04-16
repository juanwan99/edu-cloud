[edu-cloud] GPT Reviewer | 2026-04-13 11:00:37

## 审查报告: Task 1-18 (Batch 1-6) — Round 2 Re-Review

**结论**: **FAIL**

GPT Codex 独立审查（commits `2333f64..bf630b0`）：6 个 Round 1 finding 仅 2 条 resolved-correct，4 条未真正关闭；新发现 1 个 behavior_change finding (N001)。

**原始输出**: `docs/plans/.codex-raw-code-review-r2-20260413-110023.log`
**SHA256**: `82eb8bc5dce95cb9ca677cc01a054e2b7f7abea17d6e833c226f7ed530fdb02d`

**范围说明**: `bf630b0` 附带的 module-governance plan 文件已跳过，仅审 conduct 代码与测试。

---

### 第一段：测试充分性（Test Adequacy）

GPT 实跑测试分布：
- `pytest tests/test_conduct/test_admin_api.py -q` → `20 passed`
- `pytest tests/test_conduct/test_agent_tools.py -q` → `13 passed`
- `pytest tests/test_conduct/test_parent_api.py -q` → `34 passed`
- `pytest tests/test_conduct/test_admin_crud_api.py -q` → `28 passed`
- `pytest tests/test_conduct/test_{models,permissions,crypto}.py -q` → `13 passed`
- `pytest tests/test_alembic_migration.py -q` → **1 passed, 1 failed, 1 error**（关键失败）
- `pytest -q` 在 304s 超时，全量 1913 测试未跑完

**关键测试缺口**：
- F002 仍有 2 条越权红测未补（外班 `rule_item_id` 写入记录 / 外班 `student_id` 加入本班 group）
- F004 前端字段映射无测试保护（把 `item.points` 改回 `item.default_points` 仍全绿）
- F006 导出测试断言过弱（仅验 `PK` 魔数 + `>1000` 字节，空表头 4854 字节也能通过）
- Alembic smoke test 因更早历史迁移 SQLite `ALTER CONSTRAINT` 错误，未能证明 upgrade/downgrade

**测试统计偏差**: Round 2 交接单声称 "conduct 106 tests / 全量 1896 tests"，GPT 实测 `108 / 1913`，且全量绿态未验证成功（handoff 数字不准）。

---

### 第二段：行为正确性（Behavioral Correctness）

**变更理解**: Round 2 修复 6 个 finding（F001 Alembic 迁移 / F002 class-scope 守卫 / F003 Agent DataScope / F004 parent 规则页 / F005 phone 绑定 / F006 入口测试）。

**对抗性审查**（GPT 独立构造越权输入验证 F002）:
- 构造 class A 的 `add_points` 请求，携带 class B 的 `rule_item_id` → 当前实现**可成功写入**，产生跨班记录污染
- 构造 class A 的 `group_members` 请求，加入 class B 的 `student_id` → 当前实现**可成功加入**，跨班组员污染
- F002 守卫只覆盖了 `config/category/group-delete` 等端点，仍有 2 条越权面未封口

**F003 反向验证**: 删除 `_check_class_in_scope` / `_check_student_in_scope` 或对应调用点，3 条 agent scope 红测会立即转绿为红 — 验证有效。

**N001 行为变更检测**: Round 1 结论明确 `id_card` 契约为"后 6 位比对"，Round 2 实现改为"整串相等"，新测试 `test_parent_bind_id_card_mode` 把该行为固化 — 未授权行为变更，命中红旗模式（契约变更）。

---

### 第三段：未测试风险（Non-tested Risks）

- `id_card_number` 入站无 API / 入口测试，"身份证入站必经 AES-256-GCM" 仅从模型约定与测试造数侧推
- 导出 API 无法证明导出正确数据（inner join 可过滤掉所有记录仍通过大小断言）
- F002 `add_points` / group members 仍有 2 条可利用越权路径，生产启用 conduct 模块即暴露
- F004 前端字段映射回退回退无感（缺前后端契约 snapshot 测试）

---

### 发现清单

<!-- anchor: finding-classification -->

#### F001-F006 逐条复核

| Finding | Severity | Category | Type | Status | 证据 | Claude 三态 |
|---------|----------|----------|------|--------|------|------------|
| F001 Alembic 迁移缺失 | HIGH | code-bug | defect_fix | **resolved-partial** | 迁移文件齐全 ([c_add_conduct_module_tables.py](alembic/versions/c_add_conduct_module_tables.py))，但 `test_migration_creates_all_expected_tables` 在更早历史迁移上因 SQLite `ALTER CONSTRAINT` 报错 → 未证明 upgrade/downgrade 有效 | verified |
| F002 管理端跨班越权 | HIGH | code-bug | defect_fix | **not-resolved** | 守卫加了但仍有 2 条开放面：`add_points` 允许任意外班 `rule_item_id` ([admin_router.py:93](src/edu_cloud/modules/conduct/admin_router.py#L93) + [admin_service.py:244](src/edu_cloud/modules/conduct/admin_service.py#L244))；`group members` 不校验 `student_id` 归属 ([admin_router.py:326-340](src/edu_cloud/modules/conduct/admin_router.py#L326) + [admin_service.py:525,552](src/edu_cloud/modules/conduct/admin_service.py#L525)) | verified |
| F003 Agent 工具 DataScope | HIGH | code-bug | defect_fix | **resolved-correct** | 6 工具全部接入 `_check_class_in_scope` / `_check_student_in_scope` ([conduct.py:24,36,82,161,253,321,395,430](src/edu_cloud/ai/tools/conduct.py))；4 条 scope 红测 ([test_agent_tools.py:56,77,100,123](tests/test_conduct/test_agent_tools.py)) 均可在回滚时失败 | verified |
| F004 get_children 返回 class_id / ParentRules 字段 | MED | code-bug | defect_fix | **resolved-partial** | 后端 `class_id` 字段齐全 ([parent_service.py:238,262](src/edu_cloud/modules/conduct/parent_service.py))；前端 `item.points` 修正 ([ParentRules.vue:17-50](frontend/src/pages/parent/ParentRules.vue))；`test_get_children_returns_class_id` 已加 ([test_parent_api.py:534](tests/test_conduct/test_parent_api.py))；但前端字段改回 `item.default_points` 无任何测试失败（半闭环）| verified |
| F005 phone 验证模式数据源 | MED | code-bug | defect_fix | **resolved-correct** | `phone/custom` 共用 `profile.verify_code` ([parent_service.py:192,195](src/edu_cloud/modules/conduct/parent_service.py))；AES 加密写入 ([admin_service.py:121](src/edu_cloud/modules/conduct/admin_service.py))；新测试 `test_parent_bind_phone_mode` / `_wrong_code` ([test_parent_api.py:412,446](tests/test_conduct/test_parent_api.py)) 在回滚时可失败 | verified |
| F006 绑定/导出入口测试 | HIGH | test-gap | defect_fix | **resolved-partial** | 绑定分支测试有效 ([test_parent_api.py:412,446,474,504](tests/test_conduct/test_parent_api.py))；导出入口测试弱断言（仅验 `PK` 魔数 + `>1000` 字节，`test_export_records_excel` 插入 dummy `operator_id` 被 inner join 过滤仍通过），空工作簿 4854 字节也能通过 | verified |

<!-- anchor: finding-type -->

#### 新发现 Finding

**N001 — id_card 绑定契约从"后 6 位"退化为"整串相等"**

- **Status**: verified
- **Severity**: MED
- **Category**: code-bug
- **Type**: `behavior_change` （⚠️ **用户必须单独确认**）
- **Before-behavior**: Round 1 结论明确 `id_card` 验证模式比对"身份证后 6 位"（与当时 Option A 用户确认保持一致）
- **After-behavior**: Round 2 实现改为要求完整身份证串整串相等，新测试 `test_parent_bind_id_card_mode` 把该行为固化
- **Evidence**: Round 1 F005 结论段 "`id_card` 仍独立走身份证号后 6 位比对"；当前实现 [parent_service.py:188-190](src/edu_cloud/modules/conduct/parent_service.py) 做整串相等；[test_parent_api.py:474](tests/test_conduct/test_parent_api.py) 按整串写死
- **Impact**: 启用 `id_card` 验证的班级，原本按"后 6 位"可绑定的家长全部改为必须提供完整身份证号；未获批准的行为变更，与既有契约冲突
- **Inv-conflict**: direct（违反 Round 1 确认的 Option A 契约）
- **Repair hypothesis**（非权威）:
  - 可能修复方向：恢复 `id_card` 的"后 6 位"契约，同时保留 `phone/custom → verify_code` 的 Option A 路径
  - 必须避免的修复反模式：继续修改测试去迎合"整串相等"实现（把错误行为制度化）
  - **requires independent fix design + Semantic Regression Gate**

---

### Process Findings

- **P1 (继承自 R1)**：plan 缺 Contract Pack 段（invariants / counter_examples / risk_modules / test_debt），仅有测试契约。不阻断本轮，未来 T4 补齐。
- **P2 (R2 新增)**：交接单 verification 数字偏差（声称 conduct 106 / 全量 1896，实际 108 / 1913）；全量绿态未跑通（pytest -q 超时 + alembic 测试红）。Executor 下轮必须跑全量并报告实际数字。

---

<!-- anchor: pass-fail -->

### PASS/FAIL 判定

- F001 HIGH code-bug: resolved-partial → 阻塞
- F002 HIGH code-bug: **not-resolved** → 阻塞
- F003 HIGH code-bug: resolved-correct
- F004 MED code-bug: resolved-partial → 阻塞（HIGH/MED code-bug 未完全修复）
- F005 MED code-bug: resolved-correct
- F006 HIGH test-gap: resolved-partial → 阻塞
- **N001 MED code-bug behavior_change**: 未处置 → 阻塞（须用户单独批准）

**结论 FAIL**（4 条 R1 finding 未真正关闭 + 1 条新 behavior_change 未处置）。

---

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| N001 | id_card 验证改为"整串相等"（原契约"后 6 位"）| **pending** | 待用户决定：恢复 R1 确认的"后 6 位"契约 OR 显式批准 R2 的"整串相等"新契约 |

---

### Round 3 修复方向（初步分类，待 Planner 决策）

按 CLAUDE.md「FAIL 升级（T3/T4 通用）」规则：Round 3 仅审 code-bug 和 test-gap 修复。

**必须修复（code-bug HIGH/MED 阻塞 PASS）**:
- F001：修复 Alembic smoke test 红的根因（SQLite `ALTER CONSTRAINT` 兼容性 — 看是否需要 batch mode 或 skip 早期历史迁移），验证 upgrade/downgrade 可达
- F002：封口剩余 2 条越权面
  - `add_points`: rule_item_id 属班校验（防跨班 record 污染）
  - `group_members`: student_id 属班校验（防跨班组员污染）
  - 补对应越权红测
- F004：增加前端字段映射契约测试（`ParentRules.vue` 渲染 `item.points` 的 snapshot/e2e 级测试），防止字段无感回退
- F006：导出测试升级断言
  - 解包 openpyxl 工作簿读取实际 cell 内容，验证非空行数
  - 修复 `test_export_records_excel` 的 operator_id 被 inner join 过滤问题（用有效 operator_id 插入）
  - 补"删除实现后测试会失败"的反向验证

**待用户批准（behavior_change）**:
- N001：id_card 契约决策（选 A 恢复"后 6 位" / 选 B 批准"整串相等"）
  - 若选 A → F005 配套修复 `parent_service.py:188-190` + 修改 `test_parent_bind_id_card_mode`（非迎合测试实现，而是实现对齐 Round 1 契约）
  - 若选 B → 更新设计文档，在 design.md 记录行为变更决策

**Fix Intent Card 要求**：
- F002 + N001 触及架构层守卫 / 行为契约，修复前需输出 Fix Intent Card
- F001 修复需说明 SQLite 兼容性是"妥协跳过"还是"根因修复"，并注明影响面

---

## Claude 独立验证补记（2026-04-13 11:00:37 追加）

为避免对 GPT 观察的机械采信（L013 自审盲区），对关键 finding 做独立 reproduce：

### 验证 [F001] Alembic smoke test — 复现 + 发现工作区未 commit 修复

独立在 `bf630b0` worktree 跑 `tests/test_alembic_migration.py`：
- ✅ 复现 GPT 结果：`1 passed, 1 failed, 1 error`
- ✅ 根因锁定：`alembic/versions/1a325e38e941_add_entity_memory_and_project_state_.py:40` 的 `op.create_unique_constraint(...)` 对 SQLite dialect 报 `NotImplementedError: No support for ALTER of constraints in SQLite dialect`（`alembic/ddl/sqlite.py:81`）

**但在当前 HEAD 工作区 (dirty) 跑同测试：`3 passed`**。原因：工作区有 6 个 alembic migration 文件的**未 commit 修复**（`git status` 显示 6 个 M）：
- `1a325e38e941`: 把 `op.create_unique_constraint(...)` 内联到 `create_table` 的 `sa.UniqueConstraint(...)` + 移除 `op.drop_constraint`
- `2a40f59215de` / `52af1c37bf14` / `a370e2771c6d` / `b08103b3a6f5` / `c9587c787c6b`: 用 `op.batch_alter_table(...)` 包装 `drop_column`

这些修改**不属于 Round 2 commit 范围**（`bf630b0` 内不存在），但是 F001 的根因修复。

**溯源确认（2026-04-13 11:14）**: 属 `2026-04-12-haofenshu-phase1` Batch 1 Code Review R1 F001 的独立修复产物。归属依据 `docs/plans/2026-04-13-migration-gate-repair-design.md` §0 + §1.2（2026-04-13 10:51:02 创建，标注"设计完成，待用户批准"）。两个任务的 F001 均涉及 SQLite `ALTER CONSTRAINT`，命名巧合——修复一次可让两个 F001 同时受益。

**Round 3 范围裁定**: conduct F001 不进入 Round 3——该会话不侵占 haofenshu-phase1 scope。conduct F001 的 `resolved-partial` 状态保持，待 haofenshu-phase1 修复合入主干后自动升级为 `resolved-correct`（因为同一 SQLite 兼容性修复同时治愈 conduct 的 alembic smoke test）。

### 验证 [F002] 越权面 — 代码独立审查

检查 `admin_router.py:93-128` (`add_points` / `add_points_batch`)：
```python
check_class_scope(current_user, class_id)          # ✅ 校验 class_id
admin_service.add_points(..., rule_item_id=data.rule_item_id, ...)  # ❌ 未校验 rule_item_id 归属 class_id
```
确认：外班 rule_item_id 可直通 → GPT finding 事实准确。

检查 `admin_router.py:326-351` (`add_group_members` / `remove_group_member`)：
```python
check_class_scope(current_user, class_id)                              # ✅
check_resource_class(db, ConductGroup, group_id, class_id)             # ✅
admin_service.add_group_members(db, group_id, data.student_ids)        # ❌ 未校验 student_id 归属 class_id
```
确认：外班 student_id 可直通 → GPT finding 事实准确。

### N001 id_card 契约 — 代码独立审查

检查 `parent_service.py:188-191`:
```python
if verify_type == "id_card":
    stored = decrypt(profile.id_card_number) if profile else None
    if not stored or stored != verify_code:           # ❌ 整串相等
        raise ValidationError("身份证号验证失败")
```
确认：未做"后 6 位"切片（如 `stored[-6:] != verify_code`），Round 1 F005 Option A 契约被退化 → GPT finding 事实准确。

### Claude 三态结论

全部 7 条 finding（F001-F006 + N001）**Status: verified**，无 contested 条目。独立验证未发现任何 GPT 观察错误。

### 本地测试证据（Stop hook 要求）

- `python -m pytest tests/test_conduct/ -q` → **108 passed**（2:30 耗时，与 GPT collect-only 一致）
- `python -m pytest tests/test_alembic_migration.py -v`:
  - 在 `bf630b0` worktree: **1 passed, 1 failed, 1 error**（复现 GPT）
  - 在 HEAD + 工作区 dirty: **3 passed**（工作区未 commit 修改已修 SQLite 兼容性）
