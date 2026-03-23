import client from './client'

export const listQuestions = (subjectId) => client.get('/questions', { params: { subject_id: subjectId } })
export const getQuestion = (id) => client.get(`/questions/${id}`)
export const createQuestion = (data) => client.post('/questions', data)
export const updateQuestion = (id, data) => client.patch(`/questions/${id}`, data)
export const deleteQuestion = (id) => client.delete(`/questions/${id}`)
