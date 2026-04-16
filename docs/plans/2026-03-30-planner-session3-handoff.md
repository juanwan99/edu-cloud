---
type: handoff
created: 2026-03-30 22:26:47
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-business-logic-backfill-design.md
---

# 项目总规划师交接卡 — Session 3 → Session 4

## 已完成（本会话）

| 工作 | 级别 | 状态 | Commits |
|------|------|------|---------|
| Phase 2.2 设计+计划 | T3 | Gate 1 R3 通过 | 6eb7636..4716352 |
| Phase 2.2 执行（8 Task） | T3 | Gate 2 R3 通过 | 79b3dcd..e4e81ea |
| Phase 2.2 CR 修复（requires_capabilities 格式 + 测试断言） | — | 完成 | 04ade65..0088cbb |
| Phase 3.2 考后流水线接线 | T2 | 完成 | abdd019 |
| Phase 3.1 学情分析 REST API | T2 | 完成 | d951536 |

## 当前状态快照（2026-03-30 22:26）

- **分支**: master
- **测试**: ~1024 后端 + 68 前端（+10 profile/bank API + 5 pipeline wiring）
- **表**: 39
- **AI 工具**: 39
- **REST 端点**: +20（12 homework + 4 profile + 4 bank）
- **stub 清零**: _calculate_rankings / _update_error_books / run_post_exam_pipeline 全部接线完成
- **EventBus**: exam.published → on_exam_published handler 已注册

## 路线图

```
Phase 1: 数据基底 + 权限引擎 + Agent 基础设施  ← 100% 完成
  ├── 1a 模块管理      ✅
  ├── 1b 基础信息      ✅
  ├── 1c 权限引擎      ✅
  └── 1d Agent 实例化   ✅

Phase 1e: 常驻巡检 Agent                       ← 未开始（T3）

Phase 2: 核心流程层                              ← 90% 完成
  ├── 2.1 考试状态机    ✅
  ├── 2.2 作业系统      ✅ (Gate 1+2 通过)
  └── 2.3 examids 统一  ← 未开始（T2）

Phase 3: 价值输出层                              ← 70% 完成
  ├── 3.1 学情分析      ✅（pipeline 写入 + REST API + AI Tools 全有）
  ├── 3.2 考后流水线    ✅（stub 接线完成）
  └── 3.3 分析报告      ← 未开始（T3）

Phase 4: 高级功能层                              ← 未开始
```

## Phase 2.3 examids 统一 — 下一步任务

**级别**: T2（同会话执行，t2-review 自审）

**目标**: 分析查询统一使用 `exam_subject_id`（即 Subject.id）作为入参，替代当前的 `exam_id + subject_id` 双参数模式。不引入 haofenshu 的字符串复合键。

**现状分析**:
- `analytics/service.py` 的查询函数大多接收 `exam_id + subject_id` 两个参数
- AI 工具 `analytics_score.py` 也是 `exam_id + subject_id`
- Subject 表已有 `id` 字段（UUID），且有 `(exam_id, code)` 唯一约束
- 可以通过 subject_id 反查 exam_id（Subject.exam_id FK）

**改动范围**:
- `analytics/service.py`: 添加 `by_subject_id()` 辅助函数，从 subject_id 解出 exam_id
- `analytics/router.py`: 查询端点支持 `subject_id` 单参数（保持 exam_id 向后兼容）
- `ai/tools/analytics_score.py`: 工具参数可选用 subject_id
- 不改模型、不改表结构

**注意**:
- 这是渐进式统一，不是一次性重写
- 保持 exam_id 参数向后兼容（不删除）
- `python`（非 `python3`）是正确的 Python 命令

## design-concern 待处置（不阻塞）

### Phase 2.2 §8
- R2-F1: 细粒度 ScopeFilter（parent/grade_leader）延后
- R2-F4: principal VIEW_HOMEWORK only 已统一
- R2-F5: exam_id FK 约束已保证存在性

### Phase 2.1 §9
- F-04: _calculate_rankings / _update_error_books 已在 3.2 接线完成

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-30 22:26:47
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-30-planner-session3-handoff.md 了解上下文。执行 Phase 2.3 examids 统一（T2 级别）。参考 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-business-logic-backfill-design.md §2.3。完成后执行 t2-review 自审。
```
