"""扫描流水线 API 测试。"""
import pytest
from PIL import Image
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def scan_seed(client, db, tmp_path):
    """创建扫描测试种子数据 + 假扫描目录。"""
    school = School(id="scan_s1", name="扫描测试校", code="SCAN01")
    db.add(school)
    await db.flush()

    user = User(id="scan_u1", username="scan_user", display_name="扫描用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id="scan_u1", role="principal", school_id="scan_s1", is_primary=True))
    await db.commit()

    exam = Exam(id="scan_e1", name="扫描测试考试", school_id="scan_s1")
    db.add(exam)
    await db.flush()

    subject = Subject(id="scan_sub1", exam_id="scan_e1", name="地理", code="DL", school_id="scan_s1")
    db.add(subject)
    await db.commit()

    # 创建假扫描图
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    for i in range(3):
        img = Image.new("RGB", (200, 150), (240, 240, 240))
        img.save(scan_dir / f"STU{i + 1:03d}A.png")

    token = create_access_token({"sub": "scan_u1", "role": "principal", "active_role_id": "dummy"})
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "headers": headers,
        "scan_dir": str(scan_dir),
        "subject_id": "scan_sub1",
        "exam_id": "scan_e1",
    }


class TestPipelineProgress:
    async def test_progress_idle(self, client, scan_seed):
        resp = await client.get("/api/v1/scan/pipeline/progress", headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("idle", "completed")

    async def test_start_no_template(self, client, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": scan_seed["scan_dir"],
        }, headers=scan_seed["headers"])
        assert resp.status_code == 404
        assert "模板不存在" in resp.json()["detail"]

    async def test_start_nonexistent_dir(self, client, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": "/nonexistent/dir",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 400


class TestImportTpl:
    @pytest.mark.skipif(
        not __import__("os").path.exists(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl"),
        reason="Real tpl file not available",
    )
    async def test_import_real_tpl(self, client, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/import-tpl", json={
            "tpl_path": r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl",
            "subject_id": scan_seed["subject_id"],
            "side": "A",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["regions"] == 14  # 10 subjective + 4 choice_groups
        assert data["anchors"] == 4
