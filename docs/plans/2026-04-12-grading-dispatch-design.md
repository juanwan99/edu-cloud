# 阅卷调度全流程改造设计

> 创建: 2026-04-12 20:54:43
> 状态: 设计中

> [2026-04-13 07:39:41 实现完成] Commits: 7566b0a..082c7ab

## §0 背景与动机

当前"阅卷调度"页面（`GradingTasksPage.vue`）仅展示 AI 批改任务卡片列表，无法识别考试/科目，与试卷分割流程完全断开。教务主任需要在 ExamDetailPage 的"扫描状态" tab 手动切割，再跳到阅卷调度页面创建 AI 任务，流程碎片化。

本设计将阅卷调度页面改造为**全流程调度中心**，统管：分割→选择题判分→AI 阅卷→教师校对。

## §1 业务流程

```
已有扫描图片（每科一个子文件夹）
    ↓
① 试卷分割（切割各题区域 + 选择题自动识别判分）
    ↓
② AI 批量阅卷（主观题，全自动）
    ↓
③ 分配教师校对（跳转 MarkingAssignPage）
    ↓
④ 教师校对 AI 结果（通过/改分，TeacherReviewPage）
    ↓
⑤ 科目完成
```

### 关键决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 分割入口 | 阅卷调度页面统管，移除 ExamDetailPage 分割 tab | 单一入口，避免碎片化 |
| 选择题判分时机 | 切割时一步到位自动识别判分 | 纯算法无需人工介入 |
| 阅卷路径 | AI 先批，教师后校对 | 效率最高，复用已有 TeacherReviewPage |
| 页面主维度 | 以考试为主维度，每科目一行 | 匹配教务主任工作习惯 |
| 教师分配 | 复用 MarkingAssignPage，跳转操作 | 减少重复代码 |

## §2 科目阶段状态机

```
idle (未切割)
  → cutting (切割中)        [触发: 开始切割]
    → ready (待阅卷)        [切割完成，选择题已判]
      → ai_grading (AI阅卷中) [触发: 开始 AI 阅卷]
        → reviewing (待校对)   [AI 阅卷完成]
          → done (已完成)      [所有校对完成]
```

6 个阶段，对应 6 种 macaron 色标签：

| 阶段 | 标签色 | 可勾选 | 行内操作 |
|------|--------|--------|---------|
| idle | 灰 `#f3f4f6` | 是 | 预览 / 切割 |
| cutting | 蓝 `macaron-blue-light` | 否 | 停止 |
| ready | 紫 `macaron-purple-light` | 是 | AI 阅卷 |
| ai_grading | 黄 `macaron-yellow-light` | 否 | 处理中... |
| reviewing | 珊瑚 `macaron-coral-light` | 否 | 分配校对 |
| failed | 珊瑚 `macaron-coral-light` | 是 | 重试 AI 阅卷 |
| done | 薄荷 `macaron-mint-light` | 否 | 查看结果 |

## §3 前端改造

### 3.1 GradingTasksPage.vue → GradingDispatchPage.vue

重写页面，结构：

1. **页头**：标题"阅卷调度" + 考试选择器（n-select）
2. **扫描目录栏**：单行内联（目录图标 + 路径 + 更改/扫描按钮）
3. **批量操作栏**：勾选科目后出现（已选 N 个科目 + 批量切割 / 批量 AI 阅卷）
4. **科目列表表格**：6 列（复选框 / 科目 / 阶段 / 选择题 / 主观题 / 操作）

列定义：

| 列 | 宽度 | 内容 |
|----|------|------|
| 复选框 | 32px | 全选/单选，仅 idle 和 ready 可勾选 |
| 科目 | 72px | 科目名（粗体） |
| 阶段 | 82px | macaron 色 stage-tag |
| 选择题 | 1fr | 已判/总数，或"—"（未切割时） |
| 主观题 | 1fr | AI 批改进度 + 校对进度，或进度条，或"N 张扫描图" |
| 操作 | 140px | 随阶段变化的按钮 |

### 3.2 移除 ExamDetailPage 扫描 tab

删除 ExamDetailPage.vue 中 `<n-tab-pane name="scan">` 整个区块及相关 script 状态变量（`scanRootDir`、`scanFoundSubjects`、`scanProgress` 等）。

### 3.3 路由和侧栏

- 路由 `/grading/tasks` 指向新的 `GradingDispatchPage.vue`（替换原组件）
- 侧栏配置不变（`sidebarConfig.js` 中 `academic_director` 的"阅卷调度"条目保持）

### 3.4 数据获取

页面加载时：
1. `GET /api/v1/exams` → 考试列表，填充选择器
2. 选考试后 `GET /api/v1/exams/{id}/subjects` → 科目列表
3. 每个科目查询状态（新 API，见 §4.1）

### 3.5 批量操作

- **批量切割**：选中多个 idle 科目 → 依次调用 `POST /scan/pipeline/start`（串行，一个完成后自动启动下一个）
- **批量 AI 阅卷**：选中多个 ready 科目 → 依次调用 `POST /grading/tasks`

## §4 后端改造

### 4.1 新增 API：科目阅卷状态聚合

```
GET /api/v1/grading/dispatch/status?exam_id={exam_id}
```

返回该考试所有科目的阅卷调度状态：

```json
[
  {
    "subject_id": "xxx",
    "subject_name": "语文",
    "stage": "done",
    "scan_images": 50,
    "objective_total": 30,
    "objective_graded": 30,
    "subjective_total": 150,
    "ai_graded": 150,
    "ai_failed": 0,
    "reviewed": 150,
    "grading_task_id": "yyy"
  }
]
```

