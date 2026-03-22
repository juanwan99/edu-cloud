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
        logger.info(f"Loading knowledge base from {base_dir}")
        self._curriculum = load_curriculum(base_dir)
        self._l0_blocks = load_l0_blocks(base_dir)
        self._l1_concepts = load_l1_concepts(base_dir)
        self._gaokao_index = load_gaokao_index(base_dir)
        self._loaded = True
        logger.info(f"Knowledge base loaded: {self.stats()}")

    def search_curriculum(self, keyword: str, limit: int = 10) -> list[dict]:
        import json as _json
        results = []
        for module in self._curriculum.get("modules", []):
            module_matched = False
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
            for concept in module.get("big_concepts", []):
                if keyword in str(concept):
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": str(concept),
                        "type": "big_concept",
                    })
                    module_matched = True
            for creq in module.get("content_requirements", []):
                if keyword in str(creq):
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": str(creq),
                        "type": "content_requirement",
                    })
                    module_matched = True
            if not module_matched:
                module_text = _json.dumps(module, ensure_ascii=False)
                if keyword in module_text:
                    results.append({
                        "module": module.get("name", ""),
                        "module_id": module.get("id", ""),
                        "text": f"模块 {module.get('name')} 包含相关内容",
                        "type": "module_match",
                    })
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
        results = []
        for block in self._l0_blocks:
            if keyword in block.get("content", ""):
                results.append(block)
        return results[:limit]

    def get_concept(self, name: str) -> dict | None:
        for concept in self._l1_concepts:
            if concept.get("canonical_name") == name:
                return concept
            if name in concept.get("aliases", []):
                return concept
            if name in concept.get("canonical_name", ""):
                return concept
        return None

    def search_gaokao(self, year: int | None = None, region: str | None = None, limit: int = 20) -> list[dict]:
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
