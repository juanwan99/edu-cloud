# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/scan/models.py。
from edu_cloud.modules.scan.models import ScanTask, StudentAnswer  # noqa: F401
