import pytest
from edu_cloud.knowledge.store import KnowledgeStore

@pytest.fixture
def store():
    s = KnowledgeStore()
    s._curriculum = {
        "modules": [
            {"id": "mod:bio_sr:required_1", "name": "分子与细胞", "academic_requirements": [
                {"id": "req:bio_sr:001", "text": "概述细胞学说的建立过程"},
                {"id": "req:bio_sr:014", "text": "阐明基因表达的过程"},
            ]},
        ],
        "core_competencies": [
            {"id": "comp:bio_sr:life_concept", "name": "生命观念", "description": "对生命现象及相互关系的理解"},
        ],
    }
    s._l0_blocks = [
        {"id": "BK_001", "content": "细胞学说的建立者是施莱登和施旺", "category": "structure_fact", "module": "M1"},
        {"id": "BK_002", "content": "基因表达包括转录和翻译两个过程", "category": "process", "module": "M1"},
        {"id": "BK_003", "content": "DNA 双螺旋结构由沃森和克里克提出", "category": "structure_fact", "module": "M2"},
    ]
    s._l1_concepts = [
        {"id": "CP_001", "canonical_name": "细胞学说", "description": "所有生物都由细胞组成", "l0_ids": ["BK_001"], "module": "M1"},
        {"id": "CP_002", "canonical_name": "基因表达", "description": "DNA→RNA→蛋白质", "l0_ids": ["BK_002"], "module": "M1"},
    ]
    s._gaokao_index = [
        {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8},
        {"exam_id": "GK_2023_JS", "year": 2023, "region": "江苏", "question_count": 10},
    ]
    s._loaded = True
    return s

def test_search_curriculum(store):
    results = store.search_curriculum("基因表达")
    assert len(results) >= 1
    assert any("基因表达" in r["text"] for r in results)

def test_search_curriculum_no_match(store):
    results = store.search_curriculum("量子力学")
    assert len(results) == 0

def test_search_knowledge(store):
    results = store.search_knowledge("细胞学说")
    assert len(results) >= 1
    assert any("细胞学说" in r["content"] for r in results)

def test_get_concept(store):
    concept = store.get_concept("基因表达")
    assert concept is not None
    assert concept["canonical_name"] == "基因表达"

def test_get_concept_not_found(store):
    concept = store.get_concept("不存在的概念")
    assert concept is None

def test_search_gaokao(store):
    results = store.search_gaokao(year=2024)
    assert len(results) >= 1
    assert results[0]["year"] == 2024

def test_search_gaokao_by_region(store):
    results = store.search_gaokao(region="北京")
    assert len(results) >= 1

def test_store_stats(store):
    stats = store.stats()
    assert stats["l0_count"] == 3
    assert stats["l1_count"] == 2
    assert stats["gaokao_count"] == 2


def test_search_curriculum_big_concept(store):
    """T3: 搜索命中 big_concepts"""
    store._curriculum["modules"][0]["big_concepts"] = ["细胞是生命的基本单位"]
    results = store.search_curriculum("基本单位")
    assert len(results) >= 1
    assert any(r["type"] == "big_concept" for r in results)


def test_search_curriculum_content_requirement(store):
    """T3: 搜索命中 content_requirements"""
    store._curriculum["modules"][0]["content_requirements"] = [
        {"id": "cr1", "text": "理解光合作用的过程"}
    ]
    results = store.search_curriculum("光合作用")
    assert len(results) >= 1
    assert any(r["type"] == "content_requirement" for r in results)


def test_search_curriculum_module_fallback(store):
    """T3: 搜索命中 module 兜底（模块名包含关键词但其他字段不包含）"""
    store._curriculum["modules"].append({
        "id": "mod:bio_sr:m2", "name": "遗传与进化",
        "academic_requirements": [], "big_concepts": [],
        "hidden_field": "基因突变的类型与效应",
    })
    results = store.search_curriculum("基因突变")
    assert len(results) >= 1
    assert any(r["type"] == "module_match" for r in results)


def test_search_curriculum_core_competency(store):
    """T3: 搜索命中核心素养"""
    results = store.search_curriculum("生命观念")
    assert len(results) >= 1
    assert any(r["type"] == "core_competency" for r in results)


def test_get_concept_partial_match(store):
    """T3: 概念部分匹配"""
    concept = store.get_concept("基因")
    assert concept is not None
    assert "基因表达" in concept["canonical_name"]


def test_get_concept_alias(store):
    """T3: 概念别名匹配"""
    store._l1_concepts[0]["aliases"] = ["细胞理论", "cell theory"]
    concept = store.get_concept("细胞理论")
    assert concept is not None
    assert concept["canonical_name"] == "细胞学说"
