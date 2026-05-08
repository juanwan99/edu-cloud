<template>
  <n-spin :show="loading">
    <n-space>
      <n-select
        v-model:value="selectedGradeId"
        :options="gradeOptions"
        :placeholder="gradeOptions.length ? '选择年级' : '暂无数据'"
        style="min-width: 140px"
        @update:value="onGradeChange"
      />
      <n-select
        v-model:value="selectedClassId"
        :options="classOptions"
        placeholder="选择班级"
        style="min-width: 160px"
        @update:value="onClassChange"
      />
      <n-select
        v-model:value="selectedSubjectCode"
        :options="subjectOptions"
        placeholder="选择科目"
        style="min-width: 140px"
        @update:value="onSubjectChange"
      />
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="min-width: 200px"
        @update:value="onExamChange"
      />
    </n-space>
  </n-spin>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPowerOptions } from '../../api/analytics'

const emit = defineEmits(['change'])

const loading = ref(false)
const tree = ref([]) // raw grades array from API
const selectedGradeId = ref(null)
const selectedClassId = ref(null)
const selectedSubjectCode = ref(null)
const selectedExamId = ref(null)

// --- Derived option lists ---

const gradeOptions = computed(() =>
  tree.value.map(g => ({ label: g.name, value: g.id }))
)

const selectedGrade = computed(() =>
  tree.value.find(g => g.id === selectedGradeId.value) || null
)

const classOptions = computed(() => {
  if (!selectedGrade.value) return []
  return (selectedGrade.value.classes || []).map(c => ({
    label: c.name,
    value: c.id,
  }))
})

const selectedClass = computed(() => {
  if (!selectedGrade.value) return null
  return (selectedGrade.value.classes || []).find(
    c => c.id === selectedClassId.value
  ) || null
})

const subjectOptions = computed(() => {
  if (!selectedGrade.value) return []
  if (selectedClassId.value === 'all') {
    // Merge subjects from all real classes in the grade
    const seen = new Set()
    const merged = []
    for (const cls of selectedGrade.value.classes || []) {
      if (cls.id === 'all') continue
      for (const subj of cls.subjects || []) {
        if (!seen.has(subj.code)) {
          seen.add(subj.code)
          merged.push({ label: subj.name, value: subj.code })
        }
      }
    }
    return merged
  }
  if (!selectedClass.value) return []
  return (selectedClass.value.subjects || []).map(s => ({
    label: s.name,
    value: s.code,
  }))
})

const examOptions = computed(() => {
  const exams = collectExams()
  // Sort by exam_date descending
  exams.sort((a, b) => (b.exam_date || '').localeCompare(a.exam_date || ''))
  return exams.map(e => ({
    label: e.name,
    value: e.id,
  }))
})

// --- Helpers ---

function collectExams() {
  if (!selectedGrade.value || !selectedSubjectCode.value) return []
  if (selectedClassId.value === 'all') {
    // Merge exams for the subject across all real classes
    const seen = new Set()
    const merged = []
    for (const cls of selectedGrade.value.classes || []) {
      if (cls.id === 'all') continue
      const subj = (cls.subjects || []).find(s => s.code === selectedSubjectCode.value)
      if (!subj) continue
      for (const ex of subj.exams || []) {
        if (!seen.has(ex.id)) {
          seen.add(ex.id)
          merged.push(ex)
        }
      }
    }
    return merged
  }
  if (!selectedClass.value) return []
  const subj = (selectedClass.value.subjects || []).find(
    s => s.code === selectedSubjectCode.value
  )
  return subj?.exams || []
}

function autoSelectFirst(options, setter) {
  if (options.length > 0) {
    setter(options[0].value)
    return true
  }
  setter(null)
  return false
}

function emitChange() {
  const isAll = selectedClassId.value === 'all'
  emit('change', {
    gradeId: selectedGradeId.value,
    classId: isAll ? null : selectedClassId.value,
    subjectId: selectedSubjectCode.value,
    examId: selectedExamId.value,
    scope: isAll ? 'grade' : 'class',
  })
}

// --- Cascade handlers ---

function cascadeFromGrade() {
  autoSelectFirst(classOptions.value, v => { selectedClassId.value = v })
  cascadeFromClass()
}

function cascadeFromClass() {
  autoSelectFirst(subjectOptions.value, v => { selectedSubjectCode.value = v })
  cascadeFromSubject()
}

function cascadeFromSubject() {
  autoSelectFirst(examOptions.value, v => { selectedExamId.value = v })
  emitChange()
}

function onGradeChange() {
  selectedClassId.value = null
  selectedSubjectCode.value = null
  selectedExamId.value = null
  cascadeFromGrade()
}

function onClassChange() {
  selectedSubjectCode.value = null
  selectedExamId.value = null
  cascadeFromClass()
}

function onSubjectChange() {
  selectedExamId.value = null
  cascadeFromSubject()
}

function onExamChange() {
  emitChange()
}

// --- Load data ---

onMounted(async () => {
  loading.value = true
  try {
    const resp = await getPowerOptions()
    tree.value = resp.data?.grades || []
    if (tree.value.length > 0) {
      selectedGradeId.value = tree.value[0].id
      cascadeFromGrade()
    }
  } finally {
    loading.value = false
  }
})
</script>
