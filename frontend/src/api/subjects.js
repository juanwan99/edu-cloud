import client from './client'

export const listSubjects = (examId) => client.get(`/exams/${examId}/subjects`)
export const createSubject = (examId, data) => client.post(`/exams/${examId}/subjects`, data)
