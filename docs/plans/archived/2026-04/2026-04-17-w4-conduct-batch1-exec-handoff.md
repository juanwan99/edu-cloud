<!-- legacy-format -->
# W4 · conduct-roadmap Batch 1 · 执行窗口交接卡

> 类型：T1 并行执行窗口（4 窗口之一）
> 前序 plan（必读）：`docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`
> 设计文档：`docs/plans/2026-04-14-conduct-roadmap-design.md`
> Plan Review：`docs/plans/2026-04-14-conduct-roadmap-batch1-plan-review.md`（R2 已修订，10 invariants + 4 counter_examples）
> 起点 git HEAD：`6f3dc81`（commit 拆分后）
> 工作分支：**`feat/conduct-roadmap-batch1`**（独立分支）

## 1. 与前序 plan 的关系
- **前序 plan 是任务详情来源**（T1-T5: lesson_prep_leader 权限回收 + AddPointsRequest field rename + sidebar 三档按 permissions 派生 + conduct MODULE.md 补全 + 文档数字漂移修正）
- **本卡仅追加并行执行硬约束**

## 2. 范围定义

### 2.1 可改文件（白名单）
- 后端：
  - `src/edu_cloud/core/permissions.py` — `_TEACHER_BASE - {VIEW_CONDUCT, MANAGE_CONDUCT}`（T1）
  - `src/edu_cloud/modules/conduct/*` — schemas/router/service（T2 field rename）
  - `src/edu_cloud/modules/conduct/MODULE.md` — 补全 owns_tables/api/tools/tests（T4）
- 前端：
  - `frontend/src/config/sidebarConfig.js` — 三档按 permissions 派生（T3）
  - `frontend/src/config/permissions.js` — 镜像后端权限（T1）
  - `frontend/src/pages/conduct/*` — 如需对应 router 调整
- 测试：
  - `tests/test_*conduct*` — T1 API 403 + T3 入口级测试 + R-T3-followup 治理测试
  - `frontend/src/pages/conduct/__tests__/*` — T3 AppSidebar 快照（如适用）
- 文档：
  - `CLAUDE.md` — T5 数字漂移修正（120→118 等）

### 2.2 红线禁区
- `src/edu_cloud/modules/card/*` — W1 范围
- `src/edu_cloud/modules/knowledge_tree/*` — W2 间接相关
- `frontend/src/components/knowledge-tree/*` — W2 范围
- `frontend-nuxt/*` — W3 范围
- `src/edu_cloud/modules/exam/*` — 不在本批次
- `src/edu_cloud/api/compat_router.py` — Phase 5 已就位

## 3. T2+ 行为变更声明（必须执行前输出）

参考 `~/.claude/rules/bug-fix-discipline.md`。R-T1 / R-T2 / R-T3 都是 behavior_change，输出根因声明：

```
**症状**: lesson_prep_leader 当前过权（含 VIEW_CONDUCT/MANAGE_CONDUCT），违反职责定义
**根因**: _TEACHER_BASE 集合误纳两条 conduct 权限
**证据**: core/permissions.py:LXX
**影响面 (scope check)**:
  - 同模式: subject_teacher 是否也误纳？(应核实)
  - 同边界: API 403 + UI sidebar 双层验证
  - 同不变量: 角色定义文档（CLAUDE.md "角色体系"）是否需更新
**排除的假设**: 用户未要求"完全删除 lesson_prep_leader"——只做权限回收
```

类似的 R-T2 / R-T3 声明也要先写。

## 4. 实施步骤
按前序 plan §"任务分解"严格 TDD：每个 T 先写红测，再实现，再绿测。

```bash
# Step 0: 起分支
cd /home/ops/projects/edu-cloud
git checkout -b feat/conduct-roadmap-batch1
```

## 5. 测试隔离

```bash
# 仅跑 conduct + permissions 后端测试
.venv/bin/python -m pytest tests/test_*conduct* tests/test_api/test_deps.py tests/test_services/ --tb=short -q
# 预期 ≥118 conduct + 15 services（基线）+ 新增 ≥10（治理 + 入口级）

# 前端 conduct 子集
cd /home/ops/projects/edu-cloud/frontend
npx vitest run src/pages/conduct/
# 预期 ≥13 PASS（基线）+ 新增 ≥14
```

**禁止**：跑后端全量 pytest（与 W1 争抢）；跑 frontend 全量 vitest（与 W2 争抢）。

## 6. 验收契约
按前序 plan + Plan Review R2 "退出条件" + 追加：
- 不动红线文件
- conduct 测试子集 100% PASS（含新增治理测试）
- CLAUDE.md "角色体系"章节同步（lesson_prep_leader 描述更新）
- 不破坏 INV-002（fail-open 语义保留）

## 7. checkpoint 输出格式

```
【W4 conduct Batch 1 · 待汇总】
- 工作分支：feat/conduct-roadmap-batch1
- 最终 commit hash：<sha>
- T1 lesson_prep_leader 权限回收：完成/未完成
- T2 AddPointsRequest field rename：完成/未完成
- T3 sidebar 三档按 permissions 派生：完成/未完成
- T4 conduct MODULE.md 补全：完成/未完成
- T5 文档数字漂移修正：完成/未完成
- 后端 conduct 测试：N passed / 0 failed
- 前端 conduct vitest：N passed / 0 failed
- 异常/已知问题：<列出>
- 等 T2 汇总窗口 merge
```

## 8. 与其他窗口同步
- **零文件冲突**（W1/W2/W3 红线均互斥）
- **不直接 commit master** — 完成在 feat/conduct-roadmap-batch1
- **不 push origin** — T2 统一处理

## 9. 第一步指令

```bash
cd /home/ops/projects/edu-cloud
cat docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md            # 必读前序
cat docs/plans/2026-04-14-conduct-roadmap-batch1-plan-review.md     # 必读 R2 review
cat docs/plans/2026-04-17-w4-conduct-batch1-exec-handoff.md         # 必读本卡
git log --oneline -5
git status                                                           # 应空
git checkout -b feat/conduct-roadmap-batch1
# 报告："已起 feat/conduct-roadmap-batch1 分支，T1-T5 任务理解，准备 T1 根因声明 + 红测"
```

等用户确认进入 T1 实施。

## 10. 兜底
- 同子项被纠正 ≥3 次 → 主动放弃
- 测试失败原因不明 → 先输出根因声明，不"圆话"
- 任何前序 plan 与实际代码冲突 → 立即报告，不擅自调整
