[edu-cloud] GPT Reviewer R4 | 2026-04-18 (UTC+8)

## 审查报告（R4）: R3 5 findings 复核 + 全量 checklist
结论: FAIL

plan SHA256 (R4 subject): `(commit a93a765 的 plan.md，R3 回执 subject_hash 仅占位，待重算)`
raw log SHA256: `4eab48d37fca8c47e1f630b12b916c1384c7c4f0d71053d85583a4283cac5428`
raw log path: `docs/plans/.codex-raw-plan-review-20260417-r4.log`
review trigger: codex-review skill via AIPROXY gpt-5.4 (codex v0.121.0)
override 声明: 用户 2026-04-17 明示 override "禁 R3+"（"修复 然后继续审查"，持续生效至 R4）

## R3 五项复核（R4 verify —— 全部 resolved ✅）

| R3 ID | R4 Status | 证据 |
|---|---|---|
| R3-F001 | **resolved** | 4 处 AppSidebar.test.js → AppSidebar.conduct.test.js 全部同步（L48 / L1601 / L1634 / L1993） |
| R3-F002 | **resolved** | 文末 § 入口级测试补充 + § CONDUCT_ITEMS 治理测试 已改为"历史坏样例已删除，权威位置见主 Task" 声明；F006 处置总结也按新口径改写 |
| R3-F003 | **resolved** | plan L809 + design L150 已改为 "deferred 到 TD-006 批次 3 D-007" |
| R3-F004 | **resolved** | plan 顶部文件结构表 T2 收窄 / T3 扩容；design §3.1 Task 清单同步 |
| R3-F005 | **resolved** | design §3.4 矩阵行 `subject_teacher` 改后列 2 → 4，与 F005 approved 下方说明一致 |

R3 五项全部 resolved。R4 检出 **3 个新残留**（R4-F001~F003）都是收尾漂移，不涉及方向性问题。

## Checklist 结果
- A 自洽性: FAIL（R4-F002/F003 数字+名词漂移）
- B 代码库对齐: FAIL（R4-F001 提前引用未来文件）
- C 架构适配: PASS
- D 完整性: FAIL（完成标准未统一）
- D+ 测试契约质量: FAIL
- E 风险评估: PASS
- F Contract Pack 完整性: PASS（R3-F006 后续 INV-T1-003/TD-006 已稳定）

## R4 新增 Findings

### R4-F001
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Before-behavior: Task 3 结束时应只跑当时已存在的前端回归集。
- After-behavior: Step 3.11 的命令却提前包含 `AppSidebar.conduct.test.js`，而该文件直到 Task 5 Step 5.2b 才创建。
- Evidence: `plan.md:798/800/1338/1398`
- Impact: Executor 在 Task 3 就会因为引用未来文件而跑出假失败，直接阻断 T1 收尾。
- Repair hypothesis: 把 Step 3.11 命令里的 `AppSidebar.conduct.test.js` 去掉；Expected 数字也需重算（去掉 AppSidebar.conduct 贡献）。

### R4-F002
- Severity: MED
- Category: design-concern
- Type: defect_fix
- Before-behavior: R1-F006/F007 补齐后，批次 1 的通过阈值应统一到后端 129、前端 conduct 29。
- After-behavior: 设计文档 §4/§6 仍写 `125/22`，Task 3 的全量后端期望仍写 `125 passed`，Step 5.5 的全量前端总数也存在算术错误 `72 + 4 + 9 = 77`。
- Evidence: `design.md:332/334/357/358`，`plan.md:28/795/1624/1636/1482`
- Impact: Gate、Executor 和 Reviewer 会面对多套完成标准，可能错误判定是否达标。
- Repair hypothesis: 统一所有摘要层/退出条件/回归期望数字；后端改成 129，frontend conduct 改成 29，全量前端总数按实际重新核算。

### R4-F003
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: Task 2 的 `MODULE.md` 模板正文应与 frontmatter 和 ORM 真值一致。
- After-behavior: 模板正文数据流段把表名写成了 `students_profiles`，与前文 `student_profiles` 和实际 ORM 不一致。
- Evidence: `plan.md:234/340`，`design.md:30`，`models.py:16`
- Impact: 若执行者按模板原文写入，会生成一份正文事实错误的 `MODULE.md`。
- Repair hypothesis: 将 `students_profiles` 改为 `student_profiles`。

## R4 结论
**FAIL**（HIGH×1 + MED×1 + LOW×1，3 个 defect_fix；R3 核心 100% resolved，剩余为收尾数字/文件名漂移）

Gate 1 硬拦截继续生效；code_review_batch1 不触发；T1-T5 执行全部 blocked。

## R5 计划（2026-04-18 进行中）

针对 R4-F001 / F002 / F003 的修复已在 plan (R5 pending commit) 中落地：
- R4-F001: Step 3.11 vitest 命令删除 `AppSidebar.conduct.test.js`，Expected 数字 `125/18 → 126/18`
- R4-F002: plan L1482 算术 `72+4+9=77 → 72+5+10+1=88`；design §4/§6.1 数字统一 `125/22 → 129/29`
- R4-F003: plan/design 全局 `students_profiles → student_profiles`

R5 重审触发后验证。
