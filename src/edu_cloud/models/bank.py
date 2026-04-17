# Re-export: 统一 ORM 入口（见 docs/arch/orm-placement.md §5）。真实定义在 modules/bank/models.py。
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook  # noqa: F401
