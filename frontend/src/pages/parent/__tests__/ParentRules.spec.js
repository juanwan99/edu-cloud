/**
 * F004 Round 3: ParentRules 字段映射契约测试
 *
 * 目的: 防止 `item.points` 被悄悄改回 `item.default_points` 无感回退。
 * mock API 返回只含 `points` 字段，若模板误用 `default_points` → 渲染为空 → 断言失败。
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

// Mock API — 注意 mock 数据仅提供 `points` 字段，不提供 `default_points`
vi.mock('../../../api/conduct', () => ({
  getClassRulesParent: vi.fn(async () => ({
    data: {
      categories: [
        {
          id: 'cat-1',
          name: '学习表现',
          items: [
            { id: 'item-1', name: '课堂认真', points: 5 },
            { id: 'item-2', name: '迟到', points: -3 },
            { id: 'item-3', name: '自律', points: 0 },
          ],
        },
      ],
    },
  })),
}))

import ParentRules from '../ParentRules.vue'

function mountWithChild(child) {
  return mount(ParentRules, {
    global: {
      provide: {
        currentChild: ref(child),
      },
      stubs: {
        // naive-ui 内部 name 为短名（Card/Collapse/CollapseItem/List/ListItem/Tag/Empty/Spin）
        Card: { template: '<div><slot /></div>' },
        Spin: { template: '<div><slot /></div>' },
        Collapse: { template: '<div><slot /></div>' },
        // CollapseItem 默认折叠不渲染内容；stub 强制展开渲染 slot
        CollapseItem: { template: '<div><slot /></div>', props: ['title', 'name'] },
        List: { template: '<ul><slot /></ul>' },
        ListItem: { template: '<li><slot /></li>' },
        Tag: { template: '<span class="tag"><slot /></span>' },
        Empty: {
          template: '<div class="empty">{{ description }}</div>',
          props: ['description'],
        },
        RadioGroup: { template: '<div><slot /></div>' },
        RadioButton: { template: '<button><slot /></button>' },
        Input: { template: '<input />' },
      },
    },
  })
}

describe('ParentRules field mapping (F004 R3)', () => {
  it('renders item.points value from API response (not item.default_points)', async () => {
    const wrapper = mountWithChild({ class_id: 'cls-A' })
    // 等待 watch(currentChild, ..., { immediate: true }) 完成异步 API fetch
    await flushPromises()
    await nextTick()
    await flushPromises()
    await nextTick()

    const text = wrapper.text()
    // 正分渲染为 +5
    expect(text).toContain('+5')
    // 负分渲染为 -3（非 +-3）
    expect(text).toContain('-3')
    // 0 分渲染为 +0（template 用 points >= 0 ? '+' : ''）
    expect(text).toContain('+0')
    // 条目名称也应在
    expect(text).toContain('课堂认真')
    expect(text).toContain('迟到')
  })

  it('falls back to empty state when currentChild has no class_id', async () => {
    const wrapper = mountWithChild({ class_id: null })
    await nextTick()
    await nextTick()
    // 未触发 fetch，categories 为空 → "暂无班级规则"
    expect(wrapper.text()).toContain('暂无班级规则')
  })
})
