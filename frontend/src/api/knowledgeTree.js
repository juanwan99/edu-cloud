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
