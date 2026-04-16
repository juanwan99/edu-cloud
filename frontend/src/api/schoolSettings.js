import client from './client.js'

export const getSchoolSettings = (schoolId, category) =>
  client.get(`/schools/${schoolId}/settings`, { params: { category } })

export const updateSchoolSetting = (schoolId, data) =>
  client.patch(`/schools/${schoolId}/settings`, data)

export const getSchoolModules = (schoolId) =>
  client.get(`/schools/${schoolId}/modules`)

export const getEnabledModules = (schoolId) =>
  client.get(`/schools/${schoolId}/modules/enabled`)

export const toggleModule = (schoolId, moduleCode, enabled) =>
  client.patch(`/schools/${schoolId}/modules/${moduleCode}`, { enabled })
