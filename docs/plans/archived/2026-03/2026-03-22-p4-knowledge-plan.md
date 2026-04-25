<!-- pre-takeover: archived for history, not active spec -->
# P4 知识深度实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 能引用课标/教材/高考真题回答教学问题，教师能通过 Studio 发起论文写作。

**Architecture:** 知识库 JSON 文件启动时加载到内存索引（KnowledgeStore），AI Agent 通过 L3 工具查询。paper-skill 通过 httpx 调用其 REST API 创建论文任务，进度回显到 Studio。

**Tech Stack:** Python dict/list 内存索引（不引入向量库），httpx (paper-skill API client)

**Design Doc:** `docs/plans/2026-03-21-super-platform-design.md` §5 L3 工具 + §9 P4

**P2 基础:** 186 tests, AI Agent (ReAct + L1 + L4), Studio (文档 CRUD + 模板 + 审批)

**完成标志:** (1) 教师问"课标对基因表达有什么要求" → AI 引用课标原文回答 (2) 教师点"论文" → paper-skill 创建任务 → Studio 显示进度

**知识库路径:** `C:\Users\Administrator\edu-knowledge-base\subjects\biology_senior\`

---

## 文件结构

### 新增文件

```
src/edu_cloud/
├── knowledge/
│   ├── __init__.py
│   ├── store.py              # KnowledgeStore — 内存索引（课标+L0+L1+高考）
│   └── loader.py             # JSON 加载器（启动时从文件系统读取）
├── ai/tools/
│   └── knowledge.py          # L3 知识查询工具（4个）
└── services/
    └── paper_service.py      # paper-skill API 客户端

frontend/src/components/studio/
└── PaperStatus.vue           # 论文进度卡片
```

### 修改文件

```
src/edu_cloud/config.py               # 知识库路径 + paper-skill URL 配置
src/edu_cloud/api/app.py              # 启动时加载知识库
src/edu_cloud/ai/agent.py             # ROLE_TOOL_CATEGORIES 添加 L3
src/edu_cloud/ai/tools/__init__.py    # 导入 knowledge 工具
src/edu_cloud/api/studio.py           # 论文创建端点
src/edu_cloud/templates/document_templates.py  # 添加论文模板
frontend/src/components/studio/StudioPanel.vue # 论文进度显示
frontend/src/stores/studio.js         # 论文状态轮询
```

### 测试文件

```
tests/
├── test_knowledge/
│   ├── test_store.py         # 内存索引加载+查询测试
│   └── test_loader.py        # JSON 加载测试（含 tmp_path 自包含测试）
├── test_ai/
│   └── test_tools_knowledge.py  # L3 工具测试
├── test_api/
│   └── test_paper_api.py     # 论文端点 API 集成测试（权限+创建+状态）
└── test_services/
    └── test_paper_service.py # paper-skill 客户端测试（mock httpx）
```

---

## Task 1: 知识库加载与内存索引

**Files:**
- Create: `src/edu_cloud/knowledge/__init__.py`, `src/edu_cloud/knowledge/loader.py`, `src/edu_cloud/knowledge/store.py`
- Modify: `src/edu_cloud/config.py`
- Test: `tests/test_knowledge/test_store.py`, `tests/test_knowledge/test_loader.py`

- [ ] **Step 1: 添加知识库配置**

```python
# src/edu_cloud/config.py — 追加
    # Knowledge base
    KNOWLEDGE_BASE_DIR: str = "C:/Users/Administrator/edu-knowledge-base/subjects/biology_senior"
    KNOWLEDGE_ENABLED: bool = True
```

- [ ] **Step 2: 写加载器测试**

```python
# tests/test_knowledge/test_loader.py
import pytest
import json
from edu_cloud.knowledge.loader import load_curriculum, load_l0_blocks, load_l1_concepts, load_gaokao_index


