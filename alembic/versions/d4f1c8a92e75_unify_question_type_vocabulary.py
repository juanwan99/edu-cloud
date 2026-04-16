"""unify question_type vocabulary

Revision ID: d4f1c8a92e75
Revises: a7e9c4b8d123
Create Date: 2026-04-16

将 Question.question_type 与 Template.regions[].type 切换到统一的题型枚举:
  choice | multi_choice | fill_blank | essay

  Question.question_type:
    objective  → choice
    subjective → essay
  （细分 multi_choice / fill_blank 需要业务上下文，缺省走最常见映射）

  Template.regions[]:
    - 增加 question_type 字段（不删 type，type 仍是渲染提示）
    - choice_group → question_type=multi_choice 若 multi_select 为真，否则 choice
    - subjective   → question_type=essay
    - 其余 type（number_fill / absent_mark / barcode / objective）不加 question_type
"""
from typing import Sequence, Union
import json

from alembic import op


revision: str = 'd4f1c8a92e75'
down_revision: Union[str, Sequence[str], None] = 'a7e9c4b8d123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _migrate_regions_forward(regions: list) -> list:
    if not isinstance(regions, list):
        return regions
    new_regions = []
    for r in regions:
        if not isinstance(r, dict):
            new_regions.append(r)
            continue
        rtype = r.get("type")
        nr = dict(r)
        if rtype == "choice_group":
            nr["question_type"] = "multi_choice" if r.get("multi_select") else "choice"
        elif rtype == "subjective":
            nr["question_type"] = "essay"
        new_regions.append(nr)
    return new_regions


def _migrate_regions_backward(regions: list) -> list:
    if not isinstance(regions, list):
        return regions
    new_regions = []
    for r in regions:
        if not isinstance(r, dict):
            new_regions.append(r)
            continue
        nr = dict(r)
        nr.pop("question_type", None)
        new_regions.append(nr)
    return new_regions


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "UPDATE questions SET question_type = 'choice' WHERE question_type = 'objective'"
    )
    bind.exec_driver_sql(
        "UPDATE questions SET question_type = 'essay' WHERE question_type = 'subjective'"
    )

    rows = bind.exec_driver_sql("SELECT id, regions FROM templates").fetchall()
    for row_id, regions_raw in rows:
        if regions_raw is None:
            continue
        try:
            regions = json.loads(regions_raw) if isinstance(regions_raw, str) else regions_raw
        except (TypeError, ValueError):
            continue
        new_regions = _migrate_regions_forward(regions)
        if new_regions == regions:
            continue
        bind.exec_driver_sql(
            "UPDATE templates SET regions = ? WHERE id = ?",
            (json.dumps(new_regions, ensure_ascii=False), row_id),
        )


def downgrade() -> None:
    bind = op.get_bind()

    rows = bind.exec_driver_sql("SELECT id, regions FROM templates").fetchall()
    for row_id, regions_raw in rows:
        if regions_raw is None:
            continue
        try:
            regions = json.loads(regions_raw) if isinstance(regions_raw, str) else regions_raw
        except (TypeError, ValueError):
            continue
        new_regions = _migrate_regions_backward(regions)
        if new_regions == regions:
            continue
        bind.exec_driver_sql(
            "UPDATE templates SET regions = ? WHERE id = ?",
            (json.dumps(new_regions, ensure_ascii=False), row_id),
        )

    bind.exec_driver_sql(
        "UPDATE questions SET question_type = 'objective' "
        "WHERE question_type IN ('choice', 'multi_choice')"
    )
    bind.exec_driver_sql(
        "UPDATE questions SET question_type = 'subjective' "
        "WHERE question_type IN ('fill_blank', 'essay')"
    )
