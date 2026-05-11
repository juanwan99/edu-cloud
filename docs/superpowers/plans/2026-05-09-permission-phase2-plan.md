# Permission Isolation Phase 2 — 架构级修复

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Claude + GPT 联合审计发现的剩余 29 个权限隔离漏洞（5 CRITICAL / 8 HIGH / 16 MEDIUM），并通过共享基础设施消除重复模式。

**Architecture:** 三层递进 — (1) 集中化租户 helper 消除 9 处重复定义 (2) 逐模块修复 L1 跨校泄露 (3) 补充 L2 校内角色隔离。所有修复遵循统一模式：school_id 从 JWT 取 + fail-closed + 写操作加权限。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async / pytest + httpx / Alembic

**前序工作:** Phase 1 已修 10 项（commits 803ed7d..0e4bf69），见 `docs/permission-isolation-handoff.md`

---

## 审计发现覆盖矩阵

| 审计 ID | 问题 | 状态 | Plan Task |
|---------|------|------|-----------|
| C1 knowledge 零隔离 | link_question 无 question 归属校验 | 本计划 | Task 4 |
| C3 pipeline cv_template | Template 查询缺 school_id（7 处） | 本计划 | Task 2 |
| C4 pipeline scan-image | 文件路径无租户隔离 | 本计划 | Task 3 |
| C5 card_export doc-page-image | 文件路径无租户隔离 | 本计划 | Task 3 |
| H1 homework list_submissions | 查询无 school_id | 本计划 | Task 5 |
| H2 homework from-exam | class_id 不验证归属 | 本计划 | Task 5 |
| H3 bank error-book ×4 | student_id 无归属验证 | 本计划 | Task 8 |
| H4 pipeline progress/stop | 全局状态非学校隔离 | 延期（Phase 3 架构重构） |
| H5 card_export render/get doc-pages | subject_id 路径未验证 | 本计划 | Task 3 |
| M1 grading tasks | 列表无 visible_subject_codes | 本计划 | Task 8 |
| M2 bank questions ×4 | 无 subject 过滤 | 本计划 | Task 8 |
| M3 profile ×4 | subject_code 参数无验证 | 本计划 | Task 8 |
| M5 grading_review GET ×3 | 缺 require_permission | 本计划 | Task 7 |
| M6 assignment POST | 不验证实体归属 | 本计划 | Task 7 |
| M7 student 写操作 ×4 | 缺 require_permission | 本计划 | Task 7 |
| GPT-new pipeline delete_orphan | 无 school 校验 | 本计划 | Task 2 |
| GPT-new pipeline start Template | Template 缺 school_id | 本计划 | Task 2 |
| GPT-new card template_router | Template 查询只按 subject_id | 本计划 | Task 6 |

**延期说明:** H4（pipeline progress/stop 全局状态）需要 per-school pipeline 队列重构，超出逐端点修复范围，归入 Phase 3 租户中间件。

---

## 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 租户 helper | `_CROSS_SCHOOL_ROLES` 9 处重复定义 | 9 个 router 文件 | grep 确认 |
| 租户 helper | `_get_school_id()` 仅 1 处 | `exam/results_router.py:15` | grep 确认 |
| Scope 过滤 | `ScopeFilter.apply()` | `core/scope_filter.py:15-27` | 8 处 import |
| 可见性 helper | `get_visible_class_ids/subject_codes` | `api/permissions.py:18-31` | 9 处使用 |
| 管理员角色集 | `SCHOOL_ADMIN_ROLES` | `api/permissions.py:9` | frozenset |
| 模型 | Template 有 school_id 列 | `card/models.py:19` | Read 确认 |
| 模型 | ConceptGraphNode 无 school_id（全局设计） | `knowledge_tree/models.py:11-33` | Read 确认 |
| 模型 | HomeworkSubmission 无 school_id（通过 task_id→HomeworkTask 间接） | `homework/models.py` | Read 确认 |

## 增量 vs 新建论证

- 默认立场：增强已有代码
- `_CROSS_SCHOOL_ROLES` 和 `_get_school_id` 已有实现，只需集中化
- ScopeFilter 已存在但未充分利用，本次不扩展其职责（Phase 3 再评估）
- 不引入新框架/中间件，所有修复在现有 router/service 层完成

## 交付路径

- 目标：后端 API 安全修复，无前端变更
- 验证：`pytest` 全量通过 + 新增隔离测试
- 用户访问 URL：https://mcu.asia（修复后行为不变，只是阻止越权访问）

