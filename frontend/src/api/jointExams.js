import client from './client'

export const listJointExams = (params) => client.get('/joint-exams', { params })
export const getJointExam = (examId) => client.get(`/joint-exams/${examId}`)
export const createJointExam = (data) => client.post('/joint-exams', data)

export const addParticipant = (examId, schoolId) =>
  client.post(`/joint-exams/${examId}/participants`, { school_id: schoolId })
export const removeParticipant = (examId, schoolId) =>
  client.delete(`/joint-exams/${examId}/participants/${schoolId}`)

export const distributeExam = (examId) => client.post(`/joint-exams/${examId}/distribute`)
export const forceCompleteExam = (examId) => client.post(`/joint-exams/${examId}/force-complete`)

export const getExamRankings = (examId, params) =>
  client.get(`/joint-exams/${examId}/results`, { params })
export const getSchoolComparison = (examId) =>
  client.get(`/joint-exams/${examId}/results/by-school`)
export const getStudentResult = (examId, studentNumber, params) =>
  client.get(`/joint-exams/${examId}/results/students/${studentNumber}`, { params })
