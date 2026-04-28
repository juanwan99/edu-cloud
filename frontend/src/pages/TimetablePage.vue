<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">课程表</h1>
      <p class="page-subtitle">按班级查看和编辑课程表</p>
    </div>

    <!-- 统计卡片区 -->
    <n-grid :cols="4" :x-gap="12" :y-gap="12" style="margin-bottom: 16px;" v-if="semesterId">
      <n-gi>
        <n-card size="small">
          <n-statistic label="已排课班级" :value="timetableStats.classes_with_timetable || 0">
            <template #suffix>/ {{ timetableStats.total_classes || 0 }}</template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="覆盖率" :value="coveragePercent">
            <template #suffix>%</template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="当前班级课时" :value="currentClassSlotCount" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="空余时段" :value="emptySlotCount" />
        </n-card>
      </n-gi>
    </n-grid>

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
      <n-button v-if="editing" @click="cancelEdit">取消</n-button>
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
              <td v-for="d in weekdays" :key="d.value"
                :class="slotCellClass(d.value, p.id, p.period_type)"
                @click="onSlotClick(d.value, p.id, p.period_type)">
                <template v-if="p.period_type === 'class'">
                  <div v-if="getSlot(d.value, p.id)" class="slot-content">
                    <span class="slot-subject">{{ subjectLabel(getSlot(d.value, p.id).subject_code) }}</span>
                    <span class="slot-teacher">{{ teacherName(getSlot(d.value, p.id).teacher_id) }}</span>
                    <n-tooltip v-if="editing && getConflict(d.value, p.id)" trigger="hover">
                      <template #trigger>
                        <span class="conflict-icon">!</span>
                      </template>
                      {{ getConflict(d.value, p.id) }}
                    </n-tooltip>
                  </div>
                  <div v-else-if="editing" class="slot-empty"
                    :class="{ 'slot-paste-target': clipboardSlot }">
                    {{ clipboardSlot ? '粘贴' : '+' }}
                  </div>
                  <div v-else class="slot-vacant"></div>
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

    <!-- 科目课时统计 -->
    <div v-if="selectedClassId && slots.length" class="subject-stats">
      <n-space :size="8" align="center">
        <span class="stats-label">科目课时：</span>
        <n-tag v-for="item in subjectSlotStats" :key="item.code" :type="item.count >= 5 ? 'success' : 'warning'"
          size="small" round>
          {{ item.label }} {{ item.count }}节
        </n-tag>
      </n-space>
    </div>

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
      <!-- 冲突警告 -->
      <n-alert v-if="slotEditConflict" type="warning" :title="slotEditConflict" style="margin-bottom: 8px;" />
      <n-space>
        <n-button v-if="getSlot(slotForm.weekday, slotForm.period_id)" type="error" text size="small"
          @click="removeSlot">清除此节</n-button>
        <n-button v-if="editing && getSlot(slotForm.weekday, slotForm.period_id)" text size="small"
          @click="copySlot">复制此节</n-button>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { getCurrentSemester, getPeriods, getTimetable, saveTimetable, getTimetableStats } from '../api/academic.js'
import { listClasses } from '../api/students.js'
import { listTeachers } from '../api/teachers.js'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)

const semesterId = ref(null)
const classes = ref([])
const allTeachers = ref([])
const periods = ref([])
const slots = ref([])
const timetableStats = ref({})
const allClassTimetables = ref({})
const clipboardSlot = ref(null)

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

const subjectMap = Object.fromEntries(SUBJECTS.map(s => [s.code, s.label]))
const subjectOptions = SUBJECTS.map(s => ({ value: s.code, label: `${s.label} (${s.code})` }))

function subjectLabel(code) {
  return subjectMap[code] || code
}

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

// -- 统计 computed --

const coveragePercent = computed(() => {
  const rate = timetableStats.value.coverage_rate
  return rate != null ? Math.round(rate * 100) : 0
})

const currentClassSlotCount = computed(() => slots.value.length)

const classPeriodSlots = computed(() => {
  return periods.value.filter(p => p.period_type === 'class')
})

const emptySlotCount = computed(() => {
  if (!selectedClassId.value) return 0
  const totalSlots = classPeriodSlots.value.length * weekdays.length
  return totalSlots - slots.value.length
})

const subjectSlotStats = computed(() => {
  const counts = {}
  for (const s of slots.value) {
    counts[s.subject_code] = (counts[s.subject_code] || 0) + 1
  }
  return SUBJECTS
    .filter(s => counts[s.code])
    .map(s => ({ code: s.code, label: s.label, count: counts[s.code] }))
    .sort((a, b) => b.count - a.count)
})

// -- 冲突检测 --

function getConflict(weekday, periodId) {
  const slot = getSlot(weekday, periodId)
  if (!slot || !slot.teacher_id) return null
  const conflicts = []
  for (const [classId, classSlots] of Object.entries(allClassTimetables.value)) {
    if (classId === selectedClassId.value) continue
    for (const s of classSlots) {
      if (s.weekday === weekday && s.period_id === periodId && s.teacher_id === slot.teacher_id) {
        const cls = classes.value.find(c => c.id === classId)
        conflicts.push(cls?.name || classId.slice(0, 6))
      }
    }
  }
  if (conflicts.length === 0) return null
  const tName = teacherName(slot.teacher_id)
  return `${tName} 在该节次已排：${conflicts.join('、')}`
}