class TestLoaderWithTmpPath:
    """自包含测试，使用 tmp_path fixture 构造测试数据，不依赖绝对路径"""

    def test_load_curriculum_from_tmp(self, tmp_path):
        """加载课标 JSON"""
        curriculum_dir = tmp_path / "curriculum"
        curriculum_dir.mkdir()
        (curriculum_dir / "bio_senior_2025.json").write_text(json.dumps({
            "modules": [
                {"id": "m1", "name": "分子与细胞", "academic_requirements": [
                    {"id": "r1", "text": "测试学业要求"}
                ], "big_concepts": ["细胞是生命的基本单位"]},
            ],
            "core_competencies": [
                {"id": "c1", "name": "生命观念", "description": "测试素养"}
            ],
        }), encoding="utf-8")
        data = load_curriculum(str(tmp_path))
        assert "modules" in data
        assert "core_competencies" in data
        assert len(data["modules"]) == 1
        assert data["modules"][0]["name"] == "分子与细胞"

    def test_load_curriculum_missing_dir(self, tmp_path):
        """课标文件不存在 → 返回空默认值"""
        data = load_curriculum(str(tmp_path))
        assert data["modules"] == []

    def test_load_curriculum_bad_json(self, tmp_path):
        """课标 JSON 损坏 → 返回空默认值"""
        curriculum_dir = tmp_path / "curriculum"
        curriculum_dir.mkdir()
        (curriculum_dir / "bio_senior_2025.json").write_text("NOT VALID JSON{{{", encoding="utf-8")
        data = load_curriculum(str(tmp_path))
        assert data["modules"] == []

    def test_load_l0_blocks_from_tmp(self, tmp_path):
        """加载 L0 知识块"""
        l0_dir = tmp_path / "skeleton" / "L0"
        l0_dir.mkdir(parents=True)
        (l0_dir / "B01_L0.json").write_text(json.dumps([
            {"id": "BK_001", "content": "细胞学说", "category": "fact", "module": "M1"},
            {"id": "BK_002", "content": "DNA 双螺旋", "category": "fact", "module": "M1"},
        ]), encoding="utf-8")
        blocks = load_l0_blocks(str(tmp_path))
        assert len(blocks) == 2
        assert blocks[0]["id"] == "BK_001"

    def test_load_l0_blocks_bad_file_skipped(self, tmp_path):
        """L0 单个坏文件不影响其他文件加载"""
        l0_dir = tmp_path / "skeleton" / "L0"
        l0_dir.mkdir(parents=True)
        (l0_dir / "B01_L0.json").write_text("BAD JSON", encoding="utf-8")
        (l0_dir / "B02_L0.json").write_text(json.dumps([
            {"id": "BK_003", "content": "good block"}
        ]), encoding="utf-8")
        blocks = load_l0_blocks(str(tmp_path))
        assert len(blocks) == 1  # 只加载了好文件

    def test_load_l1_concepts_from_tmp(self, tmp_path):
        """加载 L1 概念"""
        l1_dir = tmp_path / "skeleton" / "L1"
        l1_dir.mkdir(parents=True)
        (l1_dir / "M01_concepts.json").write_text(json.dumps([
            {"id": "CP_001", "canonical_name": "细胞学说", "l0_ids": ["BK_001"]},
        ]), encoding="utf-8")
        concepts = load_l1_concepts(str(tmp_path))
        assert len(concepts) == 1
        assert concepts[0]["canonical_name"] == "细胞学说"

    def test_load_gaokao_index_object_wrapper(self, tmp_path):
        """高考索引 index.json 为 {exams: [...]} 格式"""
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text(json.dumps({
            "total_exams": 2,
            "exams": [
                {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8},
                {"exam_id": "GK_2023_JS", "year": 2023, "region": "江苏", "question_count": 10},
            ]
        }), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 2
        assert exams[0]["exam_id"] == "GK_2024_BJ"

    def test_load_gaokao_index_plain_list(self, tmp_path):
        """高考索引 index.json 为直接 [...] 格式"""
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text(json.dumps([
            {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8},
        ]), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 1

    def test_load_gaokao_fallback_exam_dirs(self, tmp_path):
        """无 index.json 时从 exams/ 目录扫描"""
        exams_dir = tmp_path / "gaokao" / "exams" / "GK_2024_BJ"
        exams_dir.mkdir(parents=True)
        (exams_dir / "exam.json").write_text(json.dumps({
            "exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "questions": [1, 2, 3]
        }), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 1
        assert exams[0]["question_count"] == 3

    def test_load_gaokao_bad_index_json(self, tmp_path):
        """index.json 损坏 → 返回空列表"""
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text("INVALID", encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert exams == []
```

- [ ] **Step 3: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge/test_loader.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: 实现 loader.py**

```python
# src/edu_cloud/knowledge/loader.py
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_curriculum(base_dir: str) -> dict:
    """加载课标 JSON"""
    path = Path(base_dir) / "curriculum" / "bio_senior_2025.json"
    if not path.exists():
        logger.warning(f"Curriculum file not found: {path}")
        return {"modules": [], "core_competencies": [], "quality_levels": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to load curriculum {path}: {e}")
        return {"modules": [], "core_competencies": [], "quality_levels": []}

def load_l0_blocks(base_dir: str) -> list[dict]:
    """加载所有 L0 知识块"""
    l0_dir = Path(base_dir) / "skeleton" / "L0"
    blocks = []
    if not l0_dir.exists():
        return blocks
    for f in sorted(l0_dir.glob("B*_L0.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    blocks.extend(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load {f}: {e}")
            continue
    logger.info(f"Loaded {len(blocks)} L0 blocks")
    return blocks

def load_l1_concepts(base_dir: str) -> list[dict]:
    """加载所有 L1 概念"""
    l1_dir = Path(base_dir) / "skeleton" / "L1"
    concepts = []
    if not l1_dir.exists():
        return concepts
    for f in sorted(l1_dir.glob("M*_concepts.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    concepts.extend(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load {f}: {e}")
            continue
    logger.info(f"Loaded {len(concepts)} L1 concepts")
    return concepts

def load_gaokao_index(base_dir: str) -> list[dict]:
    """加载高考题索引（不加载完整题目，按需加载）"""
    index_path = Path(base_dir) / "gaokao" / "index.json"
    if not index_path.exists():
        # fallback: 扫描 exams/ 目录
        exams_dir = Path(base_dir) / "gaokao" / "exams"
        if not exams_dir.exists():
            return []
        exams = []
        for d in sorted(exams_dir.iterdir()):
            if d.is_dir() and (d / "exam.json").exists():
                try:
                    with open(d / "exam.json", encoding="utf-8") as fh:
                        exam = json.load(fh)
                        exams.append({
                            "exam_id": exam.get("exam_id", d.name),
                            "year": exam.get("year"),
                            "region": exam.get("region"),
                            "question_count": exam.get("question_count", len(exam.get("questions", []))),
                        })
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to load {d / 'exam.json'}: {e}")
                    continue
        return exams

    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
            # index.json 可能是 {total_exams, exams: [...]} 包装或直接 [...]
            return data.get("exams", data) if isinstance(data, dict) else data
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to load gaokao index {index_path}: {e}")
        return []
```

- [ ] **Step 5: 运行 loader 测试**

Run: `python -m pytest tests/test_knowledge/test_loader.py -v`
Expected: PASS (或 skip 如果知识库不在本机)

- [ ] **Step 6: 写 KnowledgeStore 测试**

```python
# tests/test_knowledge/test_store.py
import pytest
from edu_cloud.knowledge.store import KnowledgeStore

@pytest.fixture
def store():
    """创建带测试数据的 KnowledgeStore"""
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
    """搜索课标内容"""
    results = store.search_curriculum("基因表达")
    assert len(results) >= 1
    assert any("基因表达" in r["text"] for r in results)

def test_search_curriculum_no_match(store):
    """搜索不存在的关键词"""
    results = store.search_curriculum("量子力学")
    assert len(results) == 0

def test_search_knowledge(store):
    """搜索知识块"""
    results = store.search_knowledge("细胞学说")
    assert len(results) >= 1
    assert any("细胞学说" in r["content"] for r in results)

def test_get_concept(store):
    """获取概念详情"""
    concept = store.get_concept("基因表达")
    assert concept is not None
    assert concept["canonical_name"] == "基因表达"

def test_get_concept_not_found(store):
    """概念不存在"""
    concept = store.get_concept("不存在的概念")
    assert concept is None

def test_search_gaokao(store):
    """搜索高考题"""
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
```

- [ ] **Step 7: 实现 store.py**

```python
# src/edu_cloud/knowledge/store.py
import logging
from edu_cloud.knowledge.loader import load_curriculum, load_l0_blocks, load_l1_concepts, load_gaokao_index

logger = logging.getLogger(__name__)

class KnowledgeStore:
    """知识库内存索引。启动时加载，全局单例。"""

    def __init__(self):
        self._curriculum: dict = {}
        self._l0_blocks: list[dict] = []
        self._l1_concepts: list[dict] = []
        self._gaokao_index: list[dict] = []
        self._loaded = False

    def load(self, base_dir: str):
        """从文件系统加载所有知识数据到内存"""
        logger.info(f"Loading knowledge base from {base_dir}")
        self._curriculum = load_curriculum(base_dir)
        self._l0_blocks = load_l0_blocks(base_dir)
        self._l1_concepts = load_l1_concepts(base_dir)
        self._gaokao_index = load_gaokao_index(base_dir)
        self._loaded = True
        logger.info(f"Knowledge base loaded: {self.stats()}")

    def search_curriculum(self, keyword: str, limit: int = 10) -> list[dict]:
        """搜索课标内容（学业要求、大概念、嵌套文本字段）"""
        import json as _json
        results = []
        for module in self._curriculum.get("modules", []):
            module_matched = False
            # 搜索学业要求（主要匹配源）
            for req in module.get("academic_requirements", []):
                if keyword in req.get("text", ""):
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "requirement_id": req.get("id", ""),
                        "text": req["text"],
                        "type": "academic_requirement",
                    })
                    module_matched = True
            # 搜索大概念（big_concepts）
            for concept in module.get("big_concepts", []):
                if keyword in str(concept):
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": str(concept),
                        "type": "big_concept",
                    })
                    module_matched = True
            # 搜索内容要求（content_requirements）
            for creq in module.get("content_requirements", []):
                if keyword in str(creq):
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": str(creq),
                        "type": "content_requirement",
                    })
                    module_matched = True
            # 兜底：如果上面都没命中，递归搜整个 module JSON 文本
            if not module_matched:
                module_text = _json.dumps(module, ensure_ascii=False)
                if keyword in module_text:
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": f"模块 {module.get('name')} 包含相关内容",
                        "type": "module_match",
                    })
        # 搜索核心素养
        for comp in self._curriculum.get("core_competencies", []):
            if keyword in comp.get("description", "") or keyword in comp.get("name", ""):
                results.append({
                    "module": "核心素养",
                    "requirement_id": comp.get("id", ""),
                    "text": f"{comp['name']}: {comp.get('description', '')}",
                    "type": "core_competency",
                })
        return results[:limit]

    def search_knowledge(self, keyword: str, limit: int = 20) -> list[dict]:
        """搜索 L0 知识块"""
        results = []
        for block in self._l0_blocks:
            if keyword in block.get("content", ""):
                results.append(block)
        return results[:limit]

    def get_concept(self, name: str) -> dict | None:
        """按名称获取 L1 概念"""
        for concept in self._l1_concepts:
            if concept.get("canonical_name") == name:
                return concept
            if name in concept.get("aliases", []):
                return concept
            if name in concept.get("canonical_name", ""):
                return concept
        return None

    def search_gaokao(self, year: int | None = None, region: str | None = None, limit: int = 20) -> list[dict]:
        """搜索高考题索引"""
        results = []
        for exam in self._gaokao_index:
            if year and exam.get("year") != year:
                continue
            if region and region not in exam.get("region", ""):
                continue
            results.append(exam)
        return results[:limit]

    def stats(self) -> dict:
        return {
            "loaded": self._loaded,
            "curriculum_modules": len(self._curriculum.get("modules", [])),
            "l0_count": len(self._l0_blocks),
            "l1_count": len(self._l1_concepts),
            "gaokao_count": len(self._gaokao_index),
        }


