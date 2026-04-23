---
baseline_command: ".venv/bin/python -m pytest --tb=short -q && cd frontend-nuxt && npx vitest run"
baseline_verified_at: "2026-04-23T19:36:52+08:00"
baseline_count: "backend 1970 passed, 23 skipped; frontend-nuxt 24 passed"
---

# PowerOptions 级联筛选器 + 分析报告模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 PowerOptions 级联筛选器（后端 Service + 端点）和 6 个 Nuxt 前端分析报告页面，让教师能通过 年级→班级→科目→考试 四级联动定位分析数据。

**Architecture:** 后端在 `modules/analytics/` 新增 `power_options_service.py` 和 `level_score_service.py`，路由挂到现有 `router.py`。前端在 `frontend-nuxt/` 新增 `usePowerOptions` composable + `PowerFilter` 组件 + 6 个 `pages/report/` 页面，全部使用 Element Plus + ECharts。

**Tech Stack:** FastAPI / SQLAlchemy async / pytest // Nuxt 3 / Element Plus / ECharts / Vitest

**Design doc:** `docs/plans/2026-04-23-power-options-design.md`

**semantic_regression:**
- ORC-001: PowerOptions 树中每个节点必须带 id + name，禁止复合键
- ORC-002: "all" 伪班级的 student_count 必须等于该年级所有真实班级的 student_count 之和
- ORC-003: analysisParams 输出的 class_id 当选择"全部班级"时为 null
- ORC-004: RBAC 过滤在 Service 层完成，前端不做二次过滤
- ORC-005: 等级赋分算法必须按原始分降序排列后按百分位切分，同分学生归入同一等级

---

## Batch 1: 后端 PowerOptions + 等级赋分（Task 1-3）

### Task 1: PowerOptionsService + 端点

**Files:**
- Create: `src/edu_cloud/modules/analytics/power_options_service.py`
- Modify: `src/edu_cloud/modules/analytics/router.py` (追加 1 个路由)
- Create: `tests/test_api/test_analytics_power_options.py`

**参考文件（读取但不修改）：**
- `src/edu_cloud/modules/exam/models.py` — Exam(L32-48)/Subject(L51-58)/ExamResult(L83-96)
- `src/edu_cloud/modules/student/models.py` — Class(L8-18)/Student(L25-44)
- `src/edu_cloud/api/permissions.py:18-31` — get_visible_class_ids / get_visible_subject_codes
- `src/edu_cloud/modules/analytics/router.py` — 现有路由模式（L20-31 示例）
- `tests/conftest.py:108-170` — admin_user / seed_school fixture

- [ ] **Step 1: 写 PowerOptions 空数据测试**

> **F001/F002 修复**：`seed_school` fixture 返回 `(school, secret)` 元组，必须解包。
> `admin_user` 是 platform_admin 无 school_id，analytics 端点按 `role.school_id` 过滤会拿不到数据。
> 新增 `school_admin_headers` 本地 fixture，创建 principal 角色绑定 school_id。

```python
# tests/test_api/test_analytics_power_options.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from tests.conftest import *  # noqa — reuse fixtures


@pytest.fixture
async def school_admin_headers(db, seed_school):
    """principal 角色绑定测试学校，用于 school-scoped 端点测试。"""
    school, _ = seed_school
    user = User(username="school_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="principal",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_power_options_empty(client, school_admin_headers):
    """无完成考试时返回空 grades 列表。"""
    resp = await client.get(
        "/api/v1/analytics/power-options",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"grades": []}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_power_options.py -v`
Expected: FAIL — 404（端点不存在）

- [ ] **Step 3: 实现 PowerOptionsService**

