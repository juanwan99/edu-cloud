<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">课程表</h1>
      <p class="page-subtitle">按班级查看和编辑课程表</p>
    </div>

    <!-- 筛选栏 -->
    <n-space style="margin-bottom: 16px;">
      <n-select v-model:value="selectedGrade" :options="gradeOptions" placeholder="选择年级"
        style="width: 140px;" @update:value="onGradeChange" />
      <n-select v-model:value="selectedClassId" :options="classOptions" placeholder="选择班级"
        style="width: 160px;" @update:value="loadTimetable" />
      <n-button type="primary" :disabled="!selectedClassId || !editing" @click="handleSave" :loading="saving">
        保存课表
      </n-button>
      <n-button v-if="selectedClassId && !editing" @click="editing = true">编辑</n-button>
      <n-button v-if="editing" @click="editing = false; loadTimetable()">取消</n-button>
    </n-space>

    <n-spin :show="loading">
      <!-- 课表网格 -->
      <div v-if="periods.length && selectedClassId" class="timetable-grid">
        <table>
          <thead>
            <tr>
              <th style="width: 80px;">节次</th>
              <th style="width: 60px;">时间</th>
              <th v-for="d in weekdays" :key="d.value">{{ d.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in classPeriods" :key="p.id" :class="{ 'break-row': p.period_type !== 'class' }">
              <td class="period-name">{{ p.name }}</td>
              <td class="period-time">{{ p.start_time?.slice(0, 5) }}</td>
              <td v-for="d in weekdays" :key="d.value" class="slot-cell"
                @click="editing && p.period_type === 'class' && openSlotEdit(d.value, p.id)">
                <template v-if="p.period_type === 'class'">
                  <div v-if="getSlot(d.value, p.id)" class="slot-content">
                    <span class="slot-subject">{{ getSlot(d.value, p.id).subject_code }}</span>
                    <span class="slot-teacher">{{ teacherName(getSlot(d.value, p.id).teacher_id) }}</span>
                  </div>
                  <div v-else-if="editing" class="slot-empty">+</div>
                </template>
                <template v-else>
                  <span class="break-label">{{ p.name }}</span>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <n-empty v-else-if="!loading" description="选择年级和班级查看课表" />
    </n-spin>

    <!-- 编辑弹窗 -->
    <n-modal v-model:show="showSlotEdit" preset="dialog" title="设置课程" positive-text="确定" negative-text="取消"
      @positive-click="confirmSlot">
      <n-form label-placement="left" label-width="60">
        <n-form-item label="科目">
          <n-select v-model:value="slotForm.subject_code" :options="subjectOptions" placeholder="选择科目" />
        </n-form-item>
        <n-form-item label="教师">
          <n-select v-model:value="slotForm.teacher_id" :options="teacherOptions" placeholder="选择教师" filterable />
        </n-form-item>
        <n-form-item label="教室">
          <n-input v-model:value="slotForm.room" placeholder="可选" />
        </n-form-item>
      </n-form>
      <n-button v-if="getSlot(slotForm.weekday, slotForm.period_id)" type="error" text size="small"
        @click="removeSlot">清除此节</n-button>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { getCurrentSemester, getPeriods, getTimetable, saveTimetable } from '../api/academic.js'
import { listClasses, listGrades } from '../api/students.js'
import { listTeachers } from '../api/teachers.js'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)

const semesterId = ref(null)
const grades = ref([])
const classes = ref([])
const allTeachers = ref([])
const periods = ref([])
const slots = ref([])

const selectedGrade = ref(null)
const selectedClassId = ref(null)
const showSlotEdit = ref(false)
const slotForm = ref({ weekday: 0, period_id: '', subject_code: '', teacher_id: '', room: '' })

const weekdays = [
  { value: 1, label: '周一' }, { value: 2, label: '周二' }, { value: 3, label: '周三' },
  { value: 4, label: '周四' }, { value: 5, label: '周五' },
]

const SUBJECTS = [
  { code: 'YW', label: '语文' }, { code: 'SX', label: '数学' }, { code: 'YY', label: '英语' },
  { code: 'WL', label: '物理' }, { code: 'HX', label: '化学' }, { code: 'SW', label: '生物' },
  { code: 'ZZ', label: '政治' }, { code: 'LS', label: '历史' }, { code: 'DL', label: '地理' },
  { code: 'TY', label: '体育' }, { code: 'YL', label: '音乐' }, { code: 'MS', label: '美术' },
  { code: 'XX', label: '信息' }, { code: 'TJ', label: '通技' },
]

const subjectOptions = SUBJECTS.map(s => ({ value: s.code, label: `${s.label} (${s.code})` }))

const gradeOptions = computed(() =>
  [...new Set(classes.value.map(c => c.grade))].sort().map(g => ({ value: g, label: g }))
)

const classOptions = computed(() =>
  classes.value
    .filter(c => c.grade === selectedGrade.value)
    .map(c => ({ value: c.id, label: c.name }))
)

const classPeriods = computed(() => periods.value)

const teacherOptions = computed(() =>
  allTeachers.value.map(t => ({ value: t.id, label: `${t.display_name || t.username} (${t.id.slice(0, 6)})` }))
)

function getSlot(weekday, periodId) {
  return slots.value.find(s => s.weekday === weekday && s.period_id === periodId)
}

function teacherName(tid) {
  const t = allTeachers.value.find(t => t.id === tid)
  return t ? (t.display_name || t.username) : tid?.slice(0, 6) || ''
}

function onGradeChange() {
  selectedClassId.value = null
  slots.value = []
}

function openSlotEdit(weekday, periodId) {
  const existing = getSlot(weekday, periodId)
  slotForm.value = {
    weekday, period_id: periodId,
    subject_code: existing?.subject_code || '',
    teacher_id: existing?.teacher_id || '',
    room: existing?.room || '',
  }
  showSlotEdit.value = true
}

function confirmSlot() {
  if (!slotForm.value.subject_code || !slotForm.value.teacher_id) {
    message.warning('请选择科目和教师'); return
  }
  const idx = slots.value.findIndex(s => s.weekday === slotForm.value.weekday && s.period_id === slotForm.value.period_id)
  const slot = { ...slotForm.value }
  if (idx >= 0) slots.value[idx] = slot
  else slots.value.push(slot)
  showSlotEdit.value = false
}

function removeSlot() {
  slots.value = slots.value.filter(s => !(s.weekday === slotForm.value.weekday && s.period_id === slotForm.value.period_id))
  showSlotEdit.value = false
}

async function loadTimetable() {
  if (!selectedClassId.value || !semesterId.value) return
  loading.value = true
  try {
    const { data } = await getTimetable({ semester_id: semesterId.value, class_id: selectedClassId.value })
    slots.value = data
    editing.value = false
  } catch { message.error('加载课表失败') }
  loading.value = false
}

async function handleSave() {
  saving.value = true
  try {
    await saveTimetable(selectedClassId.value, {
      semester_id: semesterId.value,
      slots: slots.value.map(s => ({
        weekday: s.weekday, period_id: s.period_id,
        subject_code: s.subject_code, teacher_id: s.teacher_id, room: s.room || null,
      })),
    })
    message.success('课表保存成功')
    editing.value = false
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
  saving.value = false
}

async function init() {
  loading.value = true
  try {
    const [semRes, clsRes, tRes] = await Promise.all([
      getCurrentSemester(),
      listClasses(),
      listTeachers().catch(() => ({ data: [] })),
    ])
    if (semRes.data?.id) {
      semesterId.value = semRes.data.id
      const { data: p } = await getPeriods(semRes.data.id)
      periods.value = p
    }
    classes.value = Array.isArray(clsRes.data) ? clsRes.data : (clsRes.data?.items || [])
    allTeachers.value = Array.isArray(tRes.data) ? tRes.data : (tRes.data?.items || [])
  } catch (e) { message.error('初始化失败') }
  loading.value = false
}

onMounted(init)
</script>

<style scoped>
.timetable-grid { overflow-x: auto; }
.timetable-grid table { width: 100%; border-collapse: collapse; background: white; border-radius: var(--radius-lg); overflow: hidden; }
.timetable-grid th { background: var(--macaron-purple-light); padding: 10px 8px; font-size: 13px; font-weight: 600; text-align: center; border: 1px solid var(--color-border-light); }
.timetable-grid td { padding: 6px 4px; text-align: center; border: 1px solid var(--color-border-light); min-height: 50px; vertical-align: middle; }
.period-name { font-weight: 600; font-size: 12px; background: var(--macaron-mint-light); }
.period-time { font-size: 11px; color: var(--color-text-muted); }
.slot-cell { cursor: pointer; min-width: 100px; height: 52px; transition: background .15s; }
.slot-cell:hover { background: var(--macaron-yellow-light); }
.slot-content { display: flex; flex-direction: column; gap: 2px; }
.slot-subject { font-weight: 600; font-size: 13px; color: var(--color-text-primary); }
.slot-teacher { font-size: 11px; color: var(--color-text-muted); }
.slot-empty { color: #ccc; font-size: 20px; }
.break-row td { background: #f8f8f8; height: 28px; }
.break-label { font-size: 11px; color: #bbb; }
</style>
