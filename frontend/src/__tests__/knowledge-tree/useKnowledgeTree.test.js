import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API module
vi.mock('../../api/knowledgeTree', () => ({
  getGraph: vi.fn(),
  getMastery: vi.fn(),
  editGraph: vi.fn(),
  qualityCheck: vi.fn(),
}))

import { getGraph, editGraph, qualityCheck } from '../../api/knowledgeTree'
import { useKnowledgeTree } from '../../components/knowledge-tree/useKnowledgeTree'

describe('useKnowledgeTree', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loadGraph passes includeDraft parameter', async () => {
    getGraph.mockResolvedValue({
      data: { navigation: [], graph: { nodes: [], edges: [] } },
    })
    const { loadGraph } = useKnowledgeTree()
    await loadGraph('M1', false)
    expect(getGraph).toHaveBeenCalledWith('M1', false)
  })

  it('loadGraph defaults includeDraft to true', async () => {
    getGraph.mockResolvedValue({
      data: { navigation: [], graph: { nodes: [], edges: [] } },
    })
    const { loadGraph } = useKnowledgeTree()
    await loadGraph('all')
    expect(getGraph).toHaveBeenCalledWith('all', true)
  })

  it('loadQuality calls qualityCheck and populates issues', async () => {
    qualityCheck.mockResolvedValue({
      data: {
        module: 'M1',
        summary: { total_nodes: 5, total_edges: 3, issues_by_severity: { HIGH: 1 } },
        issues: [{ rule_id: 'Q1', severity: 'HIGH', message: '孤立', node_ids: ['A'], edge_ids: [] }],
      },
    })
    const { loadQuality, qualityIssues, qualitySummary } = useKnowledgeTree()
    await loadQuality('M1')
    expect(qualityCheck).toHaveBeenCalledWith('M1')
    expect(qualityIssues.value.length).toBe(1)
    expect(qualityIssues.value[0].rule_id).toBe('Q1')
    expect(qualitySummary.value.total_nodes).toBe(5)
  })

  it('loadQuality propagates errors (does not swallow)', async () => {
    qualityCheck.mockRejectedValue(new Error('500 Server Error'))
    const { loadQuality } = useKnowledgeTree()
    await expect(loadQuality('M1')).rejects.toThrow('500 Server Error')
  })

  it('applyEdit reloads graph after successful edit', async () => {
    editGraph.mockResolvedValue({ data: { success: true, applied: 1 } })
    getGraph.mockResolvedValue({
      data: { navigation: [], graph: { nodes: [], edges: [] } },
    })
    const { applyEdit } = useKnowledgeTree()
    await applyEdit([{ op: 'set_review_status', edge_id: 1, status: 'teacher_reviewed' }])
    expect(editGraph).toHaveBeenCalledTimes(1)
    expect(getGraph).toHaveBeenCalledTimes(1) // reload after edit
  })

  it('loadAllModulesQuality calls qualityCheck for M1-M5', async () => {
    qualityCheck.mockResolvedValue({
      data: { module: 'M1', summary: { issues_by_severity: { HIGH: 1, MED: 2 } }, issues: [] },
    })
    const { loadAllModulesQuality, modulesQuality } = useKnowledgeTree()
    await loadAllModulesQuality()
    expect(qualityCheck).toHaveBeenCalledTimes(5)
    const calls = qualityCheck.mock.calls.map(c => c[0])
    expect(calls.sort()).toEqual(['M1', 'M2', 'M3', 'M4', 'M5'])
    expect(modulesQuality.value.M1).toEqual({ highCount: 1, medCount: 2 })
  })

  it('loadAllModulesQuality tolerates partial failures with named-module precision', async () => {
    // F002 修复：每个模块精确具名 + 失败位置固定 + 成功模块保留真实计数 + 失败模块回退为零。
    // 反证：如果 rejected 路径不回退或返回 undefined，M2 的断言会失败；
    //       如果把 fulfilled.summary 错误映射（例如漏掉 MED），M1/M3/M4/M5 的精确计数会不匹配。
    const byModule = {
      M1: { HIGH: 1, MED: 2 },
      M3: { HIGH: 3, MED: 0 },
      M4: { HIGH: 0, MED: 4 },
      M5: { HIGH: 5, MED: 5 },
    }
    qualityCheck.mockImplementation(async (mod) => {
      if (mod === 'M2') throw new Error('network 500')
      return { data: { module: mod, summary: { issues_by_severity: byModule[mod] }, issues: [] } }
    })

    const { loadAllModulesQuality, modulesQuality } = useKnowledgeTree()
    await loadAllModulesQuality()

    // 断言 1: 5 个 key 全量存在
    expect(Object.keys(modulesQuality.value).sort()).toEqual(['M1', 'M2', 'M3', 'M4', 'M5'])

    // 断言 2: 成功模块保留各自真实计数
    expect(modulesQuality.value.M1).toEqual({ highCount: 1, medCount: 2 })
    expect(modulesQuality.value.M3).toEqual({ highCount: 3, medCount: 0 })
    expect(modulesQuality.value.M4).toEqual({ highCount: 0, medCount: 4 })
    expect(modulesQuality.value.M5).toEqual({ highCount: 5, medCount: 5 })

    // 断言 3: 失败模块 M2 精确回退为零（不是 undefined、不是保留上一次值）
    expect(modulesQuality.value.M2).toEqual({ highCount: 0, medCount: 0 })

    // 断言 4: 调用次数 = 5（未因单个失败中断）
    expect(qualityCheck).toHaveBeenCalledTimes(5)
  })
})
