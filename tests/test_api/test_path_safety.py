"""路径安全回归测试 — path_safety.py 引入后的 marking/grading 端点。

覆盖：
- resolve_user_input_path: ./uploads 路径接受、/tmp 路径拒绝
- marking import 权限拒绝（需 MANAGE_GRADING）
- marking import 路径拒绝（路径逃逸）
- answer image containment（stored path 逃逸被拒）
"""

import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.shared.auth import create_access_token
from edu_cloud.config import settings


@pytest.fixture
async def path_data(db):
    """School + exam + subject + question + student answer with image_path."""
    school = School(name="路径安全测试校", code="PATH", district="D", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="路径测试考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.flush()

    subj = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(
        name="第1题", subject_id=subj.id, question_type="choice",
        max_score=5.0, correct_answer="A", school_id=school.id,
    )
    db.add(q)
    await db.flush()

    # admin user (has MANAGE_GRADING)
    admin = User(username="path_admin", display_name="Admin")
    admin.set_password("test123")
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role="admin",
                    school_id=school.id, is_primary=True))

    # teacher user (no MANAGE_GRADING)
    teacher = User(username="path_teacher", display_name="Teacher")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="teacher",
                    school_id=school.id, is_primary=True))

    await db.commit()

    admin_token = create_access_token({
        "sub": admin.id, "role": "admin",
        "school_id": school.id,
    })
    teacher_token = create_access_token({
        "sub": teacher.id, "role": "teacher",
        "school_id": school.id,
    })
    return {
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "teacher_headers": {"Authorization": f"Bearer {teacher_token}"},
        "school_id": school.id,
        "exam_id": exam.id,
        "subject_id": subj.id,
        "question_id": q.id,
    }


# ── marking import: permission rejected (needs MANAGE_GRADING) ──

@pytest.mark.asyncio
async def test_marking_import_rejects_teacher(client, path_data, tmp_path, monkeypatch):
    """teacher 角色无 MANAGE_GRADING → 403。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    folder = tmp_path / "subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": path_data["exam_id"],
        "folder_path": str(folder),
    }, headers=path_data["teacher_headers"])
    assert resp.status_code == 403


# ── marking import: path traversal rejected ──

@pytest.mark.asyncio
async def test_marking_import_rejects_path_escape(client, path_data, tmp_path, monkeypatch):
    """/tmp 路径不在 UPLOAD_DIR/STORAGE_ROOT → 403。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": path_data["exam_id"],
        "folder_path": "/tmp/evil",
    }, headers=path_data["admin_headers"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_marking_import_rejects_traversal(client, path_data, tmp_path, monkeypatch):
    """相对路径 ../../../etc → 403。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": path_data["exam_id"],
        "folder_path": "../../../etc",
    }, headers=path_data["admin_headers"])
    assert resp.status_code == 403


# ── marking import: valid path accepted ──

@pytest.mark.asyncio
async def test_marking_import_accepts_valid_path(client, path_data, tmp_path, monkeypatch):
    """UPLOAD_DIR 内的路径 → 正常（可能 400 因为目录结构不对，但不是 403）。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    folder = tmp_path / "subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": path_data["exam_id"],
        "folder_path": str(folder),
    }, headers=path_data["admin_headers"])
    assert resp.status_code != 403


# ── answer image: stored path containment ──

@pytest.mark.asyncio
async def test_answer_image_rejects_escaped_stored_path(client, path_data, db, monkeypatch, tmp_path):
    """StudentAnswer.image_path 指向 /etc/passwd → 403。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))

    answer = StudentAnswer(
        exam_id=path_data["exam_id"],
        subject_id=path_data["subject_id"],
        student_id="student-evil",
        question_id=path_data["question_id"],
        image_path="/etc/passwd",
        school_id=path_data["school_id"],
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)

    resp = await client.get(
        f"/api/v1/marking/answer/{answer.id}/image",
        headers=path_data["admin_headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_answer_image_rejects_traversal_stored_path(client, path_data, db, monkeypatch, tmp_path):
    """StudentAnswer.image_path 为 ../../etc/passwd → 403。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))

    answer = StudentAnswer(
        exam_id=path_data["exam_id"],
        subject_id=path_data["subject_id"],
        student_id="student-evil2",
        question_id=path_data["question_id"],
        image_path="../../etc/passwd",
        school_id=path_data["school_id"],
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)

    resp = await client.get(
        f"/api/v1/marking/answer/{answer.id}/image",
        headers=path_data["admin_headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_answer_image_accepts_valid_stored_path(client, path_data, db, monkeypatch, tmp_path):
    """image_path 在 storage 目录内且文件存在 → 200。"""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    img_file = storage_dir / "test.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))

    answer = StudentAnswer(
        exam_id=path_data["exam_id"],
        subject_id=path_data["subject_id"],
        student_id="student-good",
        question_id=path_data["question_id"],
        image_path=str(img_file),
        school_id=path_data["school_id"],
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)

    resp = await client.get(
        f"/api/v1/marking/answer/{answer.id}/image",
        headers=path_data["admin_headers"],
    )
    assert resp.status_code == 200


# ── resolve_user_input_path unit tests ──

def test_resolve_user_input_path_accepts_within_roots(tmp_path):
    """UPLOAD_DIR 内的路径 → 正常返回。"""
    from edu_cloud.shared.path_safety import resolve_user_input_path
    upload = tmp_path / "uploads"
    upload.mkdir()
    target = upload / "exam1" / "subj1"
    target.mkdir(parents=True)

    result = resolve_user_input_path(str(target), allowed_roots=[upload])
    assert result == target.resolve()


def test_resolve_user_input_path_rejects_outside(tmp_path):
    """不在 allowed_roots 内 → 403。"""
    from fastapi import HTTPException
    from edu_cloud.shared.path_safety import resolve_user_input_path
    upload = tmp_path / "uploads"
    upload.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        resolve_user_input_path("/tmp/evil", allowed_roots=[upload])
    assert exc_info.value.status_code == 403


def test_resolve_stored_file_path_rejects_escape(tmp_path):
    """stored path 逃逸 → 403。"""
    from fastapi import HTTPException
    from edu_cloud.shared.path_safety import resolve_stored_file_path
    upload = tmp_path / "uploads"
    upload.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        resolve_stored_file_path("/etc/passwd", allowed_roots=[upload])
    assert exc_info.value.status_code == 403


def test_resolve_stored_file_path_accepts_storage(tmp_path):
    """storage 目录内的 relative path → 正常。"""
    from edu_cloud.shared.path_safety import resolve_stored_file_path
    storage = tmp_path / "storage"
    storage.mkdir()

    result = resolve_stored_file_path(str(storage / "img.png"), allowed_roots=[storage])
    assert result == (storage / "img.png").resolve()
