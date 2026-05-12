import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'

function roundNumber(value) {
  if (value == null || Number.isNaN(Number(value))) return null
  return Math.round(Number(value) * 10) / 10
}

function chartNumber(value) {
  return roundNumber(value)
}

function rateNumber(value) {
  if (value == null || Number.isNaN(Number(value))) return 0
  return Math.round(Number(value) * 1000) / 10
}

export function buildSegmentChart(distribution) {
  const segments = distribution || []
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    grid: { left: 36, right: 16, top: 32, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: segments.map(s => s.label) },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [{
      type: 'bar',
      data: segments.map(s => s.count),
      barMaxWidth: 34,
      label: { show: true, position: 'top' },
      itemStyle: { color: CHART_PALETTE[3] },
    }],
  }
}

export function buildSubjectRateChart(subjects) {
  const list = subjects || []
  return {
    ...CHART_DEFAULTS,
    tooltip: {
      ...CHART_DEFAULTS.tooltip,
      trigger: 'axis',
      valueFormatter: value => `${roundNumber(value)}%`,
    },
    grid: { left: 44, right: 16, top: 32, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: list.map(s => s.subject_name) },
    yAxis: {
      ...CHART_DEFAULTS.yAxis,
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%' },
    },
    series: [{
      name: '得分率',
      type: 'bar',
      data: list.map(s => rateNumber(s.score_rate)),
      barMaxWidth: 34,
      label: { show: true, position: 'top', formatter: '{c}%' },
      itemStyle: { color: CHART_PALETTE[0] },
    }],
  }
}

export function buildRankTrendChart(overview, examName) {
  const ov = overview || {}
  const fullScore = Number(ov.total_full_score)
  const passLine = Number.isFinite(fullScore) && fullScore > 0 ? roundNumber(fullScore * 0.6) : null
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { top: 0, data: ['平均分', '最高分', '及格线'] },
    grid: { left: 44, right: 16, top: 42, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: [examName || '本次考试'] },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [
      {
        name: '平均分',
        type: 'line',
        data: [chartNumber(ov.avg_score)],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[0] },
      },
      {
        name: '最高分',
        type: 'line',
        data: [chartNumber(ov.max_score)],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[1] },
      },
      {
        name: '及格线',
        type: 'line',
        data: [passLine],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[2] },
      },
    ],
  }
}

export function buildClassCompareChart(classes) {
  const list = classes || []
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { top: 0, data: ['平均分', '及格率'] },
    grid: { left: 44, right: 44, top: 42, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: list.map(row => row.class_name) },
    yAxis: [
      { ...CHART_DEFAULTS.yAxis, type: 'value' },
      { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      {
        name: '平均分',
        type: 'bar',
        data: list.map(row => chartNumber(row.avg_score)),
        barMaxWidth: 34,
        label: { show: true, position: 'top' },
        itemStyle: { color: CHART_PALETTE[0] },
      },
      {
        name: '及格率',
        type: 'line',
        yAxisIndex: 1,
        data: list.map(row => rateNumber(row.pass_rate)),
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[2] },
      },
    ],
  }
}