const slotEditConflict = computed(() => {
  if (!slotForm.value.teacher_id || !slotForm.value.weekday) return null
  const conflicts = []
  for (const [classId, classSlots] of Object.entries(allClassTimetables.value)) {
    if (classId === selectedClassId.value) continue
    for (const s of classSlots) {
      if (s.weekday === slotForm.value.weekday && s.period_id === slotForm.value.period_id && s.teacher_id === slotForm.value.teacher_id) {
        const cls = classes.value.find(c => c.id === classId)
        conflicts.push(cls?.name || classId.slice(0, 6))
      }
    }
  }
  if (conflicts.length === 0) return null
  const tName = teacherName(slotForm.value.teacher_id)
  return `${tName} 在该节次已排：${conflicts.join('、')}`
})

// -- 样式辅助 --

function slotCellClass(weekday, periodId, periodType) {
  const base = ['slot-cell']
  if (periodType !== 'class') return base
  const slot = getSlot(weekday, periodId)
  if (!slot) {
    base.push('slot-cell-empty')
  } else if (editing.value && getConflict(weekday, periodId)) {
    base.push('slot-cell-conflict')
  }
  return base
}

// -- 操作 --

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

function onSlotClick(weekday, periodId, periodType) {
  if (!editing.value || periodType !== 'class') return
  if (clipboardSlot.value && !getSlot(weekday, periodId)) {
    const slot = { ...clipboardSlot.value, weekday, period_id: periodId }
    slots.value.push(slot)
    clipboardSlot.value = null
    message.success('已粘贴')
    return
  }
  openSlotEdit(weekday, periodId)
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

function copySlot() {
  const existing = getSlot(slotForm.value.weekday, slotForm.value.period_id)
  if (existing) {
    clipboardSlot.value = { subject_code: existing.subject_code, teacher_id: existing.teacher_id, room: existing.room }
    showSlotEdit.value = false
    message.info('已复制，点击空格粘贴')
  }
}

function cancelEdit() {
  editing.value = false
  clipboardSlot.value = null
  loadTimetable()
}

async function loadTimetable() {
  if (!selectedClassId.value || !semesterId.value) return
  loading.value = true
  try {
    const { data } = await getTimetable({ semester_id: semesterId.value, class_id: selectedClassId.value })
    slots.value = data
    editing.value = false
    clipboardSlot.value = null
  } catch { message.error('加载课表失败') }
  loading.value = false
}

async function loadStats() {
  if (!semesterId.value) return
  try {
    const params = { semester_id: semesterId.value }
    if (selectedClassId.value) params.class_id = selectedClassId.value
    const { data } = await getTimetableStats(params)
    timetableStats.value = data
  } catch { /* stats are non-critical */ }
}

async function loadAllClassTimetables() {
  if (!semesterId.value) return
  const result = {}
  const gradeClasses = classes.value.filter(c => c.grade === selectedGrade.value)
  const promises = gradeClasses.map(async (cls) => {
    if (cls.id === selectedClassId.value) return
    try {
      const { data } = await getTimetable({ semester_id: semesterId.value, class_id: cls.id })
      result[cls.id] = data
    } catch { /* ignore */ }
  })
  await Promise.all(promises)
  allClassTimetables.value = result
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
    clipboardSlot.value = null
    loadStats()
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
    loadStats()
  } catch (e) { message.error('初始化失败') }
  loading.value = false
}

watch(editing, (val) => {
  if (val && selectedGrade.value) {
    loadAllClassTimetables()
  }
})

onMounted(init)
</script>

<style scoped>
.timetable-grid { overflow-x: auto; }
.timetable-grid table { width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; }
.timetable-grid th { background: rgba(99, 110, 180, 0.15); padding: 10px 8px; font-size: 16px; font-weight: 600; text-align: center; border: 1px solid rgba(255,255,255,0.06); }
.timetable-grid td { padding: 6px 4px; text-align: center; border: 1px solid rgba(255,255,255,0.06); min-height: 50px; vertical-align: middle; }
.period-name { font-weight: 600; font-size: 16px; background: rgba(99, 180, 130, 0.1); }
.period-time { font-size: 16px; color: rgba(255,255,255,0.4); }
.slot-cell { cursor: pointer; min-width: 100px; height: 52px; transition: background .15s; }
.slot-cell:hover { background: rgba(255, 224, 130, 0.08); }
.slot-content { display: flex; flex-direction: column; gap: 2px; position: relative; }
.slot-subject { font-weight: 600; font-size: 16px; }
.slot-teacher { font-size: 16px; color: rgba(255,255,255,0.5); }
.slot-empty { color: rgba(255,255,255,0.2); font-size: 20px; }
.slot-vacant { }
.slot-cell-empty { border: 1px dashed rgba(255,255,255,0.15) !important; background: rgba(255,255,255,0.02); }
.slot-cell-conflict { border: 2px solid rgba(250, 200, 80, 0.6) !important; background: rgba(250, 200, 80, 0.06); }
.break-row td { background: rgba(255,255,255,0.02); height: 28px; }
.break-label { font-size: 16px; color: rgba(255,255,255,0.2); }
.conflict-icon { display: inline-block; width: 16px; height: 16px; line-height: 16px; border-radius: 50%; background: rgba(250, 200, 80, 0.8); color: #1e1e2e; font-size: 16px; font-weight: 700; position: absolute; top: -4px; right: -4px; cursor: help; }
.subject-stats { margin-top: 12px; padding: 12px 16px; background: rgba(255,255,255,0.03); border-radius: 8px; }
.stats-label { font-size: 16px; font-weight: 600; color: rgba(255,255,255,0.6); }
.slot-paste-target { color: rgba(99, 180, 130, 0.6) !important; font-size: 16px !important; border: 1px dashed rgba(99, 180, 130, 0.4); border-radius: 4px; padding: 2px 4px; }
</style>