```python
# src/edu_cloud/modules/analytics/power_options_service.py
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select, func, distinct, extract
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, ExamResult
from edu_cloud.modules.student.models import Class, Student


async def get_power_options(
    db: AsyncSession,
    school_id: str,
    visible_class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
    exam_type: str | None = None,
    year: int | None = None,
) -> dict:
    stmt = (
        select(
            Class.grade,
            Class.id.label("class_id"),
            Class.name.label("class_name"),
            Subject.id.label("subject_id"),
            Subject.code.label("subject_code"),
            Subject.name.label("subject_name"),
            Exam.id.label("exam_id"),
            Exam.name.label("exam_name"),
            Exam.exam_date.label("exam_date"),
            func.count(distinct(ExamResult.student_id)).label("student_count"),
        )
        .select_from(Exam)
        .join(Subject, Subject.exam_id == Exam.id)
        .join(ExamResult, ExamResult.exam_id == Exam.id)
        .join(Student, Student.id == ExamResult.student_id)
        .join(Class, Class.id == Student.class_id)
        .where(Exam.school_id == school_id)
        .where(Exam.status == "completed")
        .group_by(
            Class.grade, Class.id, Class.name,
            Subject.id, Subject.code, Subject.name,
            Exam.id, Exam.name, Exam.exam_date,
        )
        .order_by(Class.grade, Class.name, Subject.name, Exam.exam_date.desc())
    )

    if visible_class_ids is not None:
        stmt = stmt.where(Class.id.in_(visible_class_ids))
    if visible_subject_codes is not None:
        stmt = stmt.where(Subject.code.in_(visible_subject_codes))
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    if year:
        stmt = stmt.where(extract("year", Exam.exam_date) == year)

    rows = (await db.execute(stmt)).all()

    return _build_tree(rows)


def _build_tree(rows) -> dict:
    # F004 处置：student_count 统计的是"某班有多少学生参加了这场考试"，是 exam 级统计，
    # 这对 PowerOptions 场景是正确的——一场考试的所有科目由相同学生群体参加。
    grade_map: dict[str, dict] = {}

    for row in rows:
        grade_name = row.grade
        if grade_name not in grade_map:
            grade_map[grade_name] = {}

        class_id = row.class_id
        if class_id not in grade_map[grade_name]:
            grade_map[grade_name][class_id] = {
                "id": class_id,
                "name": row.class_name,
                "subjects": {},
            }

        cls = grade_map[grade_name][class_id]
        subj_id = row.subject_id
        if subj_id not in cls["subjects"]:
            cls["subjects"][subj_id] = {
                "id": subj_id,
                "code": row.subject_code,
                "name": row.subject_name,
                "exams": [],
            }

        cls["subjects"][subj_id]["exams"].append({
            "exam_id": row.exam_id,
            "subject_id": subj_id,
            "name": row.exam_name,
            "exam_date": row.exam_date.isoformat() if row.exam_date else None,
            "student_count": row.student_count,
        })

    grades = []
    for grade_name, classes_map in grade_map.items():
        real_classes = list(classes_map.values())

        all_subjects: dict[str, dict] = {}
        for cls in real_classes:
            for subj_id, subj in cls["subjects"].items():
                if subj_id not in all_subjects:
                    all_subjects[subj_id] = {
                        "id": subj["id"],
                        "code": subj["code"],
                        "name": subj["name"],
                        "exams": defaultdict(lambda: {"student_count": 0}),
                    }
                for exam in subj["exams"]:
                    key = exam["exam_id"]
                    entry = all_subjects[subj_id]["exams"][key]
                    entry["exam_id"] = exam["exam_id"]
                    entry["subject_id"] = exam["subject_id"]
                    entry["name"] = exam["name"]
                    entry["exam_date"] = exam["exam_date"]
                    entry["student_count"] += exam["student_count"]

        all_node = {
            "id": "all",
            "name": "全部班级",
            "subjects": {
                sid: {
                    "id": s["id"],
                    "code": s["code"],
                    "name": s["name"],
                    "exams": list(s["exams"].values()),
                }
                for sid, s in all_subjects.items()
            },
        }

        for cls in real_classes:
            cls["subjects"] = list(cls["subjects"].values())
        all_node["subjects"] = list(all_node["subjects"].values())

        grades.append({
            "name": grade_name,
            "classes": [all_node] + real_classes,
        })

    return {"grades": grades}
```

- [ ] **Step 4: 在 router.py 末尾追加 power-options 端点**

在 `src/edu_cloud/modules/analytics/router.py` 文件末尾追加：

```python
# --- PowerOptions 级联筛选器 ---

from edu_cloud.modules.analytics.power_options_service import get_power_options


@router.get("/power-options")
async def power_options(
    exam_type: str | None = Query(None),
    year: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """返回 年级→班级→科目→考试 级联筛选树。已按角色 RBAC 过滤。"""
    role = current["current_role"]
    return await get_power_options(
        db,
        school_id=role.school_id,
        visible_class_ids=get_visible_class_ids(role),
        visible_subject_codes=get_visible_subject_codes(role),
        exam_type=exam_type,
        year=year,
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_power_options.py::test_power_options_empty -v`
Expected: PASS

- [ ] **Step 6: 写有数据的测试**

在 `tests/test_api/test_analytics_power_options.py` 追加：

