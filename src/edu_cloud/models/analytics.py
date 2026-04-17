# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/analytics/models.py。
from edu_cloud.modules.analytics.models import (  # noqa: F401
    ClassAnalysis,
    StudentAnalysis,
    StudentKnpMastery,
)
