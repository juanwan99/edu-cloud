"""Backfill conduct module rows for existing schools (2026-04-13).

背景：conduct 模块加入 MODULE_CODES 时，DEFAULT_ENABLED 未同步，
init_school_modules idempotent 跳过已存在 school 的 module 初始化，
导致已建学校（如育才中学、株洲二中枫溪）school_modules 表缺 conduct 行，
前端 sidebar 按 moduleCode='conduct' 过滤 → 9 个德育菜单全被隐藏。

本脚本对所有现存学校执行：
  - 若 conduct 行不存在 → 插入 enabled=True
  - 若已存在但 enabled=False → 升级为 enabled=True
  - 若已 enabled=True → 跳过

幂等：可重复运行。

Usage:
    cd C:/Users/Administrator/edu-cloud
    python scripts/backfill_conduct_module.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import select
from edu_cloud.database import async_session
from edu_cloud.models.school import School
from edu_cloud.models.school_settings import SchoolModule


async def backfill():
    async with async_session() as db:
        schools = (await db.execute(select(School))).scalars().all()
        inserted = enabled = skipped = 0

        for school in schools:
            existing = (await db.execute(
                select(SchoolModule).where(
                    SchoolModule.school_id == school.id,
                    SchoolModule.module_code == "conduct",
                )
            )).scalar_one_or_none()

            if existing is None:
                db.add(SchoolModule(
                    school_id=school.id,
                    module_code="conduct",
                    enabled=True,
                ))
                inserted += 1
                print(f"  [插入] {school.name} ({school.id[:8]}) conduct enabled=True")
            elif not existing.enabled:
                existing.enabled = True
                enabled += 1
                print(f"  [启用] {school.name} ({school.id[:8]}) conduct False → True")
            else:
                skipped += 1
                print(f"  [跳过] {school.name} ({school.id[:8]}) conduct 已 enabled")

        await db.commit()
        print(f"\n汇总: schools={len(schools)}, 插入={inserted}, 升级={enabled}, 跳过={skipped}")


if __name__ == "__main__":
    asyncio.run(backfill())
