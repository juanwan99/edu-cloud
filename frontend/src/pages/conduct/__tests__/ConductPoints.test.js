/**
 * ConductPoints source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (student select, rule buttons, manual input, recent records)
 *  3. API calls via conduct.js (addPoints, getRecords, getRules, getStudentRankings)
 *  4. Operations (apply rule, submit manual, record columns)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductPoints.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductPoints smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductPoints.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductPoints template sections', () => {
  it('contains class-not-selected alert and quick add card', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('title="快速加分"')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains quick add card with student selection', () => {
    expect(content).toContain('title="快速加分"')
    expect(content).toContain('选择学生')
    expect(content).toContain('v-model:value="selectedStudents"')
    expect(content).toContain(':options="studentOptions"')
    expect(content).toContain('搜索并选择学生')
  })

  it('contains rule quick buttons in collapsible categories', () => {
    expect(content).toContain('班规快捷操作')
    expect(content).toContain('v-for="cat in ruleCategories"')
    expect(content).toContain('v-for="item in cat.items"')
    expect(content).toContain('@click="applyRule(item)"')
  })

  it('contains manual input section with divider', () => {
    expect(content).toContain('手动输入')
    expect(content).toContain('v-model:value="manualPoints"')
    expect(content).toContain('v-model:value="manualReason"')
    expect(content).toContain(':min="-100"')
    expect(content).toContain(':max="100"')
    expect(content).toContain('@click="submitManual"')
  })

  it('contains recent records table', () => {
    expect(content).toContain('title="最近记录"')
    expect(content).toContain(':columns="recordColumns"')
    expect(content).toContain(':data="recentRecords"')
  })
})

describe('ConductPoints API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('addPoints')
    expect(content).toContain('getRecords')
    expect(content).toContain('getRules')
    expect(content).toContain('getStudentRankings')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getStudentRankings to populate student options', () => {
    expect(content).toContain('getStudentRankings(classId.value, {})')
  })

  it('calls getRules to load rule categories', () => {
    expect(content).toContain('getRules(classId.value)')
  })

  it('calls getRecords with size 20 for recent records', () => {
    expect(content).toContain('getRecords(classId.value, { page: 1, size: 20 })')
  })

  it('calls addPoints for both rule application and manual submission', () => {
    expect(content).toContain('addPoints(classId.value, {')
    // rule application passes rule_item_id
    expect(content).toContain('rule_item_id: ruleItem.id')
    // both pass student_ids and points
    expect(content).toContain('student_ids: selectedStudents.value')
  })
})

describe('ConductPoints operations', () => {
  it('defines record table columns (time, student, points, reason, operator)', () => {
    expect(content).toContain("title: '时间'")
    expect(content).toContain("key: 'created_at'")
    expect(content).toContain("title: '学生'")
    expect(content).toContain("key: 'student_name'")
    expect(content).toContain("title: '积分'")
    expect(content).toContain("key: 'points'")
    expect(content).toContain("title: '原因'")
    expect(content).toContain("key: 'note'")
    expect(content).toContain("title: '操作人'")
    expect(content).toContain("key: 'operator_name'")
  })

  it('applies rule with default_points and rule_item_id', () => {
    expect(content).toContain('async function applyRule(ruleItem)')
    expect(content).toContain('points: ruleItem.default_points')
    expect(content).toContain('note: ruleItem.name')
    expect(content).toContain('rule_item_id: ruleItem.id')
  })

  it('submits manual points with optional reason', () => {
    expect(content).toContain('async function submitManual()')
    expect(content).toContain('points: manualPoints.value')
    expect(content).toContain('note: manualReason.value || undefined')
  })

  it('reloads records and students after point submission', () => {
    expect(content).toContain('await loadRecentRecords()')
    expect(content).toContain('await loadStudents()')
  })

  it('resets manual form after successful submission', () => {
    expect(content).toContain('manualPoints.value = null')
    expect(content).toContain("manualReason.value = ''")
  })

  it('displays success message with student count and points', () => {
    expect(content).toContain("selectedStudents.value.length")
    expect(content).toContain("Math.abs(ruleItem.default_points)")
  })

  it('loads students, rules, and records on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadStudents()')
    expect(content).toContain('loadRules()')
    expect(content).toContain('loadRecentRecords()')
  })
})

describe('ConductPoints error handling', () => {
  it('wraps loadStudents in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadStudents'),
      content.indexOf('async function loadRules')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadRules in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadRules'),
      content.indexOf('async function loadRecentRecords')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadRecentRecords in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadRecentRecords'),
      content.indexOf('async function applyRule')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps applyRule in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function applyRule'),
      content.indexOf('async function submitManual')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '操作失败'")
  })

  it('wraps submitManual in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function submitManual'),
      content.indexOf('onMounted(')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '操作失败'")
  })
})
