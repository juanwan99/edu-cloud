[edu-cloud] GPT Reviewer R2 | 2026-04-17 22:50 (UTC+8)

## 审查报告（R2）: Task 1-6（含 R1 处置）
结论: FAIL

plan SHA256: `97894724dc50cb54afc69418deead1ba90b292990eb169b4d3febfa1bba2feb0`
raw log SHA256: `90e2f2a966cfd7ccdc8c2431fe522e905ec38822229b38602bb8031bea24c4e4`
raw log path: `docs/plans/.codex-raw-plan-review-20260417-r2.log`
plan commit: `8e4f11b`
review trigger: codex-review skill via AIPROXY gpt-5.4 (codex v0.121.0)

## R2 认可的 R1 修复（已真正回填，不再附录式）

- Task 1-5 的 `state.json` `N.0/N.final` 步骤已写回正文（每 Task 两个 state Step 插入主体 + commit staged 加 state.json）。
- Task 3/5 的入口级测试、治理测试段已写回主 Task（新 Step 3.4a/3.4b/5.2a/5.2b）。
- Contract Pack 根键和字段名已改为 `contract_pack / statement / pending_test / module / YYYY-MM-DD`，未再看到 R1 的 `rule / new_test / path / 非日期 deadline`。

## R2 剩余阻塞问题（6 条，全部 defect_fix）

### R2-F001
- ID: R2-F001
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: Task 3 声称已把 T1 的 API 403 入口级测试回填进主步骤，但回填后的测试样例本身不可执行。
- After-behavior: 主 Task 中的入口级测试样例应直接引用真实模型路径，能按现有 harness 落地运行。
- Evidence: `plan.md:606-613` 在测试里写 `from edu_cloud.modules.student.models import UserRole, User`；而实际 `User` 定义在 `src/edu_cloud/models/user.py:9-18`，`UserRole` 在 `src/edu_cloud/models/user_role.py:8-24`，`src/edu_cloud/modules/student/models.py:8-39` 只有 `Class/Student`。现有 conduct 测试夹具使用 `tests/test_conduct/conftest.py:1-7` 的真实导入路径。
- Impact: F006 在 Task 3 的"已回填"只是形式回填，Executor 按正文写测试会先在 import 处失败，根本到不了 API 403 验证。
- Repair hypothesis: 统一对齐到现有 conduct test harness 的用户/角色模型导入路径，并复用现有 fixture 模式，避免在主 Task 中留不可运行样例。

### R2-F002
- ID: R2-F002
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: Task 4 主体仍残留 R1 时代的测试文件与断言口径，和"已回填到主 Task body"的说法冲突。
- After-behavior: Task 4 的 Steps、测试契约、命令应统一使用 `test_admin_crud_api.py` 和 "POST 200 + DB readback" 口径。
- Evidence: Files 段已改成 `plan.md:849-855` 的 `admin_router.py + test_admin_crud_api.py`，但 Step 4.2 仍写"在 `test_admin_api.py` 末尾追加"见 `plan.md:897-900`，测试契约命令仍指向 `test_admin_api.py` 见 `plan.md:1169-1183`，且反例还在写旧式 `assert data[0]["date"]` 见 `plan.md:1164-1167`。实际 points CRUD 测试文件是 `tests/test_conduct/test_admin_crud_api.py:1-32`。
- Impact: Executor 会按正文去改错文件、写错断言；这不是附录残留，而是主 Task 仍未清干净的 R1 口径。
- Repair hypothesis: 把 Task 4 的 Step 4.2、三条测试契约命令、反例描述全部收敛到 `test_admin_crud_api.py` 与 DB readback；禁止再混用旧 `test_admin_api.py` 口径。

### R2-F003
- ID: R2-F003
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: Task 5 虽把 F006/F007 回填进主步骤，但回填后的测试步骤依然不可直接执行，也不验证真实集成链路。
- After-behavior: Task 5 主体需要显式描述可运行的测试 harness 改造，并把必需的视图文件纳入 Files 范围。
- Evidence:
  - Step 5.2a 要求"在 `sidebarConfig.conduct.test.js` 末尾追加"并同时追加新的 `import` 语句，见 `plan.md:1312-1331`；该文件当前已有顶层 import，见 `sidebarConfig.conduct.test.js:10-12`，按正文做会生成非法 ESM。
  - Step 5.2b 要求直接往 `AppSidebar.test.js` 末尾加入口级测试，见 `plan.md:1339-1356`，但该测试文件当前在文件顶部全局 mock 了 `getSidebarItems`，见 `AppSidebar.test.js:7-14`，新 case 不会测到真实 `sidebarConfig.js`。
  - 正文要求用 `[data-module="conduct"]` 定位，见 `plan.md:1411-1412`，而当前 `frontend/src/components/shell/AppSidebar.vue:10-19` 没有该属性；但 Task 5 Files 段只列了 3 个文件，见 `plan.md:1189-1193`（未含 AppSidebar.vue）。
- Impact: Task 5 的"已回填"仍带着执行陷阱。F006/F007 在主文里不是缺席，而是写成了不可直接落地的步骤。
- Repair hypothesis:
  1. 可能的修复方向是把 Task 5 明确拆成"真实 sidebarConfig 集成测试 harness 调整"和"渲染层定位属性/替代定位策略"两部分，并把必须修改的视图文件加入 Files。
  2. 禁止通过继续扩大 mock、或把 mock 返回值直接改成 7 项来制造假绿。
  3. requires independent fix design + Semantic Regression Gate

