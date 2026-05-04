/**
 * ParentOverview.vue source text tests + mount-based tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains student info, score summary, quick entries, records
 *  3. API calls for records, scores, rankings
 *  4. Guide card for unbound state
 *  5. Error handling in data fetching
 *  6. Mount-based notification feature tests (F-009)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentOverview.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentOverview smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentOverview.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentOverview template sections', () => {
  it('contains guide card for unbound state', () => {
    expect(content).toContain('v-if="!currentChild && !loading"')
    expect(content).toContain('class="guide-card"')
    expect(content).toContain('尚未绑定孩子')
    expect(content).toContain('请先绑定孩子信息，才能查看学习数据')
    expect(content).toContain("'/parent/bind'")
  })

  it('contains student info card with avatar', () => {
    expect(content).toContain('class="student-header"')
    expect(content).toContain('class="avatar-circle"')
    expect(content).toContain('{{ avatarLetter }}')
    expect(content).toContain('{{ currentChild.student_name }}')
    expect(content).toContain("currentChild.class_name || '未分配班级'")
  })

  it('contains total points and ranking stats', () => {
    expect(content).toContain('{{ totalPoints }}')
    expect(content).toContain('总积分')
    expect(content).toContain('v-if="ranking"')
    expect(content).toContain('{{ ranking }}')
    expect(content).toContain('排名')
  })

  it('contains score summary card', () => {
    expect(content).toContain('v-if="latestScore"')
    expect(content).toContain('class="score-brief"')
    expect(content).toContain('最近考试')
    expect(content).toContain("latestScore.total_score ?? '-'")
    expect(content).toContain('班名次')
    expect(content).toContain('年名次')
  })

  it('contains 4 quick entry buttons', () => {
    expect(content).toContain('class="quick-entries"')
    expect(content).toContain("'/parent/scores'")
    expect(content).toContain('成绩查询')
    expect(content).toContain("'/parent/rankings'")
    expect(content).toContain('排行榜')
    expect(content).toContain("'/parent/rules'")
    expect(content).toContain('班规')
    expect(content).toContain("'/parent/details'")
    expect(content).toContain('操行记录')
  })

  it('contains recent records list with points tag', () => {
    expect(content).toContain('v-for="r in records"')
    expect(content).toContain("r.rule_name || r.note || '操行记录'")
    expect(content).toContain("r.points >= 0 ? '+' : ''")
  })

  it('contains empty state for no records', () => {
    expect(content).toContain('description="暂无记录"')
  })

  it('contains button to view detailed records', () => {
    expect(content).toContain('查看详细记录')
  })
})

describe('ParentOverview behavior analysis card', () => {
  it('contains behavior analysis card with trend display', () => {
    expect(content).toContain('v-if="behaviorSummary"')
    expect(content).toContain('行为分析')
    expect(content).toContain('行为趋势')
    expect(content).toContain('behaviorSummary.trend_label')
    expect(content).toContain('trendColor')
  })

  it('contains positive streak display', () => {
    expect(content).toContain('连续表现良好')
    expect(content).toContain('behaviorSummary.positive_streak_days')
  })

  it('contains top issues tags', () => {
    expect(content).toContain('behaviorSummary.top_issues')
    expect(content).toContain('需关注')
    expect(content).toContain('type="warning"')
  })

  it('computes trendColor from behavior trend', () => {
    expect(content).toContain('const trendColor = computed')
    expect(content).toContain("'#4caf50'")  // improving color
    expect(content).toContain("'#e63946'")  // declining color
  })

  it('fetches behavior summary in watch', () => {
    expect(content).toContain('getChildBehaviorSummary(child.student_id)')
    expect(content).toContain('behaviorSummary.value = behaviorRes.data')
  })

  it('imports getChildBehaviorSummary from conduct API', () => {
    expect(content).toContain('getChildBehaviorSummary')
    expect(content).toContain("from '../../api/conduct'")
  })
})

describe('ParentOverview API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { getChildRecords, getChildScores, getChildRankings, getParentNotifications, markNotificationsRead, getChildBehaviorSummary } from '../../api/conduct'")
  })

  it('fetches child records', () => {
    expect(content).toContain('await getChildRecords(child.student_id, { page: 1, size: 10 })')
  })

  it('fetches latest score', () => {
    expect(content).toContain('await getChildScores(child.student_id, { limit: 1 })')
  })

  it('fetches child rankings', () => {
    expect(content).toContain('await getChildRankings(child.student_id)')
  })
})

describe('ParentOverview computed properties', () => {
  it('computes avatar letter from student name', () => {
    expect(content).toContain("const name = props.currentChild?.student_name || ''")
    expect(content).toContain("return name.charAt(0) || '?'")
  })

  it('computes avatar background color from name hash', () => {
    expect(content).toContain('const avatarBg = computed')
    expect(content).toContain("const colors = ['#F4DA4C', '#64b5f6', '#ffb74d', '#ce93d8', '#ef9a9a', '#80cbc4']")
  })

  it('receives currentChild via props', () => {
    expect(content).toContain('currentChild: { type: Object, default: null }')
  })
})

describe('ParentOverview error handling', () => {
  it('wraps score fetch in nested try-catch', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(() => props.currentChild'),
      content.indexOf('</script>')
    )
    // Should have multiple try-catch blocks for score and ranking
    const catchCount = (watchBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(3)
  })

  it('falls back to empty records on error', () => {
    expect(content).toContain('records.value = []')
  })

  it('falls back to null for score and ranking on error', () => {
    expect(content).toContain('latestScore.value = null')
    expect(content).toContain('ranking.value = null')
  })

  it('watches currentChild with immediate flag', () => {
    expect(content).toContain('}, { immediate: true })')
  })
})

// ============================================================
// F-009: Mount-based tests — notification feature
// ============================================================

vi.mock('../../../api/conduct', () => ({
  getParentNotifications: vi.fn().mockResolvedValue({ data: [] }),
  markNotificationsRead: vi.fn().mockResolvedValue({}),
  getChildRecords: vi.fn().mockResolvedValue({ data: { items: [] } }),
  getChildScores: vi.fn().mockResolvedValue({ data: [] }),
  getChildRankings: vi.fn().mockResolvedValue({ data: [] }),
  getChildBehaviorSummary: vi.fn().mockResolvedValue({ data: null }),
}))

import { mount, flushPromises } from '@vue/test-utils'
import { getParentNotifications, markNotificationsRead, getChildBehaviorSummary } from '../../../api/conduct'

const naiveStubs = {
  'n-card': { template: '<div class="n-card"><slot /><slot name="header" /></div>', props: ['title', 'size'] },
  'n-statistic': true,
  'n-list': { template: '<div class="n-list"><slot /></div>' },
  'n-list-item': { template: '<div class="n-list-item"><slot /></div>' },
  'n-tag': true,
  'n-button': { template: '<button class="n-button" @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
  'n-empty': true,
  'n-spin': { template: '<div><slot /></div>', props: ['show'] },
  'n-h4': { template: '<h4><slot /></h4>' },
  'n-thing': { template: '<div class="n-thing" :data-title="title">{{ title }} - {{ description }}</div>', props: ['title', 'description'] },
  'n-text': { template: '<span><slot /></span>', props: ['depth'] },
}

describe('ParentOverview mount tests — notifications (F-009)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: no notifications
    getParentNotifications.mockResolvedValue({ data: [] })
  })

  it('renders notification card when data exists', async () => {
    getParentNotifications.mockResolvedValue({
      data: [
        { id: 'n1', title: '积分变动', body: '张三获得+5分' },
        { id: 'n2', title: '班规更新', body: '新增班规条目' },
      ],
    })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: null },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    expect(getParentNotifications).toHaveBeenCalledWith(true)
    expect(wrapper.html()).toContain('最新动态')
    expect(wrapper.html()).toContain('积分变动')
    expect(wrapper.html()).toContain('班规更新')
  })

  it('hides notification card when no notifications', async () => {
    getParentNotifications.mockResolvedValue({ data: [] })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: null },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    expect(wrapper.html()).not.toContain('最新动态')
  })

  it('clears notifications when mark all read is clicked', async () => {
    getParentNotifications.mockResolvedValue({
      data: [
        { id: 'n1', title: '积分变动', body: '张三获得+5分' },
      ],
    })
    markNotificationsRead.mockResolvedValue({})

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: null },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    // Notification should be visible
    expect(wrapper.html()).toContain('最新动态')
    expect(wrapper.html()).toContain('全部已读')

    // Click "全部已读" button — find the button with that text
    const buttons = wrapper.findAll('.n-button')
    const markReadBtn = buttons.find(b => b.text().includes('全部已读'))
    expect(markReadBtn).toBeTruthy()
    await markReadBtn.trigger('click')
    await flushPromises()

    expect(markNotificationsRead).toHaveBeenCalledOnce()
    // Notifications should be cleared
    expect(wrapper.html()).not.toContain('最新动态')
  })

  it('handles notification fetch error gracefully', async () => {
    getParentNotifications.mockRejectedValue(new Error('Network error'))

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: null },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    // Should not crash, and should not show notifications
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.html()).not.toContain('最新动态')
  })
})

// ============================================================
// Phase 3: Mount-based tests — behavior summary card
// ============================================================

describe('ParentOverview mount tests — behavior card (Phase 3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getParentNotifications.mockResolvedValue({ data: [] })
    getChildBehaviorSummary.mockResolvedValue({ data: null })
  })

  it('renders behavior card when summary data is fetched', async () => {
    const { getChildRecords, getChildScores, getChildRankings } = await import('../../../api/conduct')
    getChildRecords.mockResolvedValue({ data: { items: [] } })
    getChildScores.mockResolvedValue({ data: [] })
    getChildRankings.mockResolvedValue({ data: [] })
    getChildBehaviorSummary.mockResolvedValue({
      data: {
        student_name: '张三',
        trend: 'improving',
        trend_label: '进步���',
        total_points: 15,
        positive_count: 5,
        negative_count: 1,
        top_issues: ['迟到', '未交作业'],
        positive_streak_days: 3,
      },
    })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: {
        currentChild: { student_id: 's1', student_name: '张三', class_name: '高一(1)班' },
      },
      global: { stubs: naiveStubs },
    })
    // Multiple flushPromises to resolve nested sequential awaits in watch
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(getChildBehaviorSummary).toHaveBeenCalledWith('s1')
    // NCard renders header slot; body content may depend on NaiveUI internals
    expect(wrapper.html()).toContain('行为分析')
  })

  it('hides behavior card when no data', async () => {
    const { getChildRecords, getChildScores, getChildRankings } = await import('../../../api/conduct')
    getChildRecords.mockResolvedValue({ data: { items: [] } })
    getChildScores.mockResolvedValue({ data: [] })
    getChildRankings.mockResolvedValue({ data: [] })
    getChildBehaviorSummary.mockResolvedValue({ data: null })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: {
        currentChild: { student_id: 's1', student_name: '张三', class_name: '高一(1)班' },
      },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    expect(wrapper.html()).not.toContain('行为分析')
  })

  it('handles behavior summary fetch error gracefully', async () => {
    const { getChildRecords, getChildScores, getChildRankings } = await import('../../../api/conduct')
    getChildRecords.mockResolvedValue({ data: { items: [] } })
    getChildScores.mockResolvedValue({ data: [] })
    getChildRankings.mockResolvedValue({ data: [] })
    getChildBehaviorSummary.mockRejectedValue(new Error('Network error'))

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: {
        currentChild: { student_id: 's1', student_name: '张三', class_name: '高一(1)班' },
      },
      global: { stubs: naiveStubs },
    })
    await flushPromises()

    // Should not crash
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.html()).not.toContain('行为分析')
  })
})
