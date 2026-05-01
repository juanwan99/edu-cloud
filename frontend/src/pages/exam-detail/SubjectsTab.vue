<template>
  <div style="display: flex; justify-content: flex-end; margin-bottom: var(--space-4);">
    <n-button type="primary" class="btn-pill" size="small" @click="$emit('open-subject-modal')">添加科目</n-button>
  </div>
  <n-data-table :columns="subjectColumns" :data="subjects" size="small" />
</template>

<script setup>
defineProps({
  subjects: { type: Array, required: true },
})

defineEmits(['open-subject-modal'])

const subjectColumns = [
  { title: '科目名称', key: 'name' },
  { title: '代码', key: 'code', width: 120 },
]
</script>
