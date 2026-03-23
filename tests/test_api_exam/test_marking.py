import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def marking_setup(client, db, tmp_path):
    """创建测试学校/用户/考试 + 测试文件夹结构。"""
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
    assert resp.status_code == 400


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

    # 重复打分应该 409
    resp = await client.post(
        "/api/v1/marking/score",
        json={"answer_id": answer_id, "score": 9.0},
        headers=marking_setup["headers"],
    )
    assert resp.status_code == 409


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
