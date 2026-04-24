import { describe, it, expect, vi } from 'vitest'
import { mount, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div data-testid="vchart-stub" />', props: ['option', 'autoresize'] },
}))
vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))
vi.mock('echarts/charts', () => ({ HeatmapChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {}, TooltipComponent: {}, VisualMapComponent: {},
}))
import StatCard from '~/components/analytics/StatCard.vue'
import AiDiagnosisCard from '~/components/analytics/AiDiagnosisCard.vue'
import ClassRankTable from '~/components/analytics/ClassRankTable.vue'
import StudentRankTable from '~/components/analytics/StudentRankTable.vue'
import CriticalStudents from '~/components/analytics/CriticalStudents.vue'
import KnowledgeHeatmap from '~/components/analytics/KnowledgeHeatmap.vue'

describe('StatCard', () => {
  const mountStatCard = (props: Record<string, any>) =>
    mount(StatCard, { props, global: { plugins: [ElementPlus] } })

  it('renders value and label', () => {
    const wrapper = mountStatCard({ value: 85.3, label: '平均分', format: 'score' })
    expect(wrapper.text()).toContain('85.3')
    expect(wrapper.text()).toContain('平均分')
  })

  it('renders percent format', () => {
    const wrapper = mountStatCard({ value: 0.753, label: '得分率', format: 'percent' })
    expect(wrapper.text()).toContain('75.3%')
  })

  it('renders dash for null value', () => {
    const wrapper = mountStatCard({ value: null, label: '均分' })
    expect(wrapper.text()).toContain('-')
  })

  it('shows trend up arrow', () => {
    const wrapper = mountStatCard({ value: 90, label: '分数', trend: 5 })
    expect(wrapper.text()).toContain('↑')
    expect(wrapper.find('.trend.up').exists()).toBe(true)
  })

  it('shows trend down arrow', () => {
    const wrapper = mountStatCard({ value: 70, label: '分数', trend: -3 })
    expect(wrapper.text()).toContain('↓')
    expect(wrapper.find('.trend.down').exists()).toBe(true)
  })

  it('shows steady arrow for zero trend', () => {
    const wrapper = mountStatCard({ value: 80, label: '分数', trend: 0 })
    expect(wrapper.text()).toContain('→')
  })

  it('hides trend when not provided', () => {
    const wrapper = mountStatCard({ value: 80, label: '分数' })
    expect(wrapper.find('.trend').exists()).toBe(false)
  })

  it('renders subtitle when provided', () => {
    const wrapper = mountStatCard({ value: 80, label: '分数', subtitle: '较上次提升' })
    expect(wrapper.text()).toContain('较上次提升')
  })

  it('renders raw string value', () => {
    const wrapper = mountStatCard({ value: 'A+', label: '等级' })
    expect(wrapper.text()).toContain('A+')
  })
})

describe('AiDiagnosisCard', () => {
  const mountDiagnosis = (props: Record<string, any>) =>
    mount(AiDiagnosisCard, { props, global: { plugins: [ElementPlus] } })

  it('renders diagnosis text', () => {
    const wrapper = mountDiagnosis({
      text: '本次考试均分 72，低于年级均分 3 分。',
      suggestions: [],
      weakQuestions: [],
    })
    expect(wrapper.text()).toContain('本次考试均分 72')
  })

  it('renders suggestions', () => {
    const wrapper = mountDiagnosis({
      text: '分析结果',
      suggestions: ['建议重点讲解第 15 题。', '关注后进生。'],
      weakQuestions: [],
    })
    expect(wrapper.text()).toContain('建议重点讲解')
    expect(wrapper.text()).toContain('关注后进生')
  })

  it('renders weak questions with score rate', () => {
    const wrapper = mountDiagnosis({
      text: '分析结果',
      suggestions: [],
      weakQuestions: [{ name: '15', score_rate: 0.35 }],
    })
    expect(wrapper.text()).toContain('第15题')
    expect(wrapper.text()).toContain('35%')
  })

  it('shows empty state when text is sentinel', () => {
    const wrapper = mountDiagnosis({ text: '暂无诊断数据。' })
    // empty computed => true => el-empty renders with description
    expect(wrapper.text()).toContain('暂无 AI 诊断数据')
  })

  it('shows empty state when text is undefined', () => {
    const wrapper = mountDiagnosis({})
    expect(wrapper.text()).toContain('暂无 AI 诊断数据')
  })
})

