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
    return parsed.user?.id || null
  } catch {
    return null
  }
}

function _getTokenHash() {
  // Simple hash of the current JWT token for user identity binding.
  // Used to ensure stored error events belong to the current logged-in user.
  try {
    const token = localStorage.getItem('token')
    if (!token) return null
    // Use a simple hash (sum of char codes mod a large prime) for lightweight identity check
    let hash = 0
    for (let i = 0; i < token.length; i++) {
      hash = ((hash << 5) - hash + token.charCodeAt(i)) | 0
    }
    return hash.toString(36)
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

  setupConsoleCapture() {
    const self = this
    const origError = console.error
    const origWarn = console.warn
    console.error = function (...args) {
      self._push('error', 'console_error', {
        message: args.map(a => (a instanceof Error ? a.message : String(a))).join(' '),
        stack: args.find(a => a instanceof Error)?.stack?.slice(0, 1000),
      })
      origError.apply(console, args)
    }
    console.warn = function (...args) {
      self._push('warn', 'console_warn', {
        message: args.map(a => String(a)).join(' '),
      })
      origWarn.apply(console, args)
    }
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
    }).then(response => {
      if (response.ok) {
        // Clear persisted error queue on successful flush to prevent duplicates
        const userId = getCurrentUserId()
        const key = userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY
        localStorage.removeItem(key)
      }
    }).catch(() => {
      // On failure, re-queue error events for localStorage persistence
      for (const ev of events) {
        if (ev.level === 'error') this._storeErrorEvent(ev)
      }
    })
  }

  _storeErrorEvent(event) {
    // Only persist error-level events to localStorage
    if (event.level !== 'error') return
    try {
      const userId = getCurrentUserId()
      const tokenHash = _getTokenHash()
      const key = userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY
      const raw = localStorage.getItem(key)
      let stored = raw ? JSON.parse(raw) : []
      // Filter expired
      const now = Date.now()
      stored = stored.filter(e => (now - e._stored_at) < STORED_TTL_MS)
      // Add new event (cap at MAX_STORED), tag with token hash for user binding
      stored.push({ ...event, _stored_at: now, _token_hash: tokenHash })
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
      const currentHash = _getTokenHash()
      // Only restore events that are not expired AND match the current user's token
      // Events without _token_hash are discarded (legacy/unverifiable)
      const valid = stored.filter(e =>
        (now - e._stored_at) < STORED_TTL_MS &&
        e._token_hash && e._token_hash === currentHash
      )
      if (valid.length === 0) {
        localStorage.removeItem(key)
        return
      }
      // Strip internal fields and re-queue
      for (const ev of valid) {
        delete ev._stored_at
        delete ev._token_hash
        this.queue.push(ev)
      }
      localStorage.removeItem(key)
    } catch { /* ignore */ }
  }
}

const clientLogger = new ClientLogger()
export default clientLogger
