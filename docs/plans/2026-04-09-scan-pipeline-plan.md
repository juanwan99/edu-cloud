<!-- pre-takeover: archived for history, not active spec -->
# 试卷全链路打通 — exam-ai 兼容层实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 edu-cloud 新增 exam-ai 兼容路由层，使 paper-seg 零代码改动即可连接 edu-cloud 完成扫描全链路。

**Architecture:** 新建 `compat_router.py`，挂载到 `/api`（不带 `/v1`），将 paper-seg 的 8 个 API 调用转接到 edu-cloud 已有逻辑。同时修复 publish 端点的 status 限制。

**Tech Stack:** FastAPI, SQLAlchemy async, pytest, httpx AsyncClient

**Design:** `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-pipeline-design.md`

---

### Task 1: 兼容登录端点

**Files:**
- Create: `src/edu_cloud/api/compat_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_compat.py`

- [ ] **Step 1: 创建 compat_router.py 骨架 + 登录端点**

```python
"""exam-ai 兼容路由 — paper-seg 零改动对接。"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.shared.auth import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["compat"])


class CompatLoginRequest(BaseModel):
    school_code: str = ""  # paper-seg 会传，兼容层忽略
    username: str
    password: str


@router.post("/auth/login")
async def compat_login(req: CompatLoginRequest, db: AsyncSession = Depends(get_db)):
    """兼容 exam-ai 登录协议。忽略 school_code，走 edu-cloud 标准登录。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not user.verify_password(req.password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(401, "User is inactive")

    roles_result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    roles = roles_result.scalars().all()
    if not roles:
        raise HTTPException(403, "No role assigned")

    primary = next((r for r in roles if r.is_primary), roles[0])
    token = create_access_token({
        "sub": user.id,
        "role": primary.role,
        "active_role_id": primary.id,
    })
    logger.info("compat_login: user=%s, role=%s", req.username, primary.role)
    return {"access_token": token}
```

- [ ] **Step 2: 在 app.py 注册 compat_router**

在 `src/edu_cloud/api/app.py` 的路由注册区域（`app.include_router(auth_router)` 附近）添加：

```python
    from edu_cloud.api.compat_router import router as compat_router
    app.include_router(compat_router)
```

- [ ] **Step 3: 写登录测试**

创建 `tests/test_api/test_compat.py`：

```python
"""exam-ai 兼容层测试 — paper-seg 对接端点。"""
import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.modules.card.models import Template
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def compat_seed(client: AsyncClient, db):
    """创建兼容层测试所需的学校+用户+考试+科目。"""
    school = School(id="cs1", name="兼容测试校", code="COMPAT01")
    db.add(school)
    await db.commit()

    user = User(id="cu1", username="compat_user", display_name="兼容用户")
    user.set_password("pass123")
    db.add(user)
    await db.commit()

    role = UserRole(user_id="cu1", role="principal", school_id="cs1", is_primary=True)
    db.add(role)
    await db.commit()

    exam = Exam(id="ce1", name="兼容测试考试", school_id="cs1")
    db.add(exam)
    await db.commit()

    subject = Subject(id="csub1", exam_id="ce1", name="数学", code="SX", school_id="cs1")
    db.add(subject)
    await db.commit()

    return {"school_id": "cs1", "user_id": "cu1", "exam_id": "ce1", "subject_id": "csub1"}


class TestCompatLogin:
    async def test_login_with_school_code(self, client: AsyncClient, compat_seed):
        """paper-seg 传 school_code，兼容层忽略并正常返回 JWT。"""
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_login_wrong_password(self, client: AsyncClient, compat_seed):
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "wrong",
        })
        assert resp.status_code == 401
```

- [ ] **Step 4: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_compat.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/compat_router.py src/edu_cloud/api/app.py tests/test_api/test_compat.py
git commit -m "feat: exam-ai compat login endpoint for paper-seg"
```

**审查清单:**
- ✓ school_code 被忽略不影响登录
- ✓ 错误密码返回 401
- ✗ 不存在的用户返回 401（非 500）

---

### Task 2: 考试和科目列表端点

**Files:**
- Modify: `src/edu_cloud/api/compat_router.py`
- Test: `tests/test_api/test_compat.py`

- [ ] **Step 1: 添加 exams + subjects 端点**

在 `compat_router.py` 添加：

```python
from edu_cloud.api.deps import get_current_user
from edu_cloud.models.exam import Exam, Subject


