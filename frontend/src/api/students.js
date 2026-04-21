import client from './client'

export const listStudents = (params) => client.get('/students', { params })
export const createStudent = (data) => client.post('/students', data)
export const updateStudent = (id, data) => client.patch(`/students/${id}`, data)
export const deleteStudent = (id) => client.delete(`/students/${id}`)
export const importStudents = (file, { classId, grade } = {}) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('class_id', classId || '')
  fd.append('grade', grade || '')
  return client.post('/students/import', fd)
}
export const listClasses = (params) => client.get('/classes', { params })
export const listGrades = () => client.get('/grades')
export const exportStudents = (params) => client.get('/students/export', { params, responseType: 'blob' })
export const listSelections = (schoolId) => client.get(`/schools/${schoolId}/selections`, { params: { is_active: true } })
