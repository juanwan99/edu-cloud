/**
 * SSE event stream parser — shared between aiChat store and tests.
 *
 * Processes chunked SSE data with buffer management to handle
 * lines split across network chunks.
 */

/**
 * Create a stateful SSE processor that accumulates chunks and dispatches events.
 * @param {object} handlers - { onAnswer, onToolCall, onToolResult, onError, onDone }
 * @returns {{ push(chunk: string): void, flush(): void }}
 */
export function createSSEProcessor(handlers = {}) {
  let buffer = ''

  function processLine(line) {
    if (!line.startsWith('data: ')) return
    const jsonStr = line.slice(6).trim()
    if (!jsonStr) return

    try {
      const event = JSON.parse(jsonStr)
      if (event.type === 'answer') {
        handlers.onAnswer?.(event.data?.content || '')
      } else if (event.type === 'thinking') {
        handlers.onThinking?.(event.data?.content || '')
      } else if (event.type === 'plan') {
        handlers.onPlan?.(event.data?.tasks || [])
      } else if (event.type === 'task_update') {
        handlers.onTaskUpdate?.(event.data)
      } else if (event.type === 'tool_call') {
        handlers.onToolCall?.(event.data?.tool, event.data?.arguments)
      } else if (event.type === 'tool_result') {
        handlers.onToolResult?.(event.data?.tool, event.data?.result)
      } else if (event.type === 'confirmation_required') {
        handlers.onConfirmation?.(event.data)
      } else if (event.type === 'error') {
        handlers.onError?.(event.data?.message || 'Unknown error')
      } else if (event.type === 'done') {
        handlers.onDone?.(event.data?.session_id)
      }
    } catch { /* ignore malformed JSON */ }
  }

  return {
    push(chunk) {
      buffer += chunk
      const lines = buffer.split('\n')
      buffer = lines.pop() // keep incomplete trailing line
      for (const line of lines) {
        processLine(line)
      }
    },
    flush() {
      if (buffer) {
        processLine(buffer)
        buffer = ''
      }
    },
  }
}
