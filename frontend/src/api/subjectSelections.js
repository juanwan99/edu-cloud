import client from './client.js'

export const getSelections = (schoolId, params) =>
  client.get(`/schools/${schoolId}/selections`, { params })

export const createSelection = (schoolId, data) =>
  client.post(`/schools/${schoolId}/selections`, data)

export const updateSelection = (schoolId, id, data) =>
  client.patch(`/schools/${schoolId}/selections/${id}`, data)

export const deleteSelection = (schoolId, id) =>
  client.delete(`/schools/${schoolId}/selections/${id}`)
