---
topic: 2026-04-24-super-admin-cross-school-account
gate: plan_review
rounds:
  - round: 1
    status: FAIL
    findings: "3 HIGH + 4 MED"
    raw_log: "docs/plans/.codex-raw-plan-review-super-admin-r1-20260424_234500.log"
    raw_sha256: "2537f0d802a34a1c4255390ed9fcb1050b3e45a526592570d492f354465bcfec"
    mcp_thread: "019dc035-3d62-72f3-8fb5-08eebddb4caf"
    reviewed_at: "2026-04-24T23:45:00+08:00"
  - round: 2
    status: FAIL
    findings: "F001-F006 resolved-correct + F007 resolved-partial + R2-F001/R2-F002 new process findings (3 MED 残留均为 process 层)"
    raw_log: "docs/plans/.codex-raw-plan-review-super-admin-r2-20260425_000500.log"
    raw_sha256: "2802375e682d94ae31c68e1ae49345b01e9ddaed30ae8e1efbe71a806682e000"
    mcp_thread: "019dc04c-c6e8-79b1-b9f3-93eb30342244"
    reviewed_at: "2026-04-25T00:05:00+08:00"
    post_fix: "3 条残留已在 2026-04-25T00:10 轻量补丁覆盖（R2-F002 typo / F007 独立段 / R2-F001 contract_pack）"
reviewer: gpt (codex MCP)
plan_commit_r1: 8f9c03540476e77f5c32282a0d777c86ab6c825f
plan_commit_r1_revision: 08f6cbc
gate_final_status: "R2 FAIL — 按 gate 铁律禁 R3；process 残留已补丁，等待用户 manual_override 或拆 topic 决定"
---

# Plan Review R1 Report — super-admin-cross-school-account

## 原始 GPT 输出

见 `docs/plans/.codex-raw-plan-review-super-admin-r1-20260424_234500.log`（sha256 `2537f0d8...ec`）。

## Finding 三态标注

| ID | Severity | Type | Category | Verdict | 备注 |
|---|---|---|---|---|---|
| F001 | HIGH | test_gap | 完整性/不变量 | **valid** | ORC-004 后端契约（超管跨校 `role=subject_teacher` → 201，保持 `ALL_SCHOOL_ROLES`）无测试回放 |
| F002 | HIGH | test_gap | 完整性/测试质量 | **valid** | Step 1.2 "6 测试全红" 不成立：`test_platform_admin_creates_academic_director` + 其他弱断言测试在现状代码下会直接绿（Pydantic v2 extra='ignore' + UserRole.school_id nullable） |
| F003 | HIGH | defect_fix | 自洽性/行为契约 | **valid** | `openCreate` 不重置 `form.roles`，超管跨校打开表单默认 `['subject_teacher']`，用户不改角色直接保存会造出"景炎 subject_teacher 跨校账号"，偏离"创建学校管理账号"产品意图 |
| F004 | MED | defect_fix | 代码库对齐/范围控制 | **valid** | `roleOptions` 同时服务创建表单（L77）和 Excel 导入（L102 `importRole`），改全局 computed 会连带裁剪导入下拉 → 超出 scope |
| F005 | MED | test_gap | 完整性/测试质量 | **valid** | Task 2 全部 4 测试都用 `wrapper.vm.xxx` 断言，是 `ORC-003` DOM 渲染条件的逻辑镜像；缺 DOM 级入口验证 |
| F006 | MED | process | 自洽性/回滚 | **valid** | Step 3.3 场景 C 用 `localStorage.getItem('edu_cloud_token')`，实际键名是 `'token'`（已 grep 确认 `frontend/src/stores/auth.js:32/67/117`）；场景 A/D 在生产 mcu.asia 创建真实账号无 cleanup |
| F007 | MED | process | 完整性/审查流程 | **valid** | plan 缺每 Task 的"审查清单"和"边界条件 ≥3"段，违反 review-templates.md:206-215 writing-plans 必填要求 |

## R2 升级判定

按 codex-review skill §Gate 条件 R2 允许条件：
- Tier = T4？**否**（T3）
- topic 含 remote/deploy/publish？**否**
- **跨模块重构（plan 声明修改文件数 ≥2 且涉及 ≥2 个模块）？是** —— plan 修改 `src/edu_cloud/modules/student/teacher_router.py`（后端 student 模块）+ `frontend/src/pages/TeachersPage.vue`（前端 pages 模块）+ `frontend/src/api/schools.js`（前端 api 模块），≥3 文件 ≥2 模块

