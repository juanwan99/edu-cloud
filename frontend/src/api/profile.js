import client from './client'

export const getStudentTrend = (studentId, params) =>
  client.get(`/profile/students/${studentId}/trend`, { params })

export const getStudentKnowledge = (studentId, params) =>
  client.get(`/profile/students/${studentId}/knowledge`, { params })

export const getStudentErrorPatterns = (studentId, params) =>
  client.get(`/profile/students/${studentId}/error-patterns`, { params })

export const getStudentAiDiagnosis = (studentId, params) =>
  client.get(`/profile/students/${studentId}/ai-diagnosis`, { params })

export const getClassWeakness = (params) =>
  client.get('/profile/class/weakness', { params })
