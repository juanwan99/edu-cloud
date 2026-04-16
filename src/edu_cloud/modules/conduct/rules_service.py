"""班规管理业务逻辑"""
import logging

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.conduct.models import ConductRuleCategory, ConductRuleItem
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def get_rules(db: AsyncSession, class_id: str) -> list[dict]:
    """Get nested categories + items for a class."""
    categories = (
        await db.execute(
            select(ConductRuleCategory)
            .where(ConductRuleCategory.class_id == class_id)
            .order_by(ConductRuleCategory.sort_order, ConductRuleCategory.name)
        )
    ).scalars().all()

    result = []
    for cat in categories:
        items = (
            await db.execute(
                select(ConductRuleItem)
                .where(ConductRuleItem.category_id == cat.id)
                .order_by(ConductRuleItem.sort_order, ConductRuleItem.name)
            )
        ).scalars().all()

        result.append({
            "id": cat.id,
            "name": cat.name,
            "sort_order": cat.sort_order,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "points": item.points,
                    "sort_order": item.sort_order,
                }
                for item in items
            ],
        })

    return result


async def create_category(
    db: AsyncSession, class_id: str, name: str, sort_order: int = 0,
) -> dict:
    """Create a rule category for a class."""
    cat = ConductRuleCategory(
        class_id=class_id,
        name=name,
        scope="class",
        sort_order=sort_order,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "sort_order": cat.sort_order}


async def update_category(
    db: AsyncSession, category_id: str, name: str | None = None, sort_order: int | None = None,
) -> dict:
    """Update a rule category."""
    cat = await db.get(ConductRuleCategory, category_id)
    if not cat:
        raise NotFoundError("班规分类不存在")
    if name is not None:
        cat.name = name
    if sort_order is not None:
        cat.sort_order = sort_order
    await db.commit()
    await db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "sort_order": cat.sort_order}


async def delete_category(db: AsyncSession, category_id: str) -> dict:
    """Delete a category and all its items."""
    cat = await db.get(ConductRuleCategory, category_id)
    if not cat:
        raise NotFoundError("班规分类不存在")
    # Cascade delete items
    await db.execute(
        delete(ConductRuleItem).where(ConductRuleItem.category_id == category_id)
    )
    await db.delete(cat)
    await db.commit()
    return {"deleted": True}


async def create_item(
    db: AsyncSession, category_id: str, name: str, points: int, sort_order: int = 0,
) -> dict:
    """Create a rule item under a category."""
    cat = await db.get(ConductRuleCategory, category_id)
    if not cat:
        raise NotFoundError("班规分类不存在")
    item = ConductRuleItem(
        category_id=category_id,
        name=name,
        points=points,
        sort_order=sort_order,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "points": item.points,
        "sort_order": item.sort_order,
        "category_id": item.category_id,
    }


async def update_item(
    db: AsyncSession, item_id: str, name: str | None = None,
    points: int | None = None, sort_order: int | None = None,
) -> dict:
    """Update a rule item."""
    item = await db.get(ConductRuleItem, item_id)
    if not item:
        raise NotFoundError("班规条目不存在")
    if name is not None:
        item.name = name
    if points is not None:
        item.points = points
    if sort_order is not None:
        item.sort_order = sort_order
    await db.commit()
    await db.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "points": item.points,
        "sort_order": item.sort_order,
        "category_id": item.category_id,
    }


async def delete_item(db: AsyncSession, item_id: str) -> dict:
    """Delete a rule item."""
    item = await db.get(ConductRuleItem, item_id)
    if not item:
        raise NotFoundError("班规条目不存在")
    await db.delete(item)
    await db.commit()
    return {"deleted": True}