```python
from edu_cloud.modules.exam.models import Exam, Subject, ExamResult
from edu_cloud.modules.student.models import Class, Student
from datetime import datetime


async def _seed_exam_data(db, seed_school):
    """种子数据：2 年级 × 2+1 班 × 2 科目 × 2 考试。"""
    school, _ = seed_school
    school_id = school.id
    cls_g1_1 = Class(name="高一(1)班", grade="高一", school_id=school_id)
    cls_g1_2 = Class(name="高一(2)班", grade="高一", school_id=school_id)
    cls_g2_1 = Class(name="高二(1)班", grade="高二", school_id=school_id)
    db.add_all([cls_g1_1, cls_g1_2, cls_g2_1])
    await db.flush()

    exam1 = Exam(name="期中考试", status="completed", school_id=school_id,
                 exam_date=datetime(2026, 4, 10))
    exam2 = Exam(name="月考", status="completed", school_id=school_id,
                 exam_date=datetime(2026, 3, 5))
    exam_draft = Exam(name="未完成", status="draft", school_id=school_id)
    db.add_all([exam1, exam2, exam_draft])
    await db.flush()

    subj_math = Subject(exam_id=exam1.id, name="数学", code="math", school_id=school_id)
    subj_chinese = Subject(exam_id=exam1.id, name="语文", code="chinese", school_id=school_id)
    subj_math2 = Subject(exam_id=exam2.id, name="数学", code="math", school_id=school_id)
    db.add_all([subj_math, subj_chinese, subj_math2])
    await db.flush()

    stu1 = Student(name="张三", student_number="S001", class_id=cls_g1_1.id,
                   grade="高一", school_id=school_id)
    stu2 = Student(name="李四", student_number="S002", class_id=cls_g1_2.id,
                   grade="高一", school_id=school_id)
    stu3 = Student(name="王五", student_number="S003", class_id=cls_g2_1.id,
                   grade="高二", school_id=school_id)
    db.add_all([stu1, stu2, stu3])
    await db.flush()

    db.add_all([
        ExamResult(exam_id=exam1.id, student_id=stu1.id, school_id=school_id, total_score=85),
        ExamResult(exam_id=exam1.id, student_id=stu2.id, school_id=school_id, total_score=72),
        ExamResult(exam_id=exam2.id, student_id=stu1.id, school_id=school_id, total_score=90),
        ExamResult(exam_id=exam1.id, student_id=stu3.id, school_id=school_id, total_score=60),
    ])
    await db.commit()
    return {
        "exam1": exam1, "exam2": exam2,
        "cls_g1_1": cls_g1_1, "cls_g1_2": cls_g1_2, "cls_g2_1": cls_g2_1,
        "subj_math": subj_math, "subj_chinese": subj_chinese,
    }


@pytest.mark.asyncio
async def test_power_options_tree_structure(client, school_admin_headers, seed_school, db):
    """多年级多班多科目：验证树结构正确 + all 节点存在。"""
    await _seed_exam_data(db, seed_school)

    resp = await client.get("/api/v1/analytics/power-options", headers=school_admin_headers)
    assert resp.status_code == 200
    result = resp.json()

    grades = result["grades"]
    grade_names = [g["name"] for g in grades]
    assert "高一" in grade_names
    assert "高二" in grade_names

    g1 = next(g for g in grades if g["name"] == "高一")
    class_ids = [c["id"] for c in g1["classes"]]
    assert "all" in class_ids

    all_node = next(c for c in g1["classes"] if c["id"] == "all")
    assert len(all_node["subjects"]) >= 1

    # ORC-002: all 的 student_count 等于各真实班级之和
    for subj in all_node["subjects"]:
        for exam in subj["exams"]:
            total = 0
            for cls in g1["classes"]:
                if cls["id"] == "all":
                    continue
                for s in cls["subjects"]:
                    if s["id"] == subj["id"]:
                        for e in s["exams"]:
                            if e["exam_id"] == exam["exam_id"]:
                                total += e["student_count"]
            assert exam["student_count"] == total, (
                f"ORC-002: all.student_count({exam['student_count']}) != sum({total})"
            )


@pytest.mark.asyncio
async def test_power_options_excludes_draft(client, school_admin_headers, seed_school, db):
    """draft 考试不出现在 power-options 树中。"""
    await _seed_exam_data(db, seed_school)

    resp = await client.get("/api/v1/analytics/power-options", headers=school_admin_headers)
    result = resp.json()
    all_exam_names = []
    for g in result["grades"]:
        for c in g["classes"]:
            for s in c["subjects"]:
                for e in s["exams"]:
                    all_exam_names.append(e["name"])
    assert "未完成" not in all_exam_names


@pytest.mark.asyncio
async def test_power_options_rbac_subject_filter(client, db, seed_school):
    """科目教师只看到自己任教的科目。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    await _seed_exam_data(db, seed_school)

    school, _ = seed_school
    teacher = User(username="math_teacher", display_name="数学老师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(
        user_id=teacher.id, role="subject_teacher",
        school_id=school.id, is_primary=True,
        subject_codes=["math"],
    ))
    await db.commit()
    token = create_access_token({"sub": teacher.id, "role": "subject_teacher"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/analytics/power-options", headers=headers)
    assert resp.status_code == 200
    result = resp.json()

    for g in result["grades"]:
        for c in g["classes"]:
            for s in c["subjects"]:
                assert s["code"] == "math", f"ORC-004: 科目教师看到了非数学科目 {s['code']}"
```

- [ ] **Step 7: 运行全部 power-options 测试**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_power_options.py -v`
Expected: 4 PASS

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/modules/analytics/power_options_service.py \
        src/edu_cloud/modules/analytics/router.py \
        tests/test_api/test_analytics_power_options.py
git commit -m "feat(analytics): PowerOptionsService + GET /power-options 端点"
```

---

### Task 2: LevelScoreService + 等级赋分端点

