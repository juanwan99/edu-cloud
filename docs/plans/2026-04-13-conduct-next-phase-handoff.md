---
type: handoff
created: 2026-04-13 20:51:36
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-state.json
fix_intent_card_r3: C:\Users\Administrator\edu-cloud\docs\plans\.conduct-fix-intent-F002r3-N001.md
review_handoff_r3: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-review-handoff-batch1-r3.md
review_report_r3: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-review-report-batch1-r3.md
---

## 约束与偏好（德育下一阶段 Planner 视角）

### 当前状态（已落地，禁止重做）

| 阶段 | commits | 状态 |
|---|---|---|
| R1+R2 实现 | `2333f64..bf630b0` | Gate 2 R2 PASS resolved-correct |
| R3 修复 | `e584e6a..93f0b60` | Gate 2 R3-R2 PASS（F002/N001/F004/F006/F007 全 resolved-correct）|
| conduct 默认上线 | `a117222` | DEFAULT_ENABLED 加 conduct + 现存 2 所学校 backfill |
| Sidebar 挂载补齐 | `d1bfd10` | principal/platform_admin/district_admin 加入口 + grade_leader permissions 对齐后端 + 契约测试 |

**真源**:
- gates.json `code_review_batch1.status=pass round=3`（含 R3 双轮 audit trail）
- design.md 头部 `[2026-04-13 20:24:00 实现完成]` 标记
- CLAUDE.md「德育模块（conduct）[实现完成]」+ R3 详细记录
- state.json 23 tasks 全部 completed

### Tier 与流程

**默认按 T3 流程启动**（跨前后端 + 角色矩阵 + 多 deferred 项），具体任务可降级：
- 单点补丁（如 F001 等待 / sentinel 加固）→ T2 同会话
- 跨模块协同（如 F2 权限镜像系统化对齐 / Agent 工具 e2e）→ T3
- 联动好分数 Phase 1 菜单系统切换 → T4

### 待规划清单（Deferred / 未排期）

按优先级和影响面分组。**不强制全做**——按用户取舍。

#### P0 — 阻塞或潜在事故

**D-001 F001 Alembic SQLite ALTER CONSTRAINT 失败**
- 状态: deferred 到 haofenshu-phase1 Migration Gate Repair
- 设计: `docs/plans/2026-04-13-migration-gate-repair-design.md`
- 动作: 监听 haofenshu-phase1 修复合入，conduct F001 自动升级 resolved-correct
- 不需主动规划

**D-002 AddPointsRequest.date latent 422**
- 根因: `src/edu_cloud/modules/conduct/schemas.py:33-38` 字段名 `date` 与导入的 `datetime.date` 类型同名 → pydantic v2 把 Optional[date] 解析为 None-only
- 影响: 客户端传 `{"date": "2026-04-13"}` 全 422 拒绝；R3 测试已绕开（不传 date 字段）
- 修复方向: 字段重命名为 `record_date`（或 import as 别名）+ 客户端调用方同步
- 风险: 涉及 schema 公开契约变更，需要 e2e 检查所有调用方
- 推荐: T2 +前端联调

#### P1 — 一致性治理

**D-003 前后端 conduct 权限镜像系统对齐**
- 已知不一致（已修 grade_leader）：
  - `principal`: 后端 FULL（VIEW+MANAGE+RULES+PARENTS）/ 前端 VIEWER（view+export）
  - `academic_director`: 后端有 PARENTS / 前端无 PARENTS（需 grep 核实）
  - 其他角色待逐一对账
- 工具: 可写脚本扫描 `core/permissions.py` ↔ `frontend/src/config/permissions.js` diff
- 推荐: T2 治理任务（不修业务逻辑，仅镜像同步）

**D-004 lesson_prep_leader sidebar conduct 入口**
- 现状: 后端有 view_conduct（_TEACHER_BASE 含），sidebar 无 conduct 入口
- 决策点: 是产品决策（备课组长不含德育入口）还是遗漏？
- 推荐: 与产品确认后再动

**D-005 design.md §3 之外的防退化 sentinel**
- R3 的 N001 fix Intent Card 在 design.md §3 加了"Option A 锁定 / 后 6 位"sentinel
- 其他高风险契约（如 check_class_scope / check_resource_class 语义、AES-256-GCM 加密路径）尚无显式 sentinel
- 推荐: T3 加固设计文档防护

#### P2 — 真实使用验证

**D-006 家长端 e2e（移动端真实流程）**
- 当前测试仅 unit/api 层。家长端 5 页面（注册→邀请码→绑定→概览→记录）无浏览器级验证
- 推荐: T2 手测 + 视频留档；或 Playwright e2e

**D-007 6 个 Agent conduct tools 真实可用性**
- ai/tools/conduct.py: 6 工具（rankings/records/rules/points/overview/summary）已加 ctx.class_ids 校验
- 缺: AI Chat 中真实调用验证（输入"班级 X 排行"看是否正常返回）
- 推荐: T2 端到端

**D-008 Excel 导出中文+日期过滤实际效果**
- 单测覆盖 header + 行数 + 排序聚合，但中文 sheet 名/UTF-8/日期 range 真实导出未端到端验
- 推荐: T2 校长账号导出 demo

#### P3 — 风险审查

**D-009 类 F007 single-student edge case 横向审查**
- F007 暴露问题：`test_export_rankings_excel` 单学生零积分场景过弱无法抓 SUM/ORDER BY 错误
- 推断: 其他 service（statistics、analytics、homework grading 等）可能有同模式 test-gap
- 推荐: T3 系统性审查 + 加固

