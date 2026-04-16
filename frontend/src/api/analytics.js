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
