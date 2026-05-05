/**
 * Client-side logger — collects frontend errors/events and flushes to backend.
 *
 * Singleton. Auto-flushes every 5s, immediately on errors, and via sendBeacon
 * on page hide/unload. Stores unsent ERROR events in localStorage for retry.
 */

import router from '../router/index.js'

const FLUSH_INTERVAL_MS = 5000
const ENDPOINT = '/api/v1/client-logs'
const STORAGE_KEY = 'edu_log_queue'
const MAX_STORED = 20
const STORED_TTL_MS = 30 * 60 * 1000 // 30 min

function randomHex(len) {
  const arr = new Uint8Array(len / 2)
  crypto.getRandomValues(arr)
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('')
}

function nowISO() {
  // UTC+8 ISO string
  const d = new Date()
  const offset = 8 * 60
  const local = new Date(d.getTime() + offset * 60 * 1000)
  return local.toISOString().replace('Z', '+08:00')
}

function getCurrentUserId() {
  try {
    const state = localStorage.getItem('auth_state')
    if (!state) return null
    const parsed = JSON.parse(state)
    return parsed.userId || parsed.user_id || null
  } catch {
    return null
  }
}

class ClientLogger {
  constructor() {
    this.sessionId = crypto.randomUUID()
    this.traceId = 'tr_' + randomHex(12)
    this.queue = []
    this._timer = null
    this._startFlushTimer()
    this._setupVisibilityFlush()
    this._retryStoredEvents()
  }

  // --- Public API ---

  apiError(err, config) {
    // Prevent recursion: do not report errors from the logging endpoint itself
    if (config?.url === ENDPOINT || config?._meta?.isLogRequest) return

    this._push('error', 'api_error', {
      url: config?.url,
      method: config?.method,
      status: err?.response?.status,
      message: err?.message,
      trace_id: config?._meta?.traceId,
      request_id: config?._meta?.requestId,
      duration_ms: config?._meta?.startTime
        ? Date.now() - config._meta.startTime
        : undefined,
    })
  }

  jsError(error, info) {
    this._push('error', 'js_error', {
      message: error?.message || String(error),
      stack: error?.stack?.slice(0, 1000),
      info: info || undefined,
    })
  }

  routeError(error, to) {
    this._push('error', 'route_error', {
      message: error?.message || String(error),
      to_path: to?.fullPath || to?.path,
      to_name: to?.name,
    })
  }

  slowApi(config, duration) {
    this._push('warn', 'slow_api', {
      url: config?.url,
      method: config?.method,
      duration_ms: duration,
      trace_id: config?._meta?.traceId,
      request_id: config?._meta?.requestId,
    })
  }

  userAction(action, data) {
    this._push('info', 'user_action', {
      action,
      ...(data || {}),
    })
  }

  // --- Internal ---

  _push(level, eventType, data) {
    const event = {
      ts: nowISO(),
      level,
      event_type: eventType,
      page_route: router.currentRoute?.value?.fullPath || '',
      trace_id: this.traceId,
      data: data || {},
    }
    this.queue.push(event)

    // Immediate flush on errors
    if (level === 'error') {
      this._flush()
      this._storeErrorEvent(event)
    }
  }

  _startFlushTimer() {
    this._timer = setInterval(() => this._flush(), FLUSH_INTERVAL_MS)
  }

  _setupVisibilityFlush() {
    const beacon = () => {
      if (this.queue.length === 0) return
      const payload = JSON.stringify({
        client_session_id: this.sessionId,
        build_id: typeof __BUILD_ID__ !== 'undefined' ? __BUILD_ID__ : null,
        events: this.queue.splice(0, 50),
      })
      try {
        navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }))
      } catch { /* best effort */ }
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') beacon()
    })
    window.addEventListener('pagehide', beacon)
  }

  _flush() {
    if (this.queue.length === 0) return
    const events = this.queue.splice(0, 50)
    const payload = {
      client_session_id: this.sessionId,
      build_id: typeof __BUILD_ID__ !== 'undefined' ? __BUILD_ID__ : null,
      events,
    }
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {
      // On failure, re-queue error events for localStorage persistence
      for (const ev of events) {
        if (ev.level === 'error') this._storeErrorEvent(ev)
      }
    })
  }

  _storeErrorEvent(event) {
    try {
      const userId = getCurrentUserId()
      const key = userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY
      const raw = localStorage.getItem(key)
      let stored = raw ? JSON.parse(raw) : []
      // Filter expired
      const now = Date.now()
      stored = stored.filter(e => (now - e._stored_at) < STORED_TTL_MS)
      // Add new event (cap at MAX_STORED)
      stored.push({ ...event, _stored_at: now })
      if (stored.length > MAX_STORED) stored = stored.slice(-MAX_STORED)
      localStorage.setItem(key, JSON.stringify(stored))
    } catch { /* quota exceeded or private browsing */ }
  }

  _retryStoredEvents() {
    try {
      const userId = getCurrentUserId()
      const key = userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY
      const raw = localStorage.getItem(key)
      if (!raw) return
      const stored = JSON.parse(raw)
      const now = Date.now()
      const valid = stored.filter(e => (now - e._stored_at) < STORED_TTL_MS)
      if (valid.length === 0) {
        localStorage.removeItem(key)
        return
      }
      // Strip internal field and re-queue
      for (const ev of valid) {
        delete ev._stored_at
        this.queue.push(ev)
      }
      localStorage.removeItem(key)
    } catch { /* ignore */ }
  }
}

const clientLogger = new ClientLogger()
export default clientLogger