# 全局单例
knowledge_store = KnowledgeStore()
```

- [ ] **Step 8: 运行测试**

Run: `python -m pytest tests/test_knowledge/ -v`
Expected: PASS (8+ tests)

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/knowledge/ src/edu_cloud/config.py tests/test_knowledge/
git commit -m "feat(P4-1): 知识库加载与内存索引 — 课标+L0+L1+高考题"
```

**审查清单:**
- ✓ 加载器读取真实 JSON 文件（课标/L0/L1/高考）
- ✓ KnowledgeStore 支持关键词搜索（课标/知识块/概念/高考）
- ✓ 全局单例 knowledge_store
- ✓ 文件不存在时返回空结果而非崩溃
- ✓ JSON 解析错误时 try/except 捕获，单文件 skip + warning（不中断整体加载）
- ✓ gaokao index.json 兼容 `{exams:[...]}` 对象包装和直接 `[...]` 两种格式
- ✓ search_curriculum 搜索 academic_requirements + big_concepts + content_requirements + 兜底 module JSON
- ✗ 不应引入向量库（YAGNI）

**边界条件:**
- 知识库目录不存在 → 期望: 空索引，不崩溃
- 搜索关键词无匹配 → 期望: 空列表
- JSON 文件格式错误 → 期望: 跳过该文件，记录 warning（loader try/except）
- gaokao index.json 为 object 而非 list → 期望: 正确取 `exams` 字段
- L0/L1 目录中混有坏文件 → 期望: 跳过坏文件，加载其余好文件

