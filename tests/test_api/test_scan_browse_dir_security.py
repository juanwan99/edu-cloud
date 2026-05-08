"""browse-dir 目录遍历安全测试 (N-C03)。"""

import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def grading_admin_user(db):
    user = User(username="grading_admin_test", display_name="Grading Admin")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", is_primary=True))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def grading_admin_headers(grading_admin_user):
    token = create_access_token({"sub": grading_admin_user.id, "role": "academic_director"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_browse_dir_rejects_absolute_path(client, grading_admin_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "/etc"},
        headers=grading_admin_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_dir_rejects_traversal(client, grading_admin_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "../../../etc"},
        headers=grading_admin_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_dir_default_upload_dir(client, admin_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={},
        headers=admin_headers,
    )
    # 默认应该返回 200（UPLOAD_DIR 存在时）或 400（不存在时，测试环境）
    assert resp.status_code in (200, 400)
    assert resp.status_code != 403  # 不应被权限拦截


@pytest.mark.asyncio
async def test_browse_dir_relative_path_within_upload(client, grading_admin_headers, tmp_path, monkeypatch):
    """相对路径在 UPLOAD_DIR 内 -> 200。"""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    subdir = upload_root / "scan-input"
    subdir.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "scan-input"},
        headers=grading_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == "scan-input"
    assert data["parent"] == "."


@pytest.mark.asyncio
async def test_browse_dir_returns_relative_paths(client, grading_admin_headers, tmp_path, monkeypatch):
    """返回的 item path 和 current 应该是相对路径，不暴露服务器结构。"""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    child = upload_root / "exam1"
    child.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={},
        headers=grading_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == "."
    # item paths 不应包含系统绝对路径
    for item in data["items"]:
        assert not item["path"].startswith("/"), f"path should be relative: {item['path']}"
