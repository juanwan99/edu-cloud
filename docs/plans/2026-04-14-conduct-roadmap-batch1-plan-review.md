[edu-cloud] GPT Reviewer | 2026-04-14 08:45:51
## 审查报告: Task 1-6
结论: FAIL

测试充分性未达到 Gate 1 通过线。T2 已补到入口级 `POST /records + DB readback`，方向是对的；但 T1 与 T3 的正式 `测试契约` 仍分别以 `has_permission` / `hasPermission` 和 `getSidebarItems()` 作为入口，未满足 [`~/.claude/rules-t3/review-templates.md:217-240`](C:/Users/Administrator/.claude/rules-t3/review-templates.md) 对“用户可触达入口”的硬要求。更严重的是，R1 追加的入口级补救和 `CONDUCT_ITEMS.perm` 治理测试只停留在文末“处置总结”，没有回填到各 Task 的主步骤、主文件清单和主测试契约，因此 D/D+ 的硬判定仍然是 FAIL。

行为正确性方面，6 个指定关注点里有 3 个已经可以明确判定。其一，`R-T3-followup` 并非“尚未批准”：[`2026-04-14-conduct-roadmap-batch1-gates.json:31`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json) 已记录用户在 **2026-04-14 07:45:00+08:00** 精确回复“批准 F005”，所以不再需要新的用户批准；真正的问题是 design/plan 正文仍保留“待 Plan Review 二次确认”措辞，形成 bait-and-switch 风险。其二，`_TEACHER_BASE` 当前后端分别是 `set` 与数组，这使 T1 的集合减法在当下可行，但计划里没有可执行的 sentinel/contract test；只有一个格式不合法的 Contract Pack 草案提到延期覆盖，所以这不能算正式防线。其三，`from datetime import date as _date_type` 本身不会破坏 `PointsRecordResponse.date`：字段名仍是 `date`，只改了类型别名，参考 [`schemas.py:40-46`](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/conduct/schemas.py)；真正的链路问题不在 response，而在 Task 4 主步骤仍混用错误测试文件/错误 `git add`，以及前端根本没有“补录历史日期”的 UI 入口。

未测试风险主要集中在 4 个点。第一，`hasPermission()` 对未知 permission 会静默返回 `false`，见 [`frontend/src/config/permissions.js:65-67`](C:/Users/Administrator/edu-cloud/frontend/src/config/permissions.js)；这意味着任何 `CONDUCT_ITEMS` typo 都会被误解释成“设计如此”，而主 Task 5 还没有把治理测试真正纳入执行步骤。第二，`state.json` 的状态词汇本身与项目约定一致，`pending → in_progress → completed` 也确实是 executing-plans 规范要求的迁移；但主 Task 6 依旧把 `state.json` 当成收尾产物创建，执行期会缺权威 sidecar。第三，当前 [`ConductPoints.vue:55-75`](C:/Users/Administrator/edu-cloud/frontend/src/pages/conduct/ConductPoints.vue) 与 [`ConductPoints.vue:207-215`](C:/Users/Administrator/edu-cloud/frontend/src/pages/conduct/ConductPoints.vue) 没有日期输入，也没有 `record_date` 字段，甚至仍发送 `note` 而非 schema 要求的 `reason`；因此计划声称的“班主任补录昨天积分真可用”并不会因为只改 schema/router 而自然成立。第四，架构方向总体没有反向依赖或循环依赖问题，但 T2 若要兑现用户可达的补录功能，实际上已跨 schema/router/api/Vue/test 多层联动，计划需要更明确的 UX 切片和真实入口验证，而不是继续停留在 API 层自证。

## 发现清单

