<template>
  <div>
    <n-page-header title="数据导出" subtitle="导出操行数据为 Excel / CSV 文件" class="section-gap" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" class="section-gap">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <n-card class="section-gap">
        <n-space vertical :size="20">
          <!-- Export type -->
          <n-form-item label="导出类型">
            <n-radio-group v-model:value="exportType">
              <n-space>
                <n-radio value="records">积分记录</n-radio>
                <n-radio value="rankings">排行榜</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>

          <!-- File format -->
          <n-form-item label="文件格式">
            <n-radio-group v-model:value="fileFormat">
              <n-space>
                <n-radio value="excel">Excel (.xlsx)</n-radio>
                <n-radio value="csv">CSV (.csv)</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>

          <!-- Field selection -->
          <n-form-item label="导出字段">
            <n-checkbox-group v-model:value="selectedFields">
              <n-space>
                <n-checkbox value="student_name" label="姓名" />
                <n-checkbox value="points" label="积分" />
                <n-checkbox value="created_at" label="日期" />
                <n-checkbox value="note" label="原因" />
                <n-checkbox value="operator_name" label="操作人" />
              </n-space>
            </n-checkbox-group>
          </n-form-item>

          <!-- Date range (for records) -->
          <n-form-item v-if="exportType === 'records'" label="日期范围">
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              clearable
              class="full-width"
            />
          </n-form-item>

          <!-- Semester (for rankings) -->
          <n-form-item v-if="exportType === 'rankings'" label="学期">
            <n-select
              v-model:value="semesterId"
              :options="semesterOptions"
              placeholder="选择学期（可选）"
              clearable
              class="select-md"
            />
          </n-form-item>

          <!-- Preview + Export buttons -->
          <n-space>
            <n-button @click="handlePreview" :loading="previewing">预览数据</n-button>
            <n-button
              type="primary"
              size="large"
              :loading="exporting"
              :disabled="selectedFields.length === 0"
              @click="handleExport"
            >
              导出 {{ fileFormat === 'excel' ? 'Excel' : 'CSV' }}
            </n-button>
          </n-space>
        </n-space>
      </n-card>

      <!-- Preview area -->
      <n-card v-if="previewData.length > 0" title="数据预览（前 5 行）" class="section-gap">
        <n-data-table
          :columns="previewColumns"
          :data="previewData"
          :pagination="false"
          size="small"
          :bordered="false"
        />
        <div class="preview-footer">
          共 {{ previewTotal }} 条记录，仅预览前 5 条
        </div>
      </n-card>

      <!-- Export history -->
      <n-card v-if="exportHistory.length > 0" title="最近导出记录" size="small">
        <n-list bordered size="small">
          <n-list-item v-for="(h, idx) in exportHistory" :key="idx">
            <div class="row-between">
              <span>{{ h.filename }}</span>
              <span class="text-muted">{{ h.time }}</span>
            </div>
          </n-list-item>
        </n-list>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NCard, NSpace, NFormItem, NRadioGroup, NRadio,
  NDatePicker, NSelect, NButton, NAlert, NCheckboxGroup, NCheckbox,
  NDataTable, NList, NListItem, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  exportRecords, exportRankings, getSemesters,
  getRecords, getStudentRankings,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const exportType = ref('records')
const fileFormat = ref('excel')
const selectedFields = ref(['student_name', 'points', 'created_at', 'note', 'operator_name'])
const dateRange = ref(null)
const semesterId = ref(null)
const semesterOptions = ref([])
const exporting = ref(false)
const previewing = ref(false)

// Preview state
const previewData = ref([])
const previewTotal = ref(0)

// Field label map
const fieldLabels = {
  student_name: '姓名',
  points: '积分',
  created_at: '日期',
  note: '原因',
  operator_name: '操作人',
}

const previewColumns = computed(() =>
  selectedFields.value.map((key) => ({
    title: fieldLabels[key] || key,
    key,
    render: key === 'created_at'
      ? (row) => row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-'
      : undefined,
  }))
)

// Export history (localStorage)
const HISTORY_KEY = 'conduct_export_history'
const exportHistory = ref([])

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    exportHistory.value = raw ? JSON.parse(raw).slice(0, 3) : []
  } catch {
    exportHistory.value = []
  }
}

