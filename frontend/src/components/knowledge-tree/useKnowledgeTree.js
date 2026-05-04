import { ref, computed } from 'vue'
import {
  getGraph, getMastery, editGraph, qualityCheck, getStatsOverview,
  getCourseMapOverview, getCourseMapModule, getCourseMapStudyUnit,
} from '../../api/knowledgeTree'

export function useKnowledgeTree() {
  const navigationData = ref([])
  const graphData = ref({ nodes: [], edges: [] })
  const masteryData = ref({ student_id: '', concept_mastery: [], module_mastery: [] })
  const qualityIssues = ref([])
  const qualitySummary = ref(null)
  const modulesQuality = ref({})
  const statsOverview = ref(null)
  const courseMapOverview = ref(null)
  const courseMapModule = ref(null)
  const courseMapStudyUnit = ref(null)
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

  // Phase 1 T13: 统计概览（考频分布 + 模块 avg_freq + exam_coverage）
  // 加载失败 → statsOverview 保持 null → ModuleOverviewPanel 显示 '—' 降级
  async function loadStatsOverview(module = 'all') {
    try {
      const resp = await getStatsOverview(module)
      statsOverview.value = resp ?? null
    } catch (e) {
      statsOverview.value = null
    }
  }

  async function loadCourseMapOverview() {
    try {
      courseMapOverview.value = await getCourseMapOverview()
    } catch (e) {
      courseMapOverview.value = null
    }
  }

  async function loadCourseMapModule(module) {
    try {
      courseMapModule.value = await getCourseMapModule(module)
    } catch (e) {
      courseMapModule.value = null
    }
  }

  async function loadCourseMapStudyUnit(suId) {
    try {
      courseMapStudyUnit.value = await getCourseMapStudyUnit(suId)
    } catch (e) {
      courseMapStudyUnit.value = null
    }
  }

  return {
    navigationData, graphData, masteryData, qualityIssues, qualitySummary,
    modulesQuality, statsOverview,
    courseMapOverview, courseMapModule, courseMapStudyUnit,
    loading, selectedModule, selectedStudentId, moduleMastery, nodesWithMastery,
    loadGraph, loadMastery, loadQuality, loadAllModulesQuality, loadStatsOverview, applyEdit,
    loadCourseMapOverview, loadCourseMapModule, loadCourseMapStudyUnit,
  }
}

/**
 * 从节点列表聚合章节树
 * node.textbook_chapters = [{book, chapter, section, title}]
 */
export function buildChapterTree(nodes) {
  const BOOK_LABELS = {
    b1: '必修1 分子与细胞',
    b2: '必修2 遗传与进化',
    xe1: '选必1 稳态与调节',
    xe2: '选必2 生物与环境',
    xe3: '选必3 生物技术',
  }
  const bookMap = new Map()

  for (const node of nodes) {
    const chapters = node.textbook_chapters || []
    for (const ch of chapters) {
      const bookKey = ch.book
      if (!bookMap.has(bookKey)) {
        bookMap.set(bookKey, { id: bookKey, name: BOOK_LABELS[bookKey] || bookKey, chapters: new Map() })
      }
      const book = bookMap.get(bookKey)
      const chapterKey = ch.chapter
      if (!book.chapters.has(chapterKey)) {
        book.chapters.set(chapterKey, { id: chapterKey, name: chapterKey, sections: new Map() })
      }
      const chapter = book.chapters.get(chapterKey)
      const sectionKey = ch.section
      if (!chapter.sections.has(sectionKey)) {
        chapter.sections.set(sectionKey, { id: sectionKey, name: ch.title || sectionKey, concept_ids: [] })
      }
      const section = chapter.sections.get(sectionKey)
      if (!section.concept_ids.includes(node.id)) {
        section.concept_ids.push(node.id)
      }
    }
  }

  return Array.from(bookMap.values())
    .sort((a, b) => a.id.localeCompare(b.id))
    .map(book => ({
      ...book,
      chapters: Array.from(book.chapters.values())
        .sort((a, b) => a.id.localeCompare(b.id))
        .map(ch => ({
          ...ch,
          sections: Array.from(ch.sections.values())
            .sort((a, b) => a.id.localeCompare(b.id))
        }))
    }))
}
