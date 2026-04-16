import json
import sqlite3
from datetime import datetime, timezone, timedelta

TZ_CN = timezone(timedelta(hours=8))


def build_da_catalog_from_knowledge_db(conn: sqlite3.Connection) -> list[dict]:
    """从 knowledge.db 读取 DA 目录。

    Returns: [{da_id, name, module, concept_ids, study_unit_ids}]
    """
    rows = conn.execute("""
        SELECT da.id, da.name, da.linked_concept_ids, su_agg.study_unit_ids
        FROM diagnostic_attributes da
        LEFT JOIN (
            SELECT json_each.value AS da_id,
                   json_group_array(su.id) AS study_unit_ids
            FROM study_units su, json_each(su.linked_da_ids)
            GROUP BY json_each.value
        ) su_agg ON su_agg.da_id = da.id
    """).fetchall()

    catalog = []
    for da_id, name, concept_ids_json, su_ids_json in rows:
        concept_ids = json.loads(concept_ids_json) if concept_ids_json else []
        study_unit_ids = json.loads(su_ids_json) if su_ids_json else []

        # 从 concept_id 推断 module（取第一个概念的 M 前缀）
        module = None
        for cid in concept_ids:
            parts = cid.split("_")
            for p in parts:
                if p.startswith("M") and len(p) == 2 and p[1].isdigit():
                    module = p
                    break
            if module:
                break

        catalog.append({
            "da_id": da_id,
            "name": name,
            "module": module,
            "concept_ids": concept_ids,
            "study_unit_ids": study_unit_ids,
        })

    return catalog


async def sync_da_catalog(knowledge_db_path: str, db: "AsyncSession") -> int:
    """同步 DA 目录快照到 edu-cloud，实际 upsert 到 da_catalog_snapshot。

    Args:
        knowledge_db_path: knowledge.db 文件路��
        db: edu-cloud 的异步 DB session

    Returns: 同步的 DA 数量
    """
    from sqlalchemy import select
    from edu_cloud.modules.adaptive.models import DaCatalogSnapshot

    conn = sqlite3.connect(knowledge_db_path)
    try:
        catalog = build_da_catalog_from_knowledge_db(conn)
    finally:
        conn.close()

    now = datetime.now(TZ_CN)
    count = 0
    for item in catalog:
        stmt = select(DaCatalogSnapshot).where(DaCatalogSnapshot.da_id == item["da_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.name = item["name"]
            existing.module = item["module"]
            existing.concept_ids = item["concept_ids"]
            existing.study_unit_ids = item["study_unit_ids"]
            existing.synced_at = now
        else:
            snapshot = DaCatalogSnapshot(
                da_id=item["da_id"],
                name=item["name"],
                module=item["module"],
                concept_ids=item["concept_ids"],
                study_unit_ids=item["study_unit_ids"],
                synced_at=now,
            )
            db.add(snapshot)
        count += 1

    await db.flush()  # F002: 不 commit，由调用方统一提交
    return count


async def sync_da_kp_map(knowledge_db_path: str, db: "AsyncSession") -> int:
    """从 knowledge.db 同步 DA → 知识点映射到 DaKnowledgePointMap。

    每个 DA 的 linked_concept_ids 展开为 (da_id, concept_id) 行。
    """
    from sqlalchemy import delete
    from edu_cloud.modules.adaptive.models import DaKnowledgePointMap

    conn = sqlite3.connect(knowledge_db_path)
    try:
        catalog = build_da_catalog_from_knowledge_db(conn)
    finally:
        conn.close()

    # 全量替换
    await db.execute(delete(DaKnowledgePointMap))

    count = 0
    for item in catalog:
        for concept_id in (item.get("concept_ids") or []):
            db.add(DaKnowledgePointMap(
                da_id=item["da_id"],
                knowledge_point_id=concept_id,
                weight=1.0,
            ))
            count += 1

    # 不 commit — 由 sync_knowledge_on_startup 统一提交（F002 单事务）
    await db.flush()
    return count
