import client from './client'

export const getExamSummary = (examId) => client.get(`/analytics/exam/${examId}/summary`)
export const getDistribution = (examId, params) => client.get(`/analytics/exam/${examId}/distribution`, { params })
export const getSubjectQuestions = (subjectId) => client.get(`/analytics/subject/${subjectId}/questions`)