**Files:**
- Create: `src/edu_cloud/modules/analytics/level_score_service.py`
- Modify: `src/edu_cloud/modules/analytics/router.py` (追加 1 个路由)
- Create: `tests/test_api/test_analytics_level_score.py`

**参考文件：**
- `src/edu_cloud/modules/exam/models.py:83-96` — ExamResult 模型
- `src/edu_cloud/modules/student/models.py:25-44` — Student 模型

- [ ] **Step 1: 写等级赋分基础测试**

```python
# tests/test_api/test_analytics_level_score.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from tests.conftest import *  # noqa

from edu_cloud.modules.exam.models import Exam, Subject, ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.exam.models import Question
from datetime import datetime


@pytest.fixture
async def school_admin_headers(db, seed_school):
    """principal 角色绑定测试学校，用于 school-scoped 端点测试。"""
    school, _ = seed_school
    user = User(username="school_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="principal",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_level_score_data(db, seed_school):
    """10 个学生，分数从 100 到 91。"""
    school, _ = seed_school
    school_id = school.id
    cls = Class(name="高一(1)班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()

    exam = Exam(name="期末考试", status="completed", school_id=school_id,
                exam_date=datetime(2026, 6, 20))
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="物理", code="physics", school_id=school_id)
    db.add(subj)
    await db.flush()

    students = []
    for i in range(10):
        stu = Student(name=f"学生{i}", student_number=f"L{i:03d}",
                      class_id=cls.id, grade="高一", school_id=school_id)
        db.add(stu)
        students.append(stu)
    await db.flush()

    for i, stu in enumerate(students):
        db.add(ExamResult(
            exam_id=exam.id, student_id=stu.id,
            school_id=school_id, total_score=100 - i,
        ))
    await db.flush()

    # F003: LevelScoreService 从 StudentAnswer 取科目分，需要 Question + StudentAnswer
    question = Question(
        exam_id=exam.id, subject_id=subj.id, school_id=school_id,
        name="T1", question_type="objective", score=100,
    )
    db.add(question)
    await db.flush()

    for i, stu in enumerate(students):
        db.add(StudentAnswer(
            exam_id=exam.id, student_id=stu.id, subject_id=subj.id,
            question_id=question.id, school_id=school_id,
            score=100 - i,
        ))
    await db.commit()
    return {"exam": exam, "subj": subj, "cls": cls, "students": students}


DEFAULT_LEVELS = [
    {"level": "A", "start_pct": 0, "end_pct": 20, "score_min": 86, "score_max": 100},
    {"level": "B", "start_pct": 20, "end_pct": 50, "score_min": 71, "score_max": 85},
    {"level": "C", "start_pct": 50, "end_pct": 80, "score_min": 56, "score_max": 70},
    {"level": "D", "start_pct": 80, "end_pct": 100, "score_min": 41, "score_max": 55},
]


@pytest.mark.asyncio
async def test_level_score_basic(client, school_admin_headers, seed_school, db):
    """10 学生、4 等级：验证划分和赋分值。"""
    data = await _seed_level_score_data(db, seed_school)

    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={
            "exam_id": data["exam"].id,
            "subject_id": data["subj"].id,
            "class_id": None,
            "levels": DEFAULT_LEVELS,
        },
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_students"] == 10
    assert len(result["level_stats"]) == 4
    assert len(result["students"]) == 10

    # ORC-005: 按原始分降序
    scores = [s["raw_score"] for s in result["students"]]
    assert scores == sorted(scores, reverse=True)

    # A 等级应包含前 20% = 2 人
    a_stat = next(s for s in result["level_stats"] if s["level"] == "A")
    assert a_stat["count"] == 2


@pytest.mark.asyncio
async def test_level_score_empty(client, school_admin_headers, seed_school):
    """不存在的考试返回 404。"""
    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={
            "exam_id": "nonexistent",
            "subject_id": "nonexistent",
            "levels": DEFAULT_LEVELS,
        },
        headers=school_admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_level_score_tied_scores(client, school_admin_headers, seed_school, db):
    """ORC-005：同分学生必须归入同一等级。"""
    school, _ = seed_school
    school_id = school.id
    cls = Class(name="高一(1)班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()

    exam = Exam(name="并列分测试", status="completed", school_id=school_id,
                exam_date=datetime(2026, 6, 20))
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school_id)
    db.add(subj)
    await db.flush()

    question = Question(
        exam_id=exam.id, subject_id=subj.id, school_id=school_id,
        name="T1", question_type="objective", score=100,
    )
    db.add(question)
    await db.flush()

    # 5 个学生，分数 100, 95, 95, 80, 70
    raw_scores = [100, 95, 95, 80, 70]
    students = []
    for i, sc in enumerate(raw_scores):
        stu = Student(name=f"并列{i}", student_number=f"T{i:03d}",
                      class_id=cls.id, grade="高一", school_id=school_id)
        db.add(stu)
        students.append((stu, sc))
    await db.flush()

    for stu, sc in students:
        db.add(ExamResult(exam_id=exam.id, student_id=stu.id,
                          school_id=school_id, total_score=sc))
        db.add(StudentAnswer(exam_id=exam.id, student_id=stu.id,
                             subject_id=subj.id, question_id=question.id,
                             school_id=school_id, score=sc))
    await db.commit()

    # 前 40% = A（2人），第 2/3 名同分 95 应同属一个等级
    levels = [
        {"level": "A", "start_pct": 0, "end_pct": 40, "score_min": 86, "score_max": 100},
        {"level": "B", "start_pct": 40, "end_pct": 100, "score_min": 41, "score_max": 85},
    ]
    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={"exam_id": exam.id, "subject_id": subj.id, "levels": levels},
        headers=school_admin_headers,
    )
    result = resp.json()
    tied = [s for s in result["students"] if s["raw_score"] == 95]
    assert len(tied) == 2
    assert tied[0]["level"] == tied[1]["level"], "ORC-005: 同分学生必须同级"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_level_score.py -v`