### G1-001
- ID: G1-001
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: 主计划仍要求在 Task 6 才创建 `state.json`，执行 Task 1-5 期间没有权威状态 sidecar。
- After-behavior: `state.json` 应在 Gate 1 PASS 后即创建，并在每个 Task 进入/完成时执行 `pending → in_progress → completed` 迁移。
- Evidence: [`~/.claude/rules-t3/review-templates.md:244-260`](C:/Users/Administrator/.claude/rules-t3/review-templates.md) 明确要求 Gate 1 后生成 `state.json` 且 executing-plans 在每个 Task 迁移状态；但 [`2026-04-14-conduct-roadmap-batch1-plan.md:1263-1316`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 仍把 `state.json` 标为 Task 6 `Create` 并在 Step 6.2 一次性写出“前 5 个 completed”；同一文件的“R1 Findings 处置总结”又在 [`1497-1518`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 说明正确模型应是 Gate 1 后先建、逐 Task 迁移。
- Impact: 执行器若按主步骤走，会在 Task 1-5 期间失去规范要求的状态跟踪；Task 6 也会生成一个与执行期真实轨迹脱节的“终态快照”。这直接违反 Gate 1 对 state sidecar 生命周期的硬要求。
- Repair hypothesis: 1. 可能的修复方向是把“Gate 1 后创建 + 每 Task 迁移”的模型真正合并回 Task 1-6 主步骤，并把 Task 6 改成只做最终更新。 2. 禁止继续保留“正文一种生命周期、附录另一种生命周期”的双真相；也禁止用 Task 6 一次性回填全部状态来规避执行期迁移。 3. requires independent fix design + Semantic Regression Gate

### G1-002
- ID: G1-002
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: 计划宣称已补 Contract Pack，但当前段落不符合 schema，实际上不能作为正式 Contract Pack 通过审查。
- After-behavior: 计划应包含一个满足 schema 的结构化 `contract_pack:` 段，且 invariants / counter_examples / risk_modules / test_debt 均可被验证。
- Evidence: [`~/.claude/config/contract-pack-schema.md:7-44`](C:/Users/Administrator/.claude/config/contract-pack-schema.md) 要求 invariant 用 `statement`、`verification` 只能是 `existing_test|pending_test|uncovered`、`risk_modules` 键名是 `module`、`test_debt.deadline` 必须是 `YYYY-MM-DD`。但 [`2026-04-14-conduct-roadmap-batch1-plan.md:1639-1766`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 里 invariant 使用 `rule` 而非 `statement`，`verification` 是嵌套对象且值为 `new_test`，`risk_modules` 使用 `path`，`test_debt` 多个 `deadline` 不是纯日期（如 `2026-05-15（批次 3 启动时）`、`deferred（无阻塞需求）`）。
- Impact: 按用户给定的 F 项检查，这份 plan 仍然属于“缺 Formal Contract Pack / Contract Pack 不可验证”的 FAIL；分散在每个 Task 里的审查清单和边界条件不能替代 schema 化 Contract Pack。
- Repair hypothesis: 1. 可能的修复方向是按 schema 重新落一个可机读、可核验的 `contract_pack:` 真正单源，并把现有 prose/附录信息压缩映射进去。 2. 禁止继续用“看起来像 Contract Pack 的 YAML 片段”替代 schema；也禁止把多测试引用、延期理由、风险模块路径写成自由 prose。 3. requires independent fix design + Semantic Regression Gate

### G1-003
- ID: G1-003
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: Task 4 虽在 Files 段承认真实改动点是 `admin_router.py` 与 `test_admin_crud_api.py`，但主步骤、验证命令和 `git add` 仍指向旧文件，执行时会跑偏。
- After-behavior: Task 4 的所有步骤、命令和 staging 清单都应与真实 touched files 保持一致。
- Evidence: Task 4 Files 段在 [`686-695`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 已写明要改 `admin_router.py`、新增测试放在 `test_admin_crud_api.py`；但 Step 4.2 仍说“在 `tests/test_conduct/test_admin_api.py` 末尾追加”见 [`720-723`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)，Step 4.6 仍运行 `pytest tests/test_conduct/test_admin_api.py -k "record_date or add_points"` 见 [`874-880`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)，Step 4.9 仍 `git add ... admin_service.py ... test_admin_api.py` 且漏掉 `admin_router.py` 见 [`911-917`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)。实际代码库里 points CRUD 测试文件确实是 [`tests/test_conduct/test_admin_crud_api.py`](C:/Users/Administrator/edu-cloud/tests/test_conduct/test_admin_crud_api.py)，而 `data.date` 残留点也确实在 [`admin_router.py:115`](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/conduct/admin_router.py) 与 [`admin_router.py:137`](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/conduct/admin_router.py)。
- Impact: Executor 按计划执行会把真实 router 变更漏出 commit，或者在错误测试文件上得到假绿；scope_guard 与 Gate 2 也会因此接收到错误的 staged 面。
- Repair hypothesis: 将 Task 4 的步骤、验证命令和 `git add` 清单统一对齐到 `admin_router.py` + `test_admin_crud_api.py`，并把“verify only”的 `admin_service.py` 从 staging 示例中剔除。

### G1-004
- ID: G1-004
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: 计划把 T2 描述为“班主任补录昨天积分功能真可用”，但当前前端没有日期输入入口；即便 schema/router 修好，用户仍无法从 UI 触达该能力。
- After-behavior: 要么把 T2 明确收窄为 API 契约修复，要么补齐明确的前端 UX 规格、表单字段与入口级验证，使“历史日期补录”成为真实可达行为。
- Evidence: 设计文档把 T2 的关键行为写成“班主任补录昨天积分功能真可用”，见 [`design.md:198-203`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-design.md)；计划也在 [`947-955`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 与 [`895-901`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 沿用了这一表述，甚至允许“若前端根本没传 date 字段则跳过前端改动”。但当前 [`ConductPoints.vue:55-75`](C:/Users/Administrator/edu-cloud/frontend/src/pages/conduct/ConductPoints.vue) 只有积分与原因，没有日期控件；[`ConductPoints.vue:191-215`](C:/Users/Administrator/edu-cloud/frontend/src/pages/conduct/ConductPoints.vue) 的请求体也没有 `date/record_date`，反而仍提交 `note`；[`frontend/src/api/conduct.js:43-46`](C:/Users/Administrator/edu-cloud/frontend/src/api/conduct.js) 只是透传数据。
- Impact: T2 现有 plan 最多能修到“后端 API 可接受 `record_date`”，达不到设计里承诺的用户可达补录体验；这同时造成 UX 规格缺失与行为正确性过度承诺。
- Repair hypothesis: 在 plan 中二选一明确下来：要么把 T2 目标改成“后端契约修复，前端仍不提供历史日期输入”；要么补一条显式 UI slice（日期控件、字段名、提交 payload、入口测试），并同步更新退出条件与测试基线。

### G1-005
- ID: G1-005
- Severity: MED
- Category: test-gap
- Type: defect_fix
- Before-behavior: T1 与 T3 的正式测试契约仍然是 helper/config 级自证，入口级补救没有真正落回主 Task，因此行为变更仍可在缺少用户可触达验证的情况下“通过”。
- After-behavior: 每个 behavior_change Task 都应在主 `测试契约` 中包含入口级 slice，并把附录里的补充测试、文件清单、命令与现有 harness 对齐。
- Evidence: 审查模板在 [`review-templates.md:217-240`](C:/Users/Administrator/.claude/rules-t3/review-templates.md) 与 [`275-280`](C:/Users/Administrator/.claude/rules-t3/review-templates.md) 明确规定入口必须是用户可触达入口，否则 `test-gap MED`。但 T1 的 3 个 slice 仍是 `has_permission()` / `hasPermission()`，见 [`plan.md:661-682`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)；T3 的 3 个 slice 仍是 `getSidebarItems(role)`，见 [`1235-1256`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)。文末虽追加了 API 403 与 `AppSidebar` 测试草案，见 [`1561-1634`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md)，但它们既没回填到对应 Task 的主 `测试契约`，也没完全对齐当前 harness：例如现有 [`frontend/src/__tests__/AppSidebar.test.js:7-14`](C:/Users/Administrator/edu-cloud/frontend/src/__tests__/AppSidebar.test.js) 先把 `getSidebarItems` 整体 mock 成静态数据，附录里的 7 项 conduct 断言并不能直接落下。
- Impact: D+ 的硬判定仍成立：T1/T3 存在“无入口级验证”的 MED test-gap；同时 `unknown_perm` 静默失效治理测试也只在附录里，主 Task 5 仍缺少真正会被执行的 typo 守卫。
- Repair hypothesis: 把 T1/T3 的入口级 slice 直接写回各自 Task 的正式 `测试契约`，同步更新 Files/Steps/命令，并把 `CONDUCT_ITEMS.perm` 合法性测试纳入 Task 5 主流程而不是附录。

### G1-006
- ID: G1-006
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: 当前审计材料对 `R-T3-followup` 同时给出“已批准”和“待二次确认”两种状态，审批口径不自洽。
- After-behavior: 计划、设计和 gates 应只保留一个权威审批状态；既然已有精确批准记录，正文就不应继续把该行为写成待确认。
- Evidence: 设计文档仍写“需在 Plan Review 中独立标注并请用户二次确认”，见 [`design.md:238-240`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-design.md)；Task 5 仍在 [`1088`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 与 commit message [`1209-1210`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 里把 `subject_teacher 2→4` 表述为待 Plan Review 独立确认。与此同时，计划的 R1 处置总结在 [`1484`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md) 明确称其“approved”，而 [`gates.json:31`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json) 已记录用户在 **2026-04-14T07:45:00+08:00** 精确回复“批准 F005”。
- Impact: 这不会再触发新的“必须先征得用户批准”的阻塞，但会给 Planner/Executor/Reviewer 留下双重口径：一部分文本把 2→4 当已定事实，另一部分文本又把它当待确认分支，存在明显 bait-and-switch 风险。
- Repair hypothesis: 在 design.md、plan.md 主 Task 与 gates.json 三处统一审批状态，并把“保守方案 allowed_roles 白名单”保留为 rejected alternative，而不是继续悬空。

## 行为变更审批记录

本次无新增 `behavior_change` finding；现有审批状态经审计如下：

| Finding / Record | 行为变更摘要 | 用户决定 | 理由 |
|---|---|---|---|
| R-T1 | 回收 `lesson_prep_leader` 的 conduct 权限 | approved | 设计文档 §9 记载，用户原话“备课组长和打分没关系” |
| R-T2 | `AddPointsRequest.date` → `record_date` | approved | 设计文档 §9 记载，用户原话“两个都批准” |
| R-T3 | sidebar 改为按 permissions 派生（acad 3→7，grade 3→5） | approved | 设计文档 §9 记载，用户原话“两个都批准” |
| R-T3-followup / F005 | `subject_teacher` conduct 入口 2→4 | approved | [`gates.json:31`](C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json) 记录用户于 **2026-04-14 07:45:00+08:00** 精确回复“批准 F005”；但正文仍残留“待二次确认”措辞，见 G1-006 |

结论: FAIL