**D-010 seed_menus.py 缺 conduct（好分数 phase1 切换前预备）**
- 当前前端用 sidebarConfig.js 静态配置（已挂 conduct）
- 好分数 phase1 引入了动态菜单 GET /api/v1/menus + scripts/seed_menus.py
- 切换菜单源那天，seed_menus.py MODULES 必须有 conduct 模块（9 子菜单）
- 推荐: 跟好分数 phase1 协同，列入切换 checklist

### 前会话踩过的坑（Planner 必读）

#### ① 工作区可能仍有跨 session 未 commit 文件

可能见到的：
- `alembic/versions/*.py` × 6（haofenshu-phase1 F001 Migration Gate Repair）— **非本任务范围**
- `2026-04-13-migration-gate-repair-design.md` / `2026-04-12-haofenshu-phase1-*` — 好分数 session 文件
- 前会话各种 `.codex-*-raw.log` — 审查日志

**纪律**: 每次 commit 前 `git reset HEAD` 清积压 → 精确 `git add <文件>` → `git diff --cached --name-only` 验证

#### ② 多 session 并发 commit race

R3 收尾时观察到本 session 的 commit 被相邻 session 的 commit "合并"（相同时刻 stage 互相覆盖），最终 commit message 与内容不匹配。验证手段：commit 后立即 `git log --oneline -5 && git show HEAD --stat | head -10`，若内容不对立刻补 commit。

#### ③ doc-sync-guard 硬阻断

修改 design.md / 新增/删除代码文件 / 改 ORM 模型 → commit 时被 hook 拦住要求同步 CLAUDE.md。**预防**: 改 design 时同步改 CLAUDE.md「已完成设计」表格；新增模块/文件同步更新 CLAUDE.md 项目结构表。

#### ④ handoff_format_guard 拦截审查交接单格式

审查交接单的「自查（四要素格式）」段，「运行命令」必须用反引号包裹真实可执行命令（不接受"推演"等描述性词）；「逐 Task 自审」表格状态列每行必填（✅/❌/🔀），🔀 必须写具体变更内容。

#### ⑤ session_guard 阻断 executing-plans skill

T3/T4 启动 executing-plans 前需要：
- gates.json plan_review 通过（pass）或 required=false（如本任务）
- SessionState `current_topic` + `current_gates_file` 显式设置（否则多 gates.json 文件场景 fail-closed 阻断）
- 解决：本会话 SessionState path `~/.claude/hooks/state/{session_id[:8]}_state.json`，必要时手工 Edit 写入 `current_topic="2026-04-12-conduct-module"`

#### ⑥ AddPointsRequest.date 字段陷阱（latent bug）

任何使用该 schema 的测试 / 客户端代码请求 body 不要传 `date` 字段（即使 Optional），否则 422 "Input should be None"。详 D-002。

### 自治边界（L015 / L017 警示）

- 涉及前端视觉变更 + 多页面 + 用户离线 任意 2 项 → 拒绝整包自治，先拆单
- GPT 审查 finding 含 `behavior_change` 类型 → 必须单独确认，禁止批量批准
- 接到「全部修复」「都改了吧」时如果存在多个 behavior_change finding → 必须追问「批准 F00X / 拒绝 F00X」
- 用户连续 ≥3 次纠正同一子项 → 停手，输出能力边界声明 + 建议外援（codex-review diagnose / 用户接管 / 换方案）

### 测试基线（Planner 接班后用作回归基准）

```bash
# conduct 后端
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q
# 期望: 120 passed (R3 收尾基线)

# 配置/契约
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q
# 期望: 15 passed

# 前端 conduct 相关
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js src/pages/parent/__tests__/ParentRules.spec.js
# 期望: 13 passed
```

### Gate Receipt 当前状态

- `gates.json` `code_review_batch1.status=pass round=3`（PASS 已锁定）
- 任何新阶段需要新建 plan + 独立 gates 文件（不复用 conduct-module-gates.json）
- 推荐命名: `docs/plans/YYYY-MM-DD-conduct-{phase}-gates.json`

---

## 启动 Prompt

```
[edu-cloud] Planner | 2026-04-13 20:51:36
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-conduct-next-phase-handoff.md，作为德育模块下一阶段 Planner 启动。

声明 T3（默认；按子任务实际规模可降为 T2 或升为 T4）。使用 brainstorming + writing-plans skill。

德育 R1+R2+R3 已 PASS，默认上线 + sidebar 挂载已落地。本会话职责：
  1. 与用户确认下一阶段 scope（D-001 ~ D-010 取舍 / 新增需求）
  2. 对选定子项写 design.md → plan.md → handoff，分批 commit
  3. 触发 codex-review skill (Plan Review) 取 Gate 1 PASS
  4. 输出 Executor 启动 prompt（不在本会话执行实现）

⛔ 工作区可能仍有跨 session alembic / haofenshu-phase1 / migration-gate-repair 未 commit 文件，禁止侵占；每次 commit 前 `git reset HEAD` + 精确 `git add` + `git diff --cached --name-only` 验证 staged 干净。

⛔ 涉及前端权限镜像 / sidebar 挂载 / Agent 工具 等跨模块改动，必须遵守 L015 自治边界（不可自治组合先拆单）+ L017 行为变更守卫（behavior_change finding 单独确认）。

完成后输出审查交接单。
```
