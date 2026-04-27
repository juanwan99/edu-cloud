/**
 * ParentRules.vue source text tests (supplementary to ParentRules.spec.js).
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains filter controls, collapse, rule items
 *  3. API call uses getClassRulesParent
 *  4. Filtering logic (mode + search)
 *  5. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentRules.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentRules smoke (text)', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentRules.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentRules template sections', () => {
  it('contains summary bar with rule counts', () => {
    expect(content).toContain('{{ totalCount }}')
    expect(content).toContain('{{ positiveCount }}')
    expect(content).toContain('{{ negativeCount }}')
  })

  it('contains filter controls', () => {
    expect(content).toContain('v-model:value="filterMode"')
    expect(content).toContain('v-model:value="searchText"')
    expect(content).toContain('搜索规则...')
  })

  it('contains radio buttons for filter mode', () => {
    expect(content).toContain('<n-radio-button value="all">全部</n-radio-button>')
    expect(content).toContain('<n-radio-button value="positive">加分项</n-radio-button>')
    expect(content).toContain('<n-radio-button value="negative">扣分项</n-radio-button>')
  })

  it('contains collapsible categories', () => {
    expect(content).toContain('<n-collapse')
    expect(content).toContain('v-for="cat in filteredCategories"')
    expect(content).toContain(':title="categoryTitle(cat)"')
  })

  it('contains rule items with points tag', () => {
    expect(content).toContain('v-for="item in cat.filteredItems"')
    expect(content).toContain('{{ item.name }}')
    expect(content).toContain(':type="pointsTagType(item.points)"')
    expect(content).toContain("item.points >= 0 ? '+' : ''")
    expect(content).toContain('{{ item.points }}')
  })

  it('shows item description when available', () => {
    expect(content).toContain('v-if="item.description"')
    expect(content).toContain('{{ item.description }}')
  })

  it('contains empty states', () => {
    expect(content).toContain('description="该分类暂无匹配规则"')
    expect(content).toContain('description="没有匹配的规则"')
    expect(content).toContain('description="暂无班级规则"')
  })
})

describe('ParentRules API calls', () => {
  it('imports getClassRulesParent from conduct API', () => {
    expect(content).toContain("import { getClassRulesParent } from '../../api/conduct'")
  })

  it('calls API with class_id from currentChild', () => {
    expect(content).toContain('await getClassRulesParent(child.class_id)')
  })

  it('injects currentChild from parent', () => {
    expect(content).toContain("const currentChild = inject('currentChild')")
  })
})

describe('ParentRules filtering logic', () => {
  it('computes allItems by flatMapping categories', () => {
    expect(content).toContain("categories.value.flatMap(cat => cat.items || [])")
  })

  it('computes positiveCount and negativeCount', () => {
    expect(content).toContain('allItems.value.filter(i => i.points > 0).length')
    expect(content).toContain('allItems.value.filter(i => i.points < 0).length')
  })

  it('filters by mode (positive/negative)', () => {
    expect(content).toContain("if (mode === 'positive' && item.points < 0) return false")
    expect(content).toContain("if (mode === 'negative' && item.points >= 0) return false")
  })

  it('filters by search text (case-insensitive)', () => {
    expect(content).toContain("(item.name || '').toLowerCase().includes(search)")
  })

  it('only shows categories with matching items', () => {
    expect(content).toContain('.filter(cat => cat.filteredItems.length > 0)')
  })
})

describe('ParentRules category icons', () => {
  it('maps category names to icons', () => {
    expect(content).toContain("'学习': '📚'")
    expect(content).toContain("'纪律': '📏'")
    expect(content).toContain("'卫生': '🧹'")
    expect(content).toContain("'劳动': '🔧'")
    expect(content).toContain("'体育': '⚽'")
    expect(content).toContain("'品德': '🌟'")
  })

  it('has a default icon fallback', () => {
    expect(content).toContain("return '📋'")
  })
})

describe('ParentRules points tag logic', () => {
  it('maps points to tag type', () => {
    expect(content).toContain("if (points < 0) return 'error'")
    expect(content).toContain("if (points >= 5) return 'success'")
    expect(content).toContain("if (points > 0) return 'info'")
    expect(content).toContain("return 'default'")
  })

  it('marks high value items as bordered', () => {
    expect(content).toContain('function isHighValue(points)')
    expect(content).toContain('Math.abs(points) >= 5')
  })
})

describe('ParentRules error handling', () => {
  it('wraps fetch in try-catch-finally', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(currentChild'),
      content.indexOf('</script>')
    )
    expect(watchBlock).toContain('try {')
    expect(watchBlock).toContain('} catch {')
    expect(watchBlock).toContain('} finally {')
  })

  it('falls back to empty categories on error', () => {
    expect(content).toContain('categories.value = []')
  })

  it('skips fetch when no class_id', () => {
    expect(content).toContain("if (!child?.class_id) return")
  })
})
