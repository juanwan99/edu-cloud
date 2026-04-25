import client from './client'

export const getStudentErrorBook = (studentId, params) =>
  client.get(`/bank/error-book/${studentId}`, { params })

export const getErrorBookStats = (studentId) =>
  client.get(`/bank/error-book/${studentId}/stats`)

export const listBankQuestions = (params) =>
  client.get('/bank/questions', { params })

export const getBankQuestion = (questionId) =>
  client.get(`/bank/questions/${questionId}`)

export const getErrorKnowledgeSummary = (studentId) =>
  client.get(`/bank/error-book/${studentId}/knowledge-summary`)

export const getRecommendedPractice = (studentId, limit = 10) =>
  client.get(`/bank/error-book/${studentId}/recommendations`, { params: { limit } })

export const searchQuestions = (params) =>
  client.get('/bank/questions/search', { params })

export const getQuestionBankStats = () =>
  client.get('/bank/questions/stats/overview')
