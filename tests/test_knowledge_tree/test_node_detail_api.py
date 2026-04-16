"""节点详情服务测试。"""
import sqlite3
import pytest


def test_node_detail_missing_db():
    """knowledge.db 不存在时返回空结构。"""
    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    result = get_node_detail("FAKE_NODE", knowledge_db_path="/nonexistent.db")
    assert result["concept"]["id"] == "FAKE_NODE"
    assert result["curriculum"] == []
    assert result["das"] == []
    assert result["questions"] == {}


def test_node_detail_with_fixture(tmp_path):
    """F005: 用 SQLite fixture 验证 json_each 精确匹配（无宿主依赖）。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE curriculum_requirements (id TEXT PRIMARY KEY, document_id TEXT, module_id TEXT, big_concept TEXT, text TEXT, source_page INTEGER, requirement_type TEXT)")
    conn.execute("CREATE TABLE seed_req_da_map (req_id TEXT, da_id TEXT, confidence REAL, source TEXT)")
    conn.execute("CREATE TABLE content_blocks (id TEXT PRIMARY KEY, section_id TEXT, content TEXT)")
    conn.execute("CREATE TABLE sections (id TEXT PRIMARY KEY, title TEXT, document_id TEXT)")
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, type TEXT)")
    conn.execute("CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT, transfer_band TEXT, required INT)")
    conn.execute("CREATE TABLE assessment_items (id TEXT PRIMARY KEY, stem TEXT, answer TEXT, question_type TEXT)")
    conn.execute("INSERT INTO concepts VALUES ('NODE_A','TestA','L1','desc')")
    conn.execute("""INSERT INTO diagnostic_attributes VALUES ('da_1','DA1','["NODE_A"]','["can id"]','[]','[]','[]','d')""")
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    result = get_node_detail("NODE_A", knowledge_db_path=db_path)
    assert result["concept"]["name"] == "TestA"
    assert len(result["das"]) == 1
    assert result["das"][0]["da_id"] == "da_1"


def test_node_detail_pg_fallback():
    """F004: knowledge.db 不存在时保留 PG 节点信息。"""
    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    pg = {"id": "X", "name": "PG Name", "level": "L1", "module": "M1"}
    result = get_node_detail("X", pg_node=pg, knowledge_db_path="/no.db")
    assert result["concept"]["name"] == "PG Name"  # PG 数据保留，不丢失


def test_node_detail_evidence(tmp_path):
    """节点详情包含 evidence 段。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT, evidence_ids_json TEXT)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE curriculum_requirements (id TEXT PRIMARY KEY, document_id TEXT, module_id TEXT, big_concept TEXT, text TEXT, source_page INTEGER, requirement_type TEXT)")
    conn.execute("CREATE TABLE seed_req_da_map (req_id TEXT, da_id TEXT, confidence REAL, source TEXT)")
    conn.execute("CREATE TABLE content_blocks (id TEXT PRIMARY KEY, section_id TEXT, content TEXT)")
    conn.execute("CREATE TABLE sections (id TEXT PRIMARY KEY, title TEXT, document_id TEXT)")
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, type TEXT)")
    conn.execute("CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT, transfer_band TEXT, required INT)")
    conn.execute("CREATE TABLE assessment_items (id TEXT PRIMARY KEY, stem TEXT, answer TEXT, question_type TEXT)")
    conn.execute("""INSERT INTO concepts VALUES ('NODE_A','TestA','L1','desc','["EV_1","EV_2"]')""")
    conn.execute("INSERT INTO concepts VALUES ('EV_1','证据事实1','evidence','e1', NULL)")
    conn.execute("INSERT INTO concepts VALUES ('EV_2','证据事实2','evidence','e2', NULL)")
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    result = get_node_detail("NODE_A", knowledge_db_path=db_path)
    assert len(result["evidence"]) == 2
    texts = {e["text"] for e in result["evidence"]}
    assert "证据事实1" in texts
    assert "证据事实2" in texts