**结论：R2 允许**。

## 处置动作

F001-F007 全部 valid，按 finding 逐条在 plan 中修订：

| Finding | 修订位置 | 动作 |
|---|---|---|
| F001 | Task 1 Step 1.1 测试文件 + Self-Review §5 ORC-004 映射 | 新增测试 `test_platform_admin_creates_subject_teacher_cross_school` 断言 201 + role 落库 + ORC-004 双映射到 Step 1.1 此用例 + Step 2.1 |
| F002 | Task 1 Step 1.1 测试 + Step 1.2 描述 | `test_platform_admin_creates_academic_director` 加 `UserRole.school_id` 落库断言；`test_platform_admin_creates_principal_in_target_school` 已有此断言保留；Step 1.2 描述修正为"现状代码下 orphan_principal 和 subject_teacher 跨校这 3 个测试 FAIL（422/403/body 不匹配），其他 3 个测试 PASS 但在加强断言后也会 FAIL（school_id 落库不对）" |
| F003 | Task 2 新增 Step 2.6a（或放进 Step 2.7 前）+ 测试 Step 2.1 新增用例 | `openCreate()` 在 `isPlatformAdmin && selectedSchool` 时把 `form.roles` 初始化为 `['principal']`（默认管理角色）；新增测试"超管跨校 openCreate 后未手改角色时 form.roles === ['principal']" |
| F004 | Task 2 Step 2.5 重构 | 拆 `createRoleOptions`（computed，跨校裁剪）与 `importRoleOptions`（静态，全集）；模板 L78 用 `createRoleOptions`，L102 用 `importRoleOptions` |
| F005 | Task 2 Step 2.1 测试增强 | 新增 DOM 级断言：`wrapper.find('[data-testid="school-select"]').exists()` 或通过 `wrapper.html()` 搜 `学校` 下拉是否渲染；模板中 `<n-select>` 加 `data-testid` |
| F006 | Task 3 Step 3.3 | token 键改 `'token'`；场景 A/D 末尾追加 cleanup（DELETE /teachers/{id} 或手动登录 mcu.asia admin 删除） |
| F007 | 每 Task 新增"审查清单"+"边界条件（≥3）"段 | Task 1 / Task 2 / Task 3 各补两段 |

## R2 入口预期

修订完成后触发 codex-review plan R2（MCP 路径），预期 GPT 重点核对：
1. ORC-004 双映射（后端 Step 1.1 新 case + 前端 Step 2.1）
2. Step 1.2 红灯描述准确性
3. form.roles 重置逻辑
4. roleOptions 拆分
5. DOM 级测试存在
6. Task 3 token 键与 cleanup
7. 每 Task 审查清单 + 边界条件段

---

## R2 审查结果（2026-04-25T00:05:00+08:00）

**结论：FAIL（但 R1 核心 finding 全部 resolved-correct，残留 3 条均为 process 层）**

原始输出：`docs/plans/.codex-raw-plan-review-super-admin-r2-20260425_000500.log`（sha256 `2802375e...00`）

### R1 finding 核验结果

| ID | Severity | Type | R2 Verification | 依据 |
|---|---|---|---|---|
| F001 | HIGH | test_gap | **resolved-correct** | plan.md:267 新增 `test_platform_admin_creates_subject_teacher_cross_school`；ORC-004 双映射到 semantic_regression |
| F002 | HIGH | test_gap | **resolved-correct** | academic_director 测试加 school_id 落库断言；Step 1.2 红灯表格 6 FAIL + 1 PASS |
| F003 | HIGH | defect_fix | **resolved-correct** | Step 2.6a openCreate 重置 form.roles=['principal']；测试 4 锁 payload.roles |
| F004 | MED | defect_fix | **resolved-correct** | createRoleOptions + importRoleOptions 拆分；模板 L78/L102 分别绑定 |
| F005 | MED | test_gap | **resolved-correct** | data-testid="school-select" + DOM 级 2 测试 |
| F006 | MED | process | **resolved-correct** | token 键改 'token'；Step 3.4 cleanup 步骤 |
| F007 | MED | process | **resolved-partial** | 审查清单已补，但"边界条件"仍嵌在测试契约里，未独立成段 |