**测试契约:**
1. 知识库搜索准确性
   - 入口: `store.search_curriculum("基因表达")`
   - 反例: 错误实现可能全文匹配失败或返回无关结果
   - 边界: 空关键词 / 无匹配 / 匹配多条
   - 回归: N/A
   - 命令: `python -m pytest tests/test_knowledge/test_store.py -v`
2. loader 自包含测试（JSON 解析错误容错 + index.json 格式兼容）
   - 入口: `load_curriculum(tmp_path)` / `load_gaokao_index(tmp_path)`
   - 反例: 无 try/except 时一个坏文件导致整体加载失败；index.json 为 object 时返回 dict 而非 list
   - 边界: 空目录 / 损坏 JSON / object 包装 / plain list / fallback 目录扫描
   - 回归: F1(index.json object wrapper) + F2(JSON 错误处理)
   - 命令: `python -m pytest tests/test_knowledge/test_loader.py -v`

---

## Task 2: L3 知识查询工具

**Files:**
- Create: `src/edu_cloud/ai/tools/knowledge.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`, `src/edu_cloud/ai/agent.py`
- Test: `tests/test_ai/test_tools_knowledge.py`

- [ ] **Step 1: 写 L3 工具测试**

```python
# tests/test_ai/test_tools_knowledge.py
import pytest
from unittest.mock import patch, MagicMock
from edu_cloud.ai.tools.knowledge import search_curriculum, search_textbook, search_gaokao, get_concept_info

@pytest.fixture
def mock_store():
    """Mock KnowledgeStore"""
    store = MagicMock()
    store.search_curriculum.return_value = [
        {"module": "分子与细胞", "text": "阐明基因表达的过程", "requirement_id": "req:001"}
    ]
    store.search_knowledge.return_value = [
        {"id": "BK_002", "content": "基因表达包括转录和翻译", "category": "process"}
    ]
    store.get_concept.return_value = {
        "canonical_name": "基因表达",
        "description": "DNA→RNA→蛋白质",
        "l0_ids": ["BK_002"],
    }
    store.search_gaokao.return_value = [
        {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8}
    ]
    return store

@pytest.mark.asyncio
async def test_search_curriculum_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_curriculum(keyword="基因表达")
        assert len(result["results"]) >= 1
        assert "基因表达" in result["results"][0]["text"]

@pytest.mark.asyncio
async def test_search_textbook_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_textbook(keyword="基因表达")
        assert len(result["blocks"]) >= 1

@pytest.mark.asyncio
async def test_get_concept_info_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await get_concept_info(concept_name="基因表达")
        assert result["concept"]["canonical_name"] == "基因表达"

@pytest.mark.asyncio
async def test_get_concept_not_found(mock_store):
    mock_store.get_concept.return_value = None
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await get_concept_info(concept_name="不存在")
        assert "error" in result

@pytest.mark.asyncio
async def test_search_gaokao_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_gaokao(year=2024)
        assert len(result["exams"]) >= 1
        assert result["exams"][0]["year"] == 2024

@pytest.mark.asyncio
async def test_search_gaokao_no_filter(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_gaokao()
        assert "exams" in result
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ai/test_tools_knowledge.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 L3 工具**

```python
# src/edu_cloud/ai/tools/knowledge.py
from edu_cloud.ai.registry import tools
from edu_cloud.knowledge.store import knowledge_store

