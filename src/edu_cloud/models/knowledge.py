# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/knowledge/models.py。
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint  # noqa: F401
