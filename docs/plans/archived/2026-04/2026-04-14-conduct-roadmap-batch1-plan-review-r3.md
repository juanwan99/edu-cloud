[edu-cloud] GPT Reviewer R3 | 2026-04-17 (UTC+8)

## 审查报告（R3）: R2 6 findings 复核 + 全量 checklist
结论: FAIL

plan SHA256 (R3 subject): `97894724dc50cb54afc69418deead1ba90b292990eb169b4d3febfa1bba2feb0`（commit 2d8f244 的 plan.md）
raw log SHA256: `4c7b3b6504ca9e45968e8e1a4af307553c08a8243e772624238177c629d9821c`
raw log path: `docs/plans/.codex-raw-plan-review-20260417-r3.log`
review trigger: codex-review skill via AIPROXY gpt-5.4 (codex v0.121.0)
override 声明: 用户 2026-04-17 明示 override "禁 R3+" 规则（"修复 然后继续审查"）

## R2 六项复核（R3 verify）

| R2 ID | R3 Status | 证据 |
|---|---|---|
| R2-F001 | **resolved** | Task 3 Step 3.4a import 路径已改为 `edu_cloud.models.user`+`user_role`，复用 conftest pattern（`set_password` + `create_access_token({sub, role})`） |
| R2-F002 | **resolved** | Task 4 Step 4.2 锁 `test_admin_crud_api.py`；反例断言 `assert str(rec.date)`；3 条测试契约命令统一 |
| R2-F003 | **partially-resolved** | 主 Task 已拆 Step 5.2a Part A/B + 新建 `AppSidebar.conduct.test.js` + 纳入 `AppSidebar.vue` + Step 5.3 `data-module`；但主文其余位置仍残留旧文件名（测试契约命令 L1601 / Task 6 回归 L1634 / Contract Pack test_ref L2060 / 顶部文件映射 L48）→ R3-F001 |
| R2-F004 | **partially-resolved** | Task 4 正文已收窄后端；design §3.3 已同步；但 plan 顶部文件结构表 L47 仍写 T2 含 frontend + design §3.1 Task 清单 L127 仍写 T2 含后端+前端 → R3-F004 |
| R2-F005 | **partially-resolved** | pending 措辞清掉；但 §3.4 矩阵行 L238 仍写 `subject_teacher` 改后 2 项（应为 4 项）→ R3-F005 |
| R2-F006 | **partially-resolved** | Contract Pack INV-T1-003 已收窄；TD-006 已拆出 ToolAccessResolver；但批次 1 关键行为 L809 / design L150 仍写 AI tool filter（应 deferred）→ R3-F003 |

## Checklist 结果
- A 自洽性: FAIL（跨段口径未同步）
- B 代码库对齐: FAIL（旧测试文件名残留）
- C 架构适配: PASS
- D 完整性: FAIL
- D+ 测试契约质量: FAIL（测试契约命令指错文件）
- E 风险评估: PASS
- F Contract Pack 完整性: FAIL（test_ref 指旧文件）

## R3 新增 Findings

### R3-F001
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Before-behavior: R3 已把 T3 入口级测试迁到独立的 `AppSidebar.conduct.test.js`，但主文多个验证面仍引用旧 `AppSidebar.test.js` 或遗漏新文件。
- After-behavior: Task 5 测试契约、Task 6 最终回归命令、Contract Pack `INV-T3-003`、高层文件映射必须统一指向 `AppSidebar.conduct.test.js`。
- Evidence: 新文件已在主步骤落地 `plan.md:1184/1338/1398`；但测试契约仍写旧命令 `plan.md:1601`，Task 6 最终回归漏掉新文件 `plan.md:1634`，Contract Pack `test_ref` 仍指向旧文件 `plan.md:2060`，高层文件映射也未纳入新文件/视图文件 `plan.md:48`。
- Impact: Reviewer/Executor 会跑错测试或漏跑真正的入口级 harness，`INV-T3-003` 的验证映射失真。
- Repair hypothesis: 全量替换旧 `AppSidebar.test.js` 入口级引用，Task 6 回归显式加入新文件，Contract Pack `test_ref` 与文件映射同步更新。

