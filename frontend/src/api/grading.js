import client from './client'

export const listTasks = () => client.get('/grading/tasks')
export const createTask = (data) => client.post('/grading/tasks', data)
export const getTask = (taskId) => client.get(`/grading/tasks/${taskId}`)
export const listResults = (params) => client.get('/grading/results', { params })
export const getResult = (resultId) => client.get(`/grading/results/${resultId}`)
export const getDispatchStatus = (examId) =>
  client.get('/grading/dispatch/status', { params: { exam_id: examId } })

export const generateRubric = (questionId, maxScore) =>
  client.post('/grading/rubrics/generate', { question_id: questionId, max_score: maxScore })
export const getRubric = (questionId) => client.get(`/grading/rubrics/${questionId}`)
export const saveRubric = (data) => client.post('/grading/rubrics', data)
export const updateQuestionContent = (questionId, data) =>
  client.put(`/questions/${questionId}/content`, data)
export const uploadQuestionImage = (questionId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return client.post(`/questions/${questionId}/content/upload-image`, fd)
}
