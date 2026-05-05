# 阅卷分配改造交接文档

> 日期: 2026-04-26 | 任务级别: T2 行为变更
> **实现状态（2026-05-05 确认）**：已实现。marking/router.py 含 answer_count 字段，支持一题多人+数量配额。

## 需求

当前阅卷分配是"一题一人"——一道题只能分配给一个教师。需要改为"一题多人+数量"：同一道题可以分配给多个教师，每人指定批改的答卷数量。

例：第 18 题有 200 份答卷 → 教师 A 批 100 份、教师 B 批 100 份。

## 调查结论（已验证）

### 涉及文件清单

| 文件 | 改什么 |
|------|--------|
| `src/edu_cloud/modules/marking/router.py` | AssignRequest 加 answer_count; assign_question 改为一行一题一教师(不再追加到已有 assignment); _flatten_assignment 响应加 answer_count/graded_count; 加 DELETE /assignments/{id} 端点; next_answer/submit_score 传 teacher_id |
| `src/edu_cloud/modules/marking/scorer.py` | import GradingAssignment; get_next_answer 加 teacher_id 参数+配额检查; 新增 update_assignment_progress 函数 |
| `src/edu_cloud/modules/grading/assignment_service.py` | assign_block 冲突检测从"任意教师同题冲突"改为"同一教师同题冲突"; auto_assign 从按题均分改为每题均分给所有教师 |
| `frontend/src/pages/MarkingAssignPage.vue` | 从表格+1:1 映射改为 per-question 卡片+多教师+数量输入 |
| `tests/test_services/test_assignment_service.py` | test_assign_block_duplicate_rejected 拆为两个测试 |
| `tests/test_api_exam/test_marking_assign.py` | 加 3 个新测试 |

### 不涉及的文件

- `grading/models.py` — 无 schema 变更，GradingAssignment 已有 question_ids(JSON) + total_count + graded_count，够用
- `grading/assignment_router.py` — /api/v1/grading/assignments 端点不改（marking 路由是主入口）
- `ai/tools/grading_ops.py` — auto_assign 签名不变，行为变了但工具层无需改

### 关键设计决策

1. **不做答卷预分配**：不在分配时指定具体哪些 StudentAnswer 给哪个教师。采用"动态配额"——教师领取下一份未改答卷，改到自己的配额上限就停。简单且容错。
2. **total_count=0 表示不限**：向后兼容旧数据。
3. **一行一题一教师**：不再把多题合并到一个 assignment 行里追加。每次分配创建独立行。旧逻辑是追加 question_ids，新逻辑每行 question_ids 只含一个元素。

## 每个文件的具体改法

### 1. `marking/router.py`

**AssignRequest** 加字段：
```python
class AssignRequest(BaseModel):
    exam_id: str
    question_id: str
    teacher_id: str
    answer_count: int = 0  # 0 = 不限
```

**_flatten_assignment** 响应加字段：
```python
"answer_count": a.total_count, "graded_count": a.graded_count,
```

**assign_question** 核心改动：
- 保留同教师+同题的 409 冲突检测（防重复）
- 去掉"追加到已有 assignment"逻辑，每次创建独立行
- 设 `total_count=req.answer_count`

**新增 DELETE 端点**（在 list_all_assignments 和 list_teachers 之间）：
```python
@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id, current, db):
    # 管理员校验 + school_id 过滤 + db.delete
```

**next_answer 端点**（~L302）改传 teacher_id：
```python
result = await get_next_answer(
    db, question_id, school_id, teacher_id=current["user"].id,
)
```

**submit_score 端点**（~L393）加更新进度+传 teacher_id：
```python
from edu_cloud.modules.marking.scorer import update_assignment_progress
await update_assignment_progress(db, answer.question_id, current["user"].id, school_id)

next_ans = await get_next_answer(
    db, answer.question_id, school_id, teacher_id=current["user"].id,
)
```

### 2. `marking/scorer.py`

**import** 加 GradingAssignment：
```python
from edu_cloud.modules.grading.models import GradingAssignment, GradingResult
```

