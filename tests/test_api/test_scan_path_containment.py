"""scan 端点路径遍历安全测试 — scan-dir / start / pdf-import / import-tpl / scan-image。

补充 test_scan_browse_dir_security.py（仅覆盖 browse-dir），
确保所有文件路径入口都限制在 UPLOAD_DIR 内。
"""

import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def scan_auth(db):
    """Create an academic_director with school_id for tenant-aware scan tests (T1/D1).

    Returns dict with 'headers' and 'school_id'.
    """
    from edu_cloud.models.school import School
    school = School(name="扫描路径测试校", code="SCANP", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="scan_path_test", display_name="Scan Path Tester")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="academic_director",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    await db.refresh(user)
    token = create_access_token({
        "sub": user.id, "role": "academic_director",
        "school_id": school.id,
    })
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
    }


@pytest.fixture
async def grading_headers(scan_auth):
    """Backward-compatible alias — returns just the headers dict."""
    return scan_auth["headers"]


# ---------- scan-dir ----------

@pytest.mark.asyncio
async def test_scan_dir_rejects_absolute_path(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/scan-dir",
        json={"dir_path": "/etc"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scan_dir_rejects_traversal(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/scan-dir",
        json={"dir_path": "../../../etc"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scan_dir_accepts_valid_subdir(client, scan_auth, tmp_path, monkeypatch):
    """D1-R2: scan-dir path must be under school_id subdir for non-admin."""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    # Place scan dir under school_id for tenant isolation
    scan_dir = upload_root / scan_auth["school_id"] / "scan-input" / "exam1" / "yuwen"
    scan_dir.mkdir(parents=True)
    (scan_dir / "001A.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.post(
        "/api/v1/scan/pipeline/scan-dir",
        json={"dir_path": str(scan_dir)},
        headers=scan_auth["headers"],
    )
    assert resp.status_code in (200, 400)
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_scan_dir_rejects_other_school(client, scan_auth, tmp_path, monkeypatch):
    """T1-R3: scan-dir with path under another school's dir → 403."""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    other_school = upload_root / "other-school-id" / "scan-input"
    other_school.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.post(
        "/api/v1/scan/pipeline/scan-dir",
        json={"dir_path": str(other_school)},
        headers=scan_auth["headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_start_rejects_other_school(client, scan_auth, tmp_path, monkeypatch):
    """T1-R3: start with image_dir under another school → 403."""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    other_dir = upload_root / "other-school-id" / "images"
    other_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.post(
        "/api/v1/scan/pipeline/start",
        json={
            "image_dir": str(other_dir),
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "side": "A",
        },
        headers=scan_auth["headers"],
    )
    assert resp.status_code == 403


# ---------- start ----------

@pytest.mark.asyncio
async def test_start_rejects_absolute_path(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/start",
        json={
            "image_dir": "/etc",
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "side": "A",
        },
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_start_rejects_traversal(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/start",
        json={
            "image_dir": "../../../etc",
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "side": "A",
        },
        headers=grading_headers,
    )
    assert resp.status_code == 403


# ---------- pdf-import ----------

@pytest.mark.asyncio
async def test_pdf_import_rejects_absolute_path(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/pdf-import",
        json={"dir_path": "/etc"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pdf_import_rejects_traversal(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/pdf-import",
        json={"dir_path": "../../etc"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


# ---------- import-tpl ----------

@pytest.mark.asyncio
async def test_import_tpl_rejects_absolute_path(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/import-tpl",
        json={
            "tpl_path": "/etc/passwd",
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "side": "A",
        },
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_tpl_rejects_traversal(client, grading_headers):
    resp = await client.post(
        "/api/v1/scan/pipeline/import-tpl",
        json={
            "tpl_path": "../../../etc/passwd",
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "side": "A",
        },
        headers=grading_headers,
    )
    assert resp.status_code == 403


# ---------- scan-image ----------

@pytest.mark.asyncio
async def test_scan_image_rejects_absolute_path(client, grading_headers):
    resp = await client.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": "/etc/passwd"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scan_image_rejects_traversal(client, grading_headers):
    resp = await client.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": "../../../etc/passwd"},
        headers=grading_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scan_image_accepts_valid_file(client, scan_auth, tmp_path, monkeypatch):
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    # D1: file must be under UPLOAD_DIR/{school_id}/ for tenant isolation
    school_dir = upload_root / scan_auth["school_id"]
    school_dir.mkdir(parents=True)
    img = school_dir / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": f"{scan_auth['school_id']}/test.png"},
        headers=scan_auth["headers"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_scan_image_uploads_prefix_stripped(client, scan_auth, tmp_path, monkeypatch):
    """路径以 /uploads/ 开头时，前缀应被剥离后在 UPLOAD_DIR 内查找。"""
    from edu_cloud.config import settings

    upload_root = tmp_path / "uploads"
    # D1: file must be under UPLOAD_DIR/{school_id}/ for tenant isolation
    school_dir = upload_root / scan_auth["school_id"]
    school_dir.mkdir(parents=True)
    img = school_dir / "scan.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

    resp = await client.get(
        "/api/v1/scan/pipeline/scan-image",
        params={"path": f"/uploads/{scan_auth['school_id']}/scan.jpg"},
        headers=scan_auth["headers"],
    )
    assert resp.status_code == 200
