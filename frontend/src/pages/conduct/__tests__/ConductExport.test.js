/**
 * ConductExport source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (export type, file format, field selection, date range, semester, preview, history)
 *  3. API calls via conduct.js (exportRecords, exportRankings, getSemesters, getRecords, getStudentRankings)
 *  4. Export operations (CSV conversion, blob download, Excel export)
 *  5. Error handling (try-catch in export and preview)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductExport.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductExport smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductExport.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductExport template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('title="数据导出"')
    expect(content).toContain('导出操行数据为 Excel / CSV 文件')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains export type radio (records/rankings)', () => {
    expect(content).toContain('v-model:value="exportType"')
    expect(content).toContain('value="records"')
    expect(content).toContain('value="rankings"')
    expect(content).toContain('积分记录')
    expect(content).toContain('排行榜')
  })

  it('contains file format radio (excel/csv)', () => {
    expect(content).toContain('v-model:value="fileFormat"')
    expect(content).toContain('value="excel"')
    expect(content).toContain('value="csv"')
    expect(content).toContain('Excel (.xlsx)')
    expect(content).toContain('CSV (.csv)')
  })

  it('contains field selection checkboxes', () => {
    expect(content).toContain('v-model:value="selectedFields"')
    expect(content).toContain('value="student_name"')
    expect(content).toContain('value="points"')
    expect(content).toContain('value="created_at"')
    expect(content).toContain('value="note"')
    expect(content).toContain('value="operator_name"')
  })

  it('contains date range picker for records export type', () => {
    expect(content).toContain("v-if=\"exportType === 'records'\"")
    expect(content).toContain('type="daterange"')
  })

  it('contains semester selector for rankings export type', () => {
    expect(content).toContain("v-if=\"exportType === 'rankings'\"")
    expect(content).toContain('v-model:value="semesterId"')
  })

  it('contains preview and export buttons', () => {
    expect(content).toContain('预览数据')
    expect(content).toContain(':loading="previewing"')
    expect(content).toContain(':loading="exporting"')
    expect(content).toContain(':disabled="selectedFields.length === 0"')
  })

  it('contains preview data table area', () => {
    expect(content).toContain('v-if="previewData.length > 0"')
    expect(content).toContain('数据预览（前 5 行）')
    expect(content).toContain('previewColumns')
    expect(content).toContain('previewTotal')
  })

  it('contains export history section', () => {
    expect(content).toContain('v-if="exportHistory.length > 0"')
    expect(content).toContain('最近导出记录')
  })
})

describe('ConductExport API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('exportRecords')
    expect(content).toContain('exportRankings')
    expect(content).toContain('getSemesters')
    expect(content).toContain('getRecords')
    expect(content).toContain('getStudentRankings')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getSemesters for semester options', () => {
    expect(content).toContain('getSemesters(classId.value)')
  })

  it('calls getRecords for records preview', () => {
    expect(content).toContain('getRecords(classId.value, params)')
  })

  it('calls getStudentRankings for rankings preview', () => {
    expect(content).toContain('getStudentRankings(classId.value, params)')
  })

  it('calls exportRecords for Excel records export', () => {
    expect(content).toContain('exportRecords(classId.value, params)')
  })

  it('calls exportRankings for Excel rankings export', () => {
    expect(content).toContain('exportRankings(classId.value, params)')
  })
})

describe('ConductExport operations', () => {
  it('has field label mapping for column headers', () => {
    expect(content).toContain("student_name: '姓名'")
    expect(content).toContain("points: '积分'")
    expect(content).toContain("created_at: '日期'")
    expect(content).toContain("note: '原因'")
    expect(content).toContain("operator_name: '操作人'")
  })

  it('defaults selected fields to all 5 fields', () => {
    expect(content).toContain("const selectedFields = ref(['student_name', 'points', 'created_at', 'note', 'operator_name'])")
  })

  it('has convertToCSV function with BOM for Excel UTF-8 support', () => {
    expect(content).toContain('function convertToCSV(data, fields)')
    // BOM character
    expect(content).toMatch(/return '﻿'/)
  })

  it('has downloadBlob function for file download', () => {
    expect(content).toContain('function downloadBlob(blob, filename)')
    expect(content).toContain('URL.createObjectURL(blob)')
    expect(content).toContain('a.download = filename')
  })

  it('manages export history via localStorage', () => {
    expect(content).toContain("const HISTORY_KEY = 'conduct_export_history'")
    expect(content).toContain('localStorage.getItem(HISTORY_KEY)')
    expect(content).toContain('localStorage.setItem(HISTORY_KEY')
  })

  it('limits export history to 3 entries', () => {
    expect(content).toContain('.slice(0, 3)')
  })

  it('generates filenames with date suffix', () => {
    expect(content).toContain("new Date().toISOString().split('T')[0]")
    expect(content).toContain("积分记录")
    expect(content).toContain("排行榜")
  })

  it('loads semesters and history on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('if (classId.value) loadSemesters()')
    expect(content).toContain('loadHistory()')
  })
})

describe('ConductExport error handling', () => {
  it('wraps preview in try-catch', () => {
    const previewBlock = content.slice(
      content.indexOf('async function handlePreview'),
      content.indexOf('function downloadBlob')
    )
    expect(previewBlock).toContain('try {')
    expect(previewBlock).toContain('} catch')
    expect(previewBlock).toContain('加载预览数据失败')
  })

  it('wraps export in try-catch with error detail extraction', () => {
    const exportBlock = content.slice(
      content.indexOf('async function handleExport'),
      content.indexOf('onMounted(')
    )
    expect(exportBlock).toContain('try {')
    expect(exportBlock).toContain('} catch')
    expect(exportBlock).toContain("e.response?.data?.detail || '导出失败，请稍后重试'")
  })

  it('wraps loadSemesters in try-catch', () => {
    const semBlock = content.slice(
      content.indexOf('async function loadSemesters'),
      content.indexOf('async function handlePreview')
    )
    expect(semBlock).toContain('try {')
    expect(semBlock).toContain('} catch')
  })

  it('wraps loadHistory in try-catch', () => {
    expect(content).toContain('function loadHistory()')
    const histBlock = content.slice(
      content.indexOf('function loadHistory()'),
      content.indexOf('function addHistory')
    )
    expect(histBlock).toContain('try {')
    expect(histBlock).toContain('} catch')
  })
})
