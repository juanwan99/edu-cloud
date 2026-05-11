/**
 * SSE parser tests — TG-01 fix (R2 refactor: imports real sseParser.js)
 *
 * Tests the actual createSSEProcessor from src/utils/sseParser.js,
 * which is used by the aiChat store. Changes to the real parser
 * will cause these tests to fail.
 */
import { describe, it, expect } from 'vitest'
import { createSSEProcessor } from '../utils/sseParser.js'

/** Helper: push chunks through a processor and collect results. */
function processChunks(chunks) {
  const result = { content: '', tools: [], error: null, sessionId: null }

  const processor = createSSEProcessor({
    onAnswer(content) { result.content += content },
    onToolCall(tool) { result.tools.push({ name: tool, status: 'running' }) },
    onToolResult(tool) {
      const t = result.tools.find(x => x.name === tool && x.status === 'running')
      if (t) t.status = 'done'
    },
    onError(msg) { result.error = msg },
    onDone(sid) { result.sessionId = sid },
  })

  for (const chunk of chunks) {
    processor.push(chunk)
  }

  return result
}


describe('createSSEProcessor (real import)', () => {
  it('parses answer events and concatenates content', () => {
    const result = processChunks([
      'data: {"type":"answer","data":{"content":"Hello "}}\ndata: {"type":"answer","data":{"content":"world"}}\n',
    ])
    expect(result.content).toBe('Hello world')
  })

  it('handles line split across two chunks (buffer)', () => {
    const result = processChunks([
      'data: {"type":"answer","data":{"con',
      'tent":"split"}}\n',
    ])
    expect(result.content).toBe('split')
  })

  it('tracks tool_call → tool_result lifecycle', () => {
    const result = processChunks([
      'data: {"type":"tool_call","data":{"tool":"get_scores"}}\n',
      'data: {"type":"tool_result","data":{"tool":"get_scores"}}\n',
    ])
    expect(result.tools).toHaveLength(1)
    expect(result.tools[0].name).toBe('get_scores')
    expect(result.tools[0].status).toBe('done')
  })

  it('captures error events', () => {
    const result = processChunks([
      'data: {"type":"error","data":{"message":"Rate limited"}}\n',
    ])
    expect(result.error).toBe('Rate limited')
  })

  it('captures session_id from done event', () => {
    const result = processChunks([
      'data: {"type":"done","data":{"session_id":"sess-abc"}}\n',
    ])
    expect(result.sessionId).toBe('sess-abc')
  })

  it('handles answer with missing content gracefully', () => {
    const result = processChunks([
      'data: {"type":"answer","data":{}}\n',
      'data: {"type":"answer","data":{"content":"ok"}}\n',
    ])
    expect(result.content).toBe('ok')
  })

  it('ignores non-data lines', () => {
    const result = processChunks([
      'event: message\nid: 1\ndata: {"type":"answer","data":{"content":"ok"}}\n\n',
    ])
    expect(result.content).toBe('ok')
  })

  it('ignores empty data lines', () => {
    const result = processChunks([
      'data: \ndata: {"type":"answer","data":{"content":"ok"}}\n',
    ])
    expect(result.content).toBe('ok')
  })

  it('ignores malformed JSON gracefully', () => {
    const result = processChunks([
      'data: {broken json\ndata: {"type":"answer","data":{"content":"ok"}}\n',
    ])
    expect(result.content).toBe('ok')
  })

  it('handles multiple chunks with partial lines', () => {
    const result = processChunks([
      'data: {"type":"ans',
      'wer","data":{"content":"A"}}\nda',
      'ta: {"type":"answer","data":{"content":"B"}}\n',
    ])
    expect(result.content).toBe('AB')
  })

  it('handles full SSE session flow', () => {
    const result = processChunks([
      'data: {"type":"tool_call","data":{"tool":"exam_list"}}\n',
      'data: {"type":"tool_result","data":{"tool":"exam_list"}}\n',
      'data: {"type":"answer","data":{"content":"Found 3 exams."}}\n',
      'data: {"type":"done","data":{"session_id":"s-final"}}\n',
    ])
    expect(result.tools).toHaveLength(1)
    expect(result.tools[0].status).toBe('done')
    expect(result.content).toBe('Found 3 exams.')
    expect(result.sessionId).toBe('s-final')
  })
})
