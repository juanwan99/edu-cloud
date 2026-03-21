import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '../api/client.js'

export const useContextStore = defineStore('context', () => {
  const classes = ref([])
  const exams = ref([])
  const selectedExamId = ref(null)
  const dashboard = ref(null)
  const loading = ref(false)

  async function loadContext() {
    const { data } = await client.get('/workspace/context')
    classes.value = data.classes
    exams.value = data.exams
  }

  async function selectExam(examId) {
    selectedExamId.value = examId
    loading.value = true
    try {
      const { data } = await client.get(`/workspace/exams/${examId}/dashboard`)
      dashboard.value = data
    } finally {
      loading.value = false
    }
  }

  return { classes, exams, selectedExamId, dashboard, loading, loadContext, selectExam }
})