@tools.register(
    name="search_curriculum",
    description="搜索课程标准（课标）内容。输入关键词，返回匹配的学业要求和核心素养描述。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词，如'基因表达'、'细胞分裂'"},
        },
        "required": ["keyword"],
    },
    category="L3_knowledge",
)
async def search_curriculum(keyword: str) -> dict:
    results = knowledge_store.search_curriculum(keyword)
    return {"keyword": keyword, "results": results, "count": len(results)}


@tools.register(
    name="search_textbook",
    description="搜索教材内容（知识块）。输入关键词，返回匹配的教材段落和知识分类。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["keyword"],
    },
    category="L3_knowledge",
)
async def search_textbook(keyword: str) -> dict:
    blocks = knowledge_store.search_knowledge(keyword)
    return {"keyword": keyword, "blocks": blocks, "count": len(blocks)}


@tools.register(
    name="get_concept_info",
    description="获取某个生物学概念的详细信息，包括定义、关联知识块、所属模块。",
    parameters={
        "type": "object",
        "properties": {
            "concept_name": {"type": "string", "description": "概念名称，如'细胞学说'、'基因表达'"},
        },
        "required": ["concept_name"],
    },
    category="L3_knowledge",
)
async def get_concept_info(concept_name: str) -> dict:
    concept = knowledge_store.get_concept(concept_name)
    if not concept:
        return {"error": f"未找到概念: {concept_name}"}
    return {"concept": concept}


@tools.register(
    name="search_gaokao",
    description="搜索高考真题。可按年份或地区筛选，返回考试列表。",
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "年份，如 2024"},
            "region": {"type": "string", "description": "地区，如'北京'、'江苏'"},
        },
    },
    category="L3_knowledge",
)
async def search_gaokao(year: int | None = None, region: str | None = None) -> dict:
    exams = knowledge_store.search_gaokao(year=year, region=region)
    return {"exams": exams, "count": len(exams)}
```

- [ ] **Step 4: 更新工具导入和角色映射**

```python
# src/edu_cloud/ai/tools/__init__.py — 追加
from edu_cloud.ai.tools import knowledge  # noqa: F401

# src/edu_cloud/ai/agent.py — ROLE_TOOL_CATEGORIES 追加 L3
ROLE_TOOL_CATEGORIES = {
    "platform_admin": None,
    "district_admin": ["L2_cross_school", "L3_knowledge"],
    "principal": ["L1_analytics", "L2_cross_school", "L3_knowledge", "L4_action"],
    "academic_director": ["L1_analytics", "L2_cross_school", "L3_knowledge", "L4_action"],
    "grade_leader": ["L1_analytics", "L3_knowledge", "L4_action"],
    "homeroom_teacher": ["L1_analytics", "L3_knowledge", "L4_action"],
    "subject_teacher": ["L1_analytics", "L3_knowledge", "L4_action"],
}
```

- [ ] **Step 5: 在 app.py 启动时加载知识库**

```python
# src/edu_cloud/api/app.py — lifespan 中追加
from edu_cloud.knowledge.store import knowledge_store
from edu_cloud.config import settings

# 在 lifespan 函数内，create_all 之后:
if settings.KNOWLEDGE_ENABLED:
    knowledge_store.load(settings.KNOWLEDGE_BASE_DIR)
```

- [ ] **Step 6: 运行测试**

Run: `python -m pytest tests/test_ai/test_tools_knowledge.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 186 + 新增全 PASS

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/ai/tools/knowledge.py src/edu_cloud/ai/tools/__init__.py \
        src/edu_cloud/ai/agent.py src/edu_cloud/api/app.py tests/
