import math
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics.models import StudentKnpMastery
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="diag_principal", display_name="诊断校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_diagnosis_data(db, seed_school):
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(5):
        s = Student(name=f"学生{i}", student_number=f"D{i:03d}", class_id=cls.id, school_id=school.id, grade="高一")
        db.add(s)
        students.append(s)
    await db.flush()

    exam = Exam(name="诊断考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()

    # 7 个知识点，各学生掌握率不同
    # kp1: 全低 (0.2~0.3) → worst
    # kp2: 3 人 <0.6 → unmaster 多
    # kp3: 极差大 (0.1 ~ 0.9) → maxDiff
    # kp4~kp7: 普通
    kp_rates = {
        "kp1": [0.2, 0.25, 0.3, 0.22, 0.28],   # avg ~0.25, 5 人 <0.6
        "kp2": [0.5, 0.4, 0.55, 0.8, 0.9],      # 3 人 <0.6
        "kp3": [0.1, 0.5, 0.9, 0.6, 0.7],       # diff=0.8
        "kp4": [0.7, 0.75, 0.8, 0.85, 0.9],     # high, 0 人 <0.6
        "kp5": [0.6, 0.65, 0.7, 0.55, 0.5],     # 2 人 <0.6
        "kp6": [0.3, 0.35, 0.4, 0.45, 0.5],     # avg ~0.4, 5 人 <0.6
        "kp7": [0.5, 0.55, 0.6, 0.65, 0.7],     # 1 人 <0.6
    }

    for kp_id, rates in kp_rates.items():
        for i, rate in enumerate(rates):
            m = StudentKnpMastery(
                student_id=students[i].id,
                exam_id=exam.id,
                concept_id=kp_id,
                school_id=school.id,
                stu_rate=rate,
                class_rate=sum(rates) / len(rates),
                grade_rate=sum(rates) / len(rates),
            )
            db.add(m)
    await db.commit()

    return exam, subj, cls, students


@pytest.mark.asyncio
async def test_class_diagnosis_returns_three_lists(client, school_admin_headers, seed_school, db):
    exam, subj, cls, _ = await _seed_diagnosis_data(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        params={"subject_id": subj.id, "class_id": cls.id},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "worstKnowledges" in data
    assert "unmasterMaxCntKnowledges" in data
    assert "maxScoreDiffKnowledges" in data
    assert "weakKnpCount" in data


@pytest.mark.asyncio
async def test_class_diagnosis_worst_top5(client, school_admin_headers, seed_school, db):
    exam, subj, cls, _ = await _seed_diagnosis_data(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        params={"subject_id": subj.id, "class_id": cls.id},
        headers=school_admin_headers,
    )
    data = resp.json()
    worst = data["worstKnowledges"]
    assert len(worst) <= 5
    # kp1 (avg ~0.25) 应排第一
    assert worst[0]["concept_id"] == "kp1"
    # 升序排列
    rates = [w["rate"] for w in worst]
    assert rates == sorted(rates)


@pytest.mark.asyncio
async def test_class_diagnosis_unmaster_count(client, school_admin_headers, seed_school, db):
    exam, subj, cls, _ = await _seed_diagnosis_data(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        params={"subject_id": subj.id, "class_id": cls.id},
        headers=school_admin_headers,
    )
    data = resp.json()
    unmaster = data["unmasterMaxCntKnowledges"]
    assert len(unmaster) <= 5
    # kp1 和 kp6 各有 5 人 <0.6, kp2 有 3 人
    assert unmaster[0]["count"] == 5
    # 降序
    counts = [u["count"] for u in unmaster]
    assert counts == sorted(counts, reverse=True)


@pytest.mark.asyncio
async def test_class_diagnosis_max_diff(client, school_admin_headers, seed_school, db):
    exam, subj, cls, _ = await _seed_diagnosis_data(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        params={"subject_id": subj.id, "class_id": cls.id},
        headers=school_admin_headers,
    )
    data = resp.json()
    max_diff = data["maxScoreDiffKnowledges"]
    assert len(max_diff) <= 5
    # kp3 差值 0.8 应排第一
    assert max_diff[0]["concept_id"] == "kp3"
    assert abs(max_diff[0]["diff"] - 0.8) < 0.01
    # 降序
    diffs = [m["diff"] for m in max_diff]
    assert diffs == sorted(diffs, reverse=True)


@pytest.mark.asyncio
async def test_class_diagnosis_weak_count(client, school_admin_headers, seed_school, db):
    exam, subj, cls, _ = await _seed_diagnosis_data(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        params={"subject_id": subj.id, "class_id": cls.id},
        headers=school_admin_headers,
    )
    data = resp.json()
    # 7 个知识点, floor(7 * 0.3) = 2
    assert data["weakKnpCount"] == math.floor(7 * 0.3)


@pytest.mark.asyncio
async def test_class_diagnosis_empty(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    exam = Exam(name="空考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.commit()
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["worstKnowledges"] == []
    assert data["unmasterMaxCntKnowledges"] == []
    assert data["maxScoreDiffKnowledges"] == []
    assert data["weakKnpCount"] == 0
