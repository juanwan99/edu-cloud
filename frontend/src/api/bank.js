import client from './client'

export const getStudentErrorBook = (studentId, params) =>
  client.get(`/bank/error-book/${studentId}`, { params })

export const getErrorBookStats = (studentId) =>
  client.get(`/bank/error-book/${studentId}/stats`)

export const listBankQuestions = (params) =>
  client.get('/bank/questions', { params })

export const getBankQuestion = (questionId) =>
  client.get(`/bank/questions/${questionId}`)
