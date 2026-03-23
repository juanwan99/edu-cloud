/**
 * aiChat SSE parsing tests — TG-01 fix
 *
 * Tests the SSE event stream parsing logic extracted from aiChat store.
 * Validates: line splitting, buffer handling, event type dispatching,
 * malformed data resilience.
 */
import { describe, it, expect } from 'vitest'

/**
 * Parse SSE lines into structured events — mirrors the logic in aiChat.js sendMessage().
 * Extracted here for unit testability without needing a full Pinia store + fetch mock.
 */
function parseSSELines(rawText) {
  const events = []
  const lines = rawText.split('\n')

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    const jsonStr = line.slice(6).trim()
    if (!jsonStr) continue

    try {
      events.push(JSON.parse(jsonStr))
    } catch {
      // ignore parse errors — same as aiChat.js
    }
  }
  return events
}

/**
 * Simulate chunked SSE stream processing with buffer — mirrors aiChat.js buffer logic.
 */
function processSSEChunks(chunks) {
  const assistantMsg = { content: '', tools: [], sessionId: null, error: null }
  let buffer = ''

  for (const chunk of chunks) {
    buffer += chunk
    const lines = buffer.split('\n')
    buffer = lines.pop() // keep incomplete trailing line

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const jsonStr = line.slice(6).trim()
      if (!jsonStr) continue

      try {
        const event = JSON.parse(jsonStr)
        if (event.type === 'answer') {
          assistantMsg.content += event.data?.content || ''
        } else if (event.type === 'tool_call') {
          assistantMsg.tools.push({ name: event.data?.tool, status: 'running' })
        } else if (event.type === 'tool_result') {
          const tool = assistantMsg.tools.find(t => t.name === event.data?.tool && t.status === 'running')
          if (tool) tool.status = 'done'
        } else if (event.type === 'error') {
          assistantMsg.error = event.data?.message || 'Unknown error'
        } else if (event.type === 'done') {
          if (event.session_id) assistantMsg.sessionId = event.session_id
        }
      } catch { /* ignore */ }
    }
  }

  return assistantMsg
}


describe('SSE line parsing', () => {
  it('parses answer events', () => {
    const raw = 'data: {"type":"answer","data":{"content":"Hello"}}\n'
    const events = parseSSELines(raw)
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('answer')
    expect(events[0].data.content).toBe('Hello')
  })

  it('parses multiple events', () => {
    const raw = [
      'data: {"type":"tool_call","data":{"tool":"get_scores"}}',
      'data: {"type":"tool_result","data":{"tool":"get_scores"}}',
      'data: {"type":"answer","data":{"content":"Results..."}}',
      'data: {"type":"done","session_id":"sess-123"}',
    ].join('\n') + '\n'

    const events = parseSSELines(raw)
    expect(events).toHaveLength(4)
    expect(events[0].type).toBe('tool_call')
    expect(events[3].session_id).toBe('sess-123')
  })

  it('ignores non-data lines', () => {
    const raw = 'event: message\nid: 1\ndata: {"type":"answer","data":{"content":"ok"}}\n\n'
    const events = parseSSELines(raw)
    expect(events).toHaveLength(1)
  })

  it('ignores empty data lines', () => {
    const raw = 'data: \ndata: {"type":"answer","data":{"content":"ok"}}\n'
    const events = parseSSELines(raw)
    expect(events).toHaveLength(1)
  })

  it('ignores malformed JSON gracefully', () => {
    const raw = 'data: {broken json\ndata: {"type":"answer","data":{"content":"ok"}}\n'
    const events = parseSSELines(raw)
    expect(events).toHaveLength(1)
    expect(events[0].data.content).toBe('ok')
  })
})


describe('SSE chunked stream processing', () => {
  it('handles complete lines in single chunk', () => {
    const msg = processSSEChunks([
      'data: {"type":"answer","data":{"content":"Hello "}}\ndata: {"type":"answer","data":{"content":"world"}}\ndata: {"type":"done","session_id":"s1"}\n',
    ])
    expect(msg.content).toBe('Hello world')
    expect(msg.sessionId).toBe('s1')
  })

  it('handles line split across two chunks', () => {
    const msg = processSSEChunks([
      'data: {"type":"answer","data":{"con',
      'tent":"split"}}\n',
    ])
    expect(msg.content).toBe('split')
  })

  it('tracks tool_call → tool_result lifecycle', () => {
    const msg = processSSEChunks([
      'data: {"type":"tool_call","data":{"tool":"get_scores"}}\n',
      'data: {"type":"tool_result","data":{"tool":"get_scores"}}\n',
    ])
    expect(msg.tools).toHaveLength(1)
    expect(msg.tools[0].name).toBe('get_scores')
    expect(msg.tools[0].status).toBe('done')
  })

  it('captures error events', () => {
    const msg = processSSEChunks([
      'data: {"type":"error","data":{"message":"Rate limited"}}\n',
    ])
    expect(msg.error).toBe('Rate limited')
  })

  it('handles answer with missing content gracefully', () => {
    const msg = processSSEChunks([
      'data: {"type":"answer","data":{}}\n',
      'data: {"type":"answer","data":{"content":"ok"}}\n',
    ])
    expect(msg.content).toBe('ok')
  })

  it('handles multiple chunks with partial lines', () => {
    // Simulates network fragmentation
    const msg = processSSEChunks([
      'data: {"type":"ans',
      'wer","data":{"content":"A"}}\nda',
      'ta: {"type":"answer","data":{"content":"B"}}\n',
    ])
    expect(msg.content).toBe('AB')
  })
})
