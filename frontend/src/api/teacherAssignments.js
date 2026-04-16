import client from './client.js'

export const getAssignments = (schoolId, params) =>
  client.get(`/schools/${schoolId}/assignments`, { params })

export const createAssignments = (schoolId, data) =>
  client.post(`/schools/${schoolId}/assignments`, data)

export const deleteAssignment = (schoolId, id) =>
  client.delete(`/schools/${schoolId}/assignments/${id}`)

export const getAssignmentSummary = (schoolId, params) =>
  client.get(`/schools/${schoolId}/assignments/summary`, { params })
