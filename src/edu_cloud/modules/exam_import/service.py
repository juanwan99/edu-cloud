"""Exam import service —— 模块外 owner 的兼容 facade（D-03J）。

学生匹配 + 写入链 + 导入后画像/错题流水线的 owner 逻辑已上移到模块外服务边界
`services.exam_import_materialization`（D-03J）。exam_import 模块自此不再直接 import
`exam` / `grading` / `pipeline` / `profile` / `scan` / `student`（一次拆掉 6 条直接依赖边）。
本模块仅保留对外 owner 命名空间：经 re-export 暴露旧函数 / 数据类名，使既有调用点
（`exam_import.router`）与测试（`exam_import.service.*` 命名空间）行为零变更。

两个核心函数：
- match_students: link imported StudentScore rows to DB Student records
- commit_import: write the full chain Exam→Subject→Question→StudentAnswer→GradingResult→ExamResult
"""

from edu_cloud.services.exam_import_materialization import (
    MatchedStudent,
    MatchResult,
    match_students,
    commit_import,
    run_post_import_pipeline,
    _normalize_class,
)

__all__ = [
    "MatchedStudent",
    "MatchResult",
    "match_students",
    "commit_import",
    "run_post_import_pipeline",
    "_normalize_class",
]
