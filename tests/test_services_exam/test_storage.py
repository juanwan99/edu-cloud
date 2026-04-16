import os
import pytest
from edu_cloud.shared.storage import StorageService


@pytest.fixture
def storage(tmp_path):
    return StorageService(root=str(tmp_path))


def test_build_path(storage):
    path = storage.build_path(
        school_id="s1", exam_id="e1", subject_id="sub1", question_id="q1", student_id="stu001"
    )
    assert path.endswith("s1/e1/sub1/q1/stu001.png") or path.endswith("s1\\e1\\sub1\\q1\\stu001.png")


async def test_save_file(storage):
    content = b"fake png data"
    path = await storage.save(
        school_id="s1", exam_id="e1", subject_id="sub1",
        question_id="q1", student_id="stu001", data=content,
    )
    assert os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read() == content


async def test_save_file_overwrite(storage):
    await storage.save(school_id="s1", exam_id="e1", subject_id="sub1", question_id="q1", student_id="stu001", data=b"v1")
    path = await storage.save(school_id="s1", exam_id="e1", subject_id="sub1", question_id="q1", student_id="stu001", data=b"v2")
    with open(path, "rb") as f:
        assert f.read() == b"v2"


def test_path_traversal_rejected(storage):
    with pytest.raises(ValueError, match="Invalid path component"):
        storage.build_path(school_id="s1", exam_id="../escape", subject_id="sub1", question_id="q1", student_id="stu001")


def test_absolute_path_rejected(storage):
    with pytest.raises(ValueError, match="Invalid path component"):
        storage.build_path(school_id="s1", exam_id="/tmp/evil", subject_id="sub1", question_id="q1", student_id="stu001")
