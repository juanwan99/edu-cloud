import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def two_schools(db):
    s1 = School(name="学校A", code="SA", district="D", api_key_hash="x")
    s2 = School(name="学校B", code="SB", district="D", api_key_hash="x")
    db.add_all([s1, s2])
    await db.flush()

    exam_b = Exam(name="B校考试", school_id=s2.id, status="draft")
    db.add(exam_b)
    await db.flush()

    user_a = User(username="importer_a", display_name="A")
    user_a.set_password("test123")
    db.add(user_a)
    await db.flush()
    db.add(UserRole(user_id=user_a.id, role="academic_director",
                    school_id=s1.id, is_primary=True))
    await db.commit()

    token_a = create_access_token({
        "sub": user_a.id, "role": "academic_director",
        "school_id": s1.id,
    })
    return {
        "school_a_id": s1.id, "school_b_id": s2.id,
        "exam_b_id": exam_b.id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
    }


@pytest.mark.asyncio
async def test_import_rejects_other_school_exam(client, two_schools, tmp_path):
    """A校用户用 B校 exam_id 调用 import -> 400/404"""
    folder = tmp_path / "subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": two_schools["exam_b_id"],
        "folder_path": str(folder),
    }, headers=two_schools["headers_a"])
    assert resp.status_code in (400, 404)
    assert "不存在" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_import_accepts_own_school_exam(client, two_schools, db, tmp_path):
    """A校用户用自己学校的 exam_id -> 正常"""
    own_exam = Exam(name="A校考试", school_id=two_schools["school_a_id"], status="draft")
    db.add(own_exam)
    await db.commit()

    folder = tmp_path / "empty_subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": own_exam.id,
        "folder_path": str(folder),
    }, headers=two_schools["headers_a"])
    assert resp.status_code == 200
