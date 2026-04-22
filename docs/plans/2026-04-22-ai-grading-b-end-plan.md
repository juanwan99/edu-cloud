---
baseline_command: "cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q"
baseline_verified_at: "2026-04-22 22:08:48"
baseline_count: "1933 passed, 23 skipped (backend) + 234 passed (frontend vitest)"
---

# AI 阅卷 B 端改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 添加题目级 AI 阅卷能力：教务录入原题+答案 → AI 生成评分细则 → 逐题或批量阅卷 → 逐空评分明细。

**Architecture:** Question 表扩展 4 字段存储题干/答案内容，GradingTask 表加 question_id 支持题目级粒度。新增 AI Rubric 生成端点调 llm-proxy，Worker prompt 升级返回逐空明细。前端新增 AiGradingPage 左右分栏页面。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic / Vue 3 + Naive UI / llm-proxy (OpenAI-compatible)

**Design:** `docs/plans/2026-04-22-ai-grading-b-end-design.md`

## semantic_regression

- ORC-001: GradingResult 状态机 ai_pending→ai_done→confirmed 不可改变，source 语义不可改变
- ORC-002: 科目级 GradingTask（question_id=NULL）的现有行为不可回归——前置校验 4 项、worker 全科主观题加载
- ORC-003: Rubric 与 Question 一对一（UniqueConstraint on question_id）不可改变
- ORC-004: llm-proxy 调用走 OpenAI-compatible 格式（/chat/completions），slot 路由不可改变
- ORC-005: lesson_prep_leader 权限扩展只加不减，_TEACHER_BASE 现有权限集不可删除

---

### Task 1: Alembic Migration — Question + GradingTask 字段扩展

**Files:**
- Create: `alembic/versions/xxxx_add_question_content_and_grading_question_id.py`
- Modify: `src/edu_cloud/modules/exam/models.py:61-74`
- Modify: `src/edu_cloud/modules/grading/models.py:25-35`

- [ ] **Step 1: 修改 Question 模型添加 4 字段**

在 `src/edu_cloud/modules/exam/models.py` Question 类（line 61-74），在 `correct_answer` 和 `school_id` 之间添加 4 个字段:

```python
    correct_answer: Mapped[str | None] = mapped_column(String(50), default=None)
    content: Mapped[str | None] = mapped_column(Text, default=None)
    content_images: Mapped[list | None] = mapped_column(JSON, default=None)
    reference_answer: Mapped[str | None] = mapped_column(Text, default=None)
    reference_answer_images: Mapped[list | None] = mapped_column(JSON, default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
```

`Text` 已在 line 11 import 列表中。

- [ ] **Step 2: 修改 GradingTask 模型添加 question_id**

在 `src/edu_cloud/modules/grading/models.py` GradingTask 类（line 25-35），在 `subject_id` 之后添加:

```python
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    question_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("questions.id"), default=None, nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
```