### R2 新发现 Finding

| ID | Severity | Category | Type | Evidence |
|---|---|---|---|---|
| R2-F001 | MED | Contract Pack | process | plan 缺结构化 `contract_pack:` 段（~/.claude/config/contract-pack-schema.md 要求 invariants/counter_examples/risk_modules/test_debt 机读段） |
| R2-F002 | MED | 手工验收自洽性 | process | Task 3 写"全集 9 角色"，实际 roleLabels 8 项（grep 核实 `frontend/src/pages/TeachersPage.vue:148`） |

### A/B/C/D/D+/E/E+/F Checklist 结论

| 段 | R2 结论 | 原因 |
|---|---|---|
| A 自洽性 | FAIL | F007 未完成闭环；R2-F002 角色口径冲突 |
| B 代码库对齐 | PASS | - |
| C 架构适配 | PASS | - |
| D 完整性 | FAIL | 审查清单已补但边界条件未独立成段 |
| D+ 测试契约质量 | PASS | F001/F002/F005 有效 |
| E 风险评估 | PASS | - |
| E+ 决策证据 | PASS | - |
| F Contract Pack | FAIL | R2-F001 |

---

## R2 后 轻量补丁（2026-04-25T00:10，不走 gate）

R2 FAIL 禁 R3（gates_lib 入口硬拒）。但 R2 残留 3 条均为 **process / 文档层**（非 defect_fix / 非核心 test_gap），可由 Claude 做轻量补丁 + 用户 manual_override 闭环。

**补丁动作**：

| 残留 | 修复 | plan.md 改动位置 |
|---|---|---|
| R2-F002 typo | "9 个角色" → "8 个角色" | Task 3 边界条件 3 |
| F007 partial | 每 Task 增加独立 `**边界条件（≥3）:**` 段（Task 1: 5 / Task 2: 5 / Task 3: 5） | Task 1/2/3 测试契约后 |
| R2-F001 contract_pack | 新增 `## Contract Pack` 段（YAML 机读：invariants 4 / counter_examples 4 / risk_modules 3 / test_debt 2） | plan 主体 semantic_regression 后 |

**补丁 commit 预期（待后续 commit）**：`docs(plans): super-admin cross-school plan R2 post-fix (3 process findings)`

---

## 最终 Gate 状态与后续决策点

| 项 | 值 |
|---|---|
| plan_review gate status | **R2 FAIL**（不能标 PASS，gates_lib 入口规则约束） |
| R1 核心 finding | 全部 resolved-correct（F001-F006）|
| R2 残留 | 3 process finding，已轻量补丁覆盖 |
| R3 可否再跑？ | **否**（gates_lib 硬拒）|

### 用户可选动作（新会话，需用户判断）

**Option A: manual_override**（推荐，最轻量）
```python
import sys, os; sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import gates_lib, hook_lib
ctx = gates_lib.resolve_gate_context('/home/ops/projects/edu-cloud', hook_lib.SessionState(os.environ['SESSION_ID']))
gates_file = ctx.get('gates_file')
plan_hash = gates_lib.compute_file_hash('/home/ops/projects/edu-cloud/docs/plans/2026-04-24-super-admin-cross-school-account-plan.md')
gates_lib.write_receipt(
    gates_file, 'plan_review', 'manual_override', 'claude+user',
    plan_hash,
    'docs/plans/2026-04-24-super-admin-cross-school-account-plan-review.md',
    round=2,
    reason='R1 核心 F001-F006 全部 resolved-correct；R2 残留 F007 partial + R2-F001/F002 均 process 层且已补丁；core contracts 满足 Gate 1 实质要求',
    subject_ref='docs/plans/2026-04-24-super-admin-cross-school-account-plan.md',
)
```

**Option B: 拆 topic**
- sub-plan A: 核心契约（Task 1 + Task 2 代码改动 + 测试），按本 plan 直接执行
- sub-plan B: 纯文档（contract_pack 形式化 + 边界条件独立段格式化），独立小 topic 单独 PASS 一次

**Option C: WONTFIX 标记 process 残留 + override**
- 用 write_receipt 的 `wontfix` + reason 注明"3 条 process finding 与核心契约正交，不阻塞实现"

**推荐 Option A**：核心契约已锁，process 残留已补丁，manual_override 路径最短且审计证据完整。
