/**
 * ParentOverview.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains student info, score summary, quick entries, records
 *  3. API calls for records, scores, rankings
 *  4. Guide card for unbound state
 *  5. Error handling in data fetching
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentOverview.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentOverview smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentOverview.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentOverview template sections', () => {
  it('contains guide card for unbound state', () => {
    expect(content).toContain('v-if="!currentChild && !loading"')
    expect(content).toContain('class="guide-card"')
    expect(content).toContain('尚未绑定孩子')
    expect(content).toContain('请先绑定孩子信息，才能查看学习数据')
    expect(content).toContain("'/parent/bind'")
  })

  it('contains student info card with avatar', () => {
    expect(content).toContain('class="student-header"')
    expect(content).toContain('class="avatar-circle"')
    expect(content).toContain('{{ avatarLetter }}')
    expect(content).toContain('{{ currentChild.student_name }}')
    expect(content).toContain("currentChild.class_name || '未分配班级'")
  })

  it('contains total points and ranking stats', () => {
    expect(content).toContain('{{ totalPoints }}')
    expect(content).toContain('总积分')
    expect(content).toContain('v-if="ranking"')
    expect(content).toContain('{{ ranking }}')
    expect(content).toContain('排名')
  })

  it('contains score summary card', () => {
    expect(content).toContain('v-if="latestScore"')
    expect(content).toContain('class="score-brief"')
    expect(content).toContain('最近考试')
    expect(content).toContain("latestScore.total_score ?? '-'")
    expect(content).toContain('班名次')
    expect(content).toContain('年名次')
  })

  it('contains 4 quick entry buttons', () => {
    expect(content).toContain('class="quick-entries"')
    expect(content).toContain("'/parent/scores'")
    expect(content).toContain('成绩查询')
    expect(content).toContain("'/parent/rankings'")
    expect(content).toContain('排行榜')
    expect(content).toContain("'/parent/rules'")
    expect(content).toContain('班规')
    expect(content).toContain("'/parent/details'")
    expect(content).toContain('操行记录')
  })

  it('contains recent records list with points tag', () => {
    expect(content).toContain('v-for="r in records"')
    expect(content).toContain("r.rule_name || r.note || '操行记录'")
    expect(content).toContain("r.points >= 0 ? '+' : ''")
  })

  it('contains empty state for no records', () => {
    expect(content).toContain('description="暂无记录"')
  })

  it('contains button to view detailed records', () => {
    expect(content).toContain('查看详细记录')
  })
})

describe('ParentOverview API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { getChildRecords, getChildScores, getChildRankings } from '../../api/conduct'")
  })

  it('fetches child records', () => {
    expect(content).toContain('await getChildRecords(child.student_id, { page: 1, page_size: 10 })')
  })

  it('fetches latest score', () => {
    expect(content).toContain('await getChildScores(child.student_id, { limit: 1 })')
  })

  it('fetches child rankings', () => {
    expect(content).toContain('await getChildRankings(child.student_id)')
  })
})

describe('ParentOverview computed properties', () => {
  it('computes avatar letter from student name', () => {
    expect(content).toContain("const name = props.currentChild?.student_name || ''")
    expect(content).toContain("return name.charAt(0) || '?'")
  })

  it('computes avatar background color from name hash', () => {
    expect(content).toContain('const avatarBg = computed')
    expect(content).toContain("const colors = ['#63e2b7', '#64b5f6', '#ffb74d', '#ce93d8', '#ef9a9a', '#80cbc4']")
  })

  it('receives currentChild via props', () => {
    expect(content).toContain('currentChild: { type: Object, default: null }')
  })
})

describe('ParentOverview error handling', () => {
  it('wraps score fetch in nested try-catch', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(() => props.currentChild'),
      content.indexOf('</script>')
    )
    // Should have multiple try-catch blocks for score and ranking
    const catchCount = (watchBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(3)
  })

  it('falls back to empty records on error', () => {
    expect(content).toContain('records.value = []')
  })

  it('falls back to null for score and ranking on error', () => {
    expect(content).toContain('latestScore.value = null')
    expect(content).toContain('ranking.value = null')
  })

  it('watches currentChild with immediate flag', () => {
    expect(content).toContain('}, { immediate: true })')
  })
})