### R3-F002
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: 主步骤已修正 R2-F001/R2-F003，但文末补充段和处置总结仍保留旧的、不可执行的示例。
- After-behavior: 同一 plan 文件只能保留一套可执行口径；旧补充段必须改成与 R3 主步骤一致，或直接删除。
- Evidence: 主步骤已改正 T1 import/JWT 口径 `plan.md:612/634`；但文末补充仍写错 import 与 `active_role_id` `plan.md:1952/1965`。主步骤已改为独立 `AppSidebar.conduct.test.js` `plan.md:1338`，但文末补充仍写追加到 `AppSidebar.test.js` `plan.md:1973`，处置总结也仍写旧文件名 `plan.md:1866`。
- Impact: 同一份计划存在双口径，Executor 复制文末补充会直接回到 R2 已确认错误的实现。
- Repair hypothesis: 重写或删除 `§ 入口级测试补充 / § CONDUCT_ITEMS 治理测试 / 处置总结` 中的历史代码块；禁止把历史坏样例继续保留为可执行正文。

### R3-F003
- Severity: MED
- Category: test-gap
- Type: defect_fix
- Before-behavior: R2-F006 已把 ToolAccessResolver AI tool filter 拆到 `TD-006`，但批次 1 的主 Task/设计仍把它写成当前关键行为。
- After-behavior: 批次 1 T1 的关键行为应收敛到 API 403；AI tool filter 只能以 deferred debt 形式出现。
- Evidence: 批次 1 关键行为仍写 AI tool filter `plan.md:809`、`design.md:150`；而 Contract Pack 已明确拆到 `TD-006` `plan.md:2137`。
- Impact: 批次 1 范围与验证目标继续混语义，D/D+ 仍不干净。
- Repair hypothesis: 删除或改写这些"关键行为"为"deferred 到 TD-006/批次 3"。

### R3-F004
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: R2-F004 的 T2 收窄、R2-F003 的 T3 文件扩容，只在 Task 细节段修了，未同步到高层索引/矩阵。
- After-behavior: plan 顶部"文件结构"表和 design §3.1 Task 清单必须与 Task 4/5 正文文件范围一致。
- Evidence: plan 顶部仍把 T2 写成要改前端文件 `plan.md:47`；Task 4 正文已改成后端-only `plan.md:851`。plan 顶部 T3 仍只写 `sidebarConfig.js` + 一个测试文件 `plan.md:48`；Task 5 正文已纳入 `AppSidebar.vue` 与新测试文件 `plan.md:1180/1184`。design Task 清单也仍保留旧 T2 范围 `design.md:127`。
- Impact: 高层 scope 索引仍会把读者和 scope_guard 引向错误文件边界。
- Repair hypothesis: 同步所有 summary/table 层口径，不允许只有 Task 细节段是对的。

### R3-F005
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: design 已写 F005 获批，但 T3 角色矩阵行仍显示 `subject_teacher` 改后是 2 项。
- After-behavior: 矩阵行与获批说明都应是 4 项。
- Evidence: 矩阵行仍写 2 项 `design.md:238`；下方说明已写获批后应为 4 项 `design.md:240`。
- Impact: A 类自洽性仍脏，但不单独阻塞。
- Repair hypothesis: 直接把矩阵行改成 4 项并去掉问号表述。

## R3 结论
**FAIL**（HIGH×2 + MED×2 + LOW×1，5 个 defect_fix；R2 核心修复方向 100% 承认，问题全是跨段未同步残留）

Gate 1 硬拦截继续生效；code_review_batch1 不触发；T1-T5 执行全部 blocked。

## R4 计划（2026-04-17 进行中）

对应 R3-F001 ~ F005 的修复已在 plan commit `(R4 pending commit)` 中落地，R4 重审触发后验证。
