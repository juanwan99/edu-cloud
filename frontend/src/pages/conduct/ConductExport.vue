<template>
  <div>
    <n-page-header title="数据导出" subtitle="导出操行数据为 Excel 文件" style="margin-bottom: 16px;" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <n-card v-if="classId">
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

        <!-- Date range (for records) -->
        <n-form-item v-if="exportType === 'records'" label="日期范围">
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            clearable
            style="width: 100%;"
          />
        </n-form-item>

        <!-- Semester (for rankings) -->
        <n-form-item v-if="exportType === 'rankings'" label="学期">
          <n-select
            v-model:value="semesterId"
            :options="semesterOptions"
            placeholder="选择学期（可选）"
            clearable
            style="width: 300px;"
          />
        </n-form-item>

        <!-- Export button -->
        <n-button
          type="primary"
          size="large"
          :loading="exporting"
          @click="handleExport"
        >
          导出 Excel
        </n-button>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NCard, NSpace, NFormItem, NRadioGroup, NRadio,
  NDatePicker, NSelect, NButton, NAlert, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { exportRecords, exportRankings, getSemesters } from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const exportType = ref('records')
const dateRange = ref(null)
const semesterId = ref(null)
const semesterOptions = ref([])
const exporting = ref(false)

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

async function handleExport() {
  if (!classId.value) return
  exporting.value = true
  try {
    if (exportType.value === 'records') {
      const params = {}
      if (dateRange.value && dateRange.value.length === 2) {
        params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
        params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
      }
      const res = await exportRecords(classId.value, params)
      downloadBlob(res.data, `积分记录_${new Date().toISOString().split('T')[0]}.xlsx`)
    } else {
      const params = {}
      if (semesterId.value) params.semester_id = semesterId.value
      const res = await exportRankings(classId.value, params)
      downloadBlob(res.data, `排行榜_${new Date().toISOString().split('T')[0]}.xlsx`)
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
})
</script>
