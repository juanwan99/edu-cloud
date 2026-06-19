"""考试完成后的自动数据生成流水线 —— 模块外 owner 的兼容 facade（D-03I）。

冷数据生成的 owner 逻辑已上移到模块外服务边界：
- 考试快照 / 知识点掌握度 / 错误模式 / 有效分权威规则 / 一键编排
  `run_full_pipeline` → `services.post_exam_cold_data`（D-03I）
- 题库 / 错题本制品读写 → `services.post_exam_bank_artifacts`（D-03H）

pipeline 模块自此不再直接 import `exam` / `scan` / `grading` / `knowledge` /
`knowledge_tree` / `profile` / `student`（一次拆掉 7 条直接依赖边）。本模块仅保留对
外 owner 命名空间：经 re-export 暴露旧函数名，使既有调用点（exam `publish_service`、
exam_import、编排服务 `services.post_exam_pipeline` / `services.exam_publish_pipeline`）
与测试 patch（`pipeline.service.*` 命名空间）行为零变更。

触发条件：Exam.status → completed（经模块外编排服务）
幂等保证：DF-007 — try/except IntegrityError 兜底
有效分：统一读取 GradingResult.final_score（权威单一源）
"""
# 题库/错题本制品读写经模块外服务边界（D-03H）；populate_bank_questions /
# populate_error_books 及两个错题本读模型经此 re-export 保持公共导入兼容。
from edu_cloud.services.post_exam_bank_artifacts import (
    populate_bank_questions,
    populate_error_books,
    list_error_book_students_for_subject,
    list_error_book_entries_for_student,
)
# 考后冷数据 owner 逻辑经模块外服务边界（D-03I）；冷数据各步骤与有效分权威规则、
# 一键编排经此 re-export 保持公共导入与测试 patch 命名空间兼容。
from edu_cloud.services.post_exam_cold_data import (
    _get_effective_score,
    _get_effective_scores_for_subject,
    generate_exam_snapshots,
    update_knowledge_mastery,
    update_error_patterns,
    run_full_pipeline,
)

__all__ = [
    "populate_bank_questions",
    "populate_error_books",
    "list_error_book_students_for_subject",
    "list_error_book_entries_for_student",
    "_get_effective_score",
    "_get_effective_scores_for_subject",
    "generate_exam_snapshots",
    "update_knowledge_mastery",
    "update_error_patterns",
    "run_full_pipeline",
]
