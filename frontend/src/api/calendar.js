import client from './client'

export const listCalendarEvents = (params) => client.get('/calendar/events', { params })
export const createCalendarEvent = (data) => client.post('/calendar/events', data)
export const deleteCalendarEvent = (eventId) => client.delete(`/calendar/events/${eventId}`)