git commit -m "feat(P4-2): L3 知识查询工具 — 课标/教材/概念/高考 + 角色映射 + 启动加载"
```

**审查清单:**
- ✓ 4 个 L3 工具注册到 L3_knowledge category
- ✓ 所有角色（除 parent）可使用 L3 工具
- ✓ L3 工具不需要 _db/_school_id（知识库是公共数据）
- ✓ 概念不存在时返回 error dict
- ✓ app.py 启动时加载知识库
- ✗ 不应在 L3 工具中做权限检查（知识是公共的）

**边界条件:**
- 知识库未加载（KNOWLEDGE_ENABLED=False）→ 期望: 工具返回空结果
- 搜索无结果 → 期望: 空列表 + count=0
- 概念名称部分匹配 → 期望: 模糊匹配命中

**测试契约:**
1. L3 工具查询知识库
   - 入口: `search_curriculum(keyword="基因表达")`
   - 反例: 错误实现可能不调用 knowledge_store
   - 边界: 空关键词 / 无匹配 / 知识库未加载
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_tools_knowledge.py -v`

---

## Task 3: paper-skill 接入

**Files:**
- Create: `src/edu_cloud/services/paper_service.py`
- Modify: `src/edu_cloud/config.py`, `src/edu_cloud/templates/document_templates.py`, `src/edu_cloud/api/studio.py`
- Test: `tests/test_services/test_paper_service.py`

- [ ] **Step 1: 添加 paper-skill 配置**

```python
# src/edu_cloud/config.py — 追加
    # Paper-skill
    PAPER_SKILL_URL: str = "http://localhost:9103"
    PAPER_SKILL_ENABLED: bool = True
```

- [ ] **Step 2: 写 paper_service 测试**

```python
# tests/test_services/test_paper_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.services.paper_service import PaperService

@pytest.mark.asyncio
async def test_create_paper():
    """创建论文任务"""
    mock_response = MagicMock()  # httpx.Response.json() 是同步方法，用 MagicMock
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {"paper_id": "p-123", "stage": "intake", "status": "pending_intake"}
    }

    with patch("edu_cloud.services.paper_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.create_paper(budget_tier="standard", title="测试论文")
        assert result["paper_id"] == "p-123"
        assert result["stage"] == "intake"

@pytest.mark.asyncio
async def test_get_paper_status():
    """查询论文状态"""
    mock_response = MagicMock()  # httpx.Response.json() 是同步方法，用 MagicMock
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {"id": "p-123", "stage": "brainstorm", "status": "brainstorming", "cost_yuan": 5.2}
    }

    with patch("edu_cloud.services.paper_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.get_status("p-123")
        assert result["stage"] == "brainstorm"
        assert result["cost_yuan"] == 5.2

@pytest.mark.asyncio
async def test_create_paper_failure():
    """paper-skill 不可用"""
    with patch("edu_cloud.services.paper_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = Exception("Connection refused")
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.create_paper(budget_tier="standard")
        assert "error" in result
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_services/test_paper_service.py -v`
Expected: FAIL

- [ ] **Step 4: 实现 paper_service.py**

```python
# src/edu_cloud/services/paper_service.py
import httpx
import logging
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

class PaperService:
    """paper-skill REST API 客户端"""

    def __init__(self):
        self.base_url = settings.PAPER_SKILL_URL

    async def create_paper(
        self,
        budget_tier: str = "standard",
        title: str | None = None,
        seed_idea: str | None = None,
        journal_id: str | None = None,
    ) -> dict:
        """调用 paper-skill 创建论文任务"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/paper/create",
                    json={
                        "budget_tier": budget_tier,
                        "title": title,
                        "seed_idea": seed_idea,
                        "journal_id": journal_id,
                    },
                )
                data = resp.json()
                if data.get("success"):
                    return data["data"]
                return {"error": data.get("error", "创建失败")}
        except Exception as e:
            logger.error(f"paper-skill create failed: {e}")
            return {"error": f"论文服务不可用: {e}"}

    async def get_status(self, paper_id: str) -> dict:
        """查询论文进度"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/paper/{paper_id}/status")
                data = resp.json()
                if data.get("success"):
                    return data["data"]
                return {"error": data.get("error", "查询失败")}
        except Exception as e:
            logger.error(f"paper-skill status failed: {e}")
            return {"error": f"论文服务不可用: {e}"}
```

- [ ] **Step 5: 添加论文模板**

```python
# src/edu_cloud/templates/document_templates.py — TEMPLATES 追加
    "paper": {
        "key": "paper",
        "name": "教育论文",
        "sections": [
            {"key": "topic", "title": "选题方向", "prompt": "基于教学实践的论文选题"},
        ],
        "required_context": [],
        "available_roles": ["subject_teacher"],
        "requires_approval": False,
        "external_service": "paper_skill",  # 标记为外部服务
    },
```

- [ ] **Step 6: 添加论文创建 API 端点**

