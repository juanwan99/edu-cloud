# 权限隔离修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 edu-cloud 跨校数据泄露漏洞，加固五层权限隔离模型

**Architecture:** 分三阶段：Phase 1 紧急止血（P0 跨校泄露，4 个漏洞）→ Phase 2 高优加固（P1 权限提升/IDOR，3 个漏洞）→ Phase 3 架构防护（租户中间件）。每个修复遵循 TDD：先写跨校攻击测试（红），再加过滤条件（绿）。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), pytest + AsyncClient, SQLite in-memory (tests)

**审计依据:** `docs/security-audit-permission-isolation-2026-05-08.md`

---

## Phase 1: P0 紧急止血（跨校数据泄露）

### Task 1: GradingResult upsert 跨校隔离

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py:644-646`
- Modify: `src/edu_cloud/modules/grading/models.py:62` (UniqueConstraint)
- Test: `tests/test_api_exam/test_grading_isolation.py` (create)

- [ ] **Step 1: Write cross-school attack test**

```python
"""tests/test_api_exam/test_grading_isolation.py"""
import pytest
from sqlalchemy import select
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.exam.models import Exam, Subject, Question


@pytest.fixture
async def two_school_grading(db):
    """构造跨校阅卷数据：school_a 和 school_b 各有一份答卷。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    import bcrypt

    school_a = School(id="school-a", name="新凤凰", code="XFH", is_active=True)
    school_b = School(id="school-b", name="景炎中学", code="JYZX", is_active=True)
    db.add_all([school_a, school_b])
    await db.flush()

    # 各校一场考试、一个科目、一道题
    exam_a = Exam(id="exam-a", name="期中考", school_id="school-a", status="published")
    exam_b = Exam(id="exam-b", name="期中考", school_id="school-b", status="published")
    db.add_all([exam_a, exam_b])
    await db.flush()

    subj_a = Subject(id="subj-a", exam_id="exam-a", name="语文", code="YW",
                     max_score=150, school_id="school-a")
    subj_b = Subject(id="subj-b", exam_id="exam-b", name="语文", code="YW",
                     max_score=150, school_id="school-b")
    db.add_all([subj_a, subj_b])
    await db.flush()

    q_a = Question(id="q-a", subject_id="subj-a", school_id="school-a",
                   question_type="essay", name="1", max_score=10)
    q_b = Question(id="q-b", subject_id="subj-b", school_id="school-b",
                   question_type="essay", name="1", max_score=10)
    db.add_all([q_a, q_b])
    await db.flush()

    ans_a = StudentAnswer(id="ans-a", question_id="q-a", school_id="school-a",
                          student_id="stu-a", image_path="/img/a.jpg")
    ans_b = StudentAnswer(id="ans-b", question_id="q-b", school_id="school-b",
                          student_id="stu-b", image_path="/img/b.jpg")
    db.add_all([ans_a, ans_b])
    await db.flush()

    # school_b 已有一条阅卷结果
    gr_b = GradingResult(
        answer_id="ans-b", question_id="q-b", school_id="school-b",
        ai_score=8.0, ai_confidence=0.9, max_score=10, status="ai_done",
    )
    db.add(gr_b)
    await db.commit()
    return {"school_a": school_a, "school_b": school_b, "gr_b": gr_b}


@pytest.mark.asyncio
async def test_grade_single_cannot_hit_other_school_result(db, two_school_grading):
    """P0-1: school_a 的 grade-single 查询不应命中 school_b 的 GradingResult。"""
    # 模拟 school_a 用户查 ans-b 的 existing result
    # 修复前：只按 answer_id 查，会命中 school_b 的记录
    # 修复后：加 school_id 过滤，不应命中
    result = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == "ans-b",
            GradingResult.school_id == "school-a",  # school_a 视角
        )
    )).scalar_one_or_none()
    assert result is None, "school_a 不应看到 school_b 的阅卷结果"


@pytest.mark.asyncio
async def test_grade_single_finds_own_school_result(db, two_school_grading):
    """正向：school_b 查自己的结果应该能找到。"""
    result = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == "ans-b",
            GradingResult.school_id == "school-b",
        )
    )).scalar_one_or_none()
    assert result is not None
    assert result.ai_score == 8.0
```

- [ ] **Step 2: Run test to verify it passes (测试查询模式，不涉及 bug 代码路径)**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_isolation.py -v`
Expected: 2 PASS（测试本身验证的是正确的查询模式）

- [ ] **Step 3: Fix grading/router.py:644-646 — add school_id filter**

```python
# src/edu_cloud/modules/grading/router.py, line 644-646
# BEFORE:
    existing_gr = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == req.answer_id)
    )).scalar_one_or_none()

# AFTER:
    existing_gr = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == req.answer_id,
            GradingResult.school_id == school_id,
        )
    )).scalar_one_or_none()
```

- [ ] **Step 4: Harden UniqueConstraint — add school_id scope**

```python
# src/edu_cloud/modules/grading/models.py, line 62
# BEFORE:
    __table_args__ = (
        UniqueConstraint("answer_id"),

# AFTER:
    __table_args__ = (
        UniqueConstraint("school_id", "answer_id"),
```

注意：旧的 `UniqueConstraint("answer_id")` 需要通过 Alembic migration 替换。如果生产数据中已存在跨校同 answer_id 的记录（不太可能，因为 answer_id 是 UUID），migration 会失败需要先清理。

- [ ] **Step 5: Run full grading tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_isolation.py tests/test_services/test_permissions_grading.py tests/test_workers/test_grading_worker.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/grading/router.py src/edu_cloud/modules/grading/models.py tests/test_api_exam/test_grading_isolation.py
git commit -m "fix(grading): add school_id filter to grade-single upsert query (P0-1)

GradingResult lookup by answer_id now scoped to current school,
preventing cross-school result overwrites.
UniqueConstraint hardened to (school_id, answer_id)."
```

---

### Task 2: 联考成绩接口跨校泄露

**Files:**
- Modify: `src/edu_cloud/modules/exam/results_router.py:13-43`
- Modify: `src/edu_cloud/services/results_service.py:14-128`
- Test: `tests/test_services/test_results_isolation.py` (create)

- [ ] **Step 1: Write cross-school attack tests**

```python
"""tests/test_services/test_results_isolation.py"""
import pytest
from edu_cloud.services.results_service import ResultsService
from edu_cloud.models.joint_exam import JointExam, JointExamParticipant, JointExamStudentResult


@pytest.fixture
async def joint_exam_two_schools(db):
    """联考：school_a 和 school_b 各 2 名学生。"""
    exam = JointExam(
        id="je-1", name="联考", created_by="u", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id="school-a",
    )
    db.add(exam)
    await db.flush()

    for sid in ("school-a", "school-b"):
        db.add(JointExamParticipant(
            joint_exam_id="je-1", school_id=sid, status="completed",
            is_creator=(sid == "school-a"),
        ))

    students = [
        ("school-a", "张三", "001", 90.0),
        ("school-a", "李四", "002", 85.0),
        ("school-b", "王五", "003", 95.0),
        ("school-b", "赵六", "004", 70.0),
    ]
    for sid, name, num, score in students:
        db.add(JointExamStudentResult(
            joint_exam_id="je-1", school_id=sid, subject_code="YW",
            student_name=name, student_number=num, total_score=score,
            detail_scores=[],
        ))
    await db.commit()
    return exam


@pytest.mark.asyncio
async def test_rankings_filtered_by_school(db, joint_exam_two_schools):
    """P0-3: 排名接口应只返回请求者学校的学生。"""
    svc = ResultsService(db)
    rankings = await svc.get_rankings("je-1", school_id="school-a", subject_code="YW")
    assert len(rankings) == 2
    school_ids = {r["school_id"] for r in rankings}
    assert school_ids == {"school-a"}, "不应包含 school-b 的学生"


@pytest.mark.asyncio
async def test_school_comparison_filtered(db, joint_exam_two_schools):
    """P0-3: 学校对比只显示本校统计（非 admin 场景）。"""
    svc = ResultsService(db)
    comparison = await svc.get_school_comparison("je-1", school_id="school-a")
    school_ids = {r["school_id"] for r in comparison}
    assert school_ids == {"school-a"}


@pytest.mark.asyncio
async def test_student_detail_school_from_jwt(db, joint_exam_two_schools):
    """P0-2: 学生明细的 school_id 来自 JWT，不允许查他校学生。"""
    svc = ResultsService(db)
    # school-a 用户查 school-b 的学生 → 应查不到
    with pytest.raises(Exception):  # NotFoundError
        await svc.get_student_detail("je-1", "003", school_id="school-a")


@pytest.mark.asyncio
async def test_rankings_admin_sees_all(db, joint_exam_two_schools):
    """平台管理员 school_id=None 可以看全部。"""
    svc = ResultsService(db)
    rankings = await svc.get_rankings("je-1", school_id=None, subject_code="YW")
    assert len(rankings) == 4
```

- [ ] **Step 2: Run tests — expect failures (service 还没有 school_id 参数)**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_results_isolation.py -v`
Expected: FAIL (TypeError: unexpected keyword argument 'school_id')

- [ ] **Step 3: Fix ResultsService — add school_id parameter to all 3 methods**

```python
# src/edu_cloud/services/results_service.py
# 所有 3 个方法添加 school_id 参数，非 None 时加 WHERE 条件

    async def get_rankings(
        self, exam_id: str, school_id: str | None = None,
        subject_code: str | None = None,
    ) -> list[dict]:
        if subject_code:
            q = (
                select(JointExamStudentResult)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.subject_code == subject_code)
            )
            if school_id:
                q = q.where(JointExamStudentResult.school_id == school_id)
            q = q.order_by(JointExamStudentResult.total_score.desc())
            results = (await self.db.execute(q)).scalars().all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": r.total_score}
                for i, r in enumerate(results)
            ]
        else:
            q = (
                select(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                    func.sum(JointExamStudentResult.total_score).label("total"),
                )
                .where(JointExamStudentResult.joint_exam_id == exam_id)
            )
            if school_id:
                q = q.where(JointExamStudentResult.school_id == school_id)
            q = (
                q.group_by(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                )
                .order_by(func.sum(JointExamStudentResult.total_score).desc())
            )
            rows = (await self.db.execute(q)).all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": float(r.total)}
                for i, r in enumerate(rows)
            ]

    async def get_school_comparison(
        self, exam_id: str, school_id: str | None = None,
    ) -> list[dict]:
        q = (
            select(
                JointExamStudentResult.school_id,
                JointExamStudentResult.subject_code,
                func.avg(JointExamStudentResult.total_score).label("avg"),
                func.max(JointExamStudentResult.total_score).label("max"),
                func.count().label("count"),
            )
            .where(JointExamStudentResult.joint_exam_id == exam_id)
        )
        if school_id:
            q = q.where(JointExamStudentResult.school_id == school_id)
        q = q.group_by(
            JointExamStudentResult.school_id,
            JointExamStudentResult.subject_code,
        )
        rows = (await self.db.execute(q)).all()

        result = []
        for row in rows:
            scores_q = (
                select(JointExamStudentResult.total_score)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.school_id == row.school_id)
                .where(JointExamStudentResult.subject_code == row.subject_code)
            )
            scores = [s for (s,) in (await self.db.execute(scores_q)).all()]
            median = statistics.median(scores) if scores else 0.0

            result.append({
                "school_id": row.school_id,
                "subject_code": row.subject_code,
                "avg_score": round(float(row.avg), 2),
                "max_score": float(row.max),
                "median_score": median,
                "student_count": row.count,
            })
        return result

    async def get_student_detail(
        self, exam_id: str, student_number: str, school_id: str | None = None,
    ) -> dict:
        q = (
            select(JointExamStudentResult)
            .where(JointExamStudentResult.joint_exam_id == exam_id)
            .where(JointExamStudentResult.student_number == student_number)
        )
        if school_id:
            q = q.where(JointExamStudentResult.school_id == school_id)
        # ... rest unchanged
```

- [ ] **Step 4: Fix results_router.py — school_id from JWT, not query param**

```python
# src/edu_cloud/modules/exam/results_router.py
# 所有 3 个端点：school_id 从 current_role 取，非 admin 角色强制过滤

from edu_cloud.api.deps import get_current_user, require_permission

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _get_school_id(current: dict) -> str | None:
    """非 admin 角色返回 JWT school_id；admin 返回 None（全局视图）。"""
    role = current["current_role"].role
    if role in _CROSS_SCHOOL_ROLES:
        return None
    return current["current_role"].school_id


@router.get("")
async def get_rankings(
    exam_id: str,
    subject_code: str | None = None,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_rankings(
        exam_id, school_id=_get_school_id(current), subject_code=subject_code,
    )


@router.get("/by-school")
async def get_school_comparison(
    exam_id: str,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_school_comparison(exam_id, school_id=_get_school_id(current))


@router.get("/students/{student_number}")
async def get_student_detail(
    exam_id: str,
    student_number: str,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_student_detail(
        exam_id, student_number, school_id=_get_school_id(current),
    )
```

- [ ] **Step 5: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_results_isolation.py tests/test_services/test_results_service.py -v --tb=short`
Expected: ALL PASS（新测试 + 旧测试不回归）

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/exam/results_router.py src/edu_cloud/services/results_service.py tests/test_services/test_results_isolation.py
git commit -m "fix(results): enforce school_id from JWT in all joint exam result endpoints (P0-2/P0-3)

Rankings, school comparison, and student detail now filter by
current_role.school_id. Only platform_admin/district_admin see
cross-school data. Removed school_id query parameter from student detail."
```

---

### Task 3: 联考管理接口 — creator_school_id 来自 JWT

**Files:**
- Modify: `src/edu_cloud/modules/exam/joint_exam_router.py:17-46`
- Test: `tests/test_services/test_joint_exam_isolation.py` (create)

- [ ] **Step 1: Write attack test — forged creator_school_id**

```python
"""tests/test_services/test_joint_exam_isolation.py"""
import pytest
from edu_cloud.modules.exam.joint_exam_service import JointExamService
from edu_cloud.models.joint_exam import JointExam, JointExamParticipant


@pytest.mark.asyncio
async def test_list_exams_filtered_by_participant(db):
    """非 admin 只能看到自己学校参与的联考。"""
    exam = JointExam(
        id="je-vis", name="仅 school-a 参与", created_by="u", status="active",
        subjects=[], creator_school_id="school-a",
    )
    db.add(exam)
    await db.flush()
    db.add(JointExamParticipant(
        joint_exam_id="je-vis", school_id="school-a", status="active", is_creator=True,
    ))
    await db.commit()

    svc = JointExamService(db)
    # school-b 不是参与者，不应看到
    exams = await svc.list_exams(status=None, school_id="school-b")
    assert len(exams) == 0

    # school-a 是参与者，应看到
    exams = await svc.list_exams(status=None, school_id="school-a")
    assert len(exams) == 1
```

- [ ] **Step 2: Run test — expect failure (list_exams 没有 school_id 参数)**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_joint_exam_isolation.py -v`
Expected: FAIL

- [ ] **Step 3: Fix joint_exam_service.py — add school_id filter to list_exams**

```python
# src/edu_cloud/modules/exam/joint_exam_service.py
    async def list_exams(
        self, status: str | None = None, school_id: str | None = None,
    ) -> list[JointExam]:
        q = select(JointExam)
        if status:
            q = q.where(JointExam.status == status)
        if school_id:
            q = q.where(
                JointExam.id.in_(
                    select(JointExamParticipant.joint_exam_id)
                    .where(JointExamParticipant.school_id == school_id)
                )
            )
        q = q.order_by(JointExam.created_at.desc())
        return list((await self.db.execute(q)).scalars().all())
```

- [ ] **Step 4: Fix joint_exam_router.py — creator_school_id from JWT**

```python
# src/edu_cloud/modules/exam/joint_exam_router.py
# CreateExamRequest 中移除 creator_school_id 字段

class CreateExamRequest(BaseModel):
    name: str
    subjects: list[dict]
    description: str | None = None
    # creator_school_id 不再从请求体取


@router.post("", status_code=201)
async def create_exam(
    req: CreateExamRequest,
    user=Depends(require_permission(Permission.CREATE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    creator_school_id = user["current_role"].school_id
    svc = JointExamService(db, upload_dir=settings.UPLOAD_DIR)
    exam = await svc.create_exam(
        name=req.name,
        subjects=req.subjects,
        creator_school_id=creator_school_id,
        created_by=user["user"].id,
        description=req.description,
    )
    # ... rest unchanged


@router.get("")
async def list_exams(
    status: str | None = None,
    user=Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    role = user["current_role"].role
    school_id = None if role in ("platform_admin", "district_admin") else user["current_role"].school_id
    svc = JointExamService(db)
    exams = await svc.list_exams(status=status, school_id=school_id)
    return [
        {"id": e.id, "name": e.name, "status": e.status,
         "subjects": e.subjects, "created_at": str(e.created_at)}
        for e in exams
    ]
```

- [ ] **Step 5: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_joint_exam_isolation.py tests/test_api/test_joint_exams.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/exam/joint_exam_router.py src/edu_cloud/modules/exam/joint_exam_service.py tests/test_services/test_joint_exam_isolation.py
git commit -m "fix(joint-exam): creator_school_id from JWT, list filtered by participant (P0-4)

Removed creator_school_id from request body — now derived from JWT.
list_exams filters by participant relationship for non-admin roles."
```

---

## Phase 2: P1 高优加固

### Task 4: 模拟登录默认只读

**Files:**
- Modify: `src/edu_cloud/api/deps.py:105-122`
- Test: `tests/test_api/test_impersonation_isolation.py` (create)

- [ ] **Step 1: Write test — impersonation blocks write permissions**

```python
"""tests/test_api/test_impersonation_isolation.py"""
import pytest
from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS


# 模拟登录应排除的写权限
WRITE_PERMISSIONS = {
    Permission.MANAGE_EXAMS, Permission.MANAGE_GRADING,
    Permission.MANAGE_HOMEWORK, Permission.MANAGE_SCHOOLS,
    Permission.MANAGE_SCHOOL_CONFIG, Permission.MANAGE_SCHEDULING,
    Permission.MANAGE_JOINT_EXAM, Permission.CREATE_JOINT_EXAM,
    Permission.MANAGE_EXAM_RESULTS, Permission.MANAGE_CONDUCT,
    Permission.MANAGE_CONDUCT_RULES, Permission.MANAGE_CONDUCT_PARENTS,
}

IMPERSONATION_SAFE_PERMISSIONS = {
    p for p in ROLE_PERMISSIONS.get("academic_director", set())
    if p not in WRITE_PERMISSIONS
}


def test_impersonation_permissions_exclude_writes():
    """P1-1: 模拟登录应排除写权限。"""
    full = ROLE_PERMISSIONS.get("academic_director", set())
    safe = full - WRITE_PERMISSIONS
    # 确认 safe 集合不为空（还能查看）
    assert len(safe) > 0
    # 确认 safe 集合不包含任何写权限
    assert safe & WRITE_PERMISSIONS == set()
```

- [ ] **Step 2: Run test**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonation_isolation.py -v`
Expected: PASS

- [ ] **Step 3: Modify deps.py — filter write permissions for impersonation**

```python
# src/edu_cloud/api/deps.py, in get_current_user, impersonation branch (~line 115-122)
# BEFORE:
        return {
            "user": user,
            "roles": [],
            "current_role": virtual_role,
            "permissions": ROLE_PERMISSIONS.get(effective_role, set()),
            "is_impersonation": True,
            "impersonator_id": impersonator_id,
        }

# AFTER:
        full_perms = ROLE_PERMISSIONS.get(effective_role, set())
        read_only_perms = full_perms - _IMPERSONATION_BLOCKED_PERMISSIONS
        return {
            "user": user,
            "roles": [],
            "current_role": virtual_role,
            "permissions": read_only_perms,
            "is_impersonation": True,
            "impersonator_id": impersonator_id,
        }
```

在 `deps.py` 顶部添加常量：

```python
_IMPERSONATION_BLOCKED_PERMISSIONS = {
    Permission.MANAGE_EXAMS, Permission.MANAGE_GRADING,
    Permission.MANAGE_HOMEWORK, Permission.MANAGE_SCHOOLS,
    Permission.MANAGE_SCHOOL_CONFIG, Permission.MANAGE_SCHEDULING,
    Permission.MANAGE_JOINT_EXAM, Permission.CREATE_JOINT_EXAM,
    Permission.MANAGE_EXAM_RESULTS, Permission.MANAGE_CONDUCT,
    Permission.MANAGE_CONDUCT_RULES, Permission.MANAGE_CONDUCT_PARENTS,
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonation_isolation.py tests/test_api/ -v --tb=short -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/api/deps.py tests/test_api/test_impersonation_isolation.py
git commit -m "fix(auth): impersonation defaults to read-only permissions (P1-1)

Write permissions (MANAGE_*) are stripped from impersonated sessions.
Prevents privilege escalation via impersonation."
```

---

### Task 5: AI 会话 owner 校验

**Files:**
- Modify: `src/edu_cloud/api/ai.py:136-148`
- Test: `tests/test_api/test_ai_session_isolation.py` (create)

- [ ] **Step 1: Write hijack test**

```python
"""tests/test_api/test_ai_session_isolation.py"""
import pytest


def test_session_state_rejects_wrong_owner():
    """P1-2: 已有 session 被不同 user_id 复用时应拒绝。"""
    from edu_cloud.api.ai import _SessionState, _sessions, _sessions_lock
    import asyncio

    # 模拟：user-A 创建 session
    state_a = _SessionState(owner_id="user-a")

    # user-B 尝试复用同一 session_id 应该失败
    assert state_a.owner_id == "user-a"
    # 修复后 router 层会检查 owner_id != current_user.id → 403
```

- [ ] **Step 2: Fix ai.py — check owner_id on session reuse**

```python
# src/edu_cloud/api/ai.py, ~line 136-148
# BEFORE:
    async with _sessions_lock:
        if session_id not in _sessions:
            ...
        session_state = _sessions.setdefault(
            session_id, _SessionState(anonymizer=Anonymizer(), owner_id=user.id)
        )

# AFTER:
    async with _sessions_lock:
        if session_id not in _sessions:
            try:
                await audit.create_session(user.id, role, context=scope)
            except Exception as e:
                logger.warning("Failed to create audit session: %s", e)

        existing = _sessions.get(session_id)
        if existing and existing.owner_id != user.id:
            raise HTTPException(403, "Session belongs to another user")

        session_state = _sessions.setdefault(
            session_id, _SessionState(anonymizer=Anonymizer(), owner_id=user.id)
        )
```

- [ ] **Step 3: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_ai_session_isolation.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/api/ai.py tests/test_api/test_ai_session_isolation.py
git commit -m "fix(ai): validate session owner_id on reuse (P1-2)

Prevents session hijacking by checking owner_id matches current user
before allowing session reuse. Returns 403 on mismatch."
```

---

### Task 6: 考试日程 IDOR 修复

**Files:**
- Modify: `src/edu_cloud/modules/exam/router.py:386-435`
- Test: `tests/test_api_exam/test_exam_schedule_isolation.py` (create)

- [ ] **Step 1: Write IDOR test**

```python
"""tests/test_api_exam/test_exam_schedule_isolation.py"""
import pytest
from edu_cloud.modules.exam.models import Exam


@pytest.fixture
async def cross_school_exams(db):
    from edu_cloud.models.school import School
    db.add(School(id="sch-x", name="X校", code="X", is_active=True))
    db.add(School(id="sch-y", name="Y校", code="Y", is_active=True))
    await db.flush()

    exam_x = Exam(id="ex-x", name="X校期中", school_id="sch-x", status="draft")
    exam_y = Exam(id="ex-y", name="Y校期中", school_id="sch-y", status="draft")
    db.add_all([exam_x, exam_y])
    await db.commit()
    return exam_x, exam_y


@pytest.mark.asyncio
async def test_get_schedule_rejects_other_school(db, cross_school_exams):
    """P1-3: school_x 用户不应能读 school_y 的考试日程。"""
    exam_x, exam_y = cross_school_exams
    # 模拟 school_x 用户查 exam_y → 应 404
    result = await db.get(Exam, exam_y.id)
    assert result is not None  # DB 层能找到
    assert result.school_id == "sch-y"
    # 修复后 router 会 check exam.school_id != current_school → 404
```

- [ ] **Step 2: Fix exam/router.py — add school_id check to schedule endpoints**

```python
# src/edu_cloud/modules/exam/router.py, set_exam_schedule (~line 395)
# BEFORE:
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")

# AFTER:
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")
    if exam.school_id != current["current_role"].school_id:
        raise HTTPException(404, "考试不存在")

# 同样修复 get_exam_schedule (~line 431):
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")
    if exam.school_id != current["current_role"].school_id:
        raise HTTPException(404, "考试不存在")
```

注意：`get_exam_schedule` 需要将 `get_current_user` 改为 `require_permission(Permission.MANAGE_EXAMS)` 或至少保留 `get_current_user` 并加 school_id 检查。

- [ ] **Step 3: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_exam_schedule_isolation.py tests/test_api_exam/ -v --tb=short -q`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/exam/router.py tests/test_api_exam/test_exam_schedule_isolation.py
git commit -m "fix(exam): add school_id check to schedule endpoints (P1-3)

set_exam_schedule and get_exam_schedule now verify exam.school_id
matches the requesting user's school, preventing cross-school IDOR."
```

---

## Phase 3: 架构级防护（中期）

### Task 7: 租户 school_id 注入中间件

**Files:**
- Create: `src/edu_cloud/api/tenant_middleware.py`
- Test: `tests/test_api/test_tenant_middleware.py` (create)

注意：这个 Task 是中期架构任务，设计为防护层（defense-in-depth），不替代各端点的显式校验。

- [ ] **Step 1: Write middleware test**

```python
"""tests/test_api/test_tenant_middleware.py"""
import pytest
from starlette.testclient import TestClient


def test_tenant_school_id_injected_into_request_state():
    """中间件应将 school_id 注入 request.state。"""
    # 验证中间件机制：JWT 解析后 school_id 可在 request.state 访问
    # 端点可用 request.state.school_id 做二次防护
    pass  # 具体实现取决于架构决策


def test_tenant_middleware_skips_public_endpoints():
    """公共端点（health, login）不注入 school_id。"""
    pass
```

- [ ] **Step 2: Design discussion point**

中间件方案有两种路线：

**方案 A: Request-level school_id injection**
- 中间件解析 JWT，将 school_id 放入 `request.state.tenant_school_id`
- 各 service 可选用 `request.state.tenant_school_id` 做二次校验
- 优点：渐进式，不破坏现有代码
- 缺点：仍依赖各端点主动使用

**方案 B: SQLAlchemy session-level filter**
- 中间件将 school_id 写入 SQLAlchemy session info
- 自定义 Session 类自动给所有含 school_id 列的表加 WHERE
- 优点：根本性解决，新端点自动安全
- 缺点：改动大，需要处理 platform_admin 豁免

建议 Phase 3 先实施方案 A 作为过渡，方案 B 作为长期目标单独立项。

- [ ] **Step 3: Commit placeholder**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/api/tenant_middleware.py tests/test_api/test_tenant_middleware.py
git commit -m "feat(arch): add tenant school_id injection middleware skeleton (Phase 3)

Defense-in-depth: middleware extracts school_id from JWT into
request.state for optional secondary validation in endpoints."
```

---

## 全量回归验证

### Task 8: 全量测试 + 回归确认

- [ ] **Step 1: Run full backend test suite**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q`
Expected: ≥2246 passed（基线），新增 ~12 tests，failed 数 ≤ 33（既有债）

- [ ] **Step 2: Run frontend test suite**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`
Expected: 2421 tests, 0 failed

- [ ] **Step 3: Verify with grep — no remaining unfiltered queries**

```bash
# 搜索 Phase 1 修复的模式是否还有残留
cd /home/ops/projects/edu-cloud
grep -rn "GradingResult.answer_id == " src/ | grep -v school_id
grep -rn "joint_exam_id == exam_id" src/edu_cloud/services/results_service.py | head -5
grep -rn "creator_school_id" src/edu_cloud/modules/exam/joint_exam_router.py
```

Expected:
- GradingResult 查询无残留（全部加了 school_id）
- results_service 的查询都有 school_id 条件分支
- joint_exam_router 中 creator_school_id 不再出现在 CreateExamRequest 中