---

## Task 1: 集中化租户 helper

**Files:**
- Create: `src/edu_cloud/core/tenant.py`
- Modify: `src/edu_cloud/modules/exam/results_router.py` (移除本地定义)
- Modify: 其余 8 个定义 `_CROSS_SCHOOL_ROLES` 的 router 文件
- Test: `tests/test_core/test_tenant.py`

**动机:** `_CROSS_SCHOOL_ROLES` 在 9 个文件重复定义，`_get_school_id` 只在 1 个文件。集中化后所有 Task 共用。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_core/test_tenant.py
from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES, get_school_id
from fastapi import HTTPException
import pytest


def test_cross_school_roles_contains_expected():
    assert "platform_admin" in CROSS_SCHOOL_ROLES
    assert "district_admin" in CROSS_SCHOOL_ROLES
    assert len(CROSS_SCHOOL_ROLES) == 2


def test_get_school_id_normal_role():
    class FakeRole:
        role = "subject_teacher"
        school_id = "school-001"
    current = {"current_role": FakeRole()}
    assert get_school_id(current) == "school-001"


def test_get_school_id_admin_returns_none():
    class FakeRole:
        role = "platform_admin"
        school_id = None
    current = {"current_role": FakeRole()}
    assert get_school_id(current) is None


def test_get_school_id_missing_raises_403():
    class FakeRole:
        role = "subject_teacher"
        school_id = None
    current = {"current_role": FakeRole()}
    with pytest.raises(HTTPException) as exc:
        get_school_id(current)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_core/test_tenant.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: 实现 core/tenant.py**

```python
# src/edu_cloud/core/tenant.py
from fastapi import HTTPException

CROSS_SCHOOL_ROLES: frozenset[str] = frozenset({"platform_admin", "district_admin"})


def get_school_id(current: dict) -> str | None:
    role = current["current_role"]
    if role.role in CROSS_SCHOOL_ROLES:
        return None
    school_id = role.school_id
    if not school_id:
        raise HTTPException(403, "Role has no school_id")
    return school_id
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_core/test_tenant.py -v`
Expected: 4 PASS

- [ ] **Step 5: 替换所有 router 中的本地定义**

在以下 9 个文件中，将本地 `_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}` 替换为 `from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES`，并将使用处 `_CROSS_SCHOOL_ROLES` 改为 `CROSS_SCHOOL_ROLES`：

1. `src/edu_cloud/modules/exam/results_router.py` — 同时移除本地 `_get_school_id`，改用 `from edu_cloud.core.tenant import get_school_id`
2. `src/edu_cloud/modules/exam/joint_exam_router.py`
3. `src/edu_cloud/modules/grading/assignment_router.py`
4. `src/edu_cloud/modules/grading/quality_router.py`
5. `src/edu_cloud/modules/school/settings_router.py`
6. `src/edu_cloud/modules/school/assignment_router.py`
7. `src/edu_cloud/modules/school/selection_router.py`
8. `src/edu_cloud/modules/school/capability_router.py`
9. `src/edu_cloud/modules/school/audit_router.py`

- [ ] **Step 6: 全量测试回归**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: 所有现有测试通过

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/core/tenant.py tests/test_core/test_tenant.py
git add src/edu_cloud/modules/exam/results_router.py src/edu_cloud/modules/exam/joint_exam_router.py
git add src/edu_cloud/modules/grading/assignment_router.py src/edu_cloud/modules/grading/quality_router.py
git add src/edu_cloud/modules/school/settings_router.py src/edu_cloud/modules/school/assignment_router.py
git add src/edu_cloud/modules/school/selection_router.py src/edu_cloud/modules/school/capability_router.py
git add src/edu_cloud/modules/school/audit_router.py
git commit -m "refactor: centralize CROSS_SCHOOL_ROLES and get_school_id into core/tenant.py"
```

---

## Task 2: Pipeline Template 查询补 school_id + delete_orphan 归属校验

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py` (lines 480, 533, 762, 836, 911, 1094, 1129 Template 查询 + ~1283 delete_orphan Question 查询)
- Test: `tests/test_api/test_pipeline_template_isolation.py`

**依赖:** Task 1（import CROSS_SCHOOL_ROLES / get_school_id）
**串行约束:** Task 3 也改 pipeline_router.py，必须在 Task 2 之后执行。

**动机:** Template 模型有 school_id 列，但 7 处查询只按 subject_id，跨校可读/写模板。另外 delete_orphan_questions 按 subject_id/name 删 Question 无 school 校验。GPT 确认 CRITICAL。