```python
# src/edu_cloud/api/studio.py — 追加
from edu_cloud.services.paper_service import PaperService

@router.post("/paper/create")
async def create_paper(
    body: dict,
    current=Depends(require_permission(Permission.WRITE_PAPER)),
    db: AsyncSession = Depends(get_db),
):
    svc = PaperService()
    result = await svc.create_paper(
        budget_tier=body.get("budget_tier", "standard"),
        title=body.get("title"),
        seed_idea=body.get("seed_idea"),
    )
    if "error" in result:
        return result

    # 在 Studio 中创建关联文档记录
    user = current["user"]
    role = current["current_role"]
    studio_svc = StudioService(db)
    doc = await studio_svc.create_document(
        type="paper", title=result.get("title", "教育论文"),
        content_json={"paper_id": result["paper_id"], "stage": result["stage"], "status": result.get("status")},
        school_id=getattr(role, "school_id", ""),
        created_by=user.id,
        source_context={"paper_skill_id": result["paper_id"]},
    )
    await db.commit()
    return {"document_id": doc.id, "paper_id": result["paper_id"], "stage": result["stage"]}

@router.get("/paper/{paper_id}/status")
async def get_paper_status(
    paper_id: str,
    current=Depends(get_current_user),
):
    svc = PaperService()
    return await svc.get_status(paper_id)
```

- [ ] **Step 7: 运行 service 测试**

