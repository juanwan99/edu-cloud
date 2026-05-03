/**
 * ParentRankings.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains ranking info card, distribution bar, table
 *  3. API call uses getChildRankings
 *  4. Computed ranking logic (rank change, trophy, distribution)
 *  5. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentRankings.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentRankings smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentRankings.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentRankings template sections', () => {
  it('contains ranking info card with trophy', () => {
    expect(content).toContain('v-if="myRanking"')
    expect(content).toContain('{{ trophyIcon }}')
    expect(content).toContain('{{ myRanking.rank }}')
    expect(content).toContain('rankings.length')
    expect(content).toContain('{{ myRanking.total_points }}')
  })

  it('displays rank change indicators', () => {
    expect(content).toContain('v-if="rankChange > 0"')
    expect(content).toContain('v-else-if="rankChange < 0"')
    expect(content).toContain('排名不变')
  })

  it('contains score distribution bar', () => {
    expect(content).toContain('积分分布')
    expect(content).toContain('distBands.top10')
    expect(content).toContain('distBands.mid50')
    expect(content).toContain('distBands.bot40')
  })

  it('contains position marker', () => {
    expect(content).toContain('myPositionPct')
    expect(content).toContain('我在这')
  })

  it('contains rankings data table', () => {
    expect(content).toContain('title="班级排行榜"')
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="rankings"')
    expect(content).toContain(':row-class-name="rowClassName"')
  })

  it('highlights current child row', () => {
    expect(content).toContain('highlight-row')
    expect(content).toContain("style: 'border-left: 3px solid #F4DA4C;'")
  })
})

describe('ParentRankings API calls', () => {
  it('imports getChildRankings from conduct API', () => {
    expect(content).toContain("import { getChildRankings } from '../../api/conduct'")
  })

  it('fetches rankings on currentChild change', () => {
    expect(content).toContain('await getChildRankings(child.student_id)')
    expect(content).toContain("rankings.value = res.data.rankings || res.data || []")
  })
})

describe('ParentRankings table columns', () => {
  it('defines rank column with medal icons', () => {
    expect(content).toContain("title: '排名'")
    expect(content).toContain("key: 'rank'")
  })

  it('defines name column', () => {
    expect(content).toContain("title: '姓名'")
    expect(content).toContain("key: 'student_name'")
  })

  it('defines total points column', () => {
    expect(content).toContain("title: '总积分'")
    expect(content).toContain("key: 'total_points'")
  })

  it('defines points change column', () => {
    expect(content).toContain("title: '积分变化'")
    expect(content).toContain("key: 'points_change'")
  })

  it('defines rank change column', () => {
    expect(content).toContain("title: '排名变化'")
    expect(content).toContain("key: 'rank_change'")
  })
})

describe('ParentRankings computed properties', () => {
  it('computes myRanking by matching student_id', () => {
    expect(content).toContain('rankings.value.find(r => r.student_id === props.currentChild.student_id)')
  })

  it('computes rankChange from previous_rank', () => {
    expect(content).toContain('myRanking.value.previous_rank - myRanking.value.rank')
  })

  it('maps trophy icons by rank position', () => {
    expect(content).toContain("if (rank === 1) return '🥇'")
    expect(content).toContain("if (rank === 2) return '🥈'")
    expect(content).toContain("if (rank === 3) return '🥉'")
    expect(content).toContain("return '🏆'")
  })

  it('computes distribution bands', () => {
    expect(content).toContain('const distBands = computed')
    expect(content).toContain('Math.ceil(n * 0.1)')
    expect(content).toContain('Math.ceil(n * 0.5)')
  })

  it('computes position percentage for marker', () => {
    expect(content).toContain('const myPositionPct = computed')
    expect(content).toContain('(myRanking.value.rank - 0.5)')
  })
})

describe('ParentRankings error handling', () => {
  it('wraps fetch in try-catch-finally', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(() => props.currentChild'),
      content.indexOf('</script>')
    )
    expect(watchBlock).toContain('try {')
    expect(watchBlock).toContain('} catch {')
    expect(watchBlock).toContain('} finally {')
  })

  it('falls back to empty rankings on error', () => {
    expect(content).toContain('rankings.value = []')
  })

  it('watches currentChild with immediate flag', () => {
    expect(content).toContain('}, { immediate: true })')
  })
})
