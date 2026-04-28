/**
 * AnalyticsTrendPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template: filter row, dimension radio, compare mode, metric checkboxes, chart area, export button
 *  3. API calls use analytics.js trend functions + client.js direct calls
 *  4. ECharts configuration (line chart, dark theme, dual yAxis, series colors)
 *  5. Data processing (dimension switching, compare mode, metric visibility)
 *  6. Error handling (try-catch blocks)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../AnalyticsTrendPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('AnalyticsTrendPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../AnalyticsTrendPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('AnalyticsTrendPage template sections', () => {
  it('wraps in analytics-trend class', () => {
    expect(content).toContain('class="analytics-trend"')
  })

  it('has exam multi-select filter', () => {
    expect(content).toContain('v-model:value="selectedExamIds"')
    expect(content).toContain(':options="examOptions"')
    expect(content).toContain('multiple')
  })

  it('has dimension radio group with grade/class/student', () => {
    expect(content).toContain('v-model:value="dimension"')
    expect(content).toContain('n-radio-button value="grade"')
    expect(content).toContain('n-radio-button value="class"')
    expect(content).toContain('n-radio-button value="student"')
  })

  it('conditionally shows class selector when dimension is class', () => {
    expect(content).toContain("v-if=\"dimension === 'class'\"")
    expect(content).toContain('v-model:value="selectedClassId"')
    expect(content).toContain(':options="classOptions"')
  })

  it('conditionally shows student selector when dimension is student', () => {
    expect(content).toContain("v-if=\"dimension === 'student'\"")
    expect(content).toContain('v-model:value="selectedStudentId"')
    expect(content).toContain(':options="studentOptions"')
    expect(content).toContain('filterable')
  })

  it('has load trend button with loading state', () => {
    expect(content).toContain('@click="loadTrend"')
    expect(content).toContain(':loading="loading"')
  })
})

describe('AnalyticsTrendPage compare mode', () => {
  it('shows compare mode for class and student dimensions', () => {
    expect(content).toContain("v-if=\"dimension === 'class' || dimension === 'student'\"")
    expect(content).toContain('v-model:value="compareIds"')
    expect(content).toContain(':max-tag-count="2"')
  })

  it('switches compare options based on dimension', () => {
    expect(content).toContain("dimension === 'class' ? classOptions : studentOptions")
  })
})

describe('AnalyticsTrendPage metric checkboxes', () => {
  it('shows metric selector when trendData exists', () => {
    expect(content).toContain('v-if="trendData"')
    expect(content).toContain('v-model:value="visibleMetrics"')
    expect(content).toContain('n-checkbox-group')
  })

  it('has avg, pass_rate, excellent_rate checkboxes', () => {
    expect(content).toContain('value="avg"')
    expect(content).toContain('value="pass_rate"')
    expect(content).toContain('value="excellent_rate"')
  })

  it('has score checkbox visible only for student dimension', () => {
    expect(content).toContain('value="score"')
    expect(content).toContain("v-if=\"dimension === 'student'\"")
  })
})

describe('AnalyticsTrendPage chart area', () => {
  it('renders v-chart with chartOption and chart-height-xl class', () => {
    expect(content).toContain('v-if="chartOption"')
    expect(content).toContain('<v-chart ref="chartRef"')
    expect(content).toContain('chart-height-xl')
  })

  it('has export chart button', () => {
    expect(content).toContain('@click="exportChart"')
  })
})

describe('AnalyticsTrendPage API imports', () => {
  it('imports trend API functions from analytics.js', () => {
    expect(content).toContain("from '../api/analytics'")
    expect(content).toContain('getGradeTrend')
    expect(content).toContain('getClassTrend')
    expect(content).toContain('getStudentTrend')
  })

  it('imports client for direct API calls', () => {
    expect(content).toContain("import client from '../api/client'")
  })
})

describe('AnalyticsTrendPage ECharts configuration', () => {
  it('registers line chart and related components', () => {
    expect(content).toContain("import VChart from 'vue-echarts'")
    expect(content).toContain('LineChart')
    expect(content).toContain('GridComponent')
    expect(content).toContain('TooltipComponent')
    expect(content).toContain('LegendComponent')
    expect(content).toContain('DataZoomComponent')
    expect(content).toContain('CanvasRenderer')
  })

  it('defines dark theme constants', () => {
    expect(content).toContain("const DARK_TEXT = 'rgba(255, 255, 255, 0.65)'")
    expect(content).toContain("const DARK_SPLIT = 'rgba(255, 255, 255, 0.08)'")
    expect(content).toContain("const DARK_AXIS = 'rgba(255, 255, 255, 0.35)'")
  })

  it('defines SERIES_COLORS palette with 6 colors', () => {
    expect(content).toContain('const SERIES_COLORS = [')
    const colorsMatch = content.match(/SERIES_COLORS = \[([^\]]+)\]/)
    expect(colorsMatch).not.toBeNull()
    const colors = colorsMatch[1].split(',').map(c => c.trim())
    expect(colors.length).toBe(6)
  })

  it('buildDarkThemeBase creates dual yAxis config', () => {
    const fnBlock = content.slice(
      content.indexOf('function buildDarkThemeBase'),
      content.indexOf('const chartOption'),
    )
    expect(fnBlock).toContain("type: 'category'")
    expect(fnBlock).toContain("name: '分数'")
    expect(fnBlock).toContain("name: '百分比 (%)'")
    expect(fnBlock).toContain("formatter: '{value}%'")
    expect(fnBlock).toContain('min: 0')
    expect(fnBlock).toContain('max: 100')
  })

  it('applies dark theme tooltip styling', () => {
    expect(content).toContain("backgroundColor: 'rgba(30, 30, 30, 0.95)'")
    expect(content).toContain("borderColor: 'rgba(255, 255, 255, 0.1)'")
  })
})

describe('AnalyticsTrendPage chartOption series by dimension', () => {
  it('returns null when no trendData points', () => {
    expect(content).toContain("if (!trendData.value?.points?.length) return null")
  })

  it('builds grade dimension series for avg and pass_rate', () => {
    const gradeBlock = content.slice(
      content.indexOf("if (dimension.value === 'grade')"),
      content.indexOf("} else if (dimension.value === 'class')"),
    )
    expect(gradeBlock).toContain("name: '均分'")
    expect(gradeBlock).toContain("name: '及格率'")
    expect(gradeBlock).toContain("name: '优秀率'")
    expect(gradeBlock).toContain("type: 'line'")
    expect(gradeBlock).toContain('smooth: true')
  })

  it('builds class dimension with class_avg and grade_avg comparison', () => {
    const classBlock = content.slice(
      content.indexOf("} else if (dimension.value === 'class')"),
      content.indexOf('} else {'),
    )
    expect(classBlock).toContain("name: '班级均分'")
    expect(classBlock).toContain("name: '年级均分'")
    expect(classBlock).toContain('p.class_avg')
    expect(classBlock).toContain('p.grade_avg')
  })

  it('builds student dimension with score and class_avg', () => {
    const studentBlock = content.slice(
      content.indexOf("} else {"),
      content.indexOf('return opt'),
    )
    expect(studentBlock).toContain("name: '得分'")
    expect(studentBlock).toContain("name: '班级均分'")
    expect(studentBlock).toContain('p.score')
    expect(studentBlock).toContain('p.class_avg')
  })

  it('uses dashed lineStyle for comparison series', () => {
    const matches = content.match(/lineStyle: \{ type: 'dashed' \}/g)
    expect(matches).not.toBeNull()
    expect(matches.length).toBeGreaterThanOrEqual(2)
  })

  it('uses dotted lineStyle for compare mode overlay', () => {
    const matches = content.match(/lineStyle: \{ type: 'dotted' \}/g)
    expect(matches).not.toBeNull()
    expect(matches.length).toBe(2)
  })

  it('uses yAxisIndex 0 for scores and 1 for percentages', () => {
    // Percentages (pass_rate, excellent_rate) use yAxisIndex 1
    const passRateMatches = content.match(/name: '及格率'.*?yAxisIndex: 1/gs)
    expect(passRateMatches).not.toBeNull()
  })
})

describe('AnalyticsTrendPage compare mode data', () => {
  it('appends compare_series to trendData', () => {
    expect(content).toContain('trendData.value.compare_series')
  })

  it('iterates compare_series with labels and points', () => {
    expect(content).toContain('cs.label')
    expect(content).toContain('cs.points')
  })

  it('cycles SERIES_COLORS for compare series', () => {
    expect(content).toContain('SERIES_COLORS[(i + 3) % SERIES_COLORS.length]')
  })
})

describe('AnalyticsTrendPage exportChart', () => {
  it('gets chart instance via ref', () => {
    expect(content).toContain('chartRef.value?.chart')
  })

  it('warns when chart not ready', () => {
    expect(content).toContain("message.warning('图表未就绪')")
  })

  it('exports as PNG with dark background and 2x pixel ratio', () => {
    expect(content).toContain("type: 'png'")
    expect(content).toContain("backgroundColor: '#1e1e1e'")
    expect(content).toContain('pixelRatio: 2')
  })

  it('uses dimension and timestamp in filename', () => {
    expect(content).toContain('`trend-${dimension.value}-${Date.now()}.png`')
  })
})

describe('AnalyticsTrendPage data fetching on mount', () => {
  it('fetches exams list for filter options', () => {
    expect(content).toContain("client.get('/exams')")
  })

  it('fetches classes list for class filter', () => {
    expect(content).toContain("client.get('/classes')")
  })

  it('lazy-loads students when switching to student dimension', () => {
    expect(content).toContain("client.get('/students')")
    expect(content).toContain("val === 'student' && studentOptions.value.length === 0")
  })

  it('formats student options with name and number', () => {
    expect(content).toContain('`${s.name} (${s.student_number})`')
  })
})

describe('AnalyticsTrendPage dimension watch', () => {
  it('resets compareIds on dimension change', () => {
    expect(content).toContain('compareIds.value = []')
  })

  it('sets student defaults to score and avg', () => {
    expect(content).toContain("visibleMetrics.value = ['score', 'avg']")
  })

  it('sets non-student defaults to avg and pass_rate', () => {
    expect(content).toContain("visibleMetrics.value = ['avg', 'pass_rate']")
  })
})

describe('AnalyticsTrendPage loadTrend', () => {
  it('validates at least one exam selected', () => {
    expect(content).toContain("message.warning('请至少选择一次考试')")
  })

  it('validates class selection for class dimension', () => {
    expect(content).toContain("message.warning('请选择班级')")
  })

  it('validates student selection for student dimension', () => {
    expect(content).toContain("message.warning('请选择学生')")
  })

  it('calls getGradeTrend for grade dimension', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadTrend'),
      content.lastIndexOf('</script>'),
    )
    expect(loadBlock).toContain('getGradeTrend({ exam_ids: examIdsStr })')
  })

  it('calls getClassTrend for class dimension', () => {
    expect(content).toContain('getClassTrend({ exam_ids: examIdsStr, class_id: selectedClassId.value })')
  })

  it('calls getStudentTrend for student dimension', () => {
    expect(content).toContain('getStudentTrend({ exam_ids: examIdsStr, student_id: selectedStudentId.value })')
  })

  it('limits compare mode to max 2 objects', () => {
    expect(content).toContain('compareIds.value.length <= 2')
  })
})

describe('AnalyticsTrendPage error handling', () => {
  it('wraps exam fetch on mount in try-catch', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted('),
      content.indexOf('watch(dimension'),
    )
    const catchCount = (mountBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(2)
  })

  it('wraps loadTrend main call in try-catch-finally', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadTrend'),
      content.lastIndexOf('</script>'),
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch (e) {')
    expect(loadBlock).toContain('} finally {')
    expect(loadBlock).toContain('loading.value = false')
  })

  it('displays error message on loadTrend failure', () => {
    expect(content).toContain("e.response?.data?.detail || '加载失败'")
  })

  it('wraps compare series fetch in try-catch per item', () => {
    const compareBlock = content.slice(
      content.indexOf('for (const cid of compareIds.value)'),
      content.indexOf("trendData.value = { ...trendData.value, compare_series: compareSeries }"),
    )
    expect(compareBlock).toContain('try {')
    expect(compareBlock).toContain('} catch')
  })

  it('wraps dimension watch student fetch in try-catch', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(dimension'),
      content.indexOf('async function loadTrend'),
    )
    expect(watchBlock).toContain('try {')
    expect(watchBlock).toContain('} catch')
  })
})
