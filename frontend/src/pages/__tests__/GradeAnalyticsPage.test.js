/**
 * GradeAnalyticsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (selectors, charts)
 *  3. Chart configurations (bar, line, radar)
 *  4. API calls (getGradeOverview, getGradeExamTrend, getGradeSubjects)
 *  5. Data loading and state management
 *  6. Error handling
 *  7. Grade change handler
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../GradeAnalyticsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('GradeAnalyticsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../GradeAnalyticsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('GradeAnalyticsPage template structure', () => {
  it('contains grade-analytics root class', () => {
    expect(content).toContain('class="page-wrap grade-analytics"')
  })

  it('contains page title', () => {
    expect(content).toContain('<h1 class="page-title">年级分析</h1>')
  })

  it('contains grade selector', () => {
    expect(content).toContain('v-model:value="selectedGradeId"')
    expect(content).toContain(':options="gradeOptions"')
    expect(content).toContain('placeholder="选择年级"')
  })

  it('contains exam selector', () => {
    expect(content).toContain('v-model:value="selectedExamId"')
    expect(content).toContain(':options="examOptions"')
    expect(content).toContain('placeholder="选择考试"')
  })

  it('contains load button', () => {
    expect(content).toContain('@click="loadAll"')
    expect(content).toContain(':loading="loading"')
    expect(content).toContain('查看分析')
  })
})

describe('GradeAnalyticsPage chart sections', () => {
  it('contains class comparison bar chart', () => {
    expect(content).toContain('v-if="overviewData"')
    expect(content).toContain('title="班级对比"')
    expect(content).toContain(':option="barOption"')
  })

  it('contains trend line chart', () => {
    expect(content).toContain('v-if="trendData && trendData.points.length"')
    expect(content).toContain('title="考情趋势"')
    expect(content).toContain(':option="lineOption"')
  })

  it('contains subjects radar chart', () => {
    expect(content).toContain('v-if="subjectsData && subjectsData.subjects.length"')
    expect(content).toContain('title="科目对比"')
    expect(content).toContain(':option="radarOption"')
  })
})

describe('GradeAnalyticsPage bar chart configuration', () => {
  it('guards against empty classes data', () => {
    expect(content).toContain("if (!overviewData.value?.classes?.length) return {}")
  })

  it('defines three series: avg, max, min scores', () => {
    const barBlock = content.slice(
      content.indexOf('const barOption = computed'),
      content.indexOf('const lineOption = computed')
    )
    expect(barBlock).toContain("name: '均分'")
    expect(barBlock).toContain("name: '最高分'")
    expect(barBlock).toContain("name: '最低分'")
  })

  it('maps class names to x-axis', () => {
    expect(content).toContain('const names = classes.map(c => c.class_name)')
  })

  it('uses bar chart type', () => {
    const barBlock = content.slice(
      content.indexOf('const barOption = computed'),
      content.indexOf('const lineOption = computed')
    )
    expect(barBlock).toContain("type: 'bar'")
  })
})

describe('GradeAnalyticsPage line chart configuration', () => {
  it('guards against empty points data', () => {
    expect(content).toContain("if (!trendData.value?.points?.length) return {}")
  })

  it('defines three series: avg score, pass rate, excellent rate', () => {
    const lineBlock = content.slice(
      content.indexOf('const lineOption = computed'),
      content.indexOf('const radarOption = computed')
    )
    expect(lineBlock).toContain("name: '均分'")
    expect(lineBlock).toContain("name: '及格率'")
    expect(lineBlock).toContain("name: '优秀率'")
  })

  it('uses dual Y axes for scores and rates', () => {
    expect(content).toContain("{ ...CHART_DEFAULTS.yAxis, type: 'value', name: '分数'")
    expect(content).toContain("{ ...CHART_DEFAULTS.yAxis, type: 'value', name: '比率'")
  })

  it('formats rate axis as percentage', () => {
    expect(content).toContain('formatter: v => `${(v * 100).toFixed(0)}%`')
  })

  it('uses smooth lines', () => {
    const lineBlock = content.slice(
      content.indexOf('const lineOption = computed'),
      content.indexOf('const radarOption = computed')
    )
    expect(lineBlock).toContain('smooth: true')
  })

  it('uses dashed line for pass rate', () => {
    expect(content).toContain("lineStyle: { type: 'dashed' }")
  })

  it('uses dotted line for excellent rate', () => {
    expect(content).toContain("lineStyle: { type: 'dotted' }")
  })
})

describe('GradeAnalyticsPage radar chart configuration', () => {
  it('guards against empty subjects data', () => {
    expect(content).toContain("if (!subjectsData.value?.subjects?.length) return {}")
  })

  it('maps subject names to radar indicators', () => {
    expect(content).toContain('subjects.map(s => ({')
    expect(content).toContain('name: s.subject_name')
    expect(content).toContain('max: 1')
  })

  it('uses score_rate for radar values', () => {
    expect(content).toContain("name: '得分率'")
    expect(content).toContain('subjects.map(s => s.score_rate)')
  })

  it('has area style with opacity', () => {
    expect(content).toContain('areaStyle: { opacity: 0.3 }')
  })
})

describe('GradeAnalyticsPage API calls', () => {
  it('imports analytics API functions', () => {
    expect(content).toContain("import {")
    expect(content).toContain('getGradeOverview')
    expect(content).toContain('getGradeExamTrend')
    expect(content).toContain('getGradeSubjects')
  })

  it('loads grades on mount', () => {
    expect(content).toContain("client.get('/grades')")
  })

  it('loads exams on mount', () => {
    expect(content).toContain("client.get('/exams')")
  })

  it('maps grade response to options', () => {
    expect(content).toContain("label: g.name")
    expect(content).toContain("value: g.id")
  })

  it('maps exam response to options', () => {
    expect(content).toContain("label: e.name")
    expect(content).toContain("value: e.id")
  })
})

describe('GradeAnalyticsPage loadAll function', () => {
  it('validates grade selection before loading', () => {
    expect(content).toContain("if (!selectedGradeId.value)")
    expect(content).toContain("message.warning('请选择年级')")
  })

  it('always loads trend data for selected grade', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadAll'),
      content.indexOf('onMounted(async')
    )
    expect(loadBlock).toContain('getGradeExamTrend(selectedGradeId.value)')
  })

  it('conditionally loads overview and subjects when exam selected', () => {
    expect(content).toContain('if (selectedExamId.value)')
    expect(content).toContain('getGradeOverview(selectedGradeId.value, selectedExamId.value)')
    expect(content).toContain('getGradeSubjects(selectedGradeId.value, selectedExamId.value)')
  })

  it('loads overview and subjects in parallel', () => {
    const loadBlock = content.slice(
      content.indexOf('if (selectedExamId.value)'),
      content.indexOf('} catch')
    )
    expect(loadBlock).toContain('Promise.all([')
  })
})

describe('GradeAnalyticsPage grade change handler', () => {
  it('resets all data on grade change', () => {
    const fnBlock = content.slice(
      content.indexOf('async function onGradeChange'),
      content.indexOf('async function loadAll')
    )
    expect(fnBlock).toContain('overviewData.value = null')
    expect(fnBlock).toContain('trendData.value = null')
    expect(fnBlock).toContain('subjectsData.value = null')
    expect(fnBlock).toContain('selectedExamId.value = null')
  })

  it('grade selector triggers onGradeChange', () => {
    expect(content).toContain('@update:value="onGradeChange"')
  })
})

describe('GradeAnalyticsPage error handling', () => {
  it('wraps loadAll in try-catch-finally', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadAll'),
      content.indexOf('onMounted(async')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch (e) {')
    expect(loadBlock).toContain('} finally {')
  })

  it('shows error message on failure', () => {
    expect(content).toContain("message.error(e.response?.data?.detail || '加载失败')")
  })

  it('manages loading state correctly', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadAll'),
      content.indexOf('onMounted(async')
    )
    expect(loadBlock).toContain('loading.value = true')
    expect(loadBlock).toContain('loading.value = false')
  })

  it('wraps grade loading in try-catch', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted(async'),
      content.length
    )
    const catchCount = (mountBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(2)
  })
})

describe('GradeAnalyticsPage ECharts setup', () => {
  it('registers required chart types', () => {
    expect(content).toContain("import { BarChart, LineChart, RadarChart, BoxplotChart, HeatmapChart } from 'echarts/charts'")
  })

  it('registers required components', () => {
    expect(content).toContain('GridComponent')
    expect(content).toContain('TooltipComponent')
    expect(content).toContain('LegendComponent')
    expect(content).toContain('RadarComponent')
  })

  it('uses CanvasRenderer', () => {
    expect(content).toContain("import { CanvasRenderer } from 'echarts/renderers'")
  })

  it('imports VChart from vue-echarts', () => {
    expect(content).toContain("import VChart from 'vue-echarts'")
  })
})