**admin 处理:** `get_school_id()` 对 admin 返回 None。Template 查询需要条件式过滤：`if school_id: stmt = stmt.where(Template.school_id == school_id)`，admin 不加此条件（全局视图）。

- [ ] **Step 1: 写隔离测试**

```python
# tests/test_api/test_pipeline_template_isolation.py
"""Pipeline Template 跨校隔离测试。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_cv_template_isolated(
    client_school_a: AsyncClient,
    client_school_b: AsyncClient,
    template_school_a_subject_id: str,
):
    """学校 A 的模板，学校 B 查不到。"""
    resp = await client_school_b.get(
        "/api/v1/scan/pipeline/cv-template",
        params={"subject_id": template_school_a_subject_id},
    )
    assert resp.status_code == 200
    assert resp.json() == []  # 学校 B 看不到学校 A 的模板


@pytest.mark.asyncio
async def test_verify_template_isolated(
    client_school_a: AsyncClient,
    client_school_b: AsyncClient,
    template_school_a_subject_id: str,
):
    """学校 B 无法 verify 学校 A 的模板。"""
    resp = await client_school_b.get(
        "/api/v1/scan/pipeline/verify-template",
        params={"subject_id": template_school_a_subject_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("has_template") is False
```

- [ ] **Step 1b: 补充 start/preview/import/delete_orphan 入口测试**

```python
@pytest.mark.asyncio
async def test_start_pipeline_template_isolated(
    client_school_b: AsyncClient,
    subject_id_school_a: str,
):
    """学校 B 启动 pipeline 时拿不到学校 A 的模板。"""
    resp = await client_school_b.post(
        "/api/v1/scan/pipeline/start",
        json={"subject_id": subject_id_school_a, "image_dir": "/tmp/test"},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_preview_template_isolated(
    client_school_b: AsyncClient,
    subject_id_school_a: str,
):
    """学校 B preview 时拿不到学校 A 的模板。"""
    resp = await client_school_b.post(
        "/api/v1/scan/pipeline/preview",
        json={"subject_id": subject_id_school_a, "image_path": "/tmp/test.png"},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_import_tpl_template_isolated(
    client_school_b: AsyncClient,
    subject_id_school_a: str,
):
    """学校 B import-tpl 时不能覆盖学校 A 的模板。"""
    resp = await client_school_b.post(
        "/api/v1/scan/pipeline/import-tpl",
        json={"subject_id": subject_id_school_a, "tpl_path": "/tmp/test.tpl"},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_delete_orphan_questions_isolated(
    client_school_b: AsyncClient,
    subject_id_school_a: str,
):
    """学校 B 不能删除学校 A 的孤立题目。"""
    resp = await client_school_b.post(
        "/api/v1/scan/pipeline/delete-orphan-questions",
        json={"subject_id": subject_id_school_a},
    )
    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_pipeline_template_isolation.py -v`
Expected: FAIL — 学校 B 能看到学校 A 模板

- [ ] **Step 3: 修复所有 Template 查询**

在 `pipeline_router.py` 中，每处 `select(Template).where(Template.subject_id == ...)` 追加 `Template.school_id == school_id`。

需要修复的位置（行号来自实际 grep 确认）：

**统一模式：** 所有 Template 查询用条件式过滤，admin 不限制：
```python
from edu_cloud.core.tenant import get_school_id
school_id = get_school_id(current)
stmt = select(Template).where(Template.subject_id == subject_id)
if school_id:
    stmt = stmt.where(Template.school_id == school_id)
```

| # | 端点 | 行号 | 修复内容 |
|---|------|------|---------|
| 1 | start_pipeline | 480 | Template 查询追加 school_id 条件 |
| 2 | start_pipeline | 533 | 同上（第二处 Template 查询） |
| 3 | preview | 762 | Template 查询追加 school_id 条件 |
| 4 | import_tpl | 836 | Template upsert 查询追加 school_id |
| 5 | get_cv_template | 911 | Template 查询追加 school_id 条件 |
| 6 | save_cv_template | 1094 | Template upsert 查询追加 school_id |
| 7 | verify_template | 1129 | Template 查询追加 school_id 条件 |
| 8 | delete_orphan_questions | ~1283 | Question 删除追加 `Question.school_id == school_id` |

