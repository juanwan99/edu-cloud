import axios from 'axios'
import router from '../router/index.js'
import clientLogger from '../utils/clientLogger.js'

// Page-level trace ID (stable per page load, reused across requests)
let _pageTraceId = 'tr_' + Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, '0')).join('')

export function getTraceId() {
  return _pageTraceId
}

function randomHex12() {
  return Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, '0')).join('')
}

const client = axios.create({ baseURL: '/api/v1' })

client.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    try {
      const [, payloadB64] = token.split('.')
      if (payloadB64) {
        const base64 = payloadB64.replace(/-/g, '+').replace(/_/g, '/')
        const padded = base64.padEnd(base64.length + (4 - base64.length % 4) % 4, '=')
        const payload = JSON.parse(atob(padded))
        if (payload.exp && payload.exp * 1000 - Date.now() < 5 * 60 * 1000) {
          localStorage.removeItem('token')
          localStorage.removeItem('auth_state')
          window.location.href = '/login'
          return Promise.reject(new Error('Token expired'))
        }
      }
    } catch { /* malformed token — let backend 401 handle */ }
    config.headers.Authorization = `Bearer ${token}`
  }

  // Attach trace/request IDs
  const requestId = 'rq_' + randomHex12()
  config.headers['X-Trace-ID'] = _pageTraceId
  config.headers['X-Request-ID'] = requestId
  config._meta = {
    traceId: _pageTraceId,
    requestId,
    startTime: Date.now(),
  }

  return config
})

client.interceptors.response.use(
  res => {
    // Check for slow API calls (> 3000ms)
    const meta = res.config?._meta
    if (meta?.startTime) {
      const duration = Date.now() - meta.startTime
      if (duration > 3000) {
        clientLogger.slowApi(res.config, duration)
      }
    }
    return res
  },
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    } else {
      // Report non-401 API errors
      clientLogger.apiError(err, err.config)
    }
    return Promise.reject(err)
  }
)

export default client
