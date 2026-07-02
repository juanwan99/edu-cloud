"""grading module Service facade.

Only performs explicit re-exports so that the
`from edu_cloud.modules.grading.service import ...` usage in
ai/tools/grading_ops.py stays stable. No runtime behavior change.
"""
from edu_cloud.modules.grading.assignment_service import GradingAssignmentService
from edu_cloud.modules.grading.quality_service import QualityCheckService

__all__ = ["GradingAssignmentService", "QualityCheckService"]
