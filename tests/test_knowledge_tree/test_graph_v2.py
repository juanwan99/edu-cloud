"""Graph API v2 响应增强测试。"""
import pytest


@pytest.mark.asyncio
async def test_node_includes_description(client, db, seed_graph_v2):
    """node 响应包含 description。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    assert resp.status_code == 200
    nodes = resp.json()["graph"]["nodes"]
    assert len(nodes) > 0
    node = next(n for n in nodes if n["id"] == "TEST_M1_A")
    assert node["description"] == "测试概念A描述"


@pytest.mark.asyncio
async def test_node_hard_counts(client, db, seed_graph_v2):
    """node 的 hard_in_count/hard_out_count 精确（基于全量 edge，含跨模块）。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    # TEST_M1_A → TEST_M1_B (hard), TEST_M1_A → TEST_M1_C (hard), TEST_M1_A → TEST_M2_X (hard,跨模块)
    node_a = next(n for n in nodes if n["id"] == "TEST_M1_A")
    assert node_a["hard_out_count"] == 3  # 含跨模块边
    assert node_a["hard_in_count"] == 0
    node_b = next(n for n in nodes if n["id"] == "TEST_M1_B")
    assert node_b["hard_in_count"] == 1
    assert node_b["hard_out_count"] == 0


@pytest.mark.asyncio
async def test_edge_includes_confidence_and_review(client, db, seed_graph_v2):
    """edge 响应包含 confidence 和 review_status。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all",
                            headers=seed_graph_v2["auth_headers"])
    edges = resp.json()["graph"]["edges"]
    assert len(edges) > 0
    edge = edges[0]
    assert "confidence" in edge
    assert "review_status" in edge
    assert isinstance(edge["confidence"], float)


@pytest.mark.asyncio
async def test_external_hard_refs_with_module_filter(client, db, seed_graph_v2):
    """module 过滤时 external_hard_refs 包含跨模块对端。"""
    # seed_graph_v2 含跨模块边: TEST_M1_A → TEST_M2_X (hard)
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    node_a = next(n for n in nodes if n["id"] == "TEST_M1_A")
    refs = node_a["external_hard_refs"]
    assert refs is not None
    assert len(refs["out"]) == 1
    assert refs["out"][0]["module"] == "M2"


@pytest.mark.asyncio
async def test_external_hard_refs_empty_without_module_filter(client, db, seed_graph_v2):
    """module=all 时 external_hard_refs 为 None。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    for n in nodes:
        assert n["external_hard_refs"] is None
