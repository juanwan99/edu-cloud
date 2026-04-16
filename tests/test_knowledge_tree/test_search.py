"""知识点搜索 API 测试。"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode


async def _seed_search_data(db):
    now = datetime.now()
    db.add_all([
        ConceptGraphNode(
            id="CP_M1_A", name="细胞学说", knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
            aliases_json='["细胞学说三要点"]', description="施莱登和施旺创立",
        ),
        ConceptGraphNode(
            id="CP_M1_B", name="ATP合成", knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
            aliases_json=None, description="三磷酸腺苷",
        ),
        ConceptGraphNode(
            id="CP_M2_C", name="质膜结构", knowledge_level="L1",
            primary_module="M2", node_type="concept", synced_at=now,
            aliases_json='["细胞膜", "生物膜"]', description="流动镶嵌模型",
        ),
        # BigConcept（不应被搜索到）
        ConceptGraphNode(
            id="BC_M1_C1", name="细胞是基本单位", knowledge_level="L1",
            primary_module="M1", node_type="big_concept", synced_at=now,
        ),
    ])
    await db.commit()


@pytest.mark.asyncio
async def test_search_by_name(db):
    await _seed_search_data(db)
    from edu_cloud.modules.knowledge_tree.service import search_concepts
    results = await search_concepts(db, "细胞学说")
    assert len(results) == 1
    assert results[0]["id"] == "CP_M1_A"


@pytest.mark.asyncio
async def test_search_by_alias(db):
    await _seed_search_data(db)
    from edu_cloud.modules.knowledge_tree.service import search_concepts
    results = await search_concepts(db, "细胞膜")
    assert len(results) == 1
    assert results[0]["id"] == "CP_M2_C"


@pytest.mark.asyncio
async def test_search_by_description(db):
    """R3-F005: 搜索 description 字段。"""
    await _seed_search_data(db)
    from edu_cloud.modules.knowledge_tree.service import search_concepts
    results = await search_concepts(db, "施莱登")
    assert len(results) == 1
    assert results[0]["id"] == "CP_M1_A"


@pytest.mark.asyncio
async def test_search_excludes_big_concepts(db):
    """搜索只返回 concept 节点。"""
    await _seed_search_data(db)
    from edu_cloud.modules.knowledge_tree.service import search_concepts
    results = await search_concepts(db, "细胞")
    ids = {r["id"] for r in results}
    assert "BC_M1_C1" not in ids, "BigConcept should not appear in search results"
    # 细胞学说 + 质膜(别名含"细胞膜")
    assert "CP_M1_A" in ids


@pytest.mark.asyncio
async def test_search_no_match(db):
    await _seed_search_data(db)
    from edu_cloud.modules.knowledge_tree.service import search_concepts
    results = await search_concepts(db, "不存在的概念")
    assert results == []


@pytest.mark.asyncio
async def test_search_api_endpoint(client, db, admin_headers):
    await _seed_search_data(db)
    resp = await client.get("/api/v1/knowledge-tree/search?q=质膜", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "CP_M2_C"


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    resp = await client.get("/api/v1/knowledge-tree/search?q=test")
    assert resp.status_code in (401, 403)