**get_next_answer** 签名加 `*, teacher_id: str | None = None`，函数开头加配额检查：
```python
if teacher_id:
    my_assigns = (await db.execute(
        select(GradingAssignment).where(
            GradingAssignment.assigned_to == teacher_id,
            GradingAssignment.school_id == school_id,
            GradingAssignment.is_second_grading.is_(False),
        )
    )).scalars().all()
    for a in my_assigns:
        if question_id in (a.question_ids or []):
            if a.total_count > 0 and a.graded_count >= a.total_count:
                return None
            break
```

**新增函数** `update_assignment_progress`（在 submit_score 和 get_progress 之间）：
```python
async def update_assignment_progress(db, question_id, teacher_id, school_id):
    assignments = (await db.execute(
        select(GradingAssignment).where(
            GradingAssignment.assigned_to == teacher_id,
            GradingAssignment.school_id == school_id,
        )
    )).scalars().all()
    for a in assignments:
        if question_id in (a.question_ids or []):
            a.graded_count = a.graded_count + 1
            if a.total_count > 0 and a.graded_count >= a.total_count:
                a.status = "completed"
            elif a.status == "pending":
                a.status = "in_progress"
    await db.flush()
```

### 3. `grading/assignment_service.py`

**assign_block** 冲突检测加 `GradingAssignment.assigned_to == teacher_id` 条件（只查同教师）。

**auto_assign** 改为每题分给所有教师：
```python
base = total_count_per_question // n if total_count_per_question else 0
remainder = total_count_per_question % n if total_count_per_question else 0
for q_id in question_ids:
    for i, teacher_id in enumerate(teacher_ids):
        count = base + (1 if i < remainder else 0)
        # 创建 GradingAssignment(question_ids=[q_id], total_count=count, ...)
```

### 4. `MarkingAssignPage.vue`

核心变化：
- 去掉 `assignMap`（1:1 映射）、`checkedKeys`、`batchTeacherId`、批量操作栏
- 加 `newAssign = reactive({})`（per-question 的临时教师选择和数量）
- 模板从 n-data-table 改为 per-question 卡片：每题显示已分配教师列表 + "添加教师"行（n-select + n-input-number + 按钮）
- `assignedCount` → `assignedQuestionCount`（基于 assignments 数组去重）
- `teacherWorkload` 基于 answer_count 而非题数
- 加 `getAssignsForQuestion(qid)` 和 `getTeacherName(tid)` 辅助函数
- `handleAssign(questionId)` 发送 `answer_count` 字段
- 加 `removeAssign(assignId)` 调用 DELETE 端点
- myColumns 加"分配数量"和"已批改"列

### 5. 测试

**test_assignment_service.py**：
- 删 `test_assign_block_duplicate_rejected`
- 加 `test_assign_block_different_teacher_same_question_ok`（不同教师同题 → 成功）
- 加 `test_assign_block_same_teacher_same_question_rejected`（同教师同题 → ConflictError）

**test_marking_assign.py**：
- 加 `test_assign_same_question_different_teachers`（同题两教师 → 201+201，列表 2 条）
- 加 `test_assign_with_answer_count`（answer_count=30 → 响应含 answer_count=30）
- 加 `test_delete_assignment`（创建→删除→列表为空）

## 上一个会话为什么没完成

所有改动多次通过 Edit 工具写入并验证（23 个测试全过），但环境中的 linter/formatter PostToolUse hook 持续将源文件还原到原始版本。测试文件和前端文件的改动也最终被清除。需要在新窗口中一次性应用全部改动。

## 执行建议

1. 按上面 5 个文件的改法逐个 Edit
2. 跑 `pytest tests/test_api_exam/test_marking_assign.py tests/test_services/test_assignment_service.py -v`
3. 确认 23+ passed, 0 failed
4. 跑全量 `pytest --tb=short -q` 确认无回归
5. 前端 `npx vitest run` 确认无回归（本次无前端测试变更，只改 .vue）
