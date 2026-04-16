import { ref, computed } from 'vue'
import { getGraph, getMastery, editGraph, qualityCheck } from '../../api/knowledgeTree'

export function useKnowledgeTree() {
  const navigationData = ref([])
  const graphData = ref({ nodes: [], edges: [] })
  const masteryData = ref({ student_id: '', concept_mastery: [], module_mastery: [] })
  const qualityIssues = ref([])
  const qualitySummary = ref(null)
  const modulesQuality = ref({})
  const loading = ref(false)
  const selectedModule = ref('all')
  const selectedStudentId = ref(null)

  const moduleMastery = computed(() => masteryData.value.module_mastery)

  const nodesWithMastery = computed(() => {
    const masteryMap = {}
    for (const cm of masteryData.value.concept_mastery) {
      masteryMap[cm.concept_id] = cm
    }
    return graphData.value.nodes.map(node => ({
      ...node,
      mastery: masteryMap[node.id]?.mastery ?? 0,
      mastery_state: masteryMap[node.id]?.state ?? 'unseen',
      da_count: masteryMap[node.id]?.da_count ?? 0,
    }))
  })

  async function loadGraph(module = 'all', includeDraft = true) {
    selectedModule.value = module
    const resp = await getGraph(module, includeDraft)
    navigationData.value = resp.data.navigation ?? []
    graphData.value = resp.data.graph ?? { nodes: [], edges: [] }
  }

  async function loadMastery(studentId, module = 'all') {
    selectedStudentId.value = studentId
    const resp = await getMastery(studentId, module)
    masteryData.value = resp.data
  }

  async function loadQuality(module = 'all') {
    const resp = await qualityCheck(module)
    qualityIssues.value = resp.data.issues ?? []
    qualitySummary.value = resp.data.summary ?? null
  }

  async function loadAllModulesQuality() {
    const modules = ['M1', 'M2', 'M3', 'M4', 'M5']
    const results = await Promise.allSettled(
      modules.map(m => qualityCheck(m))
    )
    const next = {}
    results.forEach((r, i) => {
      const mod = modules[i]
      if (r.status === 'fulfilled') {
        const summary = r.value?.data?.summary?.issues_by_severity ?? {}
        next[mod] = { highCount: summary.HIGH ?? 0, medCount: summary.MED ?? 0 }
      } else {
        next[mod] = { highCount: 0, medCount: 0 }
      }
    })
    modulesQuality.value = next
  }

  async function applyEdit(operations) {
    loading.value = true
    try {
      const resp = await editGraph(operations)
      await loadGraph(selectedModule.value)
      return resp.data
    } finally {
      loading.value = false
    }
  }

  return {
    navigationData, graphData, masteryData, qualityIssues, qualitySummary,
    modulesQuality,
    loading, selectedModule, selectedStudentId, moduleMastery, nodesWithMastery,
    loadGraph, loadMastery, loadQuality, loadAllModulesQuality, applyEdit,
  }
}
