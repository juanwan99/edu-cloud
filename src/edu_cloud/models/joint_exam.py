# Re-export from new location for backwards compatibility (Task 22 cleanup)
from edu_cloud.modules.exam.models import (  # noqa: F401
    JointExam, JointExamParticipant, JointExamStudentResult,
)
