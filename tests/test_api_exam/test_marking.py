import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam
from edu_cloud.modules.exam.models import Subject
from edu_cloud.shared.auth import create_access_token
from edu_cloud.config import settings


@pytest.fixture
async def marking_setup(client, db, tmp_path, monkeypatch):
    """创建测试学校/用户/考试 + 测试文件夹结构。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    school = School(name="MK", code="MK01")
    db.add(school)
    await db.commit()

    user = User(username="teacher1", display_name="教师1")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="期中考试", school_id=school.id, status="scanning")
    db.add(exam)
    await db.commit()

    # 创建测试文件夹结构: 语文/4题/{student}.png
    subj_dir = tmp_path / "语文" / "4题"
    subj_dir.mkdir(parents=True)
    for i in range(3):
        (subj_dir / f"S{i:04d}.png").write_bytes(b"\x89PNG fake")

    # 另一个科目
    math_dir = tmp_path / "数学" / "15题"
    math_dir.mkdir(parents=True)
    for i in range(2):
        (math_dir / f"S{i:04d}.png").write_bytes(b"\x89PNG fake")

    return {
        "headers": headers,
        "exam_id": exam.id,
        "school_id": school.id,
        "user_id": user.id,
        "folder": str(tmp_path),
    }


# ---------- Import tests ----------

async def test_import_folder(client, marking_setup):
    resp = await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subjects_created"] == 2
    assert data["questions_created"] == 2
    assert data["answers_created"] == 5
    assert data["answers_skipped"] == 0


async def test_import_idempotent(client, marking_setup):
    """重复导入不创建重复记录。"""
    resp1 = await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["answers_created"] == 0
    assert data2["answers_skipped"] == 5


async def test_import_bad_folder(client, marking_setup):
    resp = await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": "/nonexistent"},
        headers=marking_setup["headers"],
    )
    assert resp.status_code in (400, 403)


# ---------- Subject listing ----------

async def test_list_subjects_after_import(client, marking_setup):
    await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={marking_setup['exam_id']}",
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for subj in data:
        assert len(subj["questions"]) >= 1
        for q in subj["questions"]:
            assert q["total_answers"] > 0
            assert q["graded_count"] == 0


# ---------- Grading flow ----------

async def test_next_and_score_flow(client, marking_setup):
    """完整的阅卷流程：导入→获取下一份→打分→再获取。"""
    await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )

    subjects = (await client.get(
        f"/api/v1/marking/subjects?exam_id={marking_setup['exam_id']}",
        headers=marking_setup["headers"],
    )).json()

    question_id = subjects[0]["questions"][0]["id"]

    # 获取下一份
    resp = await client.get(
        f"/api/v1/marking/next?question_id={question_id}",
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    answer_id = data["answer"]["answer_id"]

    # 打分
    resp = await client.post(
        "/api/v1/marking/score",
        json={"answer_id": answer_id, "score": 8.0},
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # 复核改分（279ea1a 起允许已 confirmed 记录改分，返回 200 + 审计日志）
    resp = await client.post(
        "/api/v1/marking/score",
        json={"answer_id": answer_id, "score": 9.0},
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200


# ---------- Progress ----------

async def test_progress_after_scoring(client, marking_setup):
    await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )

    subjects = (await client.get(
        f"/api/v1/marking/subjects?exam_id={marking_setup['exam_id']}",
        headers=marking_setup["headers"],
    )).json()
    question_id = subjects[0]["questions"][0]["id"]

    next_resp = await client.get(
        f"/api/v1/marking/next?question_id={question_id}",
        headers=marking_setup["headers"],
    )
    answer_id = next_resp.json()["answer"]["answer_id"]
    await client.post(
        "/api/v1/marking/score",
        json={"answer_id": answer_id, "score": 5.0},
        headers=marking_setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/marking/progress?exam_id={marking_setup['exam_id']}",
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"]["graded"] == 1
    assert data["overall"]["total"] == 5


# ---------- Export ----------

# ---------- F006 / F009 权限过滤回归（B2）----------

async def test_list_subjects_filters_by_subject_teacher_visibility(client, db):
    """F006/F009 回归：subject_teacher 只能看到 role.subject_codes 中的科目。

    反例：错误实现返回全部 9 科，本测试捕获此错误。
    入口：GET /api/v1/marking/subjects?exam_id=...
    边界：subject_codes=['YW']（语文） → 响应仅含语文一项
    """
    school = School(name="F006School", code="F006S")
    db.add(school)
    await db.commit()

    exam = Exam(name="F006测试考试", school_id=school.id, status="scanning")
    db.add(exam)
    await db.commit()

    subj_yw = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    subj_sx = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    subj_en = Subject(exam_id=exam.id, name="英语", code="EN", school_id=school.id)
    db.add_all([subj_yw, subj_sx, subj_en])
    await db.commit()

    user = User(username="f006_yw_teacher", display_name="语文老师")
    user.set_password("p")
    db.add(user)
    await db.commit()

    db.add(UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        subject_codes=["YW"],
        is_primary=True,
    ))
    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "subject_teacher",
    })
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    names = [s["name"] for s in data]
    assert names == ["语文"], (
        f"subject_teacher 应只看到语文，实际: {names}"
    )


async def test_list_subjects_admin_sees_all_subjects(client, db):
    """回归：academic_director / admin 角色看到全部科目，不受过滤影响。"""
    school = School(name="F006School2", code="F006S2")
    db.add(school)
    await db.commit()

    exam = Exam(name="admin测试考试", school_id=school.id, status="scanning")
    db.add(exam)
    await db.commit()

    subj_yw = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    subj_sx = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add_all([subj_yw, subj_sx])
    await db.commit()

    user = User(username="f006_admin", display_name="教务主任")
    user.set_password("p")
    db.add(user)
    await db.commit()

    db.add(UserRole(
        user_id=user.id,
        role="academic_director",
        school_id=school.id,
        is_primary=True,
    ))
    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "academic_director",
    })
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    names = sorted(s["name"] for s in resp.json())
    assert names == ["数学", "语文"]


async def test_export_csv_filters_by_subject_teacher_visibility(client, db):
    """F006/F009 回归扩展：/marking/export CSV 只导出 role.subject_codes 中的科目。

    反例：错误实现会导出全部 9 科的列头，本测试捕获此错误。
    """
    school = School(name="F006ExpSchool", code="F006ES")
    db.add(school)
    await db.commit()

    exam = Exam(name="F006导出测试", school_id=school.id, status="scanning")
    db.add(exam)
    await db.commit()

    subj_yw = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    subj_sx = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add_all([subj_yw, subj_sx])
    await db.commit()

    user = User(username="f006_exp_teacher", display_name="导出测试教师")
    user.set_password("p")
    db.add(user)
    await db.commit()

    db.add(UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        subject_codes=["YW"],
        is_primary=True,
    ))
    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "subject_teacher",
    })
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/marking/export?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    header_line = resp.text.strip().split("\n")[0]
    assert "语文" in header_line or header_line.startswith("学生ID"), (
        f"导出表头应含语文相关列: {header_line}"
    )
    assert "数学" not in header_line, (
        f"subject_teacher 不应看到数学列: {header_line}"
    )


async def test_list_subjects_subject_teacher_with_empty_codes_sees_none(client, db):
    """边界：subject_teacher 的 subject_codes 为空列表 → 看不到任何科目。"""
    school = School(name="F006School3", code="F006S3")
    db.add(school)
    await db.commit()

    exam = Exam(name="empty考试", school_id=school.id, status="scanning")
    db.add(exam)
    await db.commit()

    subj_yw = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    db.add(subj_yw)
    await db.commit()

    user = User(username="f006_no_codes", display_name="无科目教师")
    user.set_password("p")
    db.add(user)
    await db.commit()

    db.add(UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        subject_codes=[],
        is_primary=True,
    ))
    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "subject_teacher",
    })
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_export_csv(client, marking_setup):
    await client.post(
        "/api/v1/marking/import",
        json={"exam_id": marking_setup["exam_id"], "folder_path": marking_setup["folder"]},
        headers=marking_setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/marking/export?exam_id={marking_setup['exam_id']}",
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
    assert "学生ID" in lines[0]
