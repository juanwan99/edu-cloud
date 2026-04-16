"""knowledge.db → PostgreSQL 概念图谱投影同步脚本。

用法:
    python scripts/sync_concept_graph.py [--knowledge-db PATH]

默认 knowledge.db 路径: ~/edu-knowledge-base/knowledge.db
"""

import argparse
import re
import sqlite3
import sys
import asyncio
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge


DEFAULT_KNOWLEDGE_DB = Path.home() / "edu-knowledge-base" / "knowledge.db"

_MODULE_RE = re.compile(r"_M(\d+)_")


def extract_module(concept_id: str) -> str:
    """从概念 ID 提取模块编号。e.g. BIO_SR_CP_M1_ATP → M1"""
    m = _MODULE_RE.search(concept_id)
    return f"M{m.group(1)}" if m else "unknown"


def read_knowledge_db(db_path: str) -> tuple[list[dict], list[dict]]:
    """读取 knowledge.db 的 concepts 和 concept_relations。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    nodes = []
    for row in conn.execute("SELECT id, name, knowledge_level, description FROM concepts"):
        nodes.append({
            "id": row["id"],
            "name": row["name"],
            "knowledge_level": row["knowledge_level"],
            "primary_module": extract_module(row["id"]),
            "description": row["description"],
        })

    edges = []
    for row in conn.execute(
        "SELECT source_id, target_id, relation_type, strength, confidence FROM concept_relations"
    ):
        edges.append({
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "relation_type": row["relation_type"],
            "strength": row["strength"] or 1.0,
            "confidence": row["confidence"] or 1.0,
        })

    conn.close()
    return nodes, edges


async def sync_to_postgres(db: AsyncSession, nodes: list[dict], edges: list[dict]):
    """全量替换 PostgreSQL 中的概念图谱数据。"""
    now = datetime.now()

    # 先删边再删节点（FK 约束）
    await db.execute(sa.delete(ConceptGraphEdge))
    await db.execute(sa.delete(ConceptGraphNode))

    # 插入节点
    for n in nodes:
        db.add(ConceptGraphNode(
            id=n["id"],
            name=n["name"],
            knowledge_level=n["knowledge_level"],
            primary_module=n["primary_module"],
            description=n["description"],
            synced_at=now,
        ))

    await db.flush()

    # 插入边
    for e in edges:
        db.add(ConceptGraphEdge(
            source_id=e["source_id"],
            target_id=e["target_id"],
            relation_type=e["relation_type"],
            strength=e["strength"],
            confidence=e["confidence"],
            synced_at=now,
        ))

    await db.commit()


async def main(knowledge_db_path: str, database_url: str):
    """CLI 入口。"""
    print(f"Reading from {knowledge_db_path} ...")
    nodes, edges = read_knowledge_db(knowledge_db_path)
    print(f"  {len(nodes)} nodes, {len(edges)} edges")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        await sync_to_postgres(db, nodes, edges)

    await engine.dispose()
    print("Sync complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync knowledge graph to PostgreSQL")
    parser.add_argument(
        "--knowledge-db",
        default=str(DEFAULT_KNOWLEDGE_DB),
        help="Path to knowledge.db",
    )
    parser.add_argument(
        "--database-url",
        default="postgresql+asyncpg://localhost/edu_cloud",
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()
    asyncio.run(main(args.knowledge_db, args.database_url))