**save_cv_template 内部 Question 查询** (~line 944) 也需追加 `Question.school_id == school_id`。

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_pipeline_template_isolation.py -v`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_router.py tests/test_api/test_pipeline_template_isolation.py
git commit -m "fix: add school_id filter to all Template queries in pipeline_router (8 sites)"
```

---

## Task 3: 文件路径租户隔离

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py` (serve_scan_image, browse_directory)
- Modify: `src/edu_cloud/modules/card/card_export_router.py` (get_doc_page_image, render_doc_pages, get_doc_pages)
- Test: `tests/test_api/test_file_path_isolation.py`

**依赖:** Task 1（import get_school_id）
**串行约束:** 必须在 Task 2 之后（共享 pipeline_router.py）。Task 6 也改 card_export_router.py，必须在 Task 3 之后。

**动机:** 5 个端点接受用户提供的文件路径，仅校验 UPLOAD_DIR 前缀（startswith），不校验租户子目录。GPT 确认 CRITICAL。

**路径校验方式:** 使用 `Path.is_relative_to()` 替代 `startswith`，防目录名前缀碰撞（如 `school-1` vs `school-10`）。

- [ ] **Step 1: 写隔离测试**

```python
# tests/test_api/test_file_path_isolation.py
"""文件路径租户隔离测试。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_scan_image_cross_school_blocked(
    client_school_b: AsyncClient,
):
    """学校 B 无法通过路径访问学校 A 的扫描图片。"""
    resp = await client_school_b.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": "school-a-id/exam-123/subject-456/image.png"},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_scan_image_prefix_collision_blocked(
    client_school_b: AsyncClient,
):
    """前缀碰撞测试：school-1 用户不能访问 school-10 的文件。"""
    resp = await client_school_b.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": "school-10-fake/image.png"},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_doc_page_image_cross_school_blocked(
    client_school_b: AsyncClient,
):
    """学校 B 无法通过路径访问学校 A 的答题卡渲染图。"""
    resp = await client_school_b.get(
        "/api/v1/card/doc-page-image",
        params={"path": "doc-pages/other-subject-id/page-1.png"},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_browse_dir_scoped_to_school(
    client_school_a: AsyncClient,
):
    """browse-dir 只能浏览本校目录。"""
    resp = await client_school_a.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "/"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: 修复 serve_scan_image**

在 `pipeline_router.py` 的 `serve_scan_image` 中，UPLOAD_DIR 前缀校验之后追加租户路径校验（使用 `is_relative_to` 防前缀碰撞）：

```python
from edu_cloud.core.tenant import get_school_id
school_id = get_school_id(current)
if school_id:
    school_root = Path(settings.UPLOAD_DIR) / school_id
    if not resolved.is_relative_to(school_root):
        raise HTTPException(403, "Access denied")
```

- [ ] **Step 3: 修复 get_doc_page_image**

在 `card_export_router.py` 的 `get_doc_page_image` 中，校验 subject_id 归属：

```python
school_id = get_school_id(current)
if school_id:
    parts = Path(req_path).parts
    if len(parts) >= 2 and parts[0] == "doc-pages":
        subject_id = parts[1]
        subject = (await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
        )).scalar_one_or_none()
        if not subject:
            raise HTTPException(404, "Not found")
```

- [ ] **Step 4: 修复 browse_directory**

限制 browse-dir 只能浏览 `UPLOAD_DIR/{school_id}/` 下的目录（`is_relative_to` 校验）。

- [ ] **Step 5: 修复 render_doc_pages 和 get_doc_pages**

添加 subject_id 归属校验（`Subject.school_id == school_id`）后再构造路径。

- [ ] **Step 6: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_file_path_isolation.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: 全绿

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_router.py src/edu_cloud/modules/card/card_export_router.py
git add tests/test_api/test_file_path_isolation.py
git commit -m "fix: enforce tenant path isolation on file-serving and browse endpoints"
```

---

## Task 4: Knowledge link_question 归属校验

**Files:**
- Modify: `src/edu_cloud/modules/knowledge/router.py`
- Modify: `src/edu_cloud/modules/knowledge/service.py`
- Test: `tests/test_api/test_knowledge_isolation.py`

**动机:** knowledge 模块 5 个端点零权限校验。ConceptGraphNode 是全局设计（无 school_id），但 link_question 和 get_question_knowledge_points 涉及 Question（有 school_id），必须校验 question 归属。知识点本身的读取（list/get/children）是全局共享数据，可保持开放。

- [ ] **Step 1: 写隔离测试**

```python
# tests/test_api/test_knowledge_isolation.py
"""Knowledge 模块隔离测试。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_link_question_cross_school_blocked(
    client_school_b: AsyncClient,
    question_school_a_id: str,
    concept_id: str,
):
    """学校 B 不能给学校 A 的题目关联知识点。"""
    resp = await client_school_b.post(
        "/api/v1/knowledge/link",
        json={"question_id": question_school_a_id, "concept_id": concept_id},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_question_kp_cross_school_blocked(
    client_school_b: AsyncClient,
    question_school_a_id: str,
):
    """学校 B 不能查看学校 A 题目的知识点关联。"""
    resp = await client_school_b.get(
        f"/api/v1/knowledge/question/{question_school_a_id}",
    )
    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: 修复 router.py**

```python
# knowledge/router.py — link_question 端点
@router.post("/link")
async def link_question(
    req: LinkRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.EDIT_KNOWLEDGE_TREE)),
):
    school_id = current["current_role"].school_id
    result = await knowledge_service.link_question(
        db, question_id=req.question_id, concept_id=req.concept_id, school_id=school_id,
    )
    return result

# get_question_knowledge_points 端点
@router.get("/question/{question_id}")
async def get_question_kps(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    school_id = current["current_role"].school_id
    return await knowledge_service.get_question_knowledge_points(
        db, question_id=question_id, school_id=school_id,
    )
```

- [ ] **Step 3: 修复 service.py**

注意：`link_question` 现有签名是 `(db, *, question_id, concept_id, is_primary=True)`，必须保留 `is_primary` 参数，新增 kw-only `school_id`：

```python
# knowledge/service.py — 保留 is_primary，新增 school_id
async def link_question(
    db: AsyncSession, *, question_id: str, concept_id: str,
    is_primary: bool = True, school_id: str | None = None,
) -> QuestionKnowledgePoint:
    # 校验 question 归属（admin school_id=None 跳过）
    if school_id:
        from edu_cloud.modules.exam.models import Question
        q = (await db.execute(
            select(Question).where(Question.id == question_id, Question.school_id == school_id)
        )).scalar_one_or_none()
        if not q:
            from fastapi import HTTPException
            raise HTTPException(404, "Question not found")
    # ... existing link logic (unchanged)

async def get_question_knowledge_points(
    db: AsyncSession, *, question_id: str, school_id: str | None = None,
) -> list[ConceptGraphNode]:
    if school_id:
        from edu_cloud.modules.exam.models import Question
        q = (await db.execute(
            select(Question).where(Question.id == question_id, Question.school_id == school_id)
        )).scalar_one_or_none()
        if not q:
            from fastapi import HTTPException
            raise HTTPException(404, "Question not found")
    # ... existing query logic (unchanged)
```

- [ ] **Step 4: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_knowledge_isolation.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge/router.py src/edu_cloud/modules/knowledge/service.py
git add tests/test_api/test_knowledge_isolation.py
git commit -m "fix: add question ownership check to knowledge link and query endpoints"
```

---

## Task 5: Homework service 深度防御

**Files:**
- Modify: `src/edu_cloud/modules/homework/service.py` (submit, grade_single, list_submissions, grade_batch)
- Test: `tests/test_api/test_homework_submission_isolation.py`

**动机:** Router 层已校验 task 归属，但 service 层的 submit/grade_single 直接用 submission_id 查询不带 school_id。GPT 判定 router 层防护有效故降级为 HIGH，但防御深度不足 — 如果未来有其他入口调 service 就会泄露。

- [ ] **Step 1: 写隔离测试**

```python
# tests/test_api/test_homework_submission_isolation.py
"""Homework submission 深度隔离测试。"""
import pytest


@pytest.mark.asyncio
async def test_submit_validates_task_school(
    client_school_b, task_id_school_a, submission_id_school_a,
):
    """学校 B 无法提交学校 A 的作业。"""
    resp = await client_school_b.post(
        f"/api/v1/homework/tasks/{task_id_school_a}/submissions/{submission_id_school_a}/submit",
        json={"content": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grade_validates_task_school(
    client_school_b, task_id_school_a, submission_id_school_a,
):
    """学校 B 无法批改学校 A 的作业。"""
    resp = await client_school_b.post(
        f"/api/v1/homework/tasks/{task_id_school_a}/submissions/{submission_id_school_a}/grade",
        json={"score": 100, "feedback": "good"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 修复 service.py**

在 `HomeworkSubmissionService` 的 `submit()` 和 `grade_single()` 中，查询 submission 时 JOIN HomeworkTask 校验 school_id：

```python
async def submit(self, db, *, task_id: str, submission_id: str, school_id: str, **kwargs):
    submission = (await db.execute(
        select(HomeworkSubmission)
        .join(HomeworkTask, HomeworkSubmission.task_id == HomeworkTask.id)
        .where(
            HomeworkSubmission.id == submission_id,
            HomeworkSubmission.task_id == task_id,
            HomeworkTask.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not submission:
        raise HTTPException(404, "Submission not found")
    # ... rest of logic
```

同样修复 `grade_single()`, `list_submissions()`, `grade_batch()`。

- [ ] **Step 3: 更新 router 调用**

Router 中调用 service 方法时传入 `school_id=_school_id(current)` 参数。

- [ ] **Step 4: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_homework_submission_isolation.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/homework/service.py src/edu_cloud/modules/homework/router.py
git add tests/test_api/test_homework_submission_isolation.py
git commit -m "fix: add school_id depth defense to homework submission service"
```

---

## Task 6: Card template/export school_id 修复

**Files:**
- Modify: `src/edu_cloud/modules/card/template_router.py` (~line 45-55)
- Modify: `src/edu_cloud/modules/card/card_export_router.py` (~line 50-83)
- Modify: `src/edu_cloud/modules/card/router.py` (~line 537-542)
- Test: `tests/test_api/test_card_template_isolation.py`

**动机:** GPT 发现 template_router.py 的 Template 查询只按 subject_id/side，card_export generate/v2 的 Template upsert 缺 school_id，card/router.py template-json 缺 school_id。Template 模型有 school_id 列。

- [ ] **Step 1: 写隔离测试**

```python
# tests/test_api/test_card_template_isolation.py
"""Card template 跨校隔离测试。"""
import pytest


@pytest.mark.asyncio
async def test_template_download_cross_school_blocked(
    client_school_b, subject_id_school_a,
):
    resp = await client_school_b.get(
        "/api/v1/card/template/download",
        params={"subject_id": subject_id_school_a, "side": "A"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_json_cross_school_blocked(
    client_school_b, subject_id_school_a, exam_id_school_a,
):
    resp = await client_school_b.get(
        "/api/v1/card/template-json",
        params={"subject_id": subject_id_school_a, "exam_id": exam_id_school_a},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 修复三个文件的 Template 查询**

所有 `select(Template).where(Template.subject_id == ...)` 追加 `Template.school_id == school_id`。

**template_router.py** (~line 45-55): download_answer_template 内部 Template 查询
**card_export_router.py** (~line 50-83): generate_card_v2 内部 Template 查询
**card/router.py** (~line 537-542): export_template_json 内部 Template 查询

- [ ] **Step 3: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_card_template_isolation.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/card/template_router.py src/edu_cloud/modules/card/card_export_router.py
git add src/edu_cloud/modules/card/router.py tests/test_api/test_card_template_isolation.py
git commit -m "fix: add school_id filter to all card Template queries"
```

---

## Task 7: Permission decorator 加固

**Files:**
- Modify: `src/edu_cloud/modules/student/router.py` (4 write endpoints)
- Modify: `src/edu_cloud/modules/grading/grading_review_router.py` (3 GET endpoints)
- Modify: `src/edu_cloud/modules/grading/assignment_router.py` (POST cross-entity validation)
- Test: `tests/test_api/test_permission_decorators.py`

**动机:** student 写操作用 get_current_user（任何登录用户可改）；grading_review GET 用 get_current_user（无权限检查）；assignment POST 不验证 teacher/exam/subject 归属。

- [ ] **Step 1: 写权限测试**

```python
# tests/test_api/test_permission_decorators.py
"""权限装饰器加固测试。"""
import pytest


@pytest.mark.asyncio
async def test_student_create_requires_manage_teachers(
    client_no_manage_teachers,
):
    """无 MANAGE_TEACHERS 权限不能创建学生。"""
    resp = await client_no_manage_teachers.post(
        "/api/v1/students",
        json={"name": "test", "student_number": "001", "class_id": "c1"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_grading_review_results_requires_permission(
    client_no_view_grading,
):
    """无 VIEW_GRADING 权限不能查看阅卷结果。"""
    resp = await client_no_view_grading.get("/api/v1/grading/review/results")
    assert resp.status_code == 403
```

- [ ] **Step 2: 修复 student/router.py**

将 4 个写端点的 `get_current_user` 改为 `require_permission(Permission.MANAGE_TEACHERS)`（`MANAGE_STUDENTS` 不存在于当前 Permission 枚举，`MANAGE_TEACHERS` 已授权给 principal/academic_director，语义覆盖学生管理）:
- POST `/students` (创建)
- PATCH `/students/{student_id}` (更新)
- DELETE `/students/{student_id}` (删除)
- POST `/students/import` (导入)

- [ ] **Step 3: 修复 grading_review_router.py**

将 3 个 GET 端点的 `get_current_user` 改为 `require_permission(Permission.VIEW_GRADING)`:
- GET `/results`
- GET `/review/pending`
- GET `/results/{result_id}`

- [ ] **Step 4: 修复 assignment_router.py**

在 POST `/assignments` 中添加跨实体归属校验：
```python
# 校验 teacher 属于目标学校
teacher_role = (await db.execute(
    select(UserRole).where(
        UserRole.user_id == req.teacher_id,
        UserRole.school_id == school_id,
    )
)).scalar_one_or_none()
if not teacher_role:
    raise HTTPException(400, "Teacher does not belong to this school")
```

- [ ] **Step 5: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_permission_decorators.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/student/router.py src/edu_cloud/modules/grading/grading_review_router.py
git add src/edu_cloud/modules/grading/assignment_router.py tests/test_api/test_permission_decorators.py
git commit -m "fix: enforce permission decorators on student writes and grading review reads"
```

---

## Task 8: L2 校内角色隔离 — grading tasks + bank + profile

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py` (GET /tasks, GET /tasks/{task_id})
- Modify: `src/edu_cloud/modules/bank/router.py` (4 question endpoints + 4 error-book endpoints)
- Modify: `src/edu_cloud/modules/profile/router.py` (4 student endpoints)
- Test: `tests/test_api/test_l2_visible_scope.py`

**动机:** 这些端点有 L1 school_id 隔离但缺 L2 visible_subject_codes / visible_class_ids 过滤。科任教师可以看到全校所有科目/班级的数据。

- [ ] **Step 1: 写 L2 隔离测试**

```python
# tests/test_api/test_l2_visible_scope.py
"""L2 校内角色隔离测试。"""
import pytest


@pytest.mark.asyncio
async def test_grading_tasks_filtered_by_subject(
    client_math_teacher,  # subject_codes=["math"]
    grading_task_chinese_id: str,  # 语文阅卷任务
):
    """数学老师看不到语文阅卷任务。"""
    resp = await client_math_teacher.get("/api/v1/grading/tasks")
    assert resp.status_code == 200
    task_ids = [t["id"] for t in resp.json()]
    assert grading_task_chinese_id not in task_ids


@pytest.mark.asyncio
async def test_bank_questions_filtered_by_subject(
    client_math_teacher,
):
    """数学老师只能搜索数学题。"""
    resp = await client_math_teacher.get(
        "/api/v1/bank/questions",
        params={"subject_code": "chinese"},
    )
    assert resp.status_code == 200
    assert resp.json() == []  # 无权查看语文题


@pytest.mark.asyncio
async def test_error_book_filtered_by_visible_class(
    client_class1_teacher,  # class_ids=["class-1"]
    student_class2_id: str,
):
    """1 班老师看不到 2 班学生的错题本。"""
    resp = await client_class1_teacher.get(
        f"/api/v1/bank/error-book/{student_class2_id}",
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: 修复 grading/router.py**

在 GET `/tasks` 中追加 `visible_subject_codes` 过滤。GradingTask 有 `subject_id` 列（FK→subjects，`grading/models.py:28`），直接 JOIN Subject 取 code。不用 question_id（nullable + 批量任务用 question_ids JSON），避免 LEFT JOIN 漏行：

```python
from edu_cloud.api.permissions import get_visible_subject_codes
from edu_cloud.modules.exam.models import Subject

visible_subjects = get_visible_subject_codes(current["current_role"])
stmt = select(GradingTask).where(GradingTask.school_id == school_id)
if visible_subjects is not None:
    stmt = stmt.join(Subject, GradingTask.subject_id == Subject.id)\
               .where(Subject.code.in_(visible_subjects))
```

GET `/tasks/{task_id}` 同理。

- [ ] **Step 3: 修复 bank/router.py**

question 端点：追加 `visible_subject_codes` 过滤（通过 subject_code 字段）。
error-book 端点：追加学生归属校验 — 查 student.class_id 是否在 `visible_class_ids` 中。

```python
from edu_cloud.api.permissions import get_visible_class_ids

visible = get_visible_class_ids(current["current_role"])
if visible is not None:
    student = (await db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )).scalar_one_or_none()
    if not student or (student.class_id not in visible):
        raise HTTPException(403, "No access to this student")
```

- [ ] **Step 4: 修复 profile/router.py**

student 端点：追加 `subject_code` 参数校验 — 如果请求指定了 subject_code，确认在 `visible_subject_codes` 中。

```python
visible_subjects = get_visible_subject_codes(current["current_role"])
if visible_subjects is not None and subject_code and subject_code not in visible_subjects:
    raise HTTPException(403, "No access to this subject")
```

- [ ] **Step 5: 运行测试 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_l2_visible_scope.py -v`
Run: `.venv/bin/python -m pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/grading/router.py src/edu_cloud/modules/bank/router.py
git add src/edu_cloud/modules/profile/router.py tests/test_api/test_l2_visible_scope.py
git commit -m "fix: enforce L2 visible_subject_codes and visible_class_ids on grading/bank/profile"
```

---

## 显式延期项

| 项目 | 原因 | 后续处理 |
|------|------|---------|
| H4 pipeline progress/stop 全局状态 | 需要 per-school pipeline 队列重构 | Phase 3 租户中间件 |
| F-08 teacher_router 跨校查询面 | 调查确认 teacher_router 已有完整 MANAGE_TEACHERS + school_id 隔离 | 无需修复 |
| F-10 homework 同校非授权教师操作 | router 层已有 require_permission(MANAGE_HOMEWORK/VIEW_HOMEWORK) + school_id 校验 | Task 5 补 service 层 school_id 深度防御已足够；对象级 teacher/class 权限属于 L2 范畴，可后续增量 |

---

## semantic_regression:

```yaml
ORC-001: CROSS_SCHOOL_ROLES 必须只包含 platform_admin 和 district_admin
  verification: test_tenant.py::test_cross_school_roles_contains_expected

ORC-002: 非 admin 角色缺 school_id 时 get_school_id 必须 raise 403
  verification: test_tenant.py::test_get_school_id_missing_raises_403

ORC-003: Template 查询必须包含 school_id WHERE 条件（admin 豁免）
  verification: test_pipeline_template_isolation.py

ORC-004: 文件服务端点必须用 Path.is_relative_to 校验租户路径
  verification: test_file_path_isolation.py

ORC-005: knowledge link_question 必须校验 question 归属（保留 is_primary 参数）
  verification: test_knowledge_isolation.py::test_link_question_cross_school_blocked

ORC-006: homework submission service 必须通过 JOIN HomeworkTask 校验 school_id
  verification: test_homework_submission_isolation.py

ORC-007: student 写操作必须要求 MANAGE_TEACHERS 权限（MANAGE_STUDENTS 不存在）
  verification: test_permission_decorators.py::test_student_create_requires_permission

ORC-008: grading tasks 列表必须通过 GradingTask.subject_id→Subject.code 过滤（不走 question_id）
  verification: test_l2_visible_scope.py::test_grading_tasks_filtered_by_subject

ORC-009: error-book 必须校验学生在 visible_class_ids 中
  verification: test_l2_visible_scope.py::test_error_book_filtered_by_visible_class
```

---

## 执行顺序与依赖

```
Task 1 (shared helpers)
  ↓
Task 2 (pipeline Template) ──串行──→ Task 3 (pipeline 文件路径)
  ↓                                      ↓
  │                              Task 6 (card template) ──串行──→（card_export_router.py 共享）
  │
Task 4 (knowledge)     ← 可与 Task 2 并行
Task 5 (homework)      ← 可与 Task 2 并行
Task 7 (permission)    ← 可与 Task 2 并行
Task 8 (L2 scope)      ← 可与 Task 2 并行
```

**串行约束（同文件）:**
- Task 2 → Task 3（共享 `pipeline_router.py`）
- Task 3 → Task 6（共享 `card_export_router.py`）

**并行安全组:**
- 组 A: Task 2 → Task 3 → Task 6（串行链）
- 组 B: Task 4 + Task 5 + Task 7 + Task 8（与组 A 并行，互不重叠）

建议 Batch 1（CRITICAL）: Task 1 → 组 A + 组 B 的 Task 4；Batch 2（HIGH）: Task 5 + Task 7；Batch 3（MEDIUM）: Task 8。每批一次 codex-review。
