---
type: handoff
created: 2026-04-13 12:20:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md
round2_review_report: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-review-report-batch1-r2.md
fix_intent_card: C:\Users\Administrator\edu-cloud\docs\plans\.conduct-fix-intent-F002r3-N001.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-gates.json
---

## 约束与偏好（T4 流程）

### 当前阶段
- **T4 德育模块 Gate 2 Round 3 修复**（Round 2 FAIL → 本会话修复）
- SessionState `declared_tier=T4` / `effective_tier=T4` 须先声明
- R2 审查结论 FAIL，6 R1 finding 仅 F003/F005 resolved-correct；新发现 N001 behavior_change
- 用户已 **REJECT** N001（不追认 R2 的"整串相等"新契约）
- F001 deferred（归属 haofenshu-phase1 Migration Gate Repair 独立修复，不在本会话 scope）

### Round 3 任务（已落盘为 plan Batch 7 Task 19-22）
- **Task 19** F002 剩余越权面 — permissions.py 新增 check_rule_item_class + check_students_class；admin_router 补 3 端点调用；+3 红测
- **Task 20** N001 回退 — parent_service.py 改 `stored[-6:] != verify_code`；修正 test_parent_bind_id_card_mode；+2 新红测
- **Task 21** F004 前端字段 — 新建 ParentRules.spec.js（vitest + happy-dom）
- **Task 22** F006 导出断言 — openpyxl 解包读 cell，修复 test_export_records_excel 的 operator_id inner join 过滤问题
- **Task 23** 收尾 — 全量测试 + 审查交接单 + codex-review R3

### 关键约束（前会话踩过的坑，必读）

**① 工作区有 6 个 alembic migration 文件的未 commit 修改**（`git status` 可见）：
- 这些修改属 **haofenshu-phase1 F001 Migration Gate Repair** 独立修复产物
- 溯源文件 `docs/plans/2026-04-13-migration-gate-repair-design.md`（10:51 创建，标注"待用户批准"）
- **⛔ 本会话禁止 commit 这些 alembic 文件**（侵占会污染两个 T4 任务的 git 历史）
- 文件列表：`alembic/versions/{1a325e38e941, 2a40f59215de, 52af1c37bf14, a370e2771c6d, b08103b3a6f5, c9587c787c6b}_*.py`

**② Staged 区积压问题**（前会话已踩过）：
- `git status --porcelain` 会显示一堆**其他会话**已 staged 但未 commit 的文件（alembic/ + haofenshu-phase1-* + migration-gate-repair-* + tests/test_menu/ 等）
- commit 前必须 `git reset HEAD` 清理，然后**精确 `git add`** 本任务文件
- 建议流程：修完一个 Task 立即 `git reset HEAD && git add <本 Task 文件> && git commit`
- 备份清单见 `/tmp/pre-existing-staged.txt`（前会话已备份）

**③ doc-sync-guard 陷阱**：
- 工作区有其他会话的 design.md 未 commit（`2026-04-12-haofenshu-biz-replication-design.md` + `2026-04-13-migration-gate-repair-design.md`）
- 一旦这些被捎带 staged，commit 会被 doc-sync-guard 拦截要求同步 CLAUDE.md
- 解决：每次 commit 前严格 `git reset HEAD` + 精确 add

**④ CLAUDE.md 工作区修改**：
- CLAUDE.md 有未 commit 追加（haofenshu + migration-gate 条目）
- 前会话 commit `7c08f01` 意外带上了这些追加
- 本会话 commit 时如果再带上，不是灾难——这些条目本就合法；但尽量避免，保持 commit 原子性

### Fix Intent Card 要求
F002/N001 命中"架构守卫 / 行为契约红旗模式"，**必须严格遵循** `docs/plans/.conduct-fix-intent-F002r3-N001.md`:
- 不改 `check_class_scope` / `check_resource_class` 语义（R2 已通过）
- 不引入 WHERE class_id 软过滤替代 raise
- 不添加"后 6 位 OR 整串"双路径
- 越权场景必须 raise 404（不 silently no-op）

### 测试基线
- Round 2 末：conduct **108 passed**、全量 collect **1913 tests**、alembic smoke 在 `bf630b0` 为 `1 pass / 1 fail / 1 error`（F001 deferred，本会话不处理）
- Round 3 预期：conduct **113 passed**（108 + 3 F002 + 2 N001）+ 前端新增 1 vitest
- 验证命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q`

### Gate Receipt 当前状态
- `gates.json` `code_review_batch1.status=fail, round=2`
- Round 3 完成需 **codex-review skill Code Review**，PASS 后更新 status 为 pass、round=3
- `report_path` 指向 R3 报告（届时生成，不能指向 R2 FAIL 报告）

### F002/N001 审查视野

**F002 Round 3 增量 ORC**（验证命令见 Fix Intent Card）:
- ORC-009 conduct_records.rule_item_id ↔ record.class_id 必须同班
- ORC-010 conduct_group_members 写入时 student.class_id == group.class_id
- ORC-011 scope 校验在 service 前置，service 不重复校验也不绕过

**N001 增量 ORC**:
- ORC-012 id_card 比对 `stored[-6:] == verify_code`
- ORC-013 phone/custom 共享 verify_code 路径（Option A，保持）
- ORC-014 id_card_number 入站必经 AES-256-GCM
- ORC-015 verify_code 长度约束：id_card 模式 len=6，其他无固定

### Round 3 审查时 Oracle Pack 注入
Round 3 commit 后调用 codex-review code review 时，codex prompt 会自动从 plan 提取 `semantic_regression:` 段作为 Oracle Pack。Fix Intent Card §Semantic Regression Oracle Pack 的 yaml 已可复制到 plan Task 19-20 的测试契约段下方。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-13 12:20:00
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-conduct-round3-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md Batch 7 Task 19-23 执行 T4 德育模块 Gate 2 Round 3 修复。

先声明 T4 tier（SessionState declared_tier=T4）并使用 executing-plans skill。严格遵循 C:\Users\Administrator\edu-cloud\docs\plans\.conduct-fix-intent-F002r3-N001.md 的 non_goals 与 allowed_change_surface（F002/N001 命中架构守卫 + 行为契约红旗模式）。

Round 3 scope: F002 剩余越权面（Task 19） + N001 id_card 回退后 6 位（Task 20） + F004 前端字段 snapshot（Task 21） + F006 导出断言升级（Task 22）+ 收尾（Task 23）。F001 deferred 到 haofenshu-phase1，不在本会话 scope。

⛔ 工作区 6 个 alembic migration 修改属 haofenshu-phase1 F001 独立修复产物，禁止本会话 commit。每次 commit 前必须 `git reset HEAD` 清理积压 staged，然后精确 `git add` 本任务文件。

完成后输出审查交接单。
```
