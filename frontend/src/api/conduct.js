import axios from 'axios'
import api from './client'

// Separate axios instance for parent-authenticated calls (reads cp_token)
const parentClient = axios.create({ baseURL: '/api/v1' })
parentClient.interceptors.request.use(config => {
  const token = localStorage.getItem('cp_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Parent Auth (public, no token needed) ──
export const getInviteInfo = (code) => api.get(`/conduct/invite/${code}/info`)
export const parentRegister = (data) => api.post('/conduct/parent/register', data)
export const parentLogin = (data) => api.post('/conduct/parent/login', data)

// ── Parent Authenticated (use parentClient with cp_token) ──
export const getParentMe = () => parentClient.get('/conduct/parent/me')
export const bindChild = (data) => parentClient.post('/conduct/parent/bind', data)
export const getChildren = () => parentClient.get('/conduct/parent/children')
export const getChildRecords = (studentId, params) =>
  parentClient.get(`/conduct/parent/children/${studentId}/records`, { params })
export const getChildRankings = (studentId) =>
  parentClient.get(`/conduct/parent/children/${studentId}/rankings`)
export const getClassRulesParent = (classId) =>
  parentClient.get(`/conduct/parent/classes/${classId}/rules`)
export const getChildExams = (studentId) =>
  parentClient.get(`/conduct/parent/children/${studentId}/exams`)
export const getChildScores = (studentId, params) =>
  parentClient.get(`/conduct/parent/children/${studentId}/scores`, { params })
export const getChildErrorBook = (studentId, params) =>
  parentClient.get(`/conduct/parent/children/${studentId}/error-book`, { params })
export const updateParentProfile = (data) => parentClient.put('/conduct/parent/profile', data)
export const changeParentPassword = (data) => parentClient.put('/conduct/parent/password', data)

// ── Admin Config (use main api client with platform token) ──
export const getConductConfig = (classId) =>
  api.get(`/conduct/classes/${classId}/config`)
export const updateConductConfig = (classId, data) =>
  api.put(`/conduct/classes/${classId}/config`, data)
export const regenerateInviteCode = (classId) =>
  api.post(`/conduct/classes/${classId}/config/regenerate-code`)
export const getParentsList = (classId) =>
  api.get(`/conduct/classes/${classId}/parents`)
export const removeParent = (classId, userId) =>
  api.delete(`/conduct/classes/${classId}/parents/${userId}`)

// ── Records ──
export const addPoints = (classId, data) =>
  api.post(`/conduct/classes/${classId}/records`, data)
export const addPointsBatch = (classId, data) =>
  api.post(`/conduct/classes/${classId}/records/batch`, data)
export const getRecords = (classId, params) =>
  api.get(`/conduct/classes/${classId}/records`, { params })
export const deleteRecord = (classId, recordId) =>
  api.delete(`/conduct/classes/${classId}/records/${recordId}`)
export const getStudentRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/rankings/students`, { params })
export const getGroupRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/rankings/groups`, { params })

// ── Rules ──
export const getRules = (classId) =>
  api.get(`/conduct/classes/${classId}/rules`)
export const createCategory = (classId, data) =>
  api.post(`/conduct/classes/${classId}/rules/categories`, data)
export const updateCategory = (classId, catId, data) =>
  api.put(`/conduct/classes/${classId}/rules/categories/${catId}`, data)
export const deleteCategory = (classId, catId) =>
  api.delete(`/conduct/classes/${classId}/rules/categories/${catId}`)
export const createRuleItem = (classId, catId, data) =>
  api.post(`/conduct/classes/${classId}/rules/categories/${catId}/items`, data)
export const updateRuleItem = (classId, catId, itemId, data) =>
  api.put(`/conduct/classes/${classId}/rules/categories/${catId}/items/${itemId}`, data)
export const deleteRuleItem = (classId, catId, itemId) =>
  api.delete(`/conduct/classes/${classId}/rules/categories/${catId}/items/${itemId}`)

// ── Groups ──
export const getGroups = (classId) =>
  api.get(`/conduct/classes/${classId}/groups`)
export const createGroup = (classId, data) =>
  api.post(`/conduct/classes/${classId}/groups`, data)
export const deleteGroup = (classId, groupId) =>
  api.delete(`/conduct/classes/${classId}/groups/${groupId}`)
export const addGroupMembers = (classId, groupId, data) =>
  api.post(`/conduct/classes/${classId}/groups/${groupId}/members`, data)
export const removeGroupMember = (classId, groupId, studentId) =>
  api.delete(`/conduct/classes/${classId}/groups/${groupId}/members/${studentId}`)

// ── Semesters ──
export const getSemesters = (classId) =>
  api.get(`/conduct/classes/${classId}/semesters`)
export const createSemester = (classId, data) =>
  api.post(`/conduct/classes/${classId}/semesters`, data)
export const activateSemester = (classId, semId) =>
  api.put(`/conduct/classes/${classId}/semesters/${semId}/activate`)

// ── Export ──
export const exportRecords = (classId, params) =>
  api.get(`/conduct/classes/${classId}/export/records`, { params, responseType: 'blob' })
export const exportRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/export/rankings`, { params, responseType: 'blob' })

// ── Scope-adaptive overview ──
export const getConductOverview = () => api.get('/conduct/overview')

// ── School-level rules ──
export const getSchoolRules = (schoolId) => api.get(`/conduct/schools/${schoolId}/rules`)
export const createSchoolCategory = (schoolId, data) => api.post(`/conduct/schools/${schoolId}/rules/categories`, data)

// ── Parent notifications ──
export const getParentNotifications = (unreadOnly = false) =>
  parentClient.get('/conduct/parent/notifications', { params: { unread_only: unreadOnly } })
export const markNotificationsRead = () =>
  parentClient.post('/conduct/parent/notifications/read-all')

// ── Semester reports ──
export const getClassReport = (classId, params) =>
  api.get(`/conduct/classes/${classId}/report`, { params })
export const getSchoolReport = (schoolId, params) =>
  api.get(`/conduct/schools/${schoolId}/report`, { params })
