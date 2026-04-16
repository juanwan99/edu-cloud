import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_client(client: AsyncClient, db):
    """插入菜单种子后返回 client（F014 R4: 真实种入 report + principal-only contrast 子菜单）"""
    from edu_cloud.modules.menu.models import MenuConfig

    exam = MenuConfig(
        code="exam", name="阅卷", icon="document", sort=1,
        roles=["subject_teacher", "academic_director", "principal"],
        is_active=True,
    )
    db.add(exam)
    await db.flush()
    db.add(MenuConfig(
        code="exam_list", name="考试列表", icon="list", sort=1,
        parent_id=exam.id, path="/exam/list",
        roles=["subject_teacher", "academic_director", "principal"],
        is_active=True,
    ))

    report = MenuConfig(
        code="report", name="分析", icon="data-analysis", sort=2,
        roles=["subject_teacher", "principal"],
        is_active=True,
    )
    db.add(report)
    await db.flush()
    db.add(MenuConfig(
        code="report_exam", name="考试报告", icon="document", sort=1,
        parent_id=report.id, path="/report/exam",
        roles=["subject_teacher", "principal"],
        is_active=True,
    ))
    db.add(MenuConfig(
        code="report_contrast", name="班级对比", icon="histogram", sort=2,
        parent_id=report.id, path="/report/contrast",
        roles=["principal"],
        is_active=True,
    ))
    await db.commit()
    return client


class TestMenuAPI:
    async def test_get_menus_unauthenticated(self, client: AsyncClient):
        """未登录 → 401"""
        resp = await client.get("/api/v1/menus")
        assert resp.status_code in (401, 403)

    async def test_get_menus_subject_teacher(
        self, seeded_client: AsyncClient, subject_teacher_headers: dict
    ):
        """F003 (R2): subject_teacher 应看到 exam，不应看到 principal-only contrast 子菜单"""
        resp = await seeded_client.get("/api/v1/menus", headers=subject_teacher_headers)
        assert resp.status_code == 200
        data = resp.json()
        menus = data["menus"]
        codes = [m["code"] for m in menus]
        assert "exam" in codes, f"subject_teacher 应看到 exam 模块，实际: {codes}"
        assert "report" in codes, f"subject_teacher 应看到 report 模块，实际: {codes}"
        report = next(m for m in menus if m["code"] == "report")
        child_paths = [c["path"] for c in report["children"]]
        assert "/report/contrast" not in child_paths, \
            f"subject_teacher 不应看到 principal-only 的 contrast 子菜单，实际 children: {child_paths}"

    async def test_get_menus_platform_admin_structure(
        self, seeded_client: AsyncClient, admin_headers: dict
    ):
        """F003 (R2): platform_admin 不在种子 roles 中，应返回空菜单（fail-closed 语义）"""
        resp = await seeded_client.get("/api/v1/menus", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "menus" in data
        assert isinstance(data["menus"], list)
        assert data["menus"] == [], \
            f"platform_admin 不在种子 roles 中，应返回空菜单，实际: {data['menus']}"
