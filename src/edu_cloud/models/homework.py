# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/homework/models.py。
from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission  # noqa: F401
