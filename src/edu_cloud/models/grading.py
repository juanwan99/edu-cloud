# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/grading/models.py。
from edu_cloud.modules.grading.models import (  # noqa: F401
    Rubric,
    GradingTask,
    GradingResult,
    GradingPipelineLog,
    GradingAssignment,
    GradingQualityCheck,
)
