# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/profile/models.py。
from edu_cloud.modules.profile.models import (  # noqa: F401
    StudentExamSnapshot,
    StudentKnowledgeMastery,
    StudentErrorPattern,
)
