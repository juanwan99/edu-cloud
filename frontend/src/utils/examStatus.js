// F010: 考试状态英文枚举 → 中文展示映射
// 对应后端 src/edu_cloud/modules/exam/models.py:26 status 枚举
// draft → scanning → grading → reviewing → completed

export const EXAM_STATUS_LABELS = {
  draft: '草稿',
  scanning: '扫描中',
  grading: '阅卷中',
  reviewing: '审核中',
  completed: '已完成',
}

export function formatExamStatus(status) {
  if (!status) return ''
  return EXAM_STATUS_LABELS[status] || status
}