describe('ClassRankTable', () => {
  const rankings = [
    { class_name: '高一(1)班', student_count: 45, avg_score: 82.5, pass_rate: 0.9, excellent_rate: 0.3, rank: 1 },
    { class_name: '高一(2)班', student_count: 43, avg_score: 68.2, pass_rate: 0.7, excellent_rate: 0.1, rank: 2 },
  ]

  const mountTable = (props: Record<string, any>) =>
    mount(ClassRankTable, { props, global: { plugins: [ElementPlus] } })

  it('passes correct data with two classes', () => {
    const wrapper = mountTable({ rankings, gradeAvg: 75 })
    const table = wrapper.findComponent({ name: 'ElTable' })
    const data = table.props('data') as typeof rankings
    expect(data).toHaveLength(2)
    expect(data[0].class_name).toBe('高一(1)班')
    expect(data[1].class_name).toBe('高一(2)班')
  })

  it('renders class rank header', () => {
    const wrapper = mountTable({ rankings, gradeAvg: 75 })
    expect(wrapper.text()).toContain('班级排名')
  })

  it('passes rankings data to table', () => {
    const wrapper = mountTable({ rankings, gradeAvg: 75 })
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.exists()).toBe(true)
    expect(table.props('data')).toEqual(rankings)
  })
})

describe('StudentRankTable', () => {
  const students = [
    { student_id: 's1', name: '张三', score: 95, class_rank: 1, grade_rank: 1, delta_grade: 2 },
    { student_id: 's2', name: '李四', score: 80, class_rank: 2, grade_rank: 3, delta_grade: -1 },
    { student_id: 's3', name: '王五', score: 60, class_rank: 3, grade_rank: 5, delta_grade: null },
  ]

  it('renders student data', () => {
    const wrapper = mount(StudentRankTable, {
      props: { students },
      global: { plugins: [ElementPlus] },
    })
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.exists()).toBe(true)
    expect(table.props('data')).toHaveLength(3)
  })

  it('filters by search', async () => {
    const wrapper = mount(StudentRankTable, {
      props: { students },
      global: { plugins: [ElementPlus] },
    })
    const input = wrapper.findComponent({ name: 'ElInput' })
    await input.setValue('张')
    await wrapper.vm.$nextTick()
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.props('data')).toHaveLength(1)
    expect(table.props('data')[0].name).toBe('张三')
  })
})

describe('CriticalStudents', () => {
  it('renders near-pass and near-excellent groups', () => {
    const wrapper = mount(CriticalStudents, {
      props: {
        nearPass: [{ student_id: 's1', name: '临界A', score: 58, gap: 2, worst_question: { question_name: '15', loss: 4 } }],
        nearExcellent: [{ student_id: 's2', name: '临界B', score: 83, gap: 2, worst_question: null }],
        threshold: 3,
      },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('差3分及格')
    expect(wrapper.text()).toContain('差3分优秀')
  })

  it('shows empty state when no critical students', () => {
    const wrapper = mount(CriticalStudents, {
      props: { nearPass: [], nearExcellent: [], threshold: 3 },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('无临界生')
  })
})

describe('KnowledgeHeatmap', () => {
  it('renders heatmap when data provided', () => {
    const wrapper = mount(KnowledgeHeatmap, {
      props: {
        knowledgePoints: ['光合作用', '细胞分裂'],
        classes: [
          { class_id: 'c1', name: '高一(1)班', mastery: [{ kp_id: '光合作用', rate: 0.85 }, { kp_id: '细胞分裂', rate: 0.6 }] },
        ],
      },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.find('[data-testid="vchart-stub"]').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(false)
  })

  it('shows empty state when no knowledge points', () => {
    const wrapper = mount(KnowledgeHeatmap, {
      props: { knowledgePoints: [], classes: [] },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('暂无知识点数据')
  })
})
