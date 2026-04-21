import client from './client'

export const listTeachers = (params) => client.get('/teachers', { params })
export const createTeacher = (data) => client.post('/teachers', data)
export const updateTeacher = (id, data) => client.patch(`/teachers/${id}`, data)
export const deleteTeacher = (id) => client.delete(`/teachers/${id}`)
export const importTeachers = (file, role) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('role', role || 'subject_teacher')
  return client.post('/teachers/import', fd)
}
export const exportTeachers = () => client.get('/teachers/export', { responseType: 'blob' })
export const downloadTemplate = () => client.get('/teachers/export?template=1', { responseType: 'blob' })
