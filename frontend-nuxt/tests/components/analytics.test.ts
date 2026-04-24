import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StatCard from '~/components/analytics/StatCard.vue'
import AiDiagnosisCard from '~/components/analytics/AiDiagnosisCard.vue'
import ClassRankTable from '~/components/analytics/ClassRankTable.vue'

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
