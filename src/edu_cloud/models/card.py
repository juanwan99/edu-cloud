# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/card/models.py。
from edu_cloud.modules.card.models import Template, CardSkeleton  # noqa: F401
