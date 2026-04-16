import client from './client'

export const listTasks = () => client.get('/grading/tasks')
export const createTask = (data) => client.post('/grading/tasks', data)
export const getTask = (taskId) => client.get(`/grading/tasks/${taskId}`)
export const listResults = (params) => client.get('/grading/results', { params })
export const getResult = (resultId) => client.get(`/grading/results/${resultId}`)
export const getDispatchStatus = (examId) =>
  client.get('/grading/dispatch/status', { params: { exam_id: examId } })