Expected: FAIL — 404 或 405

- [ ] **Step 3: 实现 LevelScoreService**

```python
# src/edu_cloud/modules/analytics/level_score_service.py
from __future__ import annotations

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student


async def convert_level_score(
    db: AsyncSession,
    school_id: str,
    exam_id: str,
    subject_id: str,
    levels: list[dict],
    class_id: str | None = None,
) -> dict | None:
    # F003: 用 StudentAnswer 按科目聚合分数，而非 ExamResult.total_score（全科总分）
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.name,
            func.sum(StudentAnswer.score).label("total_score"),
        )
        .join(StudentAnswer, StudentAnswer.student_id == Student.id)
        .where(StudentAnswer.exam_id == exam_id)
        .where(StudentAnswer.subject_id == subject_id)
        .where(StudentAnswer.school_id == school_id)
        .where(StudentAnswer.score.is_not(None))
        .group_by(Student.id, Student.name)
        .order_by(func.sum(StudentAnswer.score).desc())
    )
    if class_id:
        stmt = stmt.where(Student.class_id == class_id)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    total = len(rows)
    sorted_levels = sorted(levels, key=lambda lv: lv["start_pct"])

    students_out = []
    level_buckets: dict[str, list] = {lv["level"]: [] for lv in sorted_levels}

    # ORC-005：同分学生归入同一等级——先按分数分组，同组使用同一百分位
    score_groups = []
    current_score = None
    for rank_idx, row in enumerate(rows):
        if row.total_score != current_score:
            current_score = row.total_score
            score_groups.append({"score": current_score, "start_idx": rank_idx, "students": []})
        score_groups[-1]["students"].append(row)

    for group in score_groups:
        pct = (group["start_idx"] / total) * 100
        assigned_level = sorted_levels[-1]
        for lv in sorted_levels:
            if lv["start_pct"] <= pct < lv["end_pct"]:
                assigned_level = lv
                break

        for row in group["students"]:
            entry = {
                "student_id": row.student_id,
                "name": row.name,
                "raw_score": row.total_score,
                "level": assigned_level["level"],
                "rank": group["start_idx"] + 1,  # 同分同名次
                "assigned_score": 0.0,
            }
            level_buckets[assigned_level["level"]].append(entry)
            students_out.append(entry)

    for lv in sorted_levels:
        bucket = level_buckets[lv["level"]]
        n = len(bucket)
        for i, stu in enumerate(bucket):
            if n <= 1:
                stu["assigned_score"] = round((lv["score_min"] + lv["score_max"]) / 2, 1)
            else:
                stu["assigned_score"] = round(
                    lv["score_max"] - (lv["score_max"] - lv["score_min"]) * i / (n - 1), 1
                )

    level_stats = []
    for lv in sorted_levels:
        bucket = level_buckets[lv["level"]]
        raw_scores = [s["raw_score"] for s in bucket]
        count = len(bucket)
        level_stats.append({
            "level": lv["level"],
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
            "raw_min": min(raw_scores) if raw_scores else None,
            "raw_max": max(raw_scores) if raw_scores else None,
            "assigned_range": [lv["score_min"], lv["score_max"]],
        })

    def _build_dist(score_list, bins=10):
        if not score_list:
            return {"segments": [], "counts": []}
        lo, hi = min(score_list), max(score_list)
        step = max((hi - lo) / bins, 1)
        segments, counts = [], []
        for i in range(bins):
            seg_lo = lo + step * i
            seg_hi = lo + step * (i + 1)
            segments.append(f"{seg_lo:.0f}-{seg_hi:.0f}")
            if i == bins - 1:
                cnt = sum(1 for s in score_list if seg_lo <= s <= seg_hi)
            else:
                cnt = sum(1 for s in score_list if seg_lo <= s < seg_hi)
            counts.append(cnt)
        return {"segments": segments, "counts": counts}

    return {
        "total_students": total,
        "level_stats": level_stats,
        "students": students_out,
        "distribution_before": _build_dist([r.total_score for r in rows]),
        "distribution_after": _build_dist([s["assigned_score"] for s in students_out]),
    }
```

