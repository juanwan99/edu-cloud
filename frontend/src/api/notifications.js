import client from './client.js'

export const getNotifications = (params = {}) => client.get('/notifications', { params })
