<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-13 06:53:16

## 审查报告: Task 1-18 (Batch 1-6) — Round 1
结论: **FAIL**

GPT Codex 独立审查（commits `2333f64..02423b9`）产出 6 个 finding + 2 个 process finding。

原始输出: `docs/plans/.codex-raw-code-review-20260413-065311.log`
SHA256: `48d0c90674bb1628871413e88c9e4eb2fcdca2731d86c9df61a36841c0129748`

---

### 第一段：测试充分性（Test Adequacy）

GPT 跑 `pytest tests/test_conduct -q` 得 78 passed，但识别出关键分支未覆盖：
- 手机号 / 身份证 绑定模式无入口级测试（只测了 custom）
- Excel 导出 API 无有效测试
- 删除 phone/id_card 分支实现后测试仍全绿

### 第二段：行为正确性（Behavioral Correctness）

**变更理解**：

本批次为德育板块（conduct module）首次实装，包含：
- 8 张 ORM 表（student_profiles / conduct_class_config / conduct_rule_categories / conduct_rule_items / conduct_records / conduct_groups / conduct_group_members / conduct_semesters）
- 5 个新 Permission（VIEW_CONDUCT / MANAGE_CONDUCT / MANAGE_CONDUCT_RULES / MANAGE_CONDUCT_PARENTS / EXPORT_CONDUCT）+ 1 个新 module_code（conduct）
- AES-256-GCM 加密模块（student PII + 绑定验证码）
- 家长端认证/查询/绑定 API + 8 页面 + ParentLayout 独立布局
- 管理端积分/班规/小组/学期/配置/家长管理 API + 9 页面 + 侧栏导航
- Excel/PDF 导出 + 6 个 Agent 工具（conduct 域）

**对抗性审查**：

GPT Reviewer 从 Executor 自审表随机抽检 2-3 项独立验证（边界输入构造、异常路径追踪、假阴性检测）：

1. **抽检"绑定验证码 3 种类型支持"**：实际只 test_parent_bind_child (custom) 有入口级测试，phone/id_card 分支删除后 suite 仍全绿 → 自审失实 → 升为 F006 HIGH
2. **抽检"Excel 导出正确"**：export_service.py 整个模块无测试入口 → 自审失实 → 并入 F006
3. **边界输入构造 F002**：构造外班 rule_item_id 传入 `/classes/A/rules/categories/.../items/X`（X 属于班 B），验证是否可成功修改 → 实际可成功 → 确认越权

5 个 code-bug：
- 数据迁移缺 Alembic revision（F001）
- 管理端跨班越权面（F002）
- Agent 工具绕过 DataScope（F003）
- 家长端规则页前后端字段不一致（F004）
- phone 验证模式数据源错误（F005）

### 第三段：未测试风险（Non-tested Risks）

- 导出 API 无任何测试覆盖
- phone/id_card 绑定分支未覆盖

---

### 发现清单

#### F001 — Alembic 迁移缺失

- **Status**: verified
- **Severity**: HIGH
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 当前分支只有 `create_all` 的开发态建表路径，既有环境没有可执行的 conduct schema 迁移，也没有 upgrade/downgrade 验证。
- **After-behavior**: conduct 模块必须通过 Alembic revision 在既有库上可升级、可回滚。
- **Evidence**: plan.md#L32, plan.md#L246, plan.md#L2068, review-handoff-batch1.md#L8, review-handoff-batch1.md#L50
- **Impact**: 这批功能无法安全上线到已有数据库；Task 1 和 Task 18 的迁移契约实际上未兑现。
- **Inv-conflict**: direct（违反"所有 schema 变更通过 Alembic 管理"不变量）
- **Repair hypothesis**: 补齐独立 revision 和迁移测试，不要继续以启动时 `Base.metadata.create_all()` 代替正式迁移。

#### F002 — 管理端跨班越权

- **Status**: verified
- **Severity**: HIGH
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 多个管理端端点只检查"有无 conduct 权限"，不校验路径里的 `class_id` 与资源归属是否一致；拿到外班资源 ID 后可以跨班改规则、删小组、改学期。
- **After-behavior**: 所有 `/{class_id}/.../{resource_id}` 写接口都应同时验证"当前角色可见该班级"且"该资源属于该班级"。
- **Evidence**: deps.py#L71, admin_router.py#L199/L210/L222/L281/L293/L305/L344, rules_service.py#L67/L83/L97, admin_service.py#L512/L525/L552/L624
- **Impact**: 直接越权面，影响规则、分组、学期等核心配置数据。
- **Inv-conflict**: direct（违反"所有资源访问经 scope filter"不变量）
- **Repair hypothesis**: 统一在 class-scope/resource-affinity 守卫层；避免堆叠单端点临时 if 判断。**requires independent fix design + Semantic Regression Gate**

#### F003 — Agent 工具绕过 DataScope

