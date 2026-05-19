import client from './client'

export function createImport(formData) {
  return client.post('/exam-imports', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function updateMapping(importId, mapping) {
  return client.patch(`/exam-imports/${importId}/mapping`, mapping)
}

export function commitImport(importId) {
  return client.post(`/exam-imports/${importId}/commit`)
}

export function getImport(importId) {
  return client.get(`/exam-imports/${importId}`)
}

export function cancelImport(importId) {
  return client.delete(`/exam-imports/${importId}`)
}
