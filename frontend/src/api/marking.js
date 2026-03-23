import client from './client'

export const importFolder = (data) => client.post('/marking/import', data, { timeout: 300000 })
export const listSubjects = (examId) => client.get('/marking/subjects', { params: { exam_id: examId } })
export const getNext = (questionId) => client.get('/marking/next', { params: { question_id: questionId } })
export const getAnswerImageUrl = (answerId) => `/api/v1/marking/answer/${answerId}/image`
export const submitScore = (data) => client.post('/marking/score', data)
export const getProgress = (examId) => client.get('/marking/progress', { params: { exam_id: examId } })
export const exportCsv = (examId) => client.get('/marking/export', { params: { exam_id: examId }, responseType: 'blob' })