function addHistory(filename) {
  const entry = { filename, time: new Date().toLocaleString('zh-CN') }
  const list = [entry, ...exportHistory.value].slice(0, 3)
  exportHistory.value = list
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list))
}

async function loadSemesters() {
  if (!classId.value) return
  try {
    const res = await getSemesters(classId.value)
    const list = res.data.semesters || res.data || []
    semesterOptions.value = list.map((s) => ({
      label: s.name + (s.is_active ? '（当前）' : ''),
      value: s.id,
    }))
  } catch {
    semesterOptions.value = []
  }
}

async function handlePreview() {
  if (!classId.value) return
  previewing.value = true
  try {
    if (exportType.value === 'records') {
      const params = { page: 1, page_size: 5 }
      if (dateRange.value && dateRange.value.length === 2) {
        params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
        params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
      }
      const res = await getRecords(classId.value, params)
      const items = res.data.items || res.data || []
      previewData.value = items.slice(0, 5)
      previewTotal.value = res.data.total || items.length
    } else {
      const params = {}
      if (semesterId.value) params.semester_id = semesterId.value
      const res = await getStudentRankings(classId.value, params)
      const rankings = res.data.rankings || res.data || []
      previewData.value = rankings.slice(0, 5).map((r) => ({
        student_name: r.student_name,
        points: r.total_points,
        created_at: null,
        note: '',
        operator_name: '',
      }))
      previewTotal.value = rankings.length
    }
  } catch {
    previewData.value = []
    previewTotal.value = 0
    message.error('加载预览数据失败')
  } finally {
    previewing.value = false
  }
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

function convertToCSV(data, fields) {
  const headers = fields.map((f) => fieldLabels[f] || f)
  const rows = data.map((row) =>
    fields.map((f) => {
      let val = row[f] ?? ''
      if (f === 'created_at' && val) val = new Date(val).toLocaleString('zh-CN')
      // Escape CSV values
      val = String(val).replace(/"/g, '""')
      return `"${val}"`
    }).join(',')
  )
  // BOM for Excel to recognize UTF-8
  return '﻿' + [headers.join(','), ...rows].join('\n')
}

async function handleExport() {
  if (!classId.value) return
  if (selectedFields.value.length === 0) {
    message.warning('请至少选择一个导出字段')
    return
  }
  exporting.value = true
  try {
    const dateSuffix = new Date().toISOString().split('T')[0]
    if (fileFormat.value === 'csv') {
      // CSV: fetch data via JSON API, convert client-side
      let allData = []
      if (exportType.value === 'records') {
        const params = { page: 1, page_size: 9999 }
        if (dateRange.value && dateRange.value.length === 2) {
          params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
          params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
        }
        const res = await getRecords(classId.value, params)
        allData = res.data.items || res.data || []
      } else {
        const params = {}
        if (semesterId.value) params.semester_id = semesterId.value
        const res = await getStudentRankings(classId.value, params)
        const rankings = res.data.rankings || res.data || []
        allData = rankings.map((r) => ({
          student_name: r.student_name,
          points: r.total_points,
          created_at: null,
          note: '',
          operator_name: '',
        }))
      }
      const csv = convertToCSV(allData, selectedFields.value)
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const filename = `${exportType.value === 'records' ? '积分记录' : '排行榜'}_${dateSuffix}.csv`
      downloadBlob(blob, filename)
      addHistory(filename)
    } else {
      // Excel: use backend export endpoint
      let filename
      if (exportType.value === 'records') {
        const params = {}
        if (dateRange.value && dateRange.value.length === 2) {
          params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
          params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
        }
        const res = await exportRecords(classId.value, params)
        filename = `积分记录_${dateSuffix}.xlsx`
        downloadBlob(res.data, filename)
      } else {
        const params = {}
        if (semesterId.value) params.semester_id = semesterId.value
        const res = await exportRankings(classId.value, params)
        filename = `排行榜_${dateSuffix}.xlsx`
        downloadBlob(res.data, filename)
      }
      addHistory(filename)
    }
    message.success('导出成功')
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  if (classId.value) loadSemesters()
  loadHistory()
})
</script>

<style scoped>
.section-gap {
  margin-bottom: var(--space-4);
}

.full-width {
  width: 100%;
}

.select-md {
  width: 300px;
}

.preview-footer {
  margin-top: var(--space-2);
  font-size: 16px;
  color: rgba(255, 255, 255, 0.4);
}

.row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-muted {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