@router.get("/exams")
async def compat_list_exams(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出当前学校的考试（paper-seg 拉取考试列表）。"""
    school_id = current["current_role"].school_id
    result = await db.execute(
        select(Exam).where(Exam.school_id == school_id).order_by(Exam.created_at.desc())
    )
    exams = result.scalars().all()
    return [{"id": e.id, "name": e.name, "status": e.status} for e in exams]


@router.get("/exams/{exam_id}/subjects")
async def compat_list_subjects(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出考试的科目（paper-seg 拉取科目列表）。"""
    school_id = current["current_role"].school_id
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    result = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    subjects = result.scalars().all()
    return [{"id": s.id, "name": s.name, "code": s.code} for s in subjects]
```

- [ ] **Step 2: 写测试**

在 `test_compat.py` 追加：

```python
class TestCompatExams:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "pass123",
        })
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_list_exams(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams", headers=headers)
        assert resp.status_code == 200
        exams = resp.json()
        assert len(exams) == 1
        assert exams[0]["id"] == "ce1"
        assert exams[0]["name"] == "兼容测试考试"

    async def test_list_subjects(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams/ce1/subjects", headers=headers)
        assert resp.status_code == 200
        subjects = resp.json()
        assert len(subjects) == 1
        assert subjects[0]["name"] == "数学"

    async def test_list_subjects_wrong_exam(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams/nonexist/subjects", headers=headers)
        assert resp.status_code == 404
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_compat.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/api/compat_router.py tests/test_api/test_compat.py
git commit -m "feat: compat exams/subjects list endpoints"
```

**审查清单:**
- ✓ 只返回当前学校的考试
- ✓ 不存在的考试返回 404
- ✗ 其他学校的考试不可见

---

### Task 3: 模板拉取端点

**Files:**
- Modify: `src/edu_cloud/api/compat_router.py`
- Test: `tests/test_api/test_compat.py`

- [ ] **Step 1: 添加模板 GET 端点**

在 `compat_router.py` 添加：

```python
from edu_cloud.modules.card.models import Template


@router.get("/templates/{subject_id}/{side}")
async def compat_get_template(
    subject_id: str,
    side: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """返回 paper-seg 兼容格式的答题卡模板。"""
    school_id = current["current_role"].school_id
    result = await db.execute(
        select(Template).where(
            Template.subject_id == subject_id,
            Template.side == side,
            Template.school_id == school_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "Template not found")

    return {
        "id": template.id,
        "subject_id": template.subject_id,
        "side": template.side,
        "image_size": {
            "width": template.image_width,
            "height": template.image_height,
        },
        "anchors": template.anchors or [],
        "regions": template.regions or [],
        "sample_image": template.sample_image,
    }
```

- [ ] **Step 2: 写测试**

在 `test_compat.py` 的 `compat_seed` fixture 末尾（`return` 之前）追加 Template 种子数据：

```python
    tpl = Template(
        subject_id="csub1", side="A", school_id="cs1",
        image_width=3308, image_height=2308,
        anchors=[{"id": "TL", "cx": 102, "cy": 97}],
        regions=[{"id": "Q01", "type": "subjective", "rect": {"x1": 100, "y1": 200, "x2": 500, "y2": 600}, "question_id": "q1"}],
    )
    db.add(tpl)
    await db.commit()
```

追加测试类：

```python
class TestCompatTemplate:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "X", "username": "compat_user", "password": "pass123",
        })
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    async def test_get_template(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/templates/csub1/A", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_size"]["width"] == 3308
        assert data["image_size"]["height"] == 2308
        assert len(data["anchors"]) == 1
        assert data["anchors"][0]["id"] == "TL"
        assert len(data["regions"]) == 1
        assert data["regions"][0]["type"] == "subjective"

    async def test_get_template_not_found(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/templates/csub1/B", headers=headers)
        assert resp.status_code == 404
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_compat.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/api/compat_router.py tests/test_api/test_compat.py
git commit -m "feat: compat template endpoint with paper-seg format"
```

**审查清单:**
- ✓ image_size 是 `{width, height}` 格式（非 image_width/image_height）
- ✓ 未发布的模板返回 404
- ✗ 其他学校的模板不可见

---

### Task 4: 扫描上传端点（切图 + 选择题 + 任务）

**Files:**
- Modify: `src/edu_cloud/api/compat_router.py`
- Test: `tests/test_api/test_compat.py`

- [ ] **Step 1: 添加 scan 系列端点**

在 `compat_router.py` 添加：

```python
from fastapi import UploadFile, File, Form
from edu_cloud.modules.scan.models import ScanTask, StudentAnswer
from edu_cloud.shared.storage import get_storage, StorageService
from edu_cloud.modules.exam.models import Question
from sqlalchemy.exc import IntegrityError


@router.post("/scan/tasks")
async def compat_create_scan_task(
    req: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """创建扫描任务。"""
    school_id = current["current_role"].school_id
    subject_id = req.get("subject_id")
    side = req.get("side", "A")
    total_images = req.get("total_images", 0)

    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    task = ScanTask(
        subject_id=subject_id, side=side,
        total_images=total_images, school_id=school_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "status": task.status, "total_images": task.total_images}


@router.patch("/scan/tasks/{task_id}")
async def compat_update_scan_task(
    task_id: str,
    req: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """更新扫描进度。"""
    school_id = current["current_role"].school_id
    task = (await db.execute(
        select(ScanTask).where(ScanTask.id == task_id, ScanTask.school_id == school_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if "processed" in req:
        task.processed = req["processed"]
    if "failed" in req:
        task.failed = req["failed"]
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "status": task.status, "processed": task.processed, "failed": task.failed}


@router.post("/scan/upload", status_code=201)
async def compat_upload_image(
    exam_id: str = Form(...),
    subject_id: str = Form(...),
    student_id: str = Form(...),
    question_id: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    """接收 paper-seg 上传的切图。字段名与 exam-ai 完全一致。"""
    school_id = current["current_role"].school_id
    data = await image.read()
    path = await storage.save(
        school_id=school_id, exam_id=exam_id, subject_id=subject_id,
        question_id=question_id, student_id=student_id, data=data,
    )
    answer = StudentAnswer(
        exam_id=exam_id, subject_id=subject_id, student_id=student_id,
        question_id=question_id, image_path=path, school_id=school_id,
    )
    db.add(answer)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Answer already exists")
    await db.refresh(answer)
    return {"id": answer.id, "image_path": answer.image_path}


class CompatObjectiveAnswer(BaseModel):
    question_id: str
    detected_answer: str
    fill_ratios: dict = {}
    anomaly: bool = False


class CompatUploadObjectiveRequest(BaseModel):
    exam_id: str
    subject_id: str
    student_id: str
    is_absent: bool = False
    answers: list[CompatObjectiveAnswer] = []


@router.post("/scan/upload-objective")
async def compat_upload_objective(
    req: CompatUploadObjectiveRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """接收 paper-seg 上传的选择题识别结果。"""
    school_id = current["current_role"].school_id

    # 验证 exam + subject
    exam = (await db.execute(
        select(Exam).where(Exam.id == req.exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    subject = (await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id, Subject.exam_id == req.exam_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    total_score = 0
    for ans in req.answers:
        # 查正确答案
        q = (await db.execute(
            select(Question).where(Question.id == ans.question_id, Question.school_id == school_id)
        )).scalar_one_or_none()
        score = 0
        if q and q.correct_answer:
            score = q.max_score if ans.detected_answer == q.correct_answer else 0
        total_score += score

        db.add(StudentAnswer(
            exam_id=req.exam_id, subject_id=req.subject_id,
            student_id=req.student_id, question_id=ans.question_id,
            detected_answer=ans.detected_answer, score=score,
            school_id=school_id,
        ))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Answers already exist")
    return {"total_score": total_score}
```

- [ ] **Step 2: 写测试**

在 `test_compat.py` 追加：

```python
from edu_cloud.modules.exam.models import Question


class TestCompatScan:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "X", "username": "compat_user", "password": "pass123",
        })
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    async def test_create_scan_task(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.post("/api/scan/tasks", json={
            "subject_id": "csub1", "side": "A", "total_images": 30,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_images"] == 30
        assert "id" in data

    async def test_upload_image(self, client: AsyncClient, compat_seed, db):
        # 需要先创建 Question（upload 时 question_id 需存在不做强制校验，但写入 StudentAnswer）
        q = Question(id="cq1", subject_id="csub1", name="17", question_type="subjective", max_score=10, school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload",
            data={"exam_id": "ce1", "subject_id": "csub1", "student_id": "STU001", "question_id": "cq1"},
            files={"image": ("crop.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            headers=headers,
        )
        assert resp.status_code == 201
        assert "image_path" in resp.json()

    async def test_upload_objective(self, client: AsyncClient, compat_seed, db):
        q = Question(id="cq2", subject_id="csub1", name="1", question_type="objective",
                     max_score=3, correct_answer="B", school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload-objective", json={
            "exam_id": "ce1", "subject_id": "csub1", "student_id": "STU002",
            "is_absent": False,
            "answers": [{"question_id": "cq2", "detected_answer": "B", "fill_ratios": {"A": 0.1, "B": 0.9}, "anomaly": False}],
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total_score"] == 3
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_compat.py -v`
Expected: 10 passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/api/compat_router.py tests/test_api/test_compat.py
git commit -m "feat: compat scan upload/objective/task endpoints"
```

**审查清单:**
- ✓ Multipart 字段名与 paper-seg ExamAIClient 一致（exam_id/subject_id/student_id/question_id/image）
- ✓ 选择题自动判分（对比 correct_answer）
- ✓ 重复上传返回 409
- ✗ 不存在的考试/科目返回 404（非 500）

---

### Task 5: 修复 publish 端点 status 限制

**Files:**
- Modify: `src/edu_cloud/modules/card/router.py`
- Test: `tests/test_api/test_compat.py`

- [ ] **Step 1: 修改 publish 端点，允许 scanning 状态重新发布**

在 `src/edu_cloud/modules/card/router.py` 第 1205-1206 行，将：

```python
    if exam.status != "draft":
        raise HTTPException(400, f"考试状态为 {exam.status}，仅 draft 可发布")
```

改为：

```python
    if exam.status not in ("draft", "scanning"):
        raise HTTPException(400, f"考试状态为 {exam.status}，仅 draft/scanning 可发布")
```

- [ ] **Step 2: 修改 status 设置逻辑，仅 draft→scanning**

在同文件第 1262-1263 行，将：

```python
    exam.status = "scanning"
```

改为：

```python
    if exam.status == "draft":
        exam.status = "scanning"
```

- [ ] **Step 3: 运行已有测试确认不破坏**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_cards.py tests/test_api/test_compat.py -v --tb=short`
Expected: all passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/card/router.py
git commit -m "fix: publish allows scanning status, idempotent re-publish"
```

**审查清单:**
- ✓ draft 状态可发布，exam.status 变为 scanning
- ✓ scanning 状态可重新发布，exam.status 保持 scanning
- ✗ grading/completed 等状态拒绝发布

---

### Task 6: 全量回归测试

**Files:** 无新文件

- [ ] **Step 1: 运行兼容层完整测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_compat.py -v`
Expected: 10 passed

- [ ] **Step 2: 运行 card 相关测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_cards.py tests/test_services_exam/test_card_layout_v3.py tests/test_services_exam/test_card_e2e.py -v --tb=short`
Expected: all passed

- [ ] **Step 3: 运行 scan 相关测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/ -k scan -v --tb=short`
Expected: all passed

- [ ] **Step 4: 运行全量测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 1580+ passed（允许已知的 migration/capability 失败）

- [ ] **Step 5: Commit（如有修复）**

```bash
git add -A && git commit -m "test: scan pipeline compat layer regression green"
```
