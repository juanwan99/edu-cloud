/**
 * ConductParents source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (invite code, stat cards, search, data table, batch remove)
 *  3. API calls via conduct.js (getParentsList, removeParent, getConductConfig, regenerateInviteCode)
 *  4. Operations (search filter, bound student count, invite link copy, batch remove)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductParents.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductParents smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductParents.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductParents template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('title="家长管理"')
    expect(content).toContain('查看和管理已注册家长')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains invite code display section', () => {
    expect(content).toContain('班级邀请码')
    expect(content).toContain("inviteCode || '未生成'")
    expect(content).toContain('复制邀请链接')
    expect(content).toContain('重新生成')
  })

  it('contains stat cards for parent count and bound students', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-label">已注册家长数')
    expect(content).toContain('class="stat-label">已绑定学生数')
    expect(content).toContain('{{ parents.length }}')
    expect(content).toContain('{{ boundStudentCount }}')
    expect(content).not.toContain('n-statistic')
  })

  it('contains search input for name/phone', () => {
    expect(content).toContain('v-model:value="searchText"')
    expect(content).toContain('placeholder="搜索姓名或手机号"')
  })

  it('contains batch remove section', () => {
    expect(content).toContain('v-if="checkedKeys.length > 0"')
    expect(content).toContain('批量移除')
    expect(content).toContain('@positive-click="handleBatchRemove"')
  })

  it('contains data table with columns', () => {
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="filteredParents"')
    expect(content).toContain('v-model:checked-row-keys="checkedKeys"')
  })
})

describe('ConductParents API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getParentsList')
    expect(content).toContain('removeParent')
    expect(content).toContain('getConductConfig')
    expect(content).toContain('regenerateInviteCode')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getParentsList to load parents', () => {
    expect(content).toContain('getParentsList(classId.value)')
  })

  it('calls removeParent for individual removal', () => {
    expect(content).toContain('removeParent(classId.value, userId)')
  })

  it('calls getConductConfig to load invite code', () => {
    expect(content).toContain('getConductConfig(classId.value)')
  })

  it('calls regenerateInviteCode', () => {
    expect(content).toContain('regenerateInviteCode(classId.value)')
  })
})

describe('ConductParents operations', () => {
  it('defines table columns (selection, name, phone, children, count, time, actions)', () => {
    expect(content).toContain("type: 'selection'")
    expect(content).toContain("title: '姓名'")
    expect(content).toContain("key: 'display_name'")
    expect(content).toContain("title: '手机号'")
    expect(content).toContain("key: 'phone'")
    expect(content).toContain("title: '绑定学生'")
    expect(content).toContain("title: '绑定学生数'")
    expect(content).toContain("title: '注册时间'")
    expect(content).toContain("title: '操作'")
  })

  it('computes boundStudentCount from parent children', () => {
    expect(content).toContain('const boundStudentCount = computed(')
    expect(content).toContain('p.children || p.bound_students')
    expect(content).toContain('ids.size')
  })

  it('filters parents by name and phone', () => {
    expect(content).toContain('const filteredParents = computed(')
    expect(content).toContain("(p.display_name || '').toLowerCase()")
    expect(content).toContain("(p.phone || '').toLowerCase()")
  })

  it('copies invite link to clipboard', () => {
    expect(content).toContain('function copyInviteLink()')
    expect(content).toContain("window.location.origin")
    expect(content).toContain('/parent/register?code=')
    expect(content).toContain('navigator.clipboard.writeText')
  })

  it('handles batch remove with sequential API calls', () => {
    expect(content).toContain('async function handleBatchRemove()')
    expect(content).toContain('for (const userId of keys)')
    expect(content).toContain('removeParent(classId.value, userId)')
    expect(content).toContain('successCount++')
  })

  it('loads parents and invite code on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadParents()')
    expect(content).toContain('loadInviteCode()')
  })
})

describe('ConductParents error handling', () => {
  it('wraps loadParents in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadParents'),
      content.indexOf('async function handleRemove')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadInviteCode in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadInviteCode'),
      content.indexOf('async function handleRegenerate')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps handleRegenerate in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleRegenerate'),
      content.indexOf('function copyInviteLink')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '刷新失败'")
  })

  it('wraps handleRemove in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleRemove'),
      content.indexOf('async function handleBatchRemove')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '移除失败'")
  })
})