- **Status**: verified
- **Severity**: HIGH
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 6 个 conduct Agent tools 基本都直接信任传入的 `class_id`/`student_id`，没有按 `ctx.class_ids` 或学生归属做裁剪；`add_conduct_points` 甚至可写入任意传入班级。
- **After-behavior**: 工具层必须与现有 analytics/students 工具一样，先做 scope 交集，再决定是否读写。
- **Evidence**: ai/tools/conduct.py#L41/L114/L202/L266/L333/L363
- **Impact**: 绕过平台已有的 AI DataScope 约束，既有读越权也有写越权。
- **Inv-conflict**: direct（违反"AI 工具调用经 DataScope 约束"不变量）
- **Repair hypothesis**: 复用现有 `ctx.class_ids` / student scope 模式，禁止在 conduct 工具里引入新的"默认放行"分支。**requires independent fix design + Semantic Regression Gate**

#### F004 — 家长端规则页契约不一致

- **Status**: verified
- **Severity**: MED
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 家长端"班规"页依赖 `currentChild.class_id` 才会请求规则，但后端 `get_children()` 不返回 `class_id`；同时页面渲染取的是 `item.default_points`，而后端实际返回 `item.points`。
- **After-behavior**: 家长规则页应能拿到当前孩子班级 ID，并正确显示规则分值。
- **Evidence**: parent_service.py#L259, ParentRules.vue#L17, ParentRules.vue#L47, parent_service.py#L407, test_parent_api.py#L118
- **Impact**: `/parent/rules` 主路径当前实际不可用。
- **Inv-conflict**: possible
- **Repair hypothesis**: 对齐 parent child payload 与页面字段契约，并补前后端联调级回归测试。

#### F005 — phone 验证模式数据源错误

- **Status**: verified
- **Severity**: MED
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 当班级把 `verify_code_type` 切到 `phone` 时，绑定逻辑会去 `decrypt(profile.emergency_contact_phone)`；但设计里 `emergency_contact_phone` 不是加密字段，Task 6 也只提供了 `verify_code` 的配置路径。
- **After-behavior**: phone 模式应使用 `student_profiles.verify_code` 字段（与 custom 模式共享存储路径），`verify_code_type` 只决定"对比哪种输入类型"的 UX 提示。
- **User decision**: 采用 **Option A**（用户 2026-04-13 确认）—— phone/custom 共享 `verify_code` 字段，id_card 仍独立走身份证号后 6 位比对
- **Evidence**: design.md#L57, design.md#L236, plan.md#L1394, parent_service.py#L192, test_admin_api.py#L27
- **Impact**: 一旦真实班级启用 phone 验证，家长绑定会系统性失败。
- **Inv-conflict**: direct（违反设计 §3 契约）
- **Repair hypothesis**: phone 分支改为读 `profile.verify_code`（明文对比前可选加密/不加密，与 custom 分支逻辑一致）。

#### F006 — 绑定与导出测试缺失

- **Status**: verified
- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Before-behavior**: 当前回归集对 `phone/id_card` 绑定分支和导出 API 没有有效覆盖；删掉这些分支/处理器，suite 仍可保持全绿。
- **After-behavior**: 绑定的 3 种验证模式和 `export/records`、`export/rankings` 至少各有一条能在错误实现下失败的入口级测试。
- **Evidence**: test_parent_api.py#L82/L125, test_admin_api.py#L27, admin_router.py#L349, export_service.py#L17
- **Impact**: 当前"78 passed"不能证明导出功能和非 custom 绑定模式可用。
- **Inv-conflict**: none
- **Repair hypothesis**: 先补入口级红测（删除实现后测试会失败），再修实现；避免只加 `assert resp.status_code == 200` 弱断言。

---

### Process Findings

- **P1**：plan 里没有 Contract Pack 段，只有测试契约段。不阻断本轮，但未来 T4 计划需补齐。
- **P2**：handoff 的 verification 映射不准确——"预审自检"未列导出和 id_card/phone 绑定覆盖，但审查清单却声明"绑定验证码 3 种类型支持"+"Excel 导出正确"。Executor 需在 Round 2 交接单中修正。

---

### PASS/FAIL 判定

- 4 个 HIGH code-bug/test-gap + 2 个 MED code-bug 均未修复 → **FAIL**
- 无 behavior_change finding，全部 defect_fix，无需用户批准
- 所有 6 个 finding 都必须在 Round 2 解决

### 行为变更审批记录

无 behavior_change finding，本节空。

---

### Round 2 修复方向

按修复风险分两类：

**低风险（直接修）**:
- F001：Alembic autogenerate revision + 迁移测试
- F004：parent_service 返回 class_id + ParentRules.vue 字段改 `item.points`
- F005：phone 分支读 `profile.verify_code`（用户选 Option A）
- F006：补入口级测试

**高风险（需独立修复设计 + Semantic Regression Gate）**:
- F002：class-scope/resource-affinity 统一守卫层
- F003：Agent 工具 DataScope 集成

F002/F003 涉及架构层守卫，Executor 修复前需先输出 Fix Intent Card。
