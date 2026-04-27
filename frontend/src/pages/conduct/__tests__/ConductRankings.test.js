/**
 * ConductRankings source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (search, semester filter, tabs, distribution chart, export button)
 *  3. API calls via conduct.js (getStudentRankings, getGroupRankings, getSemesters, exportRankings)
 *  4. Operations (tab switching, distribution buckets, medal display, search filter)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductRankings.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductRankings smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductRankings.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductRankings template sections', () => {
  it('contains page header with title', () => {
    expect(content).toContain('title="积分排行"')
  })

  it('contains search input for student name', () => {
    expect(content).toContain('v-model:value="searchName"')
    expect(content).toContain('搜索学生姓名')
  })

  it('contains semester selector', () => {
    expect(content).toContain('v-model:value="semesterId"')
    expect(content).toContain(':options="semesterOptions"')
    expect(content).toContain('选择学期')
  })

  it('contains export button', () => {
    expect(content).toContain(':loading="exporting"')
    expect(content).toContain('@click="handleExport"')
    expect(content).toContain('导出排行')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains distribution chart section', () => {
    expect(content).toContain('title="排名分布"')
    expect(content).toContain('v-if="distOption"')
    expect(content).toContain(':option="distOption"')
  })

  it('contains student/group tabs', () => {
    expect(content).toContain('v-model:value="activeTab"')
    expect(content).toContain("name=\"students\"")
    expect(content).toContain("tab=\"学生排行\"")
    expect(content).toContain("name=\"groups\"")
    expect(content).toContain("tab=\"小组排行\"")
  })

  it('contains student ranking table', () => {
    expect(content).toContain(':columns="studentColumns"')
    expect(content).toContain(':data="filteredStudentRankings"')
  })

  it('contains group ranking table', () => {
    expect(content).toContain(':columns="groupColumns"')
    expect(content).toContain(':data="groupRankings"')
  })
})

describe('ConductRankings API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getStudentRankings')
    expect(content).toContain('getGroupRankings')
    expect(content).toContain('getSemesters')
    expect(content).toContain('exportRankings')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getStudentRankings with optional semester_id', () => {
    expect(content).toContain('getStudentRankings(classId.value, params)')
  })

  it('calls getGroupRankings with optional semester_id', () => {
    expect(content).toContain('getGroupRankings(classId.value, params)')
  })

  it('calls getSemesters for semester options', () => {
    expect(content).toContain('getSemesters(classId.value)')
  })

  it('calls exportRankings for Excel export', () => {
    expect(content).toContain('exportRankings(classId.value, params)')
  })
})

describe('ConductRankings operations', () => {
  it('defines student columns (rank, name, total_points)', () => {
    expect(content).toContain("title: '排名'")
    expect(content).toContain("key: 'rank'")
    expect(content).toContain("title: '姓名'")
    expect(content).toContain("key: 'student_name'")
    expect(content).toContain("title: '总积分'")
    expect(content).toContain("key: 'total_points'")
  })

  it('defines group columns (rank, group_name, member_count, total_points, avg_points)', () => {
    expect(content).toContain("key: 'group_name'")
    expect(content).toContain("key: 'member_count'")
    expect(content).toContain("key: 'avg_points'")
  })

  it('shows medal emojis for top 3 ranks', () => {
    expect(content).toContain("const medals = { 1: '\u{1F947}', 2: '\u{1F948}', 3: '\u{1F949}' }")
  })

  it('computes average points for group rankings', () => {
    expect(content).toContain('(row.total_points / row.member_count).toFixed(1)')
  })

  it('filters student rankings by search name', () => {
    expect(content).toContain('const filteredStudentRankings = computed(')
    expect(content).toContain("searchName.value.toLowerCase()")
  })

  it('builds distribution chart with 5 score buckets', () => {
    expect(content).toContain('function buildDistOption(rankings)')
    expect(content).toContain("label: '<0'")
    expect(content).toContain("label: '0-10'")
    expect(content).toContain("label: '10-30'")
    expect(content).toContain("label: '30-50'")
    expect(content).toContain("label: '50+'")
    expect(content).toContain("type: 'bar'")
  })

  it('handles tab change to reload appropriate rankings', () => {
    expect(content).toContain('function handleTabChange(tab)')
    expect(content).toContain("tab === 'students'")
    expect(content).toContain('loadStudentRankings()')
    expect(content).toContain('loadGroupRankings()')
  })

  it('watches semesterId to reload rankings', () => {
    expect(content).toContain('watch(semesterId,')
  })

  it('has top-rank CSS style for top 3', () => {
    expect(content).toContain('.top-rank td')
    expect(content).toContain('font-weight: 600')
  })

  it('loads semesters and student rankings on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadSemesters()')
    expect(content).toContain('loadStudentRankings()')
  })
})

describe('ConductRankings error handling', () => {
  it('wraps loadStudentRankings in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadStudentRankings'),
      content.indexOf('async function loadGroupRankings')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadGroupRankings in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadGroupRankings'),
      content.indexOf('function handleTabChange')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps handleExport in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleExport'),
      content.indexOf('watch(semesterId')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '导出失败'")
  })

  it('wraps loadSemesters in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadSemesters'),
      content.indexOf('async function loadStudentRankings')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })
})
