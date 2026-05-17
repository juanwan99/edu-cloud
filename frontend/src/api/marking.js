import client from './client'

export const importFolder = (data) => client.post('/marking/import', data, { timeout: 300000 })
export const listSubjects = (examId) => client.get('/marking/subjects', { params: { exam_id: examId } })
export const getNext = (questionId, mode = 'ungraded', extra = {}) => client.get('/marking/next', { params: { question_id: questionId, mode, ...extra } })
export const getAnswerImageUrl = (answerId) => `/api/v1/marking/answer/${answerId}/image`
export const submitScore = (data) => client.post('/marking/score', data)
export const flagAnswer = (answerId, anomalyType) => client.patch(`/marking/answer/${answerId}/flag`, { anomaly_type: anomalyType })
export const getAnswerAt = (questionId, offset, mode = 'ungraded', extra = {}) => client.get('/marking/answer-at', { params: { question_id: questionId, offset, mode, ...extra } })
export const getProgress = (examId) => client.get('/marking/progress', { params: { exam_id: examId } })
export const exportCsv = (examId) => client.get('/marking/export', { params: { exam_id: examId }, responseType: 'blob' })
