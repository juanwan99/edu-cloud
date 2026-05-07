import client from './client.js'

export function startImpersonation(schoolId, role, scope = {}) {
  return client.post('/auth/impersonate', {
    school_id: schoolId,
    role,
    scope,
  })
}

export function exitImpersonation() {
  return client.post('/auth/impersonate/exit')
}