- [ ] **Step 3: 生成 Alembic migration**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m alembic revision --autogenerate -m "add question content and grading task question_id"`

验证生成文件包含 5 个 `add_column`，downgrade 包含对应 `drop_column`。

- [ ] **Step 4: 执行 migration**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m alembic upgrade head`
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/exam/models.py src/edu_cloud/modules/grading/models.py alembic/versions/*question_content*
git commit -m "feat(models): add question content fields and grading task question_id"
```

---

### Task 2: 权限对齐 — lesson_prep_leader 加阅卷权限

**Files:**
- Modify: `src/edu_cloud/core/permissions.py:240`
- Test: `tests/test_services/test_permissions_grading.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_services/test_permissions_grading.py`:

```python
from edu_cloud.core.permissions import Permission, has_permission


def test_lesson_prep_leader_has_view_grading():
    assert has_permission("lesson_prep_leader", Permission.VIEW_GRADING)


def test_lesson_prep_leader_has_manage_grading():
    assert has_permission("lesson_prep_leader", Permission.MANAGE_GRADING)


def test_lesson_prep_leader_has_manage_exams():
    assert has_permission("lesson_prep_leader", Permission.MANAGE_EXAMS)


def test_academic_director_still_has_grading():
    """ORC-005: 现有角色权限不回归。"""
    assert has_permission("academic_director", Permission.MANAGE_GRADING)
    assert has_permission("academic_director", Permission.VIEW_GRADING)


def test_subject_teacher_no_manage_grading():
    assert not has_permission("subject_teacher", Permission.MANAGE_GRADING)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_permissions_grading.py -v`
Expected: `test_lesson_prep_leader_has_manage_grading` 和 `test_lesson_prep_leader_has_manage_exams` FAIL

- [ ] **Step 3: 实现权限扩展**

修改 `src/edu_cloud/core/permissions.py` line 240，将:

```python
    "lesson_prep_leader": _TEACHER_BASE.copy(),
```

改为:

```python
    "lesson_prep_leader": _TEACHER_BASE | {
        Permission.MANAGE_GRADING,
        Permission.MANAGE_EXAMS,
    },
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_permissions_grading.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 给新增端点加 require_permission 守卫（AGP-002 修复）**

在实现 Task 3-5 的新端点时，必须使用 `require_permission` 依赖注入而非仅 `get_current_user`：
- `PUT /questions/{id}/content` → `require_permission(Permission.MANAGE_EXAMS)`
- `POST /questions/{id}/content/upload-image` → `require_permission(Permission.MANAGE_EXAMS)`
- `POST /grading/rubrics/generate` → `require_permission(Permission.MANAGE_GRADING)`
- `POST /grading/rubrics`（已有端点）→ 补加 `require_permission(Permission.MANAGE_GRADING)`
- `POST /grading/tasks`（已有端点）→ 补加 `require_permission(Permission.MANAGE_GRADING)`
- `POST /grading/review/{result_id}`（已有端点）→ 补加 `require_permission(Permission.MANAGE_GRADING)`

注：design 中 rubrics/generate 写的 VIEW_GRADING 是笔误，统一以 plan 为准用 MANAGE_GRADING（生成和保存 Rubric 是写操作）。

在 Task 3/4/5 的测试中必须包含 403 反例：用无权限角色调用新端点验证被拒。

- [ ] **Step 6: 同步前端 permissions.js（AGP-002 修复）**

在 `frontend/src/config/permissions.js` 的 `lesson_prep_leader` 权限集中添加 `manage_grading` 和 `manage_exams`，与后端保持镜像一致。

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/core/permissions.py tests/test_services/test_permissions_grading.py frontend/src/config/permissions.js
git commit -m "feat(permissions): add MANAGE_GRADING and MANAGE_EXAMS to lesson_prep_leader with endpoint guards"
```

---

### Task 3: Question Content API — 题干/答案录入端点

**Files:**
- Modify: `src/edu_cloud/modules/exam/router.py`（添加 2 个端点）
- Test: `tests/test_api_exam/test_question_content.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_api_exam/test_question_content.py`。先 Grep `src/edu_cloud/modules/exam/router.py` 确认现有 question response 函数名和结构，在测试中用现有 fixture 模式（参考 `tests/conftest.py` 的 `client` / `admin_headers` fixture）。

测试内容:
1. `test_update_question_content` — PUT 成功更新 content + reference_answer
2. `test_update_content_not_found` — 不存在的 question 返回 404
3. `test_upload_question_image` — POST multipart 上传图片返回路径

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_question_content.py -v`
Expected: FAIL

- [ ] **Step 3: 实现端点**

在 `src/edu_cloud/modules/exam/router.py` 添加:

1. `QuestionContentUpdate` schema（content/content_images/reference_answer/reference_answer_images 全 optional）
2. `PUT /questions/{question_id}/content` — 更新字段，返回 question response（含新字段）
3. `POST /questions/{question_id}/content/upload-image` — Multipart 上传，保存到 `{UPLOAD_DIR}/questions/{question_id}/{uuid}.{ext}`，返回 `{"path": "/uploads/questions/..."}`

确保 `_question_response` 或对应的 response helper 包含 content/content_images/reference_answer/reference_answer_images 字段。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_question_content.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/exam/router.py tests/test_api_exam/test_question_content.py
git commit -m "feat(exam): add question content update and image upload endpoints"
```

---

### Task 4: Rubric AI 生成 — Prompt + LLM Client + 端点

**Files:**
- Modify: `src/edu_cloud/modules/grading/prompts.py:84` — 添加 `build_rubric_generation_prompt`
- Modify: `src/edu_cloud/modules/grading/llm_client.py` — 添加 `generate_rubric` 方法
- Modify: `src/edu_cloud/modules/grading/router.py` — 添加 `POST /rubrics/generate` + helper
- Test: `tests/test_api_exam/test_rubric_generate.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_api_exam/test_rubric_generate.py`:

1. `test_generate_rubric_success` — mock `generate_rubric_via_llm`，验证返回 criteria 结构和 source="ai_generated"
2. `test_generate_rubric_no_content` — question 无 content 和 reference_answer 时返回 400

Mock 返回值:
```python
[
    {"blankNo": "1", "score": 4, "answer": "光合作用...", "intent": "考查...", "coreRequirement": "必须..."},
    {"blankNo": "2", "score": 4, "answer": "叶绿体...", "intent": "考查...", "coreRequirement": "明确..."},
]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_rubric_generate.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Rubric 生成 prompt**

在 `src/edu_cloud/modules/grading/prompts.py` 末尾添加 `build_rubric_generation_prompt(content, reference_answer, max_score, question_type)`:

- system prompt: 资深阅卷组长角色，要求拆分得分点，返回 JSON 数组
- user prompt: 原题 + 参考答案 + 满分
- 返回: `[{"role": "system", ...}, {"role": "user", ...}]`

- [ ] **Step 4: 实现 LLM Client generate_rubric 方法**

在 `src/edu_cloud/modules/grading/llm_client.py` LLMClient 类添加 `async def generate_rubric(self, messages, images_b64=None) -> list[dict]`:

- 与 `grade` 方法类似的 HTTP 调用逻辑
- `max_tokens=4096`（rubric 生成比评分更长）
- 解析 JSON 数组返回

- [ ] **Step 5: 实现 POST /rubrics/generate 端点**

在 `src/edu_cloud/modules/grading/router.py` 添加:

1. `RubricGenerateRequest` schema（question_id + max_score）
2. `generate_rubric_via_llm(question, max_score)` 独立 async 函数（便于 mock）
3. `POST /rubrics/generate` 端点:
   - 查 Question（含 content/images）
   - 校验 content 或 reference_answer 非空
   - 调 `generate_rubric_via_llm`
   - Upsert Rubric（source="ai_generated"）
   - 返回 rubric response

- [ ] **Step 6: 加强 RubricCreate 校验（AGP-003 修复）**

修改 `POST /grading/rubrics` 端点，入库前校验 criteria 结构：
1. 每个 item 必须有 `blankNo`（str）和 `score`（number >= 0）
2. `answer` 字段必须非空（AI 生成时自动填充，手动编辑时也必须填）
3. 所有 item 的 `score` 之和必须等于 `Question.max_score`（需查 DB）
4. 不满足时返回 422

新增测试：
- `test_rubric_create_missing_fields` — 缺 blankNo 返回 422
- `test_rubric_create_score_mismatch` — 总分不等于 max_score 返回 422
- `test_rubric_create_negative_score` — 负分返回 422

- [ ] **Step 7: 补图片→base64 实现（AGP-005 修复）**

在 `generate_rubric_via_llm` 函数中，明确实现图片路径→本地文件→base64 转换：
```python
import base64
from pathlib import Path

upload_root = Path(settings.UPLOAD_DIR).resolve()
images_b64 = []
for img_path in all_image_paths:
    if img_path.startswith("/uploads/"):
        local = upload_root / img_path.split("/uploads/", 1)[1]
    else:
        local = upload_root / img_path
    if local.exists() and str(local.resolve()).startswith(str(upload_root)):
        with open(local, "rb") as f:
            images_b64.append(base64.b64encode(f.read()).decode())
```

新增测试：`test_generate_rubric_with_images` — mock LLM 验证图片 base64 被传入 messages

- [ ] **Step 8: 运行测试确认通过**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_rubric_generate.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/modules/grading/prompts.py src/edu_cloud/modules/grading/llm_client.py src/edu_cloud/modules/grading/router.py tests/test_api_exam/test_rubric_generate.py
git commit -m "feat(grading): add AI rubric generation with validation and image support"
```

---

### Task 5: GradingTask 题目级支持 — Router + Worker

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py:114-229` — schema + 创建逻辑
- Modify: `src/edu_cloud/workers/grading.py:82-217` — 题目级分支
- Test: `tests/test_api_exam/test_grading_task_question.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_api_exam/test_grading_task_question.py`:

1. `test_create_task_with_question_id` — 传 question_id 创建成功，返回中含 question_id
2. `test_create_task_question_no_rubric` — 题目无 Rubric 时 400
3. `test_create_task_subject_level_unchanged` — ORC-002: 不传 question_id 走科目级逻辑不变
4. `test_create_task_question_wrong_subject` — question_id 属于另一科目时 400（AGP-001 反例）
5. `test_create_task_regrade_cleans_old_results` — 重复阅卷时先清理旧 ai_pending/ai_done 的 GradingResult（AGP-004 反例）

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_task_question.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 Router**

1. `GradingTaskCreate` 加 `question_id: str | None = None`
2. `_task_response` 加 `"question_id": t.question_id`
3. `create_grading_task` 中:
   - `if req.question_id:` → 题目级校验（AGP-001 修复：必须同时校验 `Question.id == req.question_id AND Question.subject_id == req.subject_id AND Question.school_id == school_id AND question_type IN SUBJECTIVE`，缺任一返回 400 "该题目不存在、不属于该科目或非主观题"）+ 有 Rubric + 有 StudentAnswer
   - `else:` → 现有科目级校验原封不动（ORC-002）
   - `GradingTask(question_id=req.question_id, ...)` 构造时传入
   - 新增反例测试：`test_create_task_question_wrong_subject` — question_id 属于另一科目时返回 400

- [ ] **Step 4: 修改 Worker**

`src/edu_cloud/workers/grading.py` `process_grading_task` 中:

```python
            if task.question_id:
                # AGP-001 修复：worker 也需校验 subject_id 归属 + 主观题类型（防御性断言）
                q_result = await db.execute(
                    select(Question).where(
                        Question.id == task.question_id,
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            else:
                q_result = await db.execute(
                    select(Question).where(
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
```

StudentAnswer 查询同理按 question_id 过滤。

- [ ] **Step 5: 重跑语义（AGP-004 修复）**

在 `create_grading_task` 端点中，创建 GradingTask 之前，检查并清理旧的未确认结果：
```python
# 重跑语义：清理该范围内 status != 'confirmed' 的旧 GradingResult
# （已 confirmed 的由教师确认过，不可覆盖）
old_filter = [
    GradingResult.school_id == school_id,
    GradingResult.status.in_(["ai_pending", "ai_done"]),
]
if req.question_id:
    old_filter.append(GradingResult.question_id == req.question_id)
else:
    old_filter.append(GradingResult.question_id.in_(subjective_q_ids))

old_results = (await db.execute(select(GradingResult).where(*old_filter))).scalars().all()
for old in old_results:
    await db.delete(old)
if old_results:
    await db.commit()
    logger.info("create_grading_task: cleaned %d stale results before re-grading", len(old_results))
```

同时，在 Worker 中排除已有 confirmed 结果的 answer：

```python
# Worker: 排除已确认答案，避免撞 UniqueConstraint(answer_id)
confirmed_answer_ids = set()
if answer_data:
    confirmed_rows = (await db.execute(
        select(GradingResult.answer_id).where(
            GradingResult.answer_id.in_([a["answer_id"] for a in answer_data]),
            GradingResult.status == "confirmed",
        )
    )).scalars().all()
    confirmed_answer_ids = set(confirmed_rows)
answer_data = [a for a in answer_data if a["answer_id"] not in confirmed_answer_ids]
```

这保证：
- 清理 ai_pending/ai_done → worker 可新建 GradingResult
- confirmed 答案被排除出 worker 处理范围 → 不撞 UniqueConstraint
- ORC-001 保护：已确认结果不被覆盖

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_task_question.py -v`
Expected: PASS

- [ ] **Step 6: 运行全量后端测试（ORC-002 回归验证）**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: 无新增 FAIL

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/grading/router.py src/edu_cloud/workers/grading.py tests/test_api_exam/test_grading_task_question.py
git commit -m "feat(grading): support per-question grading task in router and worker"
```

---

### Task 6: 评分 Prompt 升级 — 逐空明细返回

**Files:**
- Modify: `src/edu_cloud/modules/grading/prompts.py:11-50` — 三个 system prompt 升级
- Modify: `src/edu_cloud/modules/grading/llm_client.py:88-101` — 解析兼容
- Modify: `src/edu_cloud/workers/grading.py:178-192` — 存储 details
- Test: `tests/test_workers/test_grading_detail.py`

- [ ] **Step 1: 写测试**

创建 `tests/test_workers/test_grading_detail.py`:

```python
import json
from edu_cloud.modules.grading.prompts import build_grading_prompt


def test_grading_prompt_requests_details():
    """prompt 要求返回 details 数组。"""
    rubric = {"criteria": [{"blankNo": "1", "score": 4, "answer": "test", "intent": "i", "coreRequirement": "c"}]}
    question = {"name": "第1题", "max_score": 4}
    messages = build_grading_prompt(rubric, question, "essay")
    system_text = messages[0]["content"]
    assert "details" in system_text
    assert "blankNo" in system_text


def test_grading_prompt_backward_compat():
    """老 3 字段 criteria 也能正常构建 prompt。"""
    rubric = {"criteria": [{"point": "概念", "score": 3, "description": "正确"}]}
    question = {"name": "Q1", "max_score": 3}
    messages = build_grading_prompt(rubric, question)
    assert len(messages) == 2
```

- [ ] **Step 2: 升级 system prompts**

修改 `src/edu_cloud/modules/grading/prompts.py` 三个 system prompt，统一要求返回:

```
{"score": 总分, "details": [{"blankNo": "1", "score": 得分, "maxScore": 满分, "reason": "原因"}], "comment": "评语", "confidence": 0-1}
```

将 `_SYSTEM_PROMPT_GENERIC`/`_SYSTEM_PROMPT_FILL_BLANK`/`_SYSTEM_PROMPT_ESSAY` 中的返回格式说明替换。

修改 `build_grading_prompt` 的 user_content 中最后一行为:
```
请根据图片中的学生答案和以上评分细则进行评分，返回 JSON（含 details 逐空明细）。
```

- [ ] **Step 3: 修改 LLM Client 解析兼容**

`llm_client.py` grade 方法中解析逻辑兼容新旧格式:

```python
                feedback = parsed.get("comment", parsed.get("feedback", ""))
```

- [ ] **Step 4: 修改 Worker 存储 details**

`workers/grading.py` line 186 将 `ai_raw_response` 改为:

```python
                            ai_raw_response={
                                "raw_content": result_dict["raw_content"],
                                "details": result_dict.get("details"),
                            },
```

在 `_grade_single` 返回 dict 中透传 parsed details（从 raw_content 解析）。

- [ ] **Step 5: 补充 Worker 行为测试（AGP-006 修复）**

在 `tests/test_workers/test_grading_detail.py` 中追加：

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_worker_question_level_loads_single_question():
    """题目级任务只加载指定 question 的答案。"""
    # mock db + llm, 验证 select(Question).where(Question.id == task.question_id) 被调用
    # 验证 answer_data 只含该 question_id 的答案
    pass  # Executor 按此契约实现完整 mock


@pytest.mark.asyncio
async def test_worker_stores_details_in_raw_response():
    """Worker 将 LLM 返回的 details 存入 ai_raw_response.details。"""
    # mock llm.grade 返回含 details 的 raw_content
    # 验证 GradingResult.ai_raw_response["details"] 非空
    pass  # Executor 按此契约实现完整 mock


def test_llm_client_comment_to_feedback_compat():
    """LLM 返回 comment 字段时映射到 GradeResponse.feedback。"""
    from edu_cloud.modules.grading.llm_client import GradeResponse
    # 模拟解析 {"score": 4, "comment": "好", "confidence": 0.9, "details": [...]}
    # 验证 GradeResponse.feedback == "好"
    pass  # Executor 按此契约实现
```

每个测试的 `pass` 注释标明了契约意图，Executor 必须实现完整 mock 和断言。

- [ ] **Step 6: 运行测试**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_workers/test_grading_detail.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/grading/prompts.py src/edu_cloud/modules/grading/llm_client.py src/edu_cloud/workers/grading.py tests/test_workers/test_grading_detail.py
git commit -m "feat(grading): upgrade prompts for per-blank scoring details with worker tests"
```

---

### Task 7: dispatch/status 扩展 — 返回题目详情

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py:407-578` — questions 列表

- [ ] **Step 1: 在 get_dispatch_status 循环内查题目信息**

在 `for subj in subjects:` 循环中，查询主观题+rubric 状态+per-question answer/graded counts，组装 `questions_info` 列表。

- [ ] **Step 2: 在 result.append 中添加 `"questions": questions_info`**

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/ -k "dispatch" -v --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/grading/router.py
git commit -m "feat(grading): include question details in dispatch/status response"
```

---

### Task 8: 前端 API + 路由 + 组件 + 页面

**Files:**
- Modify: `frontend/src/api/grading.js`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/components/RubricEditor.vue`
- Create: `frontend/src/components/QuestionContentModal.vue`
- Create: `frontend/src/pages/AiGradingPage.vue`
- Modify: `frontend/src/pages/GradingDispatchPage.vue`

- [ ] **Step 1: 扩展 grading API**

在 `frontend/src/api/grading.js` 添加:
- `generateRubric(questionId, maxScore)` → POST /grading/rubrics/generate
- `getRubric(questionId)` → GET /grading/rubrics/{questionId}
- `saveRubric(data)` → POST /grading/rubrics
- `updateQuestionContent(questionId, data)` → PUT /questions/{id}/content
- `uploadQuestionImage(questionId, file)` → POST /questions/{id}/content/upload-image

- [ ] **Step 2: 添加路由**

在 `frontend/src/router/index.js` 阅卷部分添加:
```javascript
{ path: 'exams/:examId/ai-grading/:subjectId', name: 'AiGrading',
  component: () => import('../pages/AiGradingPage.vue'),
  meta: { roles: GRADING_DISPATCH_ROLES } },
```

- [ ] **Step 3: 创建 RubricEditor.vue**

评分细则展示与编辑组件（v-model 双向绑定 criteria 数组，分值合计校验，loading 状态）。

- [ ] **Step 4: 创建 QuestionContentModal.vue**

题干/答案编辑弹窗（textarea + 多图上传 NUpload）。

- [ ] **Step 5: 创建 AiGradingPage.vue**

左右分栏页面:
- 左侧: 主观题列表（有内容/有细则状态标签）
- 右侧: 原题卡片 + 答案卡片 + 评分细则（RubricEditor）+ 阅卷操作（进度+按钮）
- 编辑弹窗（QuestionContentModal ×2）
- 轮询逻辑（createTask → setInterval getTask → 完成后 clearInterval）

- [ ] **Step 6: 在 GradingDispatchPage 添加 AI 阅卷入口**

每科行添加"AI 阅卷"按钮，`router.push(/exams/${examId}/ai-grading/${subj.subject_id})`。

- [ ] **Step 7: 构建验证**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vite build 2>&1 | tail -10`
Expected: 无编译错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/grading.js frontend/src/router/index.js frontend/src/components/RubricEditor.vue frontend/src/components/QuestionContentModal.vue frontend/src/pages/AiGradingPage.vue frontend/src/pages/GradingDispatchPage.vue
git commit -m "feat(frontend): add AiGradingPage with question-level grading UI"
```

---

### Task 9: 前端测试 + 集成验证

**Files:**
- Create: `frontend/src/components/__tests__/RubricEditor.spec.js`

- [ ] **Step 1: RubricEditor 测试**

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RubricEditor from '../../components/RubricEditor.vue'

describe('RubricEditor', () => {
  const items = [
    { blankNo: '1', score: 4, answer: 'A1', intent: 'I1', coreRequirement: 'C1' },
    { blankNo: '2', score: 4, answer: 'A2', intent: 'I2', coreRequirement: 'C2' },
  ]

  it('renders items', () => {
    const w = mount(RubricEditor, { props: { modelValue: items, maxScore: 8 } })
    expect(w.findAll('.rubric-item')).toHaveLength(2)
  })

  it('shows total', () => {
    const w = mount(RubricEditor, { props: { modelValue: items, maxScore: 8 } })
    expect(w.text()).toContain('8 / 8')
  })

  it('warns mismatch', () => {
    const w = mount(RubricEditor, { props: { modelValue: items, maxScore: 10 } })
    expect(w.find('.warning').exists()).toBe(true)
  })

  it('empty state', () => {
    const w = mount(RubricEditor, { props: { modelValue: [], maxScore: 8 } })
    expect(w.text()).toContain('暂无')
  })
})
```

- [ ] **Step 2: 前端全量测试**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 3: 后端全量测试**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: 无新增 FAIL（基线 1933 passed）

- [ ] **Step 4: 端点可达验证（AGP-007 修复：不 kill 全局进程）**

用 pytest httpx AsyncClient 验证新端点注册成功（复用 conftest 的 client fixture）：

```python
# tests/test_api_exam/test_endpoint_smoke.py
@pytest.mark.asyncio
async def test_rubric_generate_endpoint_exists(client, admin_headers):
    resp = await client.post("/api/v1/grading/rubrics/generate", json={}, headers=admin_headers)
    assert resp.status_code != 404  # 422 或 400 都说明端点存在

@pytest.mark.asyncio
async def test_question_content_endpoint_exists(client, admin_headers):
    resp = await client.put("/api/v1/questions/fake/content", json={}, headers=admin_headers)
    assert resp.status_code != 404

@pytest.mark.asyncio
async def test_dispatch_status_returns_questions(client, db_engine, admin_headers):
    """AGP-006: dispatch/status 返回 questions 字段。"""
    from tests.helpers import create_exam_with_question
    exam, subj, q = await create_exam_with_question(db_engine, question_type="essay")
    resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "questions" in data[0]
```

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_endpoint_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/__tests__/RubricEditor.spec.js tests/test_api_exam/test_endpoint_smoke.py
git commit -m "test: add RubricEditor and endpoint smoke tests"
```

---

## Contract Pack（AGP-008 修复）

### invariants

| ID | 不变量 | verification |
|---|---|---|
| INV-01 | GradingResult.answer_id UniqueConstraint 不可删除 | new_test: `test_create_task_regrade_cleans_old_results`（验证清理 + worker 不撞约束） |
| INV-02 | Rubric 与 Question 一对一（UniqueConstraint on question_id） | new_test: `test_rubric_create_upsert`（同 question_id 第二次调用更新而非报错） |
| INV-03 | 科目级 GradingTask（question_id=NULL）前置校验 4 项不变 | new_test: `test_create_task_subject_level_unchanged` |
| INV-04 | GradingResult 状态机 confirmed 结果不被重跑覆盖 | new_test: `test_create_task_regrade_preserves_confirmed`（confirmed 答案排除出 worker 范围） |
| INV-05 | Worker 题目级分支仍只处理主观题 | new_test: `test_worker_question_level_loads_single_question`（断言 SUBJECTIVE 过滤） |

### counter_examples

| ID | 反例描述 | tests_that_still_pass | mitigation |
|---|---|---|---|
| CE-01 | question_id 属于另一科目但同一学校 → 脏任务 | `test_create_task_question_wrong_subject` 返回 400 | Router 同时校验 question_id + subject_id + school_id |
| CE-02 | Rubric criteria 总分 != Question.max_score → 错误评分 | `test_rubric_create_score_mismatch` 返回 422 | 入库前读 Question.max_score 做守恒校验 |
| CE-03 | 重复阅卷撞 UniqueConstraint(answer_id) → 批次中断 | `test_create_task_regrade_cleans_old_results` | Router 清理 ai_pending/ai_done + Worker 排除 confirmed 答案 |

### risk_modules

| 模块 | 风险点 | 改动文件数 |
|---|---|---|
| `modules/grading/router.py` | 新增 3 端点 + 改 3 端点（tasks/rubrics/review 加权限守卫）+ dispatch 扩展 | 1 |
| `modules/grading/prompts.py` | 评分 prompt 升级返回 details + 新增 rubric 生成 prompt | 1 |
| `modules/grading/llm_client.py` | 新增 generate_rubric 方法 + grade 解析兼容 comment/feedback | 1 |
| `modules/exam/models.py` | Question 加 4 字段（migration） | 1 |
| `modules/exam/router.py` | 新增 2 端点（content update + image upload） | 1 |
| `modules/grading/models.py` | GradingTask 加 question_id（migration）；Rubric.criteria 类型注解改 `Mapped[list]` | 1 |
| `workers/grading.py` | 题目级分支 + 排除 confirmed + 逐空明细存储 | 1 |
| `core/permissions.py` | lesson_prep_leader 权限扩展 | 1 |
| `frontend/src/config/permissions.js` | 前端权限镜像同步 | 1 |
| `frontend/src/pages/AiGradingPage.vue` | 新页面 | 1 |
| `frontend/src/components/RubricEditor.vue` | 新组件 | 1 |
| `frontend/src/components/QuestionContentModal.vue` | 新组件 | 1 |
| `frontend/src/api/grading.js` | 新增 API 方法 | 1 |
| `frontend/src/router/index.js` | 新增路由 | 1 |

### test_debt

| 项 | 理由 | deadline |
|---|---|---|
| Worker 端到端集成测试（真实 DB + mock LLM） | 当前 worker 测试全用 mock session，首版先保持一致 | 下一轮迭代（AI 阅卷 v2） |
| 前端 AiGradingPage 完整 E2E | 需浏览器环境，Vitest 只能测组件级 | 手动验证覆盖 |
| dispatch/status 多任务聚合语义 | 题目级+科目级任务并存时的 stage 推导需专项测试 | AI 阅卷 v2（当前只取最新 task） |

### 补充说明

**Rubric.criteria 类型注解**（R2 NEW-02）：`models.py` 中 `Mapped[dict]` 改为 `Mapped[list]`，JSON 字段内容不变，只是类型注解更准确。

**dispatch/status 多任务语义**（R2 NEW-01）：当前 dispatch/status 按 `subject_id` 取最新一条 GradingTask。引入题目级任务后，同一科目可能有多条 task。首版保持现有"取最新 task"行为不变——题目级任务的进度通过 `questions[].graded_count` 展示，科目级 stage 仍由最新 task 决定。完整的多任务聚合语义推迟到 AI 阅卷 v2。
