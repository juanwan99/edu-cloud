import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('F003 Slice G: publishCard 走 /api/v1/card/publish 单次调用', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
    global.localStorage = { getItem: vi.fn().mockReturnValue('fake-token') }

    document.body.innerHTML = '<div class="preview-wrap"><div class="page" data-paper="A3" data-side="A"><div>test</div></div></div>'
    window._getValues = () => ({ paperSize: 'A3' })
  })

  it('V2: publishCard 只调用 /api/v1/card/publish 一次，参数含 subject_id/exam_id', async () => {
    const mockPdfBlob = new Blob(['fake pdf'], { type: 'application/pdf' })
    global.fetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockPdfBlob),
    })

    const { publishCard } = await import('../card-editor/export.js')

    await publishCard('subject-123', 'exam-456', '答题卡.pdf')

    const apiCalls = global.fetch.mock.calls.filter(c => c[0] === '/api/v1/card/publish')
    expect(apiCalls.length).toBe(1)
    const call = apiCalls[0]
    expect(call[0]).toBe('/api/v1/card/publish')
    expect(call[1].method).toBe('POST')
    const body = JSON.parse(call[1].body)
    expect(body.subject_id).toBe('subject-123')
    expect(body.exam_id).toBe('exam-456')
    expect(body.paper_size).toBe('A3')
    expect(typeof body.html).toBe('string')
  })

  it('V2b: publishCard fetch 失败时 throw', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 500 })
    const { publishCard } = await import('../card-editor/export.js')
    await expect(publishCard('s1', 'e1', 'f.pdf')).rejects.toThrow(/500/)
  })
})