stage 由后端根据数据推导：
- `idle`：无 StudentAnswer 记录
- `cutting`：有活跃的 pipeline（`pipeline_service.is_running()` 且 subject 匹配）
- `ready`：有 StudentAnswer 但无 GradingTask
- `ai_grading`：有 GradingTask 且 status=processing
- `reviewing`：GradingTask status=completed 且有未校对的 AIGradingResult
- `done`：所有 AIGradingResult 的 review_status != pending

实现位置：`modules/grading/router.py` 新增路由函数。

### 4.2 pipeline_service 扩展：选择题识别

修改 `pipeline_service.py` 的 `process_one_image()`：

当前逻辑只处理 `type=subjective` 的 regions。扩展为：

1. 遍历 `type=choice_group` 的 regions
2. 对每个 choice_group 区域：坐标缩放 → 裁切灰度图 → 调用 `recognize_choice_group()`
3. 将识别结果（detected_answer, fill_ratios, anomaly）收集到返回值中

新增 `save_objective_fn` 回调参数（与 `save_answer_fn` 并行），由 `pipeline_router.py` 的 `build_pipeline_save_objective_fn()` 工厂构造。

选择题判分逻辑：从 `scan/router.py` 的 `upload_objective` 中提取为共享函数 `grade_objective_answer(detected_answer, correct_answer, max_score) → (score, is_correct)`，pipeline 和 router 共用。

### 4.3 pipeline_service 扩展：多科目串行队列

当前 pipeline 全局只有一个 `_running` 锁。批量切割多科目需要排队机制：

新增 `_queue: list[dict]`，每项包含 `{subject_id, image_dir, template, ...}`。`run_pipeline` 完成当前科目后自动取下一个。

`GET /scan/pipeline/progress` 返回扩展：

```json
{
  "status": "running",
  "current_subject_id": "xxx",
  "total": 50,
  "processed": 18,
  "failed": 0,
  "current_file": "001A.png",
  "queue_remaining": 2
}
```

前端根据 `queue_remaining` 展示"剩余 N 个科目排队中"。

### 4.4 GradingTask 关联信息

修改 `_task_response()` 返回 subject_name 和 exam_name（JOIN 查询 Subject → Exam），解决卡片无辨识信息的问题。（虽然旧的卡片 UI 不再使用，但 API 返回完整信息是正确的做法。）

## §5 数据流

### 切割 + 选择题判分流程

```
前端: POST /scan/pipeline/start (subject_id, image_dir, side)
  ↓
pipeline_service.run_pipeline()
  ↓ 逐张 process_one_image():
  │
  ├─ 条码识别 → student_id
  ├─ 遍历 type=subjective regions → crop → save_answer_fn → StudentAnswer(image_path)
  └─ 遍历 type=choice_group regions → crop灰度 → recognize_choice_group()
       → save_objective_fn → StudentAnswer(detected_answer, score, fill_ratios)
```

### AI 阅卷流程（不变）

```
前端: POST /grading/tasks (subject_id)
  → 前置校验（主观题存在 + Rubric + StudentAnswer）
  → 创建 GradingTask → enqueue arq
  → worker: 逐份 LLM 评分 → AIGradingResult
```

### 教师校对流程（不变）

```
前端: 点击"分配校对" → 跳转 /marking/assign?exam_id=xxx
  → MarkingAssignPage 分配题目给教师
  → 教师在 TeacherReviewPage 逐条通过/改分
```

## §6 文件变更清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `frontend/src/pages/GradingDispatchPage.vue` | 新建 | 替代 GradingTasksPage.vue |
| `frontend/src/pages/GradingTasksPage.vue` | 删除 | 被 GradingDispatchPage 替代 |
| `frontend/src/pages/ExamDetailPage.vue` | 修改 | 移除 scan tab 及相关变量 |
| `frontend/src/router/index.js` | 修改 | `/grading/tasks` 指向新组件 |
| `frontend/src/api/grading.js` | 修改 | 新增 `getDispatchStatus(examId)` |
| `src/edu_cloud/modules/scan/pipeline_service.py` | 修改 | 增加选择题识别 + 多科目队列 |
| `src/edu_cloud/modules/scan/pipeline_router.py` | 修改 | 新增 `build_pipeline_save_objective_fn` |
| `src/edu_cloud/modules/scan/objective_grading.py` | 新建 | 共享函数 `grade_objective_answer()` |
| `src/edu_cloud/modules/grading/router.py` | 修改 | 新增 `GET /grading/dispatch/status` |

## §7 不变量

- `StudentAnswer` 表结构不变
- `GradingTask` / `AIGradingResult` / `TeacherReview` 表结构不变
- `MarkingAssignPage` / `MarkingPage` / `TeacherReviewPage` 不修改
- vision 模块（fillmark.py 等）只调用不修改
- 兼容路由（`compat_router.py`）不变——paper-seg 仍可通过旧 API 上传

## §8 测试策略

| 测试范围 | 方式 |
|---------|------|
| `grade_objective_answer()` | 单元测试：正确/错误/多选/空答案 |
| `pipeline_service` 选择题识别 | 单元测试：mock recognize_choice_group，验证 save_objective_fn 被调用 |
| `pipeline_service` 多科目队列 | 单元测试：入队/出队/进度查询 |
| `GET /grading/dispatch/status` | API 测试：各阶段状态推导 |
| `GradingDispatchPage` | Vitest：组件渲染/批量选择/操作按钮显示 |
| ExamDetailPage scan tab 移除 | Vitest：确认 scan tab 不渲染 |
