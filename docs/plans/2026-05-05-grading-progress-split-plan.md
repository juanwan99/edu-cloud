# 阅卷进度拆分：人工 vs AI 分离计数与展示

> T2 行为变更 | 影响模块: grading（后端 API + 前端卡片）

## 背景与动机

当前 `GET /grading/dispatch/status` 将 AI 阅卷和人工阅卷混合计数，前端只有一个进度条。
用户在复核场景下无法快速判断"AI 已评了多少、人工已评了多少、还剩多少"。

**用户需求**：人工和 AI 进度条并列、分开显示数量。

## 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 后端 API | `GET /dispatch/status` 返回 `ai_graded`(GradingTask.completed) / `reviewed`(confirmed count) / `subjective_total` | `grading_review_router.py:171-398` | read |
| 数据模型 | GradingResult.status(ai_pending/ai_done/confirmed) + source(ai/ai_override/manual) | `models.py:45-102` | read |
| 前端卡片 | SubjectStatusCard.vue 只在 cutting 阶段显示进度条 | `SubjectStatusCard.vue:18-24` | read |
| 前端调度页 | GradingDispatchPage.vue 轮询 dispatch/status | `GradingDispatchPage.vue` | read |

## 增量 vs 新建论证

- 默认立场：增强已有 dispatch/status API + SubjectStatusCard 组件
- 不新建 API 或组件，只扩展返回字段和卡片 UI

## 交付路径

- 后端：修改 `grading_review_router.py` 的 dispatch/status 端点
- 前端：修改 `SubjectStatusCard.vue` 卡片组件 + `GradingDispatchPage.vue` 传参
- 生产 URL：`https://mcu.asia` → nginx → `frontend/dist/`
- 后端验证：pytest

## 设计决策

### D1: 计数字段拆分

**现有字段**（废弃）：
- `ai_graded`: GradingTask.completed（只看最新任务，漏旧任务/grade_single）
- `reviewed`: confirmed WHERE ai_task_id=latest_task（只看最新任务）

**新字段**（从 GradingResult 直接聚合，不依赖 GradingTask）：

| 字段 | 计算逻辑 | 含义 |
|------|---------|------|
| `ai_done_count` | COUNT(status='ai_done') | AI 已评分、待教师复核 |
| `ai_confirmed_count` | COUNT(status='confirmed' AND source IN ('ai','ai_override')) | AI 评分已确认（含改分） |
| `manual_confirmed_count` | COUNT(status='confirmed' AND source='manual') | 纯人工已评分 |
| `ai_pending_count` | GradingTask processing 时: task.total - task.completed - task.failed；否则 0 | AI 评分进行中 |
| `subjective_total` | 不变（image_path IS NOT NULL） | 主观题答卷总数 |

**兼容性**：保留旧 `ai_graded` 和 `reviewed` 字段（值改为新逻辑聚合），避免前端其他页面报错。
- `ai_graded` = `ai_done_count + ai_confirmed_count`
- `reviewed` = `ai_confirmed_count + manual_confirmed_count`

**Evidence**: `grading_review_router.py:247-261` 现有 reviewed 只查 latest task 的 confirmed，漏纯人工。

### D2: 历史数据 source=NULL 处理

confirmed 且 source IS NULL 的记录需要修复：
- `ai_score IS NOT NULL` 或 `ai_task_id IS NOT NULL` → 回填 `source='ai'`
- 否则 → 回填 `source='manual'`

用一次性脚本处理，不做 migration。

### D3: stage 推导修正

现有 stage 判断 `reviewed < ai_graded`（`grading_review_router.py:372`）混合了人工和 AI。

修正为：
- `reviewing`：有 AI 评分完成但未全部确认 → `ai_done_count > 0`
- `done`：所有 AI 结果已确认 且 无运行中任务 → `ai_done_count == 0 AND grading_task.status == 'completed'`

### D4: 前端进度条设计

在 SubjectStatusCard 的 `card-mid` 区域，所有有答卷的阶段（不仅 cutting）都显示双进度条：

```
AI  ████████░░░░  42/100
人工 ███░░░░░░░░░   8/100
```

- AI 进度条：紫色（`--color-primary`），分子 = ai_done_count + ai_confirmed_count + ai_pending_count
- 人工进度条：橙色（`--color-warning`），分子 = manual_confirmed_count
- 分母 = subjective_total
- 进度条高度 4px（比现有 6px 更细）
- 两条进度条垂直并列，间距 3px

### D5: questions 逐题维度

