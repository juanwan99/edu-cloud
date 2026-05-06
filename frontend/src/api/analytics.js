import client from './client'

export const getExamSummary = (examId) => client.get(`/analytics/exam/${examId}/summary`)
export const getDistribution = (examId, params) => client.get(`/analytics/exam/${examId}/distribution`, { params })
export const getSubjectQuestions = (subjectId) => client.get(`/analytics/subject/${subjectId}/questions`)

export const getSegmentConfig = () => client.get('/analytics/segments/config')
export const updateSegmentConfig = (data) => client.put('/analytics/segments/config', data)

export const queryReport = (data) => client.post('/analytics/report/query', data)
export const getGradeTrend = (params) => client.get('/analytics/report/trend/grade', { params })
export const getClassTrend = (params) => client.get('/analytics/report/trend/class', { params })
export const getStudentTrend = (params) => client.get('/analytics/report/trend/student', { params })
export const exportReport = (data) => client.post('/analytics/report/export', data)

export const getPowerOptions = () => client.get('/analytics/power-options')
export const getQuestionInsights = (examId) => client.get(`/analytics/exam/${examId}/question-insights`)
export const getExamDiagnosis = (examId, params) => client.get(`/analytics/exam/${examId}/diagnosis`, { params })
export const getAiGradingReport = (examId, params) => client.get(`/analytics/exam/${examId}/ai-grading-report`, { params })
export const getStudentRankings = (examId, params) => client.get(`/analytics/exam/${examId}/student-rankings`, { params })
export const getCriticalStudents = (examId, params) => client.get(`/analytics/exam/${examId}/critical-students`, { params })
export const getClassBoxplot = (examId, params) => client.get(`/analytics/exam/${examId}/class-boxplot`, { params })
export const getClassKnowledge = (examId, params) => client.get(`/analytics/exam/${examId}/class-knowledge`, { params })
export const getClassDiagnosis = (examId, params) => client.get(`/analytics/exam/${examId}/class-diagnosis`, { params })
export const getClassErrorPatterns = (examId, params) => client.get(`/analytics/exam/${examId}/class-error-patterns`, { params })
export const getLayerAnalysis = (examId, params) => client.get(`/analytics/exam/${examId}/layer-analysis`, { params })
export const getCommonWrongQuestions = (examId, params) => client.get(`/analytics/exam/${examId}/common-wrong-questions`, { params })

// WP-D: 年级聚合分析
export const getGradeOverview = (gradeId, examId) => client.get(`/analytics/grade/${gradeId}/overview`, { params: { exam_id: examId } })
export const getGradeExamTrend = (gradeId, limit = 10) => client.get(`/analytics/grade/${gradeId}/trend`, { params: { limit } })
export const getGradeSubjects = (gradeId, examId) => client.get(`/analytics/grade/${gradeId}/subjects`, { params: { exam_id: examId } })

// Phase 2-A/B/C: 真实下载（PDF / XLSX）
export const exportGradeReport = (examId, subjectId, format = 'pdf') =>
  client.get(
    `/analytics/report/grade/${examId}/${subjectId}/export`,
    { params: { format }, responseType: 'blob' },
  )

export const exportStudentReport = (studentId, examId, subjectId, format = 'pdf') =>
  client.get(
    `/analytics/report/student/${studentId}/${examId}/${subjectId}/export`,
    { params: { format }, responseType: 'blob' },
  )

// 通用：将 blob 响应保存为下载文件（解析 Content-Disposition 中的文件名）
export function downloadBlob(resp, fallbackName) {
  const blob = resp.data
  const cd = resp.headers?.['content-disposition'] || ''
  let filename = fallbackName
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  if (m) {
    try { filename = decodeURIComponent(m[1]) } catch { /* ignore */ }
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
