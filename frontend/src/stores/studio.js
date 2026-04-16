import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '../api/client.js'

export const useStudioStore = defineStore('studio', () => {
  const templates = ref([])
  const documents = ref([])
  const currentDoc = ref(null)
  const loading = ref(false)

  async function loadTemplates() {
    const { data } = await client.get('/studio/templates')
    templates.value = data
  }

  async function loadDocuments() {
    const { data } = await client.get('/studio/documents')
    documents.value = data
  }

  async function getDocument(docId) {
    loading.value = true
    try {
      const { data } = await client.get(`/studio/documents/${docId}`)
      currentDoc.value = data
    } finally { loading.value = false }
  }

  async function updateDocument(docId, contentJson, changeSummary) {
    const { data } = await client.patch(`/studio/documents/${docId}`, {
      content_json: contentJson, change_summary: changeSummary,
    })
    currentDoc.value = data
    await loadDocuments()
  }

  async function transitionStatus(docId, status) {
    const { data } = await client.post(`/studio/documents/${docId}/transition`, { status })
    currentDoc.value = data
    await loadDocuments()
  }

  async function createPaper(budgetTier, title, seedIdea) {
    const { data } = await client.post('/studio/paper/create', {
      budget_tier: budgetTier, title, seed_idea: seedIdea,
    })
    if (data.error) throw new Error(data.error)
    await loadDocuments()
    return data
  }

  async function getPaperStatus(paperId) {
    const { data } = await client.get(`/studio/paper/${paperId}/status`)
    return data
  }

  return { templates, documents, currentDoc, loading, loadTemplates, loadDocuments, getDocument, updateDocument, transitionStatus, createPaper, getPaperStatus }
})