- [ ] **Step 4: 在 router.py 末尾追加等级赋分端点**

在 `src/edu_cloud/modules/analytics/router.py` 文件末尾追加：

```python
# --- 等级赋分 ---

from edu_cloud.modules.analytics.level_score_service import convert_level_score


@router.post("/level-score/convert")
async def level_score_convert(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """等级赋分转换：原始分按百分位划分等级，线性插值赋分。"""
    role = current["current_role"]
    result = await convert_level_score(
        db,
        school_id=role.school_id,
        exam_id=body["exam_id"],
        subject_id=body["subject_id"],
        levels=body["levels"],
        class_id=body.get("class_id"),
    )
    if result is None:
        raise HTTPException(404, "无成绩数据")
    return result
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_level_score.py -v`
Expected: 3 PASS

- [ ] **Step 6: 运行全量后端测试确认无回归**

Run: `.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: 1977+ passed（基线 1970 + 新增 7：power_options 4 + level_score 3）

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/analytics/level_score_service.py \
        src/edu_cloud/modules/analytics/router.py \
        tests/test_api/test_analytics_level_score.py
git commit -m "feat(analytics): LevelScoreService + POST /level-score/convert 端点"
```

---

### Task 3: useApi 扩展 + usePowerOptions composable + 前端测试

**Files:**
- Modify: `frontend-nuxt/composables/useApi.ts:84-86` (替换 getPowerOptions stub，追加方法)
- Create: `frontend-nuxt/composables/usePowerOptions.ts`
- Create: `frontend-nuxt/tests/composables/usePowerOptions.test.ts`

**参考文件：**
- `frontend-nuxt/composables/useApi.ts` — 现有 request 函数 (L17-36)、getPowerOptions stub (L84-86)
- `frontend-nuxt/tests/setup.ts` — 测试 setup 模式 (L1-51)
- `frontend-nuxt/tests/composables/useApi.test.ts` — 现有 composable 测试模式

- [ ] **Step 1: 在 useApi.ts 替换 getPowerOptions stub 并追加方法**

替换 `frontend-nuxt/composables/useApi.ts` 中 L84-86 的 `getPowerOptions` stub：

```typescript
    // F007: 方法名与 useApi.ts 已有命名保持一致（getPowerOptions / getExamGradeAggregates）
    // 注：design.md 中 created_at 应为 exam_date（与 Exam 模型一致）
    getPowerOptions: (params?: Record<string, any>) =>
      request('/analytics/power-options', { query: params }),
```

在 return 块末尾 `// === Raw ===` 前追加：

```typescript
    // === Level Score ===
    convertLevelScore: (data: any) =>
      request('/analytics/level-score/convert', { method: 'POST', body: data }),

    // === Report ===
    queryReport: (data: any) =>
      request('/analytics/report/query', { method: 'POST', body: data }),
    upsertSegmentsConfig: (data: any) =>
      request('/analytics/segments/config', { method: 'PUT', body: data }),
    deleteSegmentOverride: (subjectCode: string) =>
      request(`/analytics/segments/config/${subjectCode}`, { method: 'DELETE' }),
```

- [ ] **Step 1.5: 同步修改 useApi.test.ts (F006)**

把 `frontend-nuxt/tests/composables/useApi.test.ts` 中 `describe('getPowerOptions stub')` 的 3 个测试改为验证 `$fetch` 调用路径是 `/analytics/power-options`（不再是 stub 返回空数组，而是真实调用 request）。

- [ ] **Step 2: 创建 usePowerOptions composable**

```typescript
// frontend-nuxt/composables/usePowerOptions.ts
export interface ExamNode {
  exam_id: string
  subject_id: string
  name: string
  exam_date: string | null
  student_count: number
}

export interface SubjectNode {
  id: string
  code: string
  name: string
  exams: ExamNode[]
}

export interface ClassNode {
  id: string
  name: string
  subjects: SubjectNode[]
}

export interface GradeNode {
  name: string
  classes: ClassNode[]
}

export function usePowerOptions() {
  const tree = ref<GradeNode[]>([])
  const loading = ref(false)

  const selectedGrade = ref('')
  const selectedClassId = ref('all')
  const selectedSubjectId = ref('')
  const selectedExamId = ref('')

  const gradeOptions = computed(() => tree.value.map(g => g.name))

  const classOptions = computed(() => {
    const grade = tree.value.find(g => g.name === selectedGrade.value)
    return grade?.classes ?? []
  })

  const subjectOptions = computed(() => {
    const cls = classOptions.value.find(c => c.id === selectedClassId.value)
    return cls?.subjects ?? []
  })

  const examOptions = computed(() => {
    const subj = subjectOptions.value.find(s => s.id === selectedSubjectId.value)
    return subj?.exams ?? []
  })

  watch(selectedGrade, () => {
    selectedClassId.value = classOptions.value[0]?.id ?? 'all'
  })
  watch(selectedClassId, () => {
    selectedSubjectId.value = subjectOptions.value[0]?.id ?? ''
  })
  watch(selectedSubjectId, () => {
    selectedExamId.value = examOptions.value[0]?.exam_id ?? ''
  })

  const analysisParams = computed(() => ({
    exam_id: selectedExamId.value,
    subject_id: selectedSubjectId.value,
    class_id: selectedClassId.value === 'all' ? null : selectedClassId.value,
  }))

  const hasSelection = computed(() => !!selectedExamId.value)

  async function load(examType?: string, year?: number) {
    loading.value = true
    try {
      const api = useApi()
      const data = await api.getPowerOptions({
        exam_type: examType,
        year,
      })
      tree.value = data.grades
      if (tree.value.length) {
        selectedGrade.value = tree.value[0].name
      }
    } finally {
      loading.value = false
    }
  }

  return {
    load, tree, loading,
    selectedGrade, selectedClassId, selectedSubjectId, selectedExamId,
    gradeOptions, classOptions, subjectOptions, examOptions,
    analysisParams, hasSelection,
  }
}
```

