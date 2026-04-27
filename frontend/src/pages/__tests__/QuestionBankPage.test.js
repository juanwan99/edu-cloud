/**
 * QuestionBankPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains stats overview, search/filter bar, question list, pagination
 *  3. API calls for search and stats
 *  4. Question type and difficulty label mappings
 *  5. Error handling patterns
 *  6. Filter and pagination logic
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../QuestionBankPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('QuestionBankPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../QuestionBankPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('QuestionBankPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('题库')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('按知识点/难度/题型/来源搜索题目')
  })

  it('contains stats overview cards', () => {
    expect(content).toContain('class="stats-grid"')
    expect(content).toContain('statsData.total_count')
    expect(content).toContain('class="stat-label">题目总数')
    expect(content).toContain('class="stat-label">题型分类')
    expect(content).toContain('class="stat-label">难度等级')
    expect(content).toContain('class="stat-label">题目来源')
  })

  it('contains search input with keyword binding', () => {
    expect(content).toContain('v-model:value="keyword"')
    expect(content).toContain('placeholder="搜索题目内容..."')
    expect(content).toContain('@keyup.enter="doSearch"')
  })

  it('contains filter selects for type, difficulty, and source', () => {
    expect(content).toContain('v-model:value="questionType"')
    expect(content).toContain('v-model:value="difficultyLevel"')
    expect(content).toContain('v-model:value="source"')
    expect(content).toContain('placeholder="题型"')
    expect(content).toContain('placeholder="难度"')
    expect(content).toContain('placeholder="来源"')
  })

  it('contains search and reset buttons', () => {
    expect(content).toContain('@click="doSearch"')
    expect(content).toContain('@click="resetFilters"')
    expect(content).toContain('>搜索<')
    expect(content).toContain('>重置<')
  })

  it('contains question card list', () => {
    expect(content).toContain('class="question-list"')
    expect(content).toContain('class="question-card"')
    expect(content).toContain('class="question-content"')
    expect(content).toContain('class="question-text"')
    expect(content).toContain('class="question-meta"')
  })

  it('contains question tags and knowledge points display', () => {
    expect(content).toContain('class="question-tags"')
    expect(content).toContain('class="question-kps"')
    expect(content).toContain('class="kp-label">知识点:')
  })

  it('contains pagination component', () => {
    expect(content).toContain('class="pagination-bar"')
    expect(content).toContain('n-pagination')
    expect(content).toContain(':item-count="total"')
    expect(content).toContain(':page-sizes="[10, 20, 50]"')
  })

  it('contains empty states for no results and no search', () => {
    expect(content).toContain('description="未找到匹配的题目"')
    expect(content).toContain('description="请设置筛选条件后搜索"')
  })
})

describe('QuestionBankPage question type labels', () => {
  it('defines QUESTION_TYPE_LABELS mapping', () => {
    expect(content).toContain("choice: '选择题'")
    expect(content).toContain("fill_blank: '填空题'")
    expect(content).toContain("essay: '主观题'")
    expect(content).toContain("true_false: '判断题'")
  })

  it('defines question type filter options', () => {
    expect(content).toContain("{ label: '选择题', value: 'choice' }")
    expect(content).toContain("{ label: '填空题', value: 'fill_blank' }")
    expect(content).toContain("{ label: '主观题', value: 'essay' }")
    expect(content).toContain("{ label: '判断题', value: 'true_false' }")
  })
})

describe('QuestionBankPage difficulty labels', () => {
  it('defines DIFFICULTY_LABELS mapping', () => {
    expect(content).toContain("easy: '简单'")
    expect(content).toContain("medium: '中等'")
    expect(content).toContain("hard: '困难'")
  })

  it('defines difficulty filter options', () => {
    expect(content).toContain("{ label: '简单', value: 'easy' }")
    expect(content).toContain("{ label: '中等', value: 'medium' }")
    expect(content).toContain("{ label: '困难', value: 'hard' }")
  })
})

describe('QuestionBankPage tag type helpers', () => {
  it('maps question type to tag type', () => {
    expect(content).toContain("{ choice: 'info', fill_blank: 'warning', essay: 'success', true_false: 'default' }")
  })

  it('maps difficulty to tag type', () => {
    expect(content).toContain("{ easy: 'success', medium: 'warning', hard: 'error' }")
  })
})

describe('QuestionBankPage API calls', () => {
  it('imports search and stats APIs', () => {
    expect(content).toContain("import { searchQuestions, getQuestionBankStats } from '../api/bank.js'")
  })

  it('calls searchQuestions with filter params', () => {
    const fnBlock = content.slice(
      content.indexOf('async function doSearch'),
      content.indexOf('function resetFilters')
    )
    expect(fnBlock).toContain('params.keyword = keyword.value')
    expect(fnBlock).toContain('params.question_type = questionType.value')
    expect(fnBlock).toContain('params.difficulty_level = difficultyLevel.value')
    expect(fnBlock).toContain('params.source = source.value')
    expect(fnBlock).toContain('await searchQuestions(params)')
  })

  it('parses paginated response format', () => {
    expect(content).toContain('questions.value = data.items')
    expect(content).toContain('total.value = data.total')
  })

  it('calls getQuestionBankStats for overview', () => {
    expect(content).toContain('await getQuestionBankStats()')
    expect(content).toContain('statsData.value = data')
  })

  it('generates source options from stats data', () => {
    expect(content).toContain('data.by_source')
    expect(content).toContain('Object.keys(data.by_source).map')
  })

  it('loads stats and does initial search on mount', () => {
    expect(content).toContain('loadStats()')
    expect(content).toContain('doSearch()')
  })
})

describe('QuestionBankPage filter and pagination logic', () => {
  it('resets filters and triggers search', () => {
    const fnBlock = content.slice(
      content.indexOf('function resetFilters'),
      content.indexOf('function onPageChange')
    )
    expect(fnBlock).toContain("keyword.value = ''")
    expect(fnBlock).toContain('questionType.value = null')
    expect(fnBlock).toContain('difficultyLevel.value = null')
    expect(fnBlock).toContain('source.value = null')
    expect(fnBlock).toContain('page.value = 1')
    expect(fnBlock).toContain('doSearch()')
  })

  it('handles page change by updating page and searching', () => {
    const fnBlock = content.slice(
      content.indexOf('function onPageChange'),
      content.indexOf('function onPageSizeChange')
    )
    expect(fnBlock).toContain('page.value = newPage')
    expect(fnBlock).toContain('doSearch()')
  })

  it('handles page size change by resetting to page 1', () => {
    expect(content).toContain('function onPageSizeChange(newSize)')
    expect(content).toContain('pageSize.value = newSize')
    // page reset and search are in the same function
    const fnStart = content.indexOf('function onPageSizeChange')
    const fnEnd = content.indexOf('onMounted(', fnStart)
    const fnBlock = content.slice(fnStart, fnEnd)
    expect(fnBlock).toContain('page.value = 1')
    expect(fnBlock).toContain('doSearch()')
  })

  it('uses default pageSize of 20', () => {
    expect(content).toContain('const pageSize = ref(20)')
  })
})

describe('QuestionBankPage error handling', () => {
  it('wraps doSearch in try-catch with empty fallback', () => {
    const fnBlock = content.slice(
      content.indexOf('async function doSearch'),
      content.indexOf('function resetFilters')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('questions.value = []')
    expect(fnBlock).toContain('total.value = 0')
  })

  it('wraps loadStats in try-catch with null fallback', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadStats'),
      content.indexOf('async function doSearch')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('statsData.value = null')
  })
})