Run: `python -m pytest tests/test_services/test_paper_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7.5: 写 paper API 端点测试**

```python
# tests/test_api/test_paper_api.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_create_paper_requires_write_paper_permission(client):
    """未认证用户不能创建论文"""
    resp = await client.post("/api/v1/studio/paper/create", json={"budget_tier": "standard"})
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_create_paper_success(client, subject_teacher_headers):
    """subject_teacher 可以创建论文"""
    mock_svc = AsyncMock()
    mock_svc.create_paper.return_value = {
        "paper_id": "p-test-123", "stage": "intake", "status": "pending_intake"
    }
    with patch("edu_cloud.api.studio.PaperService", return_value=mock_svc):
        resp = await client.post(
            "/api/v1/studio/paper/create",
            json={"budget_tier": "standard", "title": "测试论文"},
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "paper_id" in data

@pytest.mark.asyncio
async def test_get_paper_status_auth_required(client):
    """未认证不能查询论文进度"""
    resp = await client.get("/api/v1/studio/paper/p-123/status")
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_get_paper_status_success(client, subject_teacher_headers):
    """认证用户可查询论文进度"""
    mock_svc = AsyncMock()
    mock_svc.get_status.return_value = {
        "id": "p-123", "stage": "brainstorm", "status": "brainstorming", "cost_yuan": 5.2
    }
    with patch("edu_cloud.api.studio.PaperService", return_value=mock_svc):
        resp = await client.get(
            "/api/v1/studio/paper/p-123/status",
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "brainstorm"
```

Run: `python -m pytest tests/test_api/test_paper_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/services/paper_service.py src/edu_cloud/config.py \
        src/edu_cloud/templates/document_templates.py src/edu_cloud/api/studio.py \
        tests/test_services/test_paper_service.py tests/test_api/test_paper_api.py
git commit -m "feat(P4-3): paper-skill 接入 — 创建论文+查询进度+Studio关联+论文模板+API测试"
```

**审查清单:**
- ✓ PaperService 调用 paper-skill REST API
- ✓ 创建论文同时在 Studio 创建 Document 记录
- ✓ paper-skill 不可用时返回 error 而非崩溃
- ✓ 论文模板只对 subject_teacher 可见
- ✓ mock_response 使用 MagicMock（httpx.Response.json() 是同步方法，不用 AsyncMock）
- ✓ API 端点测试覆盖权限检查（未认证 401/403）和正常流程
- ✗ 不应在 edu-cloud 内实现论文写作逻辑（委托给 paper-skill）

**边界条件:**
- paper-skill 服务不可用 → 期望: error dict，不崩溃
- paper_id 不存在 → 期望: paper-skill 返回 404，转为 error
- budget_tier 非法值 → 期望: paper-skill 处理
- 未认证用户调用论文端点 → 期望: 401/403

**测试契约:**
1. paper-skill API 调用（service 层）
   - 入口: `svc.create_paper(budget_tier="standard")`
   - 反例: 错误实现可能不 catch 网络异常；AsyncMock 做 mock_response 会导致 json() 返回 coroutine
   - 边界: 服务不可用 / 返回 success=false / 超时
   - 回归: F6(mock 类型修复)
   - 命令: `python -m pytest tests/test_services/test_paper_service.py -v`
2. 论文端点 API 集成测试（API 层）
   - 入口: `POST /api/v1/studio/paper/create` + `GET /api/v1/studio/paper/{id}/status`
   - 反例: 错误实现可能遗漏权限检查，未认证用户可访问
   - 边界: 未认证 / 非 subject_teacher / paper-skill mock 返回
   - 回归: F4(端点测试缺失)
   - 命令: `python -m pytest tests/test_api/test_paper_api.py -v`

---

## Task 4: 前端论文进度 + 端到端验证

**Files:**
- Create: `frontend/src/components/studio/PaperStatus.vue`
- Modify: `frontend/src/components/studio/StudioPanel.vue`, `frontend/src/stores/studio.js`

- [ ] **Step 1: 扩展 studio store**

```javascript
// frontend/src/stores/studio.js — 追加
  async function createPaper(budgetTier, title, seedIdea) {
    const { data } = await client.post('/studio/paper/create', {
      budget_tier: budgetTier, title, seed_idea: seedIdea,
    })
    if (data.error) throw new Error(data.error)
    await loadDocuments()
    return data
  }

  async function getPaperStatus(paperId) {
    const { data } = await client.get(`/studio/paper/${paperId}/status`)
    return data
  }

  return { templates, documents, currentDoc, loading,
           loadTemplates, loadDocuments, getDocument, updateDocument,
           transitionStatus, createPaper, getPaperStatus }
```

- [ ] **Step 2: 创建 PaperStatus 组件**

```vue
<!-- frontend/src/components/studio/PaperStatus.vue -->
<template>
  <n-card size="small" v-if="paperId">
    <template #header>
      <n-text>论文进度</n-text>
    </template>
    <n-space vertical>
      <n-text>阶段: {{ status?.stage || '加载中...' }}</n-text>
      <n-text>状态: {{ status?.status || '-' }}</n-text>
      <n-text v-if="status?.cost_yuan">费用: ¥{{ status.cost_yuan }}</n-text>
      <n-progress
        :percentage="stagePercent"
        :status="status?.stage === 'completed' ? 'success' : 'default'"
      />
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const props = defineProps({ paperId: String })
const studioStore = useStudioStore()
const status = ref(null)
let timer = null

const STAGES = ['intake', 'brainstorm', 'literature', 'outline', 'writing', 'review', 'format', 'output', 'completed']
const stagePercent = computed(() => {
  if (!status.value?.stage) return 0
  const idx = STAGES.indexOf(status.value.stage)
  return Math.round(((idx + 1) / STAGES.length) * 100)
})

async function poll() {
  if (props.paperId) {
    status.value = await studioStore.getPaperStatus(props.paperId)
    if (status.value?.stage === 'completed') {
      clearInterval(timer)
    }
  }
}

onMounted(() => {
  poll()
  timer = setInterval(poll, 15000)  // 每 15 秒轮询
})
onUnmounted(() => clearInterval(timer))
</script>
```

- [ ] **Step 3: 在 StudioPanel 中集成论文入口**

在 StudioPanel 的模板卡片点击处理中，对 `paper` 模板走 `createPaper` 而非 AI 对话：

```javascript
// StudioPanel.vue — handleTemplateSelect 修改
async function handleTemplateSelect(tmpl) {
  if (tmpl.key === 'paper') {
    try {
      await studioStore.createPaper('standard', null, null)
    } catch (e) {
      // 显示错误
    }
    return
  }
  // 其他模板走 AI 对话
  await chatStore.sendMessage(`请帮我生成${tmpl.name}`)
  studioStore.loadDocuments()
}
```

在文档预览中，对 `type=paper` 的文档显示 PaperStatus 而非编辑器。

- [ ] **Step 4: 端到端验证（P4 完成标志）**

**标志 1:** 知识查询
1. 以 zhanglaoshi 登录
2. 在 AI 对话框输入 "课标对基因表达有什么要求"
3. AI 调用 `search_curriculum` 工具 → 返回课标原文引用
Expected: AI 回答包含课标中"阐明基因表达的过程"等原文

**标志 2:** 论文创建（需 paper-skill 运行）
1. 右栏看到"教育论文"模板卡片（subject_teacher 角色）
2. 点击 → 调用 paper-skill → Studio 出现论文记录
3. 点击论文记录 → 看到 PaperStatus 进度条

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(P4-4): 前端论文进度 + Studio 论文入口 + 端到端验证"
```

**审查清单:**
- ✓ 论文模板点击调用 paper-skill 而非 AI 对话
- ✓ PaperStatus 轮询进度（15s 间隔）
- ✓ 进度条显示 9 阶段百分比
- ✓ 论文完成后停止轮询
- ✗ 不应在前端存储 paper-skill 的认证信息

**边界条件:**
- paper-skill 不可用 → 期望: 显示错误提示
- paper 已完成 → 期望: 停止轮询，进度 100%
- 非 subject_teacher 角色 → 期望: 看不到论文模板卡片

**测试契约:**
1. 论文创建+进度查询
   - 入口: `POST /api/v1/studio/paper/create` + `GET /api/v1/studio/paper/{id}/status`
   - 反例: 错误实现可能不在 Studio 创建 Document 记录
   - 边界: paper-skill 不可用 / paper_id 不存在
   - 回归: N/A
   - 命令: 手动验证 + `python -m pytest tests/test_services/test_paper_service.py -v`