- [ ] **Step 3: 写 composable 单测**

```typescript
// frontend-nuxt/tests/composables/usePowerOptions.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { usePowerOptions } from '~/composables/usePowerOptions'

const MOCK_TREE = {
  grades: [
    {
      name: '高一',
      classes: [
        {
          id: 'all', name: '全部班级',
          subjects: [
            { id: 's1', code: 'math', name: '数学',
              exams: [{ exam_id: 'e1', subject_id: 's1', name: '期中', exam_date: '2026-04-10', student_count: 90 }] },
          ],
        },
        {
          id: 'c1', name: '高一(1)班',
          subjects: [
            { id: 's1', code: 'math', name: '数学',
              exams: [{ exam_id: 'e1', subject_id: 's1', name: '期中', exam_date: '2026-04-10', student_count: 45 }] },
          ],
        },
      ],
    },
  ],
}

describe('usePowerOptions', () => {
  beforeEach(() => {
    ;(globalThis as any).useApi = () => ({
      getPowerOptions: vi.fn().mockResolvedValue(MOCK_TREE),
    })
  })

  it('load 后自动选中首项', async () => {
    const po = usePowerOptions()
    await po.load()
    await nextTick()

    expect(po.gradeOptions.value).toEqual(['高一'])
    expect(po.selectedGrade.value).toBe('高一')
    expect(po.selectedClassId.value).toBe('all')
  })

  it('级联重置：切换班级重置科目和考试', async () => {
    const po = usePowerOptions()
    await po.load()
    await nextTick()

    po.selectedClassId.value = 'c1'
    await nextTick()
    expect(po.selectedSubjectId.value).toBe('s1')
    expect(po.selectedExamId.value).toBe('e1')
  })

  it('analysisParams: all → class_id null (ORC-003)', async () => {
    const po = usePowerOptions()
    await po.load()
    await nextTick()

    expect(po.analysisParams.value.class_id).toBeNull()

    po.selectedClassId.value = 'c1'
    await nextTick()
    expect(po.analysisParams.value.class_id).toBe('c1')
  })

  it('空数据: gradeOptions 为空数组', async () => {
    ;(globalThis as any).useApi = () => ({
      getPowerOptions: vi.fn().mockResolvedValue({ grades: [] }),
    })
    const po = usePowerOptions()
    await po.load()
    expect(po.gradeOptions.value).toEqual([])
    expect(po.hasSelection.value).toBe(false)
  })
})
```

- [ ] **Step 4: 运行前端测试**

Run: `cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run tests/composables/usePowerOptions.test.ts`
Expected: 4 PASS

- [ ] **Step 5: 运行全量前端测试确认无回归**

Run: `cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run`
Expected: 28 PASS（基线 24 + 新增 4）

- [ ] **Step 6: Commit**

```bash
git add frontend-nuxt/composables/useApi.ts \
        frontend-nuxt/composables/usePowerOptions.ts \
        frontend-nuxt/tests/composables/usePowerOptions.test.ts
git commit -m "feat(frontend-nuxt): usePowerOptions composable + useApi analytics 方法"
```

---

## Batch 2: PowerFilter 组件 + 6 个报告页面（Task 4-10）

> Batch 2 前端页面依赖 ECharts 和 Element Plus。每个页面独立文件，均消费 PowerFilter 组件。
> 安装依赖一次性完成（Task 4 Step 1）。
> 页面为纯前端渲染，后端端点已就绪，不需要后端改动。

### Task 4: ECharts 依赖 + PowerFilter 组件

**Files:**
- Modify: `frontend-nuxt/package.json` (添加 echarts + vue-echarts)
- Create: `frontend-nuxt/components/common/PowerFilter.vue`
- Modify: `frontend-nuxt/tests/setup.ts` (追加 usePowerOptions + onMounted mock)

- [ ] **Step 1: 安装 ECharts**

Run: `cd /home/ops/projects/edu-cloud/frontend-nuxt && npm install echarts vue-echarts`