def test_node_detail_evidence_empty(tmp_path):
    """evidence_ids_json 为 NULL → evidence 段为空列表。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT, evidence_ids_json TEXT)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE curriculum_requirements (id TEXT PRIMARY KEY, document_id TEXT, module_id TEXT, big_concept TEXT, text TEXT, source_page INTEGER, requirement_type TEXT)")
    conn.execute("CREATE TABLE seed_req_da_map (req_id TEXT, da_id TEXT, confidence REAL, source TEXT)")
    conn.execute("CREATE TABLE content_blocks (id TEXT PRIMARY KEY, section_id TEXT, content TEXT)")
    conn.execute("CREATE TABLE sections (id TEXT PRIMARY KEY, title TEXT, document_id TEXT)")
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, type TEXT)")
    conn.execute("CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT, transfer_band TEXT, required INT)")
    conn.execute("CREATE TABLE assessment_items (id TEXT PRIMARY KEY, stem TEXT, answer TEXT, question_type TEXT)")
    conn.execute("INSERT INTO concepts VALUES ('NODE_A','TestA','L1','desc', NULL)")
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    result = get_node_detail("NODE_A", knowledge_db_path=db_path)
    assert result["evidence"] == []


def test_node_detail_evidence_missing_ids(tmp_path):
    """evidence_ids_json 引用不存在的 ID → 跳过该 ID。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT, evidence_ids_json TEXT)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE curriculum_requirements (id TEXT PRIMARY KEY, document_id TEXT, module_id TEXT, big_concept TEXT, text TEXT, source_page INTEGER, requirement_type TEXT)")
    conn.execute("CREATE TABLE seed_req_da_map (req_id TEXT, da_id TEXT, confidence REAL, source TEXT)")
    conn.execute("CREATE TABLE content_blocks (id TEXT PRIMARY KEY, section_id TEXT, content TEXT)")
    conn.execute("CREATE TABLE sections (id TEXT PRIMARY KEY, title TEXT, document_id TEXT)")
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, type TEXT)")
    conn.execute("CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT, transfer_band TEXT, required INT)")
    conn.execute("CREATE TABLE assessment_items (id TEXT PRIMARY KEY, stem TEXT, answer TEXT, question_type TEXT)")
    conn.execute("""INSERT INTO concepts VALUES ('NODE_A','TestA','L1','desc','["NONEXISTENT"]')""")
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    result = get_node_detail("NODE_A", knowledge_db_path=db_path)
    assert result["evidence"] == []


def test_node_detail_no_prefix_collision(tmp_path):
    """F004 反例: NODE_A 不应匹配到 NODE_AB 的 DA（json_each 精确匹配验证）。"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE curriculum_requirements (id TEXT PRIMARY KEY, document_id TEXT, module_id TEXT, big_concept TEXT, text TEXT, source_page INTEGER, requirement_type TEXT)")
    conn.execute("CREATE TABLE seed_req_da_map (req_id TEXT, da_id TEXT, confidence REAL, source TEXT)")
    conn.execute("CREATE TABLE content_blocks (id TEXT PRIMARY KEY, section_id TEXT, content TEXT)")
    conn.execute("CREATE TABLE sections (id TEXT PRIMARY KEY, title TEXT, document_id TEXT)")
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, type TEXT)")
    conn.execute("CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT, transfer_band TEXT, required INT)")
    conn.execute("CREATE TABLE assessment_items (id TEXT PRIMARY KEY, stem TEXT, answer TEXT, question_type TEXT)")
    # NODE_A 和 NODE_AB 是不同概念
    conn.execute("INSERT INTO concepts VALUES ('NODE_A','TestA','L1','d')")
    conn.execute("INSERT INTO concepts VALUES ('NODE_AB','TestAB','L1','d')")
    # DA 只关联 NODE_AB，不关联 NODE_A
    conn.execute("""INSERT INTO diagnostic_attributes VALUES ('da_ab','DA_AB','["NODE_AB"]','["x"]','[]','[]','[]','d')""")
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    # 查 NODE_A 不应返回 NODE_AB 的 DA（LIKE '%NODE_A%' 会错误匹配）
    result = get_node_detail("NODE_A", knowledge_db_path=db_path)
    assert len(result["das"]) == 0, f"NODE_A should have 0 DAs, got {len(result['das'])} (prefix collision!)"
