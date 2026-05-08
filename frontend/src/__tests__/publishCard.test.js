import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the Axios client module
const mockPost = vi.fn()
vi.mock('../api/client', () => ({
  default: { post: mockPost, get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

describe('F003 Slice G: publishCard 走 Axios client.post 单次调用', () => {
  beforeEach(() => {
    mockPost.mockReset()
    global.localStorage = { getItem: vi.fn().mockReturnValue('fake-token') }

    document.body.innerHTML = '<div class="preview-wrap"><div class="page" data-paper="A3" data-side="A"><div>test</div></div></div>'
    window._getValues = () => ({ paperSize: 'A3' })
  })

  it('V2: publishCard 只调用 client.post(/card/publish) 一次，参数含 subject_id/exam_id', async () => {
    const mockPdfBlob = new Blob(['fake pdf'], { type: 'application/pdf' })
    mockPost.mockResolvedValue({ data: mockPdfBlob, status: 200 })

    const { publishCard } = await import('../card-editor/export.js')

    await publishCard('subject-123', 'exam-456', '答题卡.pdf')

    const publishCalls = mockPost.mock.calls.filter(c => c[0] === '/card/publish')
    expect(publishCalls.length).toBe(1)
    const [path, body, config] = publishCalls[0]
    expect(path).toBe('/card/publish')
    expect(body.subject_id).toBe('subject-123')
    expect(body.exam_id).toBe('exam-456')
    expect(body.paper_size).toBe('A3')
    expect(typeof body.html).toBe('string')
    expect(config.responseType).toBe('blob')
  })

  it('V2b: publishCard client.post 失败时 throw', async () => {
    mockPost.mockRejectedValue(new Error('Request failed with status code 500'))
    const { publishCard } = await import('../card-editor/export.js')
    await expect(publishCard('s1', 'e1', 'f.pdf')).rejects.toThrow(/500/)
  })
})
