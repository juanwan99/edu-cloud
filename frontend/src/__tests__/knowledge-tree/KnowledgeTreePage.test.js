import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'

/**
 * KnowledgeTreePage 页面级逻辑测试。
 * 直接测试页面组件需要大量 mock（auth store, API, 子组件）。
 * 这里提取并验证关键页面级逻辑：canEdit watcher + handleEdit 流程。
 */

// 模拟 canEdit watcher 行为
describe('KnowledgeTreePage canEdit watcher logic', () => {
  it('resets activeTab to graph when canEdit becomes false', async () => {
    const canEdit = ref(true)
    const activeTab = ref('review')

    // 模拟 watch 逻辑（与 KnowledgeTreePage.vue 一致）
    const { watch } = await import('vue')
    watch(canEdit, (val) => {
      if (!val && activeTab.value === 'review') {
        activeTab.value = 'graph'
      }
    })

    canEdit.value = false
    await nextTick()
    expect(activeTab.value).toBe('graph')
  })

  it('keeps activeTab when canEdit becomes false but tab is graph', async () => {
    const canEdit = ref(true)
    const activeTab = ref('graph')

    const { watch } = await import('vue')
    watch(canEdit, (val) => {
      if (!val && activeTab.value === 'review') {
        activeTab.value = 'graph'
      }
    })

    canEdit.value = false
    await nextTick()
    expect(activeTab.value).toBe('graph')
  })
})

// 模拟 handleEdit 流程（验证 loadQuality 被调用）
describe('KnowledgeTreePage handleEdit logic', () => {
  it('calls loadQuality after successful edit when canEdit=true', async () => {
    const loadQualityCalled = ref(false)
    const canEdit = ref(true)
    const selectedModule = ref('M1')

    // 模拟 handleEdit 逻辑
    const applyEdit = vi.fn().mockResolvedValue({})
    const loadQuality = vi.fn().mockImplementation(() => { loadQualityCalled.value = true })

    async function handleEdit(operations) {
      await applyEdit(operations)
      if (canEdit.value) {
        await loadQuality(selectedModule.value)
      }
    }

    await handleEdit([{ op: 'set_review_status', edge_id: 1, status: 'teacher_reviewed' }])
    expect(applyEdit).toHaveBeenCalledTimes(1)
    expect(loadQuality).toHaveBeenCalledWith('M1')
  })

  it('does not call loadQuality when canEdit=false', async () => {
    const canEdit = ref(false)
    const selectedModule = ref('M1')

    const applyEdit = vi.fn().mockResolvedValue({})
    const loadQuality = vi.fn()

    async function handleEdit(operations) {
      await applyEdit(operations)
      if (canEdit.value) {
        await loadQuality(selectedModule.value)
      }
    }

    await handleEdit([{ op: 'set_review_status', edge_id: 1, status: 'teacher_reviewed' }])
    expect(loadQuality).not.toHaveBeenCalled()
  })
})

// Batch 2 routing logic 真实覆盖移至 KnowledgeTreePage.mount.test.js
// 原先的本地镜像测试（2026-04-10 Batch 2 R0）在 R1 修复 F-001/F-002 后编码了过时的语义
// （`handleModuleSelect('all')` 曾不调 loadQuality），已删除以避免测试与实现语义漂移。
// 参考: codex-review R2 finding F-005（test-gap）
