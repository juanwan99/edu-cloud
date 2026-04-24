# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/academic/models.py。
from edu_cloud.modules.academic.models import (  # noqa: F401
    Semester,
    TimePeriod,
    TimetableSlot,
)
