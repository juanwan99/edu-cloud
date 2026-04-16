from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from edu_cloud.models.base import Base


class MenuConfig(Base):
    __tablename__ = "menu_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("menu_configs.id"), nullable=True
    )
    path: Mapped[str | None] = mapped_column(String(128), nullable=True)
    roles = Column(JSON, nullable=False, server_default="[]")
    requires_module: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
