import client from './client'

export const listTasks = () => client.get('/grading/tasks')
export const createTask = (data) => client.post('/grading/tasks', data)
export const getTask = (taskId) => client.get(`/grading/tasks/${taskId}`)
export const listResults = (params) => client.get('/grading/results', { params })
export const getResult = (resultId) => client.get(`/grading/results/${resultId}`)
export const getPending = () => client.get('/grading/review/pending')
export const submitReview = (resultId, data) => client.post(`/grading/review/${resultId}`, data)