- [ ] **Step 2: 创建 PowerFilter.vue**

创建 `frontend-nuxt/components/common/PowerFilter.vue`，4 个 ElSelect 水平排列，v-model 绑定 usePowerOptions 状态，onMounted 调 load()。组件内容见设计文档 §3.2。考试选择器显示"名称 (日期)"格式，无数据时 disabled。

- [ ] **Step 3: 在 setup.ts 追加 usePowerOptions 和 onMounted mock**

在 `frontend-nuxt/tests/setup.ts` 的 `beforeEach` 前追加 `g.usePowerOptions` 和 `g.onMounted` mock，返回空状态的 composable。

- [ ] **Step 3.5: PowerFilter mount test (F008)**

创建 `frontend-nuxt/tests/components/PowerFilter.test.ts`，验证：
1. 挂载后渲染 4 个 ElSelect（年级/班级/科目/考试）
2. onMounted 调用 `load()`
3. 无数据时所有 select disabled
4. 有数据时选项正确渲染

```typescript
// frontend-nuxt/tests/components/PowerFilter.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PowerFilter from '~/components/common/PowerFilter.vue'

describe('PowerFilter', () => {
  it('renders 4 ElSelect components', () => {
    const wrapper = mount(PowerFilter)
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBe(4)
  })

  it('calls load on mounted', () => {
    // usePowerOptions mock 的 load 应被调用
    mount(PowerFilter)
    const mockPO = (globalThis as any).usePowerOptions()
    expect(mockPO.load).toHaveBeenCalled()
  })
})
```

- [ ] **Step 4: 运行全量前端测试确认无回归**

Run: `cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run`
Expected: 28 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend-nuxt/components/common/PowerFilter.vue \
        frontend-nuxt/tests/setup.ts \
        frontend-nuxt/tests/components/PowerFilter.test.ts \
        frontend-nuxt/package.json frontend-nuxt/package-lock.json
git commit -m "feat(frontend-nuxt): PowerFilter 级联筛选组件 + ECharts 依赖 + mount test"
```

---

### Task 5-9: 6 个报告页面

> 每个页面独立 commit。页面代码见设计文档 §4.1-4.6。
> 页面均在 `frontend-nuxt/pages/report/` 下，Nuxt 文件路由自动注册。
> 每个页面顶部渲染 `<PowerFilter />`，watch analysisParams 触发数据加载。

**Task 5**: `pages/report/exam.vue` — 考试报告（统计卡片 + 分布图 + 题目分析表）
**Task 6**: `pages/report/contrast.vue` — 班级对比（分组柱状图 + 对比表格）
**Task 7**: `pages/report/custom.vue` — 自定义分析（指标复选 + 动态图表）
**Task 8**: `pages/report/table.vue` — 自定义表格（纯表格 + CSV 导出）
**Task 9**: `pages/report/level-score.vue` — 等级赋分（配置区 + 赋分前后对比 + 学生明细）

每个 Task 步骤相同：
- [ ] **Step 1: 创建页面文件**（代码见设计文档对应节）
- [ ] **Step 2: Commit**

### Task 10: report/config.vue + 收尾

**Files:**
- Create: `frontend-nuxt/pages/report/config.vue`
- Modify: `CLAUDE.md` (更新端点表和测试计数)

- [ ] **Step 1: 创建 config.vue**（不依赖 PowerFilter，独立的分数段配置页）
- [ ] **Step 2: 运行全量前端测试**

Run: `cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run`
Expected: 28+ PASS

- [ ] **Step 3: 运行全量后端测试**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: 1976+ passed

- [ ] **Step 4: 更新 CLAUDE.md**

在 API 端点表追加 `GET /analytics/power-options` 和 `POST /analytics/level-score/convert`。更新测试计数。更新 useApi 方法描述。

- [ ] **Step 5: Commit**

```bash
git add frontend-nuxt/pages/report/config.vue CLAUDE.md
git commit -m "feat(frontend-nuxt): report/config.vue + CLAUDE.md 同步"
```

---

## 测试契约汇总

| 入口 | 反例 | 边界 | 回归 | 命令 |
|------|------|------|------|------|
| PowerOptions 端点 | 空数据→`{grades:[]}` | RBAC 过滤科目 | draft 不出现 | `.venv/bin/python -m pytest tests/test_api/test_analytics_power_options.py -v` |
| 等级赋分端点 | 不存在考试→404 | A 等级人数=前20%；并列分同级(ORC-005) | 原始分降序+同分同级 | `.venv/bin/python -m pytest tests/test_api/test_analytics_level_score.py -v` |
| usePowerOptions | 空数据→空选项 | 级联重置 | ORC-003 class_id=null | `cd frontend-nuxt && npx vitest run tests/composables/usePowerOptions.test.ts` |
| 全量后端 | — | — | 无回归 | `.venv/bin/python -m pytest --tb=short -q` |
| 全量前端 | — | — | 无回归 | `cd frontend-nuxt && npx vitest run` |
