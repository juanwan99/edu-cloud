import client from './client'

export const listSemesters = (params) => client.get('/academic/semesters', { params })
export const createSemester = (data) => client.post('/academic/semesters', data)
export const getCurrentSemester = () => client.get('/academic/semesters/current')
export const updateSemester = (id, data) => client.patch(`/academic/semesters/${id}`, data)
export const activateSemester = (id) => client.post(`/academic/semesters/${id}/activate`)

export const getPeriods = (semesterId) => client.get('/academic/periods', { params: { semester_id: semesterId } })
export const setPeriods = (data) => client.put('/academic/periods', data)

export const getTimetable = (params) => client.get('/academic/timetable', { params })
export const saveTimetable = (classId, data) => client.put(`/academic/timetable/${classId}`, data)
export const getTimetableStats = (params) => client.get('/academic/timetable/stats', { params })
