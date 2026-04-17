<!-- legacy-format -->
# W4-Exec · conduct-roadmap Batch 1 · T1-T5 实施 · 执行交接卡

> 类型：T3 plan 实施窗口（必须**新 session**，CLAUDE.md T3 流程硬约束）
> 创建：2026-04-18 规划窗口
> 工作分支：`feat/conduct-roadmap-batch1` @ `637ce2f`
> 工作 worktree：**`/home/ops/projects/edu-cloud`**（主仓，W4 plan session 已结束）
> 前置 plan：`docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`（status=approved，gate_1_result=PASS @ R7）

## 1. T3 硬约束（不可绕过）
- 项目 CLAUDE.md "单会话工作流" 段：T3/T4 设计→计划→**独立新会话执行**
- W4 plan session 已 end（R7 PASS），T1-T5 实施必须**新开 session**
- 新 session 必须声明 `effective_tier=T3` + 调用 `executing-plans` skill

## 2. plan 概览（依据：plan 实查）
- **5 task**，独立 commit，顺序 T5 → T4 → T1 → T2 → T3
- **T5**：CLAUDE.md 数字漂移修正（热身，2 commits）
- **T4**：conduct MODULE.md 补全（governance，2 commits）
- **T1**：lesson_prep_leader conduct 权限回收（behavior_change，3 commits）
- **T2**：AddPointsRequest.date → record_date（1 commit）
- **T3**：sidebar 三档按 permissions 派生（behavior_change，2 commits）

T1+T3 含 behavior_change（已 L017 用户 2026-04-14 批准）

## 3. 范围定义

### 3.1 可改文件（白名单，按 task 引用 plan 详情）
- T5：`CLAUDE.md` 数字漂移段
- T4：`src/edu_cloud/modules/conduct/MODULE.md`（新建）
- T1：`src/edu_cloud/core/permissions.py`（lesson_prep_leader）+ `frontend/src/config/permissions.js`（前端镜像）+ 入口级测试 `tests/test_*lesson_prep*` / `frontend test`
- T2：`src/edu_cloud/modules/conduct/schemas.py` + `admin_router.py:115,137`（field rename）+ 测试
- T3：`frontend/src/config/sidebarConfig.js`（permissions 派生）+ `frontend/src/components/shell/AppSidebar.vue` data-module 属性 + 入口级测试

### 3.2 红线禁区
- 不动 `src/edu_cloud/modules/card/*` （W1 范围，已 6c1ee0e）
- 不动 `frontend/src/components/knowledge-tree/*` （W2 范围）
- 不动 `frontend-nuxt/*` （W3 范围）
- 不动其他 modules/*（仅 conduct）
- 不动 lockfile / pyproject 主版本

## 4. 实施步骤

```bash
# 新开 Claude Code session（必须！T3 硬约束）
# 启动话术见本卡 §8

cd /home/ops/projects/edu-cloud

# 验证起点
git log --oneline -3  # 应见 637ce2f / 583205d / 19b4a4f
git rev-parse --abbrev-ref HEAD  # 必 = feat/conduct-roadmap-batch1
git status  # 应空（test_output PDF 飘 OK）

# 调用 executing-plans skill 自动按 plan 执行 T5 → T4 → T1 → T2 → T3
# 每 task 独立 commit + 跑入口级测试
```

## 5. 测试子集
- conduct 后端：`/home/ops/projects/edu-cloud/.venv/bin/python -m pytest tests/test_*conduct* tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py tests/test_api/test_deps.py -q`
- conduct 前端：`cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/conduct/ src/components/shell/`
- **禁止**全量 pytest（与 W2-R2 / T2 资源争抢）

## 6. 验收契约
- 5 task 全 commit + 各自入口级测试 PASS
- 基线：conduct 118 + services 15 → 完成后 conduct ≥128 + services 15 + frontend ≥27
- 完成后触发 `codex-review code_review_batch1`

## 7. checkpoint 输出格式（每 task 完成后）

```
【W4 T<N> · 待确认】
- task：T<N> <description>
- commits：<sha list>
- 测试子集：N passed
- behavior_change verify：<如适用>
- 异常：<列出>
- 等用户确认进 T<N+1>
```

全部完成后：
```
【W4 batch1 全部完成 · 待 code_review_batch1】
- T1-T5 全 PASS
- 后端基线：conduct N / services N
- 前端基线：N
- 触发 codex-review code_review_batch1：task ID <id>
- 等 R1 结果 → PASS 进 T2-补遗 / FAIL 进 R2 修复
```

## 8. 第一步指令（新 session 启动话术）

```
继续 conduct-roadmap-batch1 T1-T5 实施。

工作目录：/home/ops/projects/edu-cloud
工作分支：feat/conduct-roadmap-batch1 @ 637ce2f
依据 plan：docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md（status=approved, gate_1_result=PASS）
依据交接卡：docs/plans/2026-04-18-w4-exec-T1-T5-handoff.md

T3 硬约束：本 session 必须声明 effective_tier=T3 + 调用 executing-plans skill。

第一步：
1. 验证起点（git log + status + branch）
2. 读 plan + 本交接卡
3. 调 executing-plans skill 按 T5 → T4 → T1 → T2 → T3 顺序自动执行
4. 每 task 独立 commit + 跑入口级测试
5. T1/T3 behavior_change 实施前必须输出 T2 根因声明
```

## 9. 与其他窗口同步
- W4 实施期间不影响 W2-R2 / T2-Partial（不同 worktree + 不同分支）
- W4 完成后由 T2-补遗 session merge 到 master

## 10. 兜底
- 入口级测试失败 → 按 bug-fix-discipline.md 输出 T2 根因声明再修
- behavior_change 边界不清 → 停下问用户，不擅自扩大范围
- 同 task 被纠正 ≥3 次 → L015 主动放弃
