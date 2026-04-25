import client from './client'

export const listTasks = (params) => client.get('/homework/tasks', { params })
export const createTask = (data) => client.post('/homework/tasks', data)
export const getTask = (id) => client.get(`/homework/tasks/${id}`)
export const updateTask = (id, data) => client.patch(`/homework/tasks/${id}`, data)
export const deleteTask = (id) => client.delete(`/homework/tasks/${id}`)
export const publishTask = (id) => client.post(`/homework/tasks/${id}/publish`)
export const closeTask = (id) => client.post(`/homework/tasks/${id}/close`)

export const listSubmissions = (taskId, params) => client.get(`/homework/tasks/${taskId}/submissions`, { params })
export const submitHomework = (taskId, subId, data) => client.post(`/homework/tasks/${taskId}/submissions/${subId}/submit`, data)
export const gradeSingle = (taskId, subId, data) => client.post(`/homework/tasks/${taskId}/submissions/${subId}/grade`, data)
export const gradeBatch = (taskId, data) => client.post(`/homework/tasks/${taskId}/grade-batch`, data)

// WP-C: 考后推送 + 内容增强
export const createFromExam = (examId, classId) => client.post('/homework/tasks/from-exam', { exam_id: examId, class_id: classId })
export const getContentDetail = (taskId) => client.get(`/homework/tasks/${taskId}/content-detail`)
