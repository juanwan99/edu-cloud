"""render-doc-pages 端点测试。"""
import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def auth_headers(db):
    """创建认证用户，返回 headers。"""
    school = School(id="s1", name="测试学校", code="TEST01")
    db.add(school)
    await db.commit()

    user = User(id="u1", username="testuser", display_name="测试用户")
    user.set_password("123456")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id="s1", is_primary=True))
    await db.flush()

    token = create_access_token({"sub": "u1", "school_id": "s1", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


class TestRenderDocPages:
    """POST /api/v1/card/render-doc-pages 测试。"""

    async def test_reject_unsupported_format(self, client: AsyncClient, auth_headers):
        """拒绝非 docx/pdf 文件。"""
        resp = await client.post(
            "/api/v1/card/render-doc-pages",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "仅支持" in resp.json()["detail"]

    async def test_reject_unauthenticated(self, client: AsyncClient):
        """未认证请求返回 401。"""
        resp = await client.post(
            "/api/v1/card/render-doc-pages",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code in (401, 403)

    async def test_render_pdf_pages(self, client: AsyncClient, auth_headers, tmp_path):
        """正常 PDF 文件渲染为页面图片。"""
        import fitz
        # Create a minimal 2-page PDF
        doc = fitz.open()
        for i in range(2):
            page = doc.new_page(width=595, height=842)  # A4
            page.insert_text((72, 72), f"Page {i + 1}", fontsize=24)
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        with open(pdf_path, "rb") as f:
            resp = await client.post(
                "/api/v1/card/render-doc-pages",
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "pages" in data
        assert len(data["pages"]) == 2

        for i, page in enumerate(data["pages"], start=1):
            assert page["page_num"] == i
            assert page["image_url"].startswith("/uploads/doc-pages/")
            assert page["image_url"].endswith(f"page_{i}.png")
            assert page["width"] > 0
            assert page["height"] > 0

    async def test_corrupt_file_returns_400_for_empty(self, client: AsyncClient, auth_headers):
        """空内容文件返回 400（pymupdf 无法打开）。"""
        # pymupdf cannot save a 0-page PDF, so we send minimal invalid bytes
        resp = await client.post(
            "/api/v1/card/render-doc-pages",
            files={"file": ("empty.pdf", b"%PDF-1.0\n", "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_corrupt_pdf_returns_400(self, client: AsyncClient, auth_headers):
        """损坏的 PDF 返回 400。"""
        resp = await client.post(
            "/api/v1/card/render-doc-pages",
            files={"file": ("bad.pdf", b"not a real pdf", "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_docx_fallback_message(self, client: AsyncClient, auth_headers):
        """无法打开的 docx 返回友好提示。"""
        resp = await client.post(
            "/api/v1/card/render-doc-pages",
            files={"file": ("test.docx", b"not a real docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "转换为 PDF" in resp.json()["detail"]

    async def test_url_contains_uuid_dir(self, client: AsyncClient, auth_headers, tmp_path):
        """返回的 URL 包含 uuid 目录。"""
        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        with open(pdf_path, "rb") as f:
            resp = await client.post(
                "/api/v1/card/render-doc-pages",
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        url = resp.json()["pages"][0]["image_url"]
        # URL format: /uploads/doc-pages/{32-char-hex-uuid}/page_1.png
        parts = url.split("/")
        assert parts[1] == "uploads"
        assert parts[2] == "doc-pages"
        assert len(parts[3]) == 32  # uuid4().hex is 32 hex chars
        assert parts[4] == "page_1.png"
