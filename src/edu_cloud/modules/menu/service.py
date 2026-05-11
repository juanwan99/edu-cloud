import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.menu.models import MenuConfig

logger = logging.getLogger(__name__)


class MenuService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_menus_for_user(
        self,
        role: str,
        enabled_modules: Optional[list[str] | set[str]],
    ) -> list[dict]:
        """返回当前角色可见的菜单树。

        Args:
            role: 用户当前角色
            enabled_modules: 学校已启用的模块列表/集合，None 表示不过滤
        """
        logger.debug("get_menus_for_user: role=%s, enabled_modules=%s", role, enabled_modules)
        # Single query: fetch all active menus, assemble tree in Python (O(n))
        stmt = (
            select(MenuConfig)
            .where(MenuConfig.is_active.is_(True))
            .order_by(MenuConfig.parent_id, MenuConfig.sort)
        )
        result = await self.session.execute(stmt)
        all_menus = result.scalars().all()

        top_menus: list[MenuConfig] = []
        children_by_parent: dict[int, list[MenuConfig]] = {}
        for item in all_menus:
            if item.parent_id is None:
                top_menus.append(item)
            else:
                children_by_parent.setdefault(item.parent_id, []).append(item)

        menus = []
        for menu in top_menus:
            if role not in (menu.roles or []):
                continue
            if menu.requires_module and enabled_modules is not None:
                if menu.requires_module not in enabled_modules:
                    continue

            children = []
            for child in children_by_parent.get(menu.id, []):
                if role not in (child.roles or []):
                    continue
                children.append({
                    "name": child.name,
                    "path": child.path,
                    "icon": child.icon,
                })

            if children:
                menus.append({
                    "code": menu.code,
                    "name": menu.name,
                    "icon": menu.icon,
                    "sort": menu.sort,
                    "children": children,
                })

        return menus
