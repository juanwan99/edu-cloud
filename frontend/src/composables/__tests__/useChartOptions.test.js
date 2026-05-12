import { describe, it, expect } from 'vitest'
import { buildSegmentChart, buildSubjectRateChart, buildRankTrendChart, buildClassCompareChart } from '../useChartOptions'

describe('useChartOptions', () => {
  describe('buildSegmentChart', () => {
    it('maps distribution data to bar chart', () => {
      const dist = [{ label: '80-90', count: 6 }, { label: '90-100', count: 2 }]
      const opt = buildSegmentChart(dist)
      expect(opt.xAxis.data).toEqual(['80-90', '90-100'])
      expect(opt.series[0].data).toEqual([6, 2])
      expect(opt.series[0].type).toBe('bar')
    })

    it('handles null/empty distribution', () => {
      expect(buildSegmentChart(null).xAxis.data).toEqual([])
      expect(buildSegmentChart([]).series[0].data).toEqual([])
    })
  })

  describe('buildSubjectRateChart', () => {
    it('maps subjects to score rate bars', () => {
      const subjects = [
        { subject_name: '语文', score_rate: 0.825 },
        { subject_name: '数学', score_rate: 0.76 },
      ]
      const opt = buildSubjectRateChart(subjects)
      expect(opt.xAxis.data).toEqual(['语文', '数学'])
      expect(opt.series[0].data).toEqual([82.5, 76])
    })

    it('handles null subjects', () => {
      expect(buildSubjectRateChart(null).xAxis.data).toEqual([])
    })
  })

  describe('buildRankTrendChart', () => {
    it('includes avg, max, and pass line', () => {
      const overview = { avg_score: 78, max_score: 99, total_full_score: 100 }
      const opt = buildRankTrendChart(overview, '期中考试')
      expect(opt.xAxis.data).toEqual(['期中考试'])
      expect(opt.series).toHaveLength(3)
      expect(opt.series[0].data).toEqual([78])
      expect(opt.series[1].data).toEqual([99])
      expect(opt.series[2].data).toEqual([60])
    })

    it('handles null overview', () => {
      const opt = buildRankTrendChart(null, null)
      expect(opt.xAxis.data).toEqual(['本次考试'])
      expect(opt.series[0].data).toEqual([null])
    })
  })

  describe('buildClassCompareChart', () => {
    it('maps classes to dual-axis chart', () => {
      const classes = [
        { class_name: '1班', avg_score: 80, pass_rate: 0.85 },
        { class_name: '2班', avg_score: 75, pass_rate: 0.7 },
      ]
      const opt = buildClassCompareChart(classes)
      expect(opt.xAxis.data).toEqual(['1班', '2班'])
      expect(opt.series[0].type).toBe('bar')
      expect(opt.series[1].type).toBe('line')
      expect(opt.series[1].yAxisIndex).toBe(1)
    })

    it('handles null classes', () => {
      expect(buildClassCompareChart(null).xAxis.data).toEqual([])
    })
  })
})
