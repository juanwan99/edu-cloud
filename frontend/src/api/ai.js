import client from './client'

export const getRefTypes = () => client.get('/ai/ref-types')

export const getRefs = (type, { search, parentId, limit } = {}) => {
  const params = { type }
  if (search) params.search = search
  if (parentId) params.parent_id = parentId
  if (limit) params.limit = limit
  return client.get('/ai/refs', { params })
}
