function fmt(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  const n = Number(value)
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatDelta(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  const n = Number(value)
  if (n > 0) return `进 ${n}`
  if (n < 0) return `退 ${Math.abs(n)}`
  return '持平'
}

export function getSubjectColumns() {
  return [
    { title: '科目', key: 'subject_name', width: 100 },
    { title: '满分', key: 'full_score', width: 80, render: row => fmt(row.full_score) },
    { title: '参考人数', key: 'student_count', width: 90 },
    { title: '平均分', key: 'avg_score', width: 90, render: row => fmt(row.avg_score) },
    { title: '最高分', key: 'max_score', width: 90, render: row => fmt(row.max_score) },
    { title: '最低分', key: 'min_score', width: 90, render: row => fmt(row.min_score) },
    { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
    { title: '及格率', key: 'pass_rate', width: 90, render: row => pct(row.pass_rate) },
    { title: '优秀率', key: 'excellent_rate', width: 90, render: row => pct(row.excellent_rate) },
  ]
}

export function getClassColumns() {
  return [
    { title: '排名', key: 'rank', width: 70 },
    { title: '班级', key: 'class_name', width: 120 },
    { title: '参考人数', key: 'student_count', width: 90 },
    { title: '平均分', key: 'avg_score', width: 90, render: row => fmt(row.avg_score) },
    { title: '最高分', key: 'max_score', width: 90, render: row => fmt(row.max_score) },
    { title: '最低分', key: 'min_score', width: 90, render: row => fmt(row.min_score) },
    { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
    { title: '及格率', key: 'pass_rate', width: 90, render: row => pct(row.pass_rate) },
    { title: '优秀率', key: 'excellent_rate', width: 90, render: row => pct(row.excellent_rate) },
  ]
}

export function getStudentColumns(subjects) {
  const subjectCols = (subjects || []).map(subject => ({
    title: subject.subject_name,
    key: `subject_${subject.subject_code}`,
    width: 90,
    render: row => fmt(row.subject_scores?.[subject.subject_code]?.score),
  }))

  return [
    { title: '排名', key: 'grade_rank', width: 70 },
    { title: '姓名', key: 'name', width: 100 },
    { title: '班级', key: 'class_name', width: 120 },
    { title: '学号', key: 'student_number', width: 110, render: row => row.student_number || '-' },
    ...subjectCols,
    { title: '总分', key: 'total_score', width: 90, render: row => fmt(row.total_score) },
    { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
    { title: '班级排名', key: 'class_rank', width: 90 },
    { title: '年级进退', key: 'delta_grade', width: 100, render: row => formatDelta(row.delta_grade) },
    { title: '班级进退', key: 'delta_class', width: 100, render: row => formatDelta(row.delta_class) },
  ]
}

export { fmt, pct, formatDelta }
