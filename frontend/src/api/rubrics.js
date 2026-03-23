import client from './client'

export const getRubric = (questionId) => client.get(`/grading/rubrics/${questionId}`)
export const upsertRubric = (data) => client.post('/grading/rubrics', data)
