from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import get_current_user
from edu_cloud.database import get_db
from edu_cloud.modules.menu.service import MenuService
from edu_cloud.services.school_settings_service import get_enabled_modules

router = APIRouter(prefix="/api/v1/menus", tags=["menus"])


@router.get("")
async def get_menus(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户角色可见的菜单树"""
    menu_service = MenuService(db)

    current_role = user["current_role"]
    role = current_role.role
    school_id = current_role.school_id

    enabled_modules = None
    if school_id:
        enabled_modules = await get_enabled_modules(db, school_id=school_id)

    menus = await menu_service.get_menus_for_user(
        role=role,
        enabled_modules=enabled_modules,
    )
    return {"menus": menus}
