import pytest
from io import BytesIO

PNG_HEADER = b"\x89PNG\r\n\x1a\n"

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def upload_setup(client, db):
    school = School(name="Test", code="UL01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="E", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="Math", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()
    question = Question(
        subject_id=subject.id, name="Q1", question_type="essay",
        max_score=10, school_id=school.id,
    )
    db.add(question)
    await db.commit()

    return headers, exam.id, subject.id, question.id


async def test_upload_rejects_oversized_file(client, upload_setup):
    headers, exam_id, subject_id, question_id = upload_setup
    big_data = PNG_HEADER + b"x" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/scan/upload",
        data={
            "exam_id": exam_id,
            "subject_id": subject_id,
            "student_id": "S001",
            "question_id": question_id,
        },
        files={"image": ("big.png", BytesIO(big_data), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 413


async def test_upload_batch_rejects_oversized_file(client, upload_setup):
    """batch 上传中某张图片超限 → 413，且已保存的文件被清理。"""
    headers, exam_id, subject_id, question_id = upload_setup
    small_data = PNG_HEADER + b"x" * 100
    big_data = PNG_HEADER + b"x" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/scan/upload/batch",
        data={
            "exam_id": exam_id,
            "subject_id": subject_id,
            "student_id": "S002",
            "question_ids": f"{question_id},{question_id}",
        },
        files=[
            ("images", ("small.png", BytesIO(small_data), "image/png")),
            ("images", ("big.png", BytesIO(big_data), "image/png")),
        ],
        headers=headers,
    )
    assert resp.status_code == 413


async def test_upload_normal_size_passes(client, upload_setup):
    """正常大小文件（< 10MB）应返回 201。"""
    headers, exam_id, subject_id, question_id = upload_setup
    normal_data = PNG_HEADER + b"x" * 1024
    resp = await client.post(
        "/api/v1/scan/upload",
        data={
            "exam_id": exam_id,
            "subject_id": subject_id,
            "student_id": "S003",
            "question_id": question_id,
        },
        files={"image": ("ok.png", BytesIO(normal_data), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 201


async def test_upload_exact_limit_passes(client, upload_setup):
    """恰好等于 10MB 的文件应通过（检查条件是 > 而非 >=）。"""
    headers, exam_id, subject_id, question_id = upload_setup
    exact_data = PNG_HEADER + b"x" * (10 * 1024 * 1024 - len(PNG_HEADER))
    resp = await client.post(
        "/api/v1/scan/upload",
        data={
            "exam_id": exam_id,
            "subject_id": subject_id,
            "student_id": "S004",
            "question_id": question_id,
        },
        files={"image": ("exact.png", BytesIO(exact_data), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 201
