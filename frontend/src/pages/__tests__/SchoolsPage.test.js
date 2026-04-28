/**
 * SchoolsPage source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (header, stats, filter bar, table/card views, create modal)
 *  3. API imports and calls (listSchools, createSchool)
 *  4. CRUD logic (handleCreate validation, form fields, reset)
 *  5. Search and district filter
 *  6. Error handling (try-catch, interceptor, message feedback)
 *
 * Style: readFileSync + toContain/toMatch. No mount.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../SchoolsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('SchoolsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../SchoolsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SchoolsPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('学校管理')
    expect(content).toContain('管理系统中的学校信息')
  })

  it('contains stats row with three stat cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('学校总数')
    expect(content).toContain('活跃学校')
    expect(content).toContain('学区数')
  })

  it('contains filter bar with search, district select, and view toggle', () => {
    expect(content).toContain('class="filter-bar"')
    expect(content).toContain('搜索学校名称')
    expect(content).toContain('按学区筛选')
    expect(content).toContain('v-model:value="searchQuery"')
    expect(content).toContain('v-model:value="districtFilter"')
  })

  it('contains view mode toggle with table and card options', () => {
    expect(content).toContain('v-model:value="viewMode"')
    expect(content).toContain("value=\"table\"")
    expect(content).toContain("value=\"card\"")
    expect(content).toContain('表格')
    expect(content).toContain('卡片')
  })

  it('contains table view with n-data-table', () => {
    expect(content).toContain("v-if=\"viewMode === 'table'\"")
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="filteredSchools"')
    expect(content).toContain(':loading="loading"')
  })

  it('contains card view with school cards', () => {
    expect(content).toContain('class="card-grid"')
    expect(content).toContain('class="school-card"')
    expect(content).toContain('v-for="s in filteredSchools"')
  })

  it('card view displays school details', () => {
    expect(content).toContain('{{ s.name }}')
    expect(content).toContain('{{ s.code }}')
    expect(content).toContain("{{ s.district || '-' }}")
    expect(content).toContain("{{ s.contact_name || '-' }}")
    expect(content).toContain("{{ s.contact_phone || '-' }}")
  })

  it('card view shows active/inactive tags', () => {
    expect(content).toContain('v-if="s.is_active"')
    expect(content).toContain('type="success"')
    expect(content).toContain('type="error"')
    expect(content).toContain('>活跃</n-tag>')
    expect(content).toContain('>停用</n-tag>')
  })

  it('contains create school modal', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="添加学校"')
    expect(content).toContain('positive-text="添加"')
    expect(content).toContain('negative-text="取消"')
    expect(content).toContain('@positive-click="handleCreate"')
  })
})

describe('SchoolsPage create modal form fields', () => {
  it('has all five form fields', () => {
    expect(content).toContain('label="学校名称"')
    expect(content).toContain('label="学校代码"')
    expect(content).toContain('label="学区"')
    expect(content).toContain('label="联系人"')
    expect(content).toContain('label="联系电话"')
  })

  it('form fields bind to reactive form object', () => {
    expect(content).toContain('v-model:value="form.name"')
    expect(content).toContain('v-model:value="form.code"')
    expect(content).toContain('v-model:value="form.district"')
    expect(content).toContain('v-model:value="form.contact_name"')
    expect(content).toContain('v-model:value="form.contact_phone"')
  })

  it('has placeholder text for each field', () => {
    expect(content).toContain('placeholder="例如：第一中学"')
    expect(content).toContain('placeholder="例如：SCHOOL01"')
    expect(content).toContain('placeholder="例如：河源市源城区"')
    expect(content).toContain('placeholder="例如：张主任"')
    expect(content).toContain('placeholder="例如：13800138000"')
  })
})

describe('SchoolsPage API imports', () => {
  it('imports listSchools and createSchool from api/schools', () => {
    expect(content).toContain("import { listSchools, createSchool } from '../api/schools'")
  })

  it('imports useMessage from naive-ui', () => {
    expect(content).toContain("import { useMessage } from 'naive-ui'")
  })

  it('imports NTag for render functions', () => {
    expect(content).toContain("import { NTag } from 'naive-ui'")
  })
})

describe('SchoolsPage reactive state', () => {
  it('declares loading ref', () => {
    expect(content).toContain('const loading = ref(true)')
  })

  it('declares schools ref as empty array', () => {
    expect(content).toContain('const schools = ref([])')
  })

  it('declares showCreate ref', () => {
    expect(content).toContain('const showCreate = ref(false)')
  })

  it('declares form reactive with all fields', () => {
    expect(content).toContain("const form = reactive({ name: '', code: '', district: '', contact_name: '', contact_phone: '' })")
  })

  it('declares searchQuery and districtFilter and viewMode refs', () => {
    expect(content).toContain("const searchQuery = ref('')")
    expect(content).toContain('const districtFilter = ref(null)')
    expect(content).toContain("const viewMode = ref('table')")
  })
})

describe('SchoolsPage computed stats', () => {
  it('computes total from schools array length', () => {
    expect(content).toContain('total: all.length')
  })

  it('computes active count by filtering is_active', () => {
    expect(content).toContain('active: all.filter((s) => s.is_active).length')
  })

  it('computes district count using Set', () => {
    expect(content).toContain('districts: districtSet.size')
  })
})

describe('SchoolsPage search and filter logic', () => {
  it('filters schools by name using searchQuery (case-insensitive)', () => {
    expect(content).toContain('const q = searchQuery.value.toLowerCase()')
    expect(content).toContain("s.name?.toLowerCase().includes(q)")
  })

  it('filters schools by district using districtFilter', () => {
    expect(content).toContain('s.district === districtFilter.value')
  })

  it('computes districtOptions from unique districts sorted', () => {
    expect(content).toMatch(/new Set\(schools\.value\.map\(\(s\) => s\.district\)\.filter\(Boolean\)\)/)
  })
})

describe('SchoolsPage table columns', () => {
  it('defines column for school name', () => {
    expect(content).toContain("title: '学校名称', key: 'name'")
  })

  it('defines column for school code', () => {
    expect(content).toContain("title: '学校代码', key: 'code'")
  })

  it('defines column for district with fallback', () => {
    expect(content).toContain("title: '学区', key: 'district'")
    expect(content).toContain("row.district || '-'")
  })

  it('defines column for status with NTag render', () => {
    expect(content).toContain("title: '状态', key: 'is_active'")
    expect(content).toContain("row.is_active ? '活跃' : '停用'")
  })

  it('defines column for created_at with date formatting', () => {
    expect(content).toContain("title: '创建时间', key: 'created_at'")
    expect(content).toContain("toLocaleDateString('zh-CN')")
  })
})

describe('SchoolsPage loadSchools', () => {
  it('sets loading true then calls listSchools API', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSchools'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('loading.value = true')
    expect(fnBlock).toContain('await listSchools()')
  })

  it('assigns response data to schools ref', () => {
    expect(content).toContain('schools.value = data')
  })

  it('sets loading false after completion', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSchools'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('loading.value = false')
  })

  it('wraps in try-catch for error handling', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSchools'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })
})

describe('SchoolsPage handleCreate', () => {
  it('validates name, code, and district are required', () => {
    expect(content).toContain("if (!form.name || !form.code || !form.district)")
    expect(content).toContain("message.warning('请填写完整')")
  })

  it('returns false on validation failure and on catch', () => {
    const start = content.indexOf('async function handleCreate')
    const end = content.indexOf('onMounted(loadSchools)')
    const fnBlock = content.slice(start, end)
    // Two return false paths: validation + catch
    const returnFalseCount = (fnBlock.match(/return false/g) || []).length
    expect(returnFalseCount).toBe(2)
  })

  it('calls createSchool with form data', () => {
    expect(content).toContain('await createSchool({')
    expect(content).toContain('name: form.name')
    expect(content).toContain('code: form.code')
    expect(content).toContain('district: form.district')
  })

  it('sends optional fields as undefined when empty', () => {
    expect(content).toContain('contact_name: form.contact_name || undefined')
    expect(content).toContain('contact_phone: form.contact_phone || undefined')
  })

  it('shows success message on creation', () => {
    expect(content).toContain("message.success('学校添加成功')")
  })

  it('resets form after successful creation', () => {
    expect(content).toContain("Object.assign(form, { name: '', code: '', district: '', contact_name: '', contact_phone: '' })")
  })

  it('closes modal and reloads schools after success', () => {
    const fnBlock = content.slice(
      content.indexOf('await createSchool('),
      content.indexOf('} catch (e)')
    )
    expect(fnBlock).toContain('showCreate.value = false')
    expect(fnBlock).toContain('await loadSchools()')
  })

  it('shows error message from response detail on failure', () => {
    expect(content).toContain("e.response?.data?.detail || '添加失败'")
  })
})

describe('SchoolsPage lifecycle', () => {
  it('calls loadSchools on mount', () => {
    expect(content).toContain('onMounted(loadSchools)')
  })
})

describe('SchoolsPage styles', () => {
  it('uses scoped styles', () => {
    expect(content).toContain('<style scoped>')
  })

  it('defines stats-row as responsive grid', () => {
    expect(content).toContain('grid-template-columns: repeat(auto-fit')
  })

  it('defines card-grid with auto-fill responsive layout', () => {
    expect(content).toContain('grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))')
  })

  it('school-card has hover transform', () => {
    expect(content).toContain('.school-card:hover')
    expect(content).toContain('transform: translateY(-2px)')
  })
})
