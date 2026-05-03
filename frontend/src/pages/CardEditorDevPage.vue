<template>
  <div class="card-editor-dev-page">
    <n-button text style="margin-bottom: 8px;" @click="$router.push(`/exams/${examId}`)">
      <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
      返回考试详情
    </n-button>
    <div style="display:flex; gap:12px; align-items:center; margin-bottom:8px; font-size: 16px;">
      <label>科目：</label>
      <select v-model="selectedSubject" style="padding:4px 8px;">
        <option v-for="s in subjects" :key="s.id" :value="s">{{ s.name }}</option>
      </select>
      <span v-if="selectedSubject" style="color:#888;">ID: {{ selectedSubject.id }}</span>
    </div>
    <CardEditor
      v-if="selectedSubject"
      :key="selectedSubject.id"
      :exam-id="examId"
      :subject-id="selectedSubject.id"
      :subject-name="selectedSubject.name"
      :card-title="examName"
    />
    <div v-else style="color:#999;padding:40px;text-align:center;">选择科目后加载编辑器</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NIcon } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import CardEditor from '../components/CardEditor.vue'
import { listSubjects } from '../api/subjects'
import client from '../api/client'

const route = useRoute()
const examId = ref(route.params.examId || '')
const subjects = ref([])
const selectedSubject = ref(null)
const examName = ref('')

onMounted(async () => {
  try {
    const res = await listSubjects(examId.value)
    subjects.value = res.data
    const targetId = route.query.subject
    if (targetId) {
      selectedSubject.value = subjects.value.find(s => s.id === targetId) || subjects.value[0]
    } else {
      selectedSubject.value = subjects.value[0]
    }
  } catch (e) {
    console.error('加载科目失败:', e)
  }
  try {
    const res = await client.get(`/exams/${examId.value}`)
    examName.value = res.data.name || ''
  } catch {}
})
</script>

<style scoped>
.card-editor-dev-page {
  padding: 8px;
}
</style>
