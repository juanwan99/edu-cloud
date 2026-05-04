import client from './client'

export const getGraph = (module = 'all', includeDraft = true) =>
  client.get('/knowledge-tree/graph', { params: { module, include_draft: includeDraft } })

export const getMastery = (studentId, module = 'all') =>
  client.get('/knowledge-tree/mastery', { params: { student_id: studentId, module } })

export const getNodeDetail = (nodeId, signal) =>
  client.get(`/knowledge-tree/graph/${nodeId}/detail`, { signal })

export const searchConcepts = (q) =>
  client.get('/knowledge-tree/search', { params: { q } })

export const editGraph = (operations) =>
  client.post('/knowledge-tree/edit', { operations })

export const qualityCheck = (module = 'all') =>
  client.get('/knowledge-tree/quality-check', { params: { module } })

export async function getExamItems(nodeId, page = 1, pageSize = 20) {
  const resp = await client.get(
    `/knowledge-tree/graph/${nodeId}/exam-items`,
    { params: { page, page_size: pageSize } }
  )
  return resp.data
}

export async function getStatsOverview(module = 'all') {
  const resp = await client.get('/knowledge-tree/stats/overview', {
    params: { module }
  })
  return resp.data
}

export async function getCourseMapOverview() {
  const resp = await client.get('/knowledge-tree/course-map/overview')
  return resp.data
}

export async function getCourseMapModule(module) {
  const resp = await client.get(`/knowledge-tree/course-map/module/${module}`)
  return resp.data
}

export async function getCourseMapStudyUnit(suId) {
  const resp = await client.get(`/knowledge-tree/course-map/study-unit/${encodeURIComponent(suId)}`)
  return resp.data
}
