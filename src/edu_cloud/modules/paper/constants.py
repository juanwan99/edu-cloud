"""Paper 模块常量（S1-C 1.5）。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.5
refs: 附录 C §Gap#4（试卷权限分层）

S4 4.2 paper.access_policy 消费本枚举做 3 层分享工作流（teacher_private / school_shared / district_shared）。
S1-C 只定义常量，不上 DB CHECK 或 SQLAlchemy Enum 列（见 test_debt #2 deadline 2026-06-30）。
"""
from enum import Enum


class PaperAccessLevel(str, Enum):
    """试卷访问层级（S4 4.2 分享工作流使用）."""
    TEACHER_PRIVATE = "teacher_private"
    SCHOOL_SHARED = "school_shared"
    DISTRICT_SHARED = "district_shared"
