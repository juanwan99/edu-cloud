import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.menu.models import MenuConfig
from edu_cloud.modules.menu.service import MenuService


@pytest.fixture
async def menu_service(db: AsyncSession):
    return MenuService(db)


@pytest.fixture
async def seed_menus(db: AsyncSession):
    """插入测试菜单数据：2 个顶级模块，各 2 个子菜单"""
    exam = MenuConfig(
        code="exam", name="阅卷", icon="document", sort=1,
        roles=["teacher", "academic_director", "principal"],
        is_active=True,
    )
    db.add(exam)
    await db.flush()

    db.add_all([
        MenuConfig(
            code="exam_list", name="考试列表", icon="list", sort=1,
            parent_id=exam.id, path="/exam/list",
            roles=["teacher", "academic_director", "principal"],
            is_active=True,
        ),
        MenuConfig(
            code="exam_quiz", name="测验列表", icon="edit-pen", sort=2,
            parent_id=exam.id, path="/exam/quiz",
            roles=["teacher", "academic_director"],
            is_active=True,
        ),
    ])

    report = MenuConfig(
        code="report", name="分析", icon="data-analysis", sort=2,
        roles=["teacher", "principal", "grade_leader"],
        is_active=True,
    )
    db.add(report)
    await db.flush()

    db.add_all([
        MenuConfig(
            code="report_exam", name="考试报告", icon="document", sort=1,
            parent_id=report.id, path="/report/exam",
            roles=["teacher", "principal", "grade_leader"],
            is_active=True,
        ),
        MenuConfig(
            code="report_contrast", name="班级对比", icon="histogram", sort=2,
            parent_id=report.id, path="/report/contrast",
            roles=["principal", "grade_leader"],
            is_active=True,
        ),
    ])
    await db.commit()
    return {"exam_id": exam.id, "report_id": report.id}


class TestMenuService:
    async def test_get_menus_for_teacher(self, menu_service, seed_menus):
        """teacher 角色应看到阅卷+分析模块"""
        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=None
        )
        assert len(menus) == 2
        assert menus[0]["code"] == "exam"
        assert len(menus[0]["children"]) == 2
        assert menus[1]["code"] == "report"
        assert len(menus[1]["children"]) == 1

    async def test_get_menus_for_principal(self, menu_service, seed_menus):
        """principal 角色应看到全部子菜单"""
        menus = await menu_service.get_menus_for_user(
            role="principal", enabled_modules=None
        )
        report_menu = next(m for m in menus if m["code"] == "report")
        assert len(report_menu["children"]) == 2

    async def test_module_filter(self, menu_service, seed_menus):
        """requires_module 过滤：模块未启用的菜单不显示"""
        from sqlalchemy import update
        await menu_service.session.execute(
            update(MenuConfig).where(MenuConfig.code == "exam").values(requires_module="exam")
        )
        await menu_service.session.commit()

        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=["report"]
        )
        assert len(menus) == 1
        assert menus[0]["code"] == "report"

    async def test_inactive_menu_hidden(self, menu_service, seed_menus):
        """is_active=False 的菜单不显示"""
        from sqlalchemy import update
        await menu_service.session.execute(
            update(MenuConfig).where(MenuConfig.code == "exam").values(is_active=False)
        )
        await menu_service.session.commit()

        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=None
        )
        assert all(m["code"] != "exam" for m in menus)

    async def test_empty_role_returns_empty(self, menu_service, seed_menus):
        """不匹配任何角色 → 空菜单"""
        menus = await menu_service.get_menus_for_user(
            role="parent", enabled_modules=None
        )
        assert len(menus) == 0

    async def test_sorted_by_sort_field(self, menu_service, db: AsyncSession):
        """菜单按 sort 字段排序（顶级 + 子菜单）— 乱序插入也能正确排序。

        F003 R1 处置：原实现用 seed_menus fixture（顺序插入）+ 弱断言
        (`menus[0]["sort"] < menus[1]["sort"]`)。若 service 删除 `.order_by(MenuConfig.sort)`，
        SQLite 默认会保持插入顺序，测试依然通过——是典型的"测试只能捕获实现镜像"。

        修复：
        1. fixture 按 sort 逆序插入（先 sort=2 的 report、再 sort=1 的 exam；子菜单同理）
        2. 断言精确顺序列表，而非成对比较
        3. 同时覆盖顶级和子菜单的 sort 排序
        """
        # 乱序插入（顶级 + 子菜单均先插大 sort 值，再插小 sort 值）
        report = MenuConfig(
            code="report", name="分析", icon="data-analysis", sort=2,
            roles=["principal"],
            is_active=True,
        )
        db.add(report)
        await db.flush()
        # 先插 sort=2 的 report_contrast，再插 sort=1 的 report_exam
        db.add_all([
            MenuConfig(
                code="report_contrast", name="班级对比", icon="histogram", sort=2,
                parent_id=report.id, path="/report/contrast",
                roles=["principal"], is_active=True,
            ),
            MenuConfig(
                code="report_exam", name="考试报告", icon="document", sort=1,
                parent_id=report.id, path="/report/exam",
                roles=["principal"], is_active=True,
            ),
        ])

        exam = MenuConfig(
            code="exam", name="阅卷", icon="document", sort=1,
            roles=["principal"],
            is_active=True,
        )
        db.add(exam)
        await db.flush()
        # 先插 sort=2 的 exam_quiz，再插 sort=1 的 exam_list
        db.add_all([
            MenuConfig(
                code="exam_quiz", name="测验列表", icon="edit-pen", sort=2,
                parent_id=exam.id, path="/exam/quiz",
                roles=["principal"], is_active=True,
            ),
            MenuConfig(
                code="exam_list", name="考试列表", icon="list", sort=1,
                parent_id=exam.id, path="/exam/list",
                roles=["principal"], is_active=True,
            ),
        ])
        await db.commit()

        menus = await menu_service.get_menus_for_user(
            role="principal", enabled_modules=None
        )

        # 顶级精确顺序：exam (sort=1) → report (sort=2)
        assert [m["code"] for m in menus] == ["exam", "report"]

        # exam 子菜单精确顺序：exam_list (sort=1) → exam_quiz (sort=2)
        assert [c["path"] for c in menus[0]["children"]] == ["/exam/list", "/exam/quiz"]

        # report 子菜单精确顺序：report_exam (sort=1) → report_contrast (sort=2)
        assert [c["path"] for c in menus[1]["children"]] == ["/report/exam", "/report/contrast"]