本次只拆科目级计数，`questions[].graded_count` 暂不拆分。

## 任务拆分

### Task 1: 后端 — dispatch/status API 字段拆分
**文件**: `src/edu_cloud/modules/grading/grading_review_router.py`

1. 在科目循环内，用 3 条 COUNT 查询替代现有的 reviewed/ai_graded 计算：
   ```python
   # AI 已评分待复核
   ai_done_count = COUNT(GradingResult) WHERE question_id IN subjective_q_ids
       AND school_id = effective_school_id AND status = 'ai_done'
   # AI 已确认
   ai_confirmed_count = COUNT(GradingResult) WHERE question_id IN subjective_q_ids
       AND school_id = effective_school_id AND status = 'confirmed'
       AND source IN ('ai', 'ai_override')
   # 人工已确认
   manual_confirmed_count = COUNT(GradingResult) WHERE question_id IN subjective_q_ids
       AND school_id = effective_school_id AND status = 'confirmed'
       AND source = 'manual'
   ```
2. ai_pending_count 从 GradingTask 计算：
   ```python
   if grading_task and grading_task.status in ('pending', 'processing'):
       ai_pending_count = (grading_task.total or 0) - (grading_task.completed or 0) - (grading_task.failed or 0)
   else:
       ai_pending_count = 0
   ```
3. 返回新字段，保留旧字段兼容：
   ```python
   "ai_done_count": ai_done_count,
   "ai_confirmed_count": ai_confirmed_count,
   "manual_confirmed_count": manual_confirmed_count,
   "ai_pending_count": ai_pending_count,
   # 兼容
   "ai_graded": ai_done_count + ai_confirmed_count,
   "reviewed": ai_confirmed_count + manual_confirmed_count,
   ```
4. 修正 stage 推导（第 372 行）：
   - `reviewing` 条件改为 `ai_done_count > 0`
   - `done` 条件改为 `ai_done_count == 0 and grading_task.status == 'completed'`

**测试契约**:
- 入口: GET /grading/dispatch/status?exam_id=X
- 反例: 只有人工评分时 ai_done_count/ai_confirmed_count 应为 0，manual_confirmed_count > 0
- 边界: subjective_total=0 时所有计数为 0
- 回归: 旧字段 ai_graded/reviewed 值与新字段一致
- 命令: `.venv/bin/python -m pytest tests/ -k "dispatch_status" -q`

### Task 2: 历史数据修复脚本
**文件**: `scripts/backfill_grading_source.py`（新建，一次性）

查找 `status='confirmed' AND source IS NULL` 的 GradingResult：
- `ai_score IS NOT NULL OR ai_task_id IS NOT NULL` → `source='ai'`
- 否则 → `source='manual'`

dry-run 模式默认，`--commit` 参数才真正写入。

### Task 3: 前端 — SubjectStatusCard 双进度条
**文件**: `frontend/src/pages/grading-dispatch/SubjectStatusCard.vue`

1. 在 `card-mid` 区域，当 `subject.subjective_total > 0` 时渲染双进度条
2. AI 进度条（紫色）+ 人工进度条（橙色），高度 4px，间距 3px
3. 数量标签："AI 42/100 | 人工 8/100"
4. 移除 cutting 阶段的单独进度条逻辑（统一用双进度条，cutting 阶段不显示阅卷进度）

**测试契约**:
- 入口: SubjectStatusCard 渲染
- 反例: subjective_total=0 时不渲染进度条
- 边界: ai_done_count + ai_confirmed_count > subjective_total 时 clamp 到 100%
- 回归: cutting 阶段仍显示切割进度条（不是阅卷进度条）
- 命令: `npx vitest run --reporter=verbose -t "SubjectStatusCard"`

### Task 4: 前端 — GradingDispatchPage 数据绑定
**文件**: `frontend/src/pages/GradingDispatchPage.vue`

确认 subject 对象直接传给 SubjectStatusCard，新字段自动透传。
如有 stageGroups 或其他聚合逻辑使用旧字段名，同步更新。

## 执行顺序

Task 2（数据修复） → Task 1（后端 API） → Task 3+4（前端，可并行）

## 风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| 历史 source=NULL 记录 | 计数偏差 | Task 2 修复脚本 |
| 3 条额外 COUNT 查询性能 | 每科目 +3 query | 已有 index ix_grading_result_school_status 覆盖 |
| 前端其他页面用 ai_graded/reviewed | 兼容性 | 保留旧字段，值用新逻辑计算 |
