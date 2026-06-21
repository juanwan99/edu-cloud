"""marking 人工阅卷工作流的跨模块数据依赖边界（模块外应用服务）。

集中 marking 工作流所需的 exam / grading / scan ORM 模型与 grading 详情解析助手，
使 marking 模块不再直接 import `exam` / `grading` / `scan` —— 一次拆掉
`marking -> {exam, grading, scan}` 3 条直接依赖边（D-03K）。exam / grading / scan
仍是各自 ORM 模型与 `detail_flatten` 助手的 owner，本服务只做 re-export facade：
marking 经此单一模块外边界访问跨模块数据，类对象与函数引用与历史完全一致，行为零变更。

与 `services.effective_scores` / `services.exam_import_materialization` 同范式：
service 层可 module-level import `edu_cloud.modules.*`（依赖守卫 `check_module_dependencies`
仅扫 `src/edu_cloud/modules/`，不计 services→modules 边），模块侧改为从本 facade 取符号，
marking 的跨模块数据依赖自此在一处集中声明。
"""
from edu_cloud.modules.exam.models import Exam, Question, Subject
from edu_cloud.modules.grading.detail_flatten import (
    flatten_llm_details,
    parse_raw_content,
)
from edu_cloud.modules.grading.models import GradingAssignment, GradingResult
from edu_cloud.modules.scan.models import StudentAnswer

__all__ = [
    "Exam",
    "Subject",
    "Question",
    "StudentAnswer",
    "GradingAssignment",
    "GradingResult",
    "flatten_llm_details",
    "parse_raw_content",
]
