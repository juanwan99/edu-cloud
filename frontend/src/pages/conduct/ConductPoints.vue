<template>
  <div>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: var(--space-4);">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Quick add card -->
      <n-card title="快速加分" style="margin-bottom: var(--space-4);">
        <n-space vertical :size="16">
          <!-- Student selection -->
          <div>
            <div style="margin-bottom: var(--space-2); font-weight: var(--fw-medium);">选择学生</div>
            <n-select
              v-model:value="selectedStudents"
              :options="studentOptions"
              multiple
              filterable
              placeholder="搜索并选择学生"
              :loading="loadingStudents"
            />
          </div>

          <!-- Rule quick buttons -->
          <div v-if="ruleCategories.length > 0">
            <div style="margin-bottom: var(--space-2); font-weight: var(--fw-medium);">班规快捷操作</div>
            <n-collapse>
              <n-collapse-item
                v-for="cat in ruleCategories"
                :key="cat.id"
                :title="cat.name"
                :name="cat.id"
              >
                <n-space :size="8" style="flex-wrap: wrap;">
                  <n-button
                    v-for="item in cat.items"
                    :key="item.id"
                    :type="item.default_points >= 0 ? 'success' : 'error'"
                    size="small"
                    secondary
                    :disabled="selectedStudents.length === 0"
                    @click="applyRule(item)"
                  >
                    {{ item.name }}（{{ item.default_points >= 0 ? '+' : '' }}{{ item.default_points }}）
                  </n-button>
                </n-space>
              </n-collapse-item>
            </n-collapse>
          </div>

          <!-- Manual input -->
          <n-divider>手动输入</n-divider>
          <n-space>
            <n-input-number
              v-model:value="manualPoints"
              placeholder="积分"
              :min="-100"
              :max="100"
              style="width: 120px;"
            />
            <n-input
              v-model:value="manualReason"
              placeholder="原因说明"
              style="width: 240px;"
            />
            <n-button
              type="primary"
              :disabled="selectedStudents.length === 0 || !manualPoints"
              :loading="submitting"
              @click="submitManual"
            >
              提交
            </n-button>
          </n-space>
        </n-space>
      </n-card>

      <!-- Recent records -->
      <n-card title="最近记录">
        <n-spin :show="loadingRecords">
          <n-data-table
            :columns="recordColumns"
            :data="recentRecords"
            :pagination="false"
            size="small"
          />
        </n-spin>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader, NCard, NSpace, NSelect, NButton, NInputNumber,
  NInput, NDataTable, NSpin, NDivider, NCollapse, NCollapseItem,
  NAlert, NTag, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  addPoints, getRecords, getRules, getStudentRankings,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => {
  const role = auth.currentRole
  if (!role) return null
  return role.class_ids?.[0] || null
})

const selectedStudents = ref([])
const studentOptions = ref([])
const loadingStudents = ref(false)
const ruleCategories = ref([])
const manualPoints = ref(null)
const manualReason = ref('')
const submitting = ref(false)
const recentRecords = ref([])
const loadingRecords = ref(false)

const recordColumns = [
  {
    title: '时间',
    key: 'created_at',
    width: 160,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-',
  },
  { title: '学生', key: 'student_name', width: 100 },
  {
    title: '积分',
    key: 'points',
    width: 80,
    render: (row) => h(NTag, {
      type: row.points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => `${row.points >= 0 ? '+' : ''}${row.points}`),
  },
  { title: '原因', key: 'note', ellipsis: { tooltip: true } },
  { title: '操作人', key: 'operator_name', width: 100 },
]

async function loadStudents() {
  if (!classId.value) return
  loadingStudents.value = true
  try {
    const res = await getStudentRankings(classId.value, {})
    const rankings = res.data.rankings || res.data || []
    studentOptions.value = rankings.map((s) => ({
      label: s.student_name,
      value: s.student_id,
    }))
  } catch {
    studentOptions.value = []
  } finally {
    loadingStudents.value = false
  }
}

async function loadRules() {
  if (!classId.value) return
  try {
    const res = await getRules(classId.value)
    ruleCategories.value = res.data.categories || res.data || []
  } catch {
    ruleCategories.value = []
  }
}

async function loadRecentRecords() {
  if (!classId.value) return
  loadingRecords.value = true
  try {
    const res = await getRecords(classId.value, { page: 1, size: 20 })
    recentRecords.value = res.data.items || res.data || []
  } catch {
    recentRecords.value = []
  } finally {
    loadingRecords.value = false
  }
}

async function applyRule(ruleItem) {
  if (selectedStudents.value.length === 0) return
  submitting.value = true
  try {
    await addPoints(classId.value, {
      student_ids: selectedStudents.value,
      points: ruleItem.default_points,
      note: ruleItem.name,
      rule_item_id: ruleItem.id,
    })
    message.success(`已为 ${selectedStudents.value.length} 名学生${ruleItem.default_points >= 0 ? '加' : '扣'} ${Math.abs(ruleItem.default_points)} 分`)
    await loadRecentRecords()
    await loadStudents()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function submitManual() {
  if (selectedStudents.value.length === 0 || !manualPoints.value) return
  submitting.value = true
  try {
    await addPoints(classId.value, {
      student_ids: selectedStudents.value,
      points: manualPoints.value,
      note: manualReason.value || undefined,
    })
    message.success(`已为 ${selectedStudents.value.length} 名学生${manualPoints.value >= 0 ? '加' : '扣'} ${Math.abs(manualPoints.value)} 分`)
    manualPoints.value = null
    manualReason.value = ''
    await loadRecentRecords()
    await loadStudents()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (classId.value) {
    loadStudents()
    loadRules()
    loadRecentRecords()
  }
})
</script>