### R2-F004
- ID: R2-F004
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: T2 仍被主文表述为"班主任补录历史日期积分真可用"，但正文步骤又允许完全跳过前端，现代码也没有日期输入入口。
- After-behavior: T2 要么被收窄成后端 API 契约修复，要么主 Task 必须补齐明确的 UI 规格、前端字段改造和入口级验证。
- Evidence: 主步骤写"若前端目前根本没传 date 字段，跳过前端改动"，见 `plan.md:1072-1079`；但审查清单仍宣称"班主任补录历史日期积分真可用"，见 `plan.md:1144-1152`。当前 UI 在 `frontend/src/pages/conduct/ConductPoints.vue:53-76` 没有日期控件，提交时仍发 `note` 而非 schema 所需 `reason`，见 `ConductPoints.vue:191-215`；API 层只是透传，见 `frontend/src/api/conduct.js:43-46`。
- Impact: T2 的 UX 规格与主步骤不自洽，且与现代码不对齐。按当前 plan 执行，最多只能保证"后端接受 `record_date`"，达不到正文承诺的用户可达行为。
- Repair hypothesis: 在主 Task 中二选一写死目标边界。不要一边允许跳过前端，一边继续把"历史日期补录可用"当作退出语义。

### R2-F005
- ID: R2-F005
- Severity: HIGH
- Category: design-concern
- Type: defect_fix
- Before-behavior: 文档体系对 `subject_teacher 2→4` 同时给出"已批准"和"待二次确认"两种状态。
- After-behavior: design/plan/gates 应只保留单一审批真相；既然已有精确批准，正文不应再保留待确认表述。
- Evidence: plan 主文已写"已批准"，见 `plan.md:1302`；gates 也已记录 `approved`，见 `gates.json:27-33`。但 design 主体仍写"需在 Plan Review 中独立标注并请用户二次确认"，见 `design.md:238-240`，风险段也仍写"列入 Plan Review 独立确认"，见 `design.md:342-345`。
- Impact: 审批审计链存在双口径，用户点名要求排查的"待二次确认"残留仍在主设计正文，不是只在历史附录里。
- Repair hypothesis: 统一清理 design 正文中的 pending 话术，把保守 2 项方案保留为 rejected alternative 即可，不要继续悬空。

### R2-F006
- ID: R2-F006
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: Contract Pack 字段名虽已对齐 schema，但仍有 invariant 把两个语义绑在一条里，只给了一个验证映射。
- After-behavior: 每条 invariant 应只陈述一个可验证语义，verification/test_ref 必须完整覆盖该语义。
- Evidence: `INV-T1-003` 在 `plan.md:1962-1965` 同时声称"API 403"与"ToolAccessResolver 过滤 6 conduct AI tools"，但唯一映射的 `test_ref` 只是 `test_lesson_prep_leader_cannot_call_conduct_api`；Task 3 主步骤和测试契约里也没有任何 ToolAccessResolver/AI tool 过滤测试，见 `plan.md:597-648` 与 `plan.md:838-843`。
- Impact: Contract Pack 现在不是字段名错，而是 verification 映射仍不严谨。F 项检查里的"可验证"要求没有完全满足。
- Repair hypothesis:
  1. 可能的修复方向是把"API 403"与"AI 工具过滤"拆成两条 invariant，并分别映射独立验证。
  2. 禁止继续用一条 invariant 混装多段语义，再用单个 test_ref 代指"整体已验证"；也禁止把未覆盖语义藏进 statement prose。
  3. requires independent fix design + Semantic Regression Gate

## 补充判断
- `Task 1-5 state.json N.0/N.final` 已确实回填进主任务体，这部分不再是 R1 的附录式修补。
- Contract Pack 的 schema 字段名也已回正，不再使用 `rule/new_test/path/非日期 deadline`。
- 但上述 6 条说明：R2 仍未达到"主文 fully back-filled 且可执行"的标准，所以 Gate 1 结论仍是 FAIL。

## R2 结论
**FAIL**（HIGH×5 + MED×1，6 个 defect_fix）

Gate 1 硬拦截继续生效；code_review_batch1 不触发；T1-T5 执行全部 blocked。

## 下一步选项（需用户裁决）

按 CLAUDE.md 全局规则 "T3/T4 plan commit 后 → codex-review plan（gates.json 硬拦截，不过**拆 topic**，**禁 R3+**）"：

| # | 方向 | 说明 |
|---|---|---|
| A | **拆 topic**（推荐）：把批次 1 T1-T5 拆成更小的 topic，每个独立走 Gate 1 | 符合规则；工作量大；需新 design + plan + gates |
| B | **用户 override 禁令**允许 R3 继续修 plan | 违反 "禁 R3+"；需用户明示授权；R3 修 6 findings 后再跑 review |
| C | **缩小 plan 范围**到 R2 已 PASS 子集：仅 T5（文档数字）+ T4（MODULE.md）+ F004 state.json 机制 | 保留 R2 认可的部分；T1/T2/T3 延后（因为 R2-F001/002/003 全部卡住它们） |
| D | **放弃批次 1**，接受 FAIL 状态，批次 2/3 也相应延后 | 最低风险；T1-T5 所解决的治理债继续存在 |

R2-F004 额外含**behavior_change 子决策**（T2 收窄成"后端 API 契约修复"vs补齐完整 UI 规格），需独立 L017 批准。
