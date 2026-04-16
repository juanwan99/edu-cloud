import client from './client'

export const login = (schoolCode, username, password) =>
  client.post('/auth/login', { school_code: schoolCode, username, password })
