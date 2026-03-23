import client from './client'

export const listSchools = () => client.get('/schools')
export const createSchool = (data) => client.post('/schools', data)
