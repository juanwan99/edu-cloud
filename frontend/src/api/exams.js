import client from './client'

export const listExams = () => client.get('/exams')
export const getExam = (examId) => client.get(`/exams/${examId}`)
export const createExam = (data) => client.post('/exams', data)
export const updateExam = (examId, data) => client.patch(`/exams/${examId}`, data)
export const archiveExam = (examId) => client.post(`/exams/${examId}/archive`)
