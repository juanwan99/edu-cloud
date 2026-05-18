/**
 * SchoolSettingsPage source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (tabs: modules, segments, settings, capabilities)
 *  3. API imports (getSchoolModules, toggleModule, getSchoolSettings, etc.)
 *  4. Module toggle CRUD
 *  5. Settings table + inline edit modal
 *  6. Capability matrix (init, set, filter)
 *  7. Error handling (try-catch, message feedback)
 *
 * Style: readFileSync + toContain/toMatch. No mount.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../SchoolSettingsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('SchoolSettingsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../SchoolSettingsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SchoolSettingsPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('学校配置')
    expect(content).toContain('管理功能模块和学校设置')
  })

  it('contains module summary line', () => {
    expect(content).toContain('enabledCount')
    expect(content).toContain('modules.length')
    expect(content).toContain('个模块')
  })

  it('uses n-tabs with three tab panes', () => {
    expect(content).toContain('<n-tabs type="line" animated>')
    expect(content).toContain('name="modules"')
    expect(content).toContain('name="settings"')
    expect(content).toContain('name="capabilities"')
    expect(content).not.toContain('name="segments"')
  })

  it('tab labels are correct', () => {
    expect(content).toContain('tab="功能模块"')
    expect(content).toContain('tab="学校设置"')
    expect(content).toContain('tab="能力矩阵"')
    expect(content).not.toContain('tab="分数段"')
  })
})

describe('SchoolSettingsPage modules tab', () => {
  it('contains module management card', () => {
    expect(content).toContain('title="功能模块管理"')
    expect(content).toContain('启用或禁用学校可用的功能模块')
  })

  it('describes module disable effect', () => {
    expect(content).toContain('禁用后，对应的导航菜单、API 和 AI 助手工具将不可用')
  })

  it('iterates over modules with v-for', () => {
    expect(content).toContain('v-for="m in modules"')
    expect(content).toContain(':key="m.code"')
    expect(content).toContain('class="module-row"')
  })

  it('displays module name and code', () => {
    expect(content).toContain('{{ m.name }}')
    expect(content).toContain('{{ m.code }}')
  })

  it('shows module description from MODULE_DESCRIPTIONS', () => {
    expect(content).toContain('MODULE_DESCRIPTIONS[m.code]')
  })

  it('uses n-switch for toggle with loading state', () => {
    expect(content).toContain(':value="m.enabled"')
    expect(content).toContain(':loading="toggling === m.code"')
    expect(content).toContain('@update:value="(v) => handleToggle(m.code, v)"')
  })

  it('has icon for each module row', () => {
    expect(content).toContain(':is="getModuleIcon(m.code)"')
  })
})

describe('SchoolSettingsPage MODULE_DESCRIPTIONS constant', () => {
  it('defines descriptions for all 9 module codes', () => {
    expect(content).toContain("exam: '考试创建、科目管理、题目编辑、答题卡设计'")
    expect(content).toContain("grading: 'AI 阅卷、评分细则、教师复核、阅卷调度'")
    expect(content).toContain("homework: '作业布置、提交批改、统计分析'")
    expect(content).toContain("study_analytics: '成绩分析、趋势对比、分层学情'")
    expect(content).toContain("research: '教研协作、集体备课、课题管理'")
    expect(content).toContain("teaching: '排课、选考组合、课表管理'")
    expect(content).toContain("calendar: '校历事件、通知规则、学期管理'")
    expect(content).toContain("studio: '文档生成、报告模板、论文协作'")
    expect(content).toContain("conduct: '操行管理、积分记录、班规、家长端'")
  })
})

describe('SchoolSettingsPage MODULE_ICONS mapping', () => {
  it('maps each module code to an icon component', () => {
    expect(content).toContain('exam: FileText')
    expect(content).toContain('grading: PenTool')
    expect(content).toContain('homework: FileEdit')
    expect(content).toContain('study_analytics: BarChart3')
    expect(content).toContain('research: FlaskConical')
    expect(content).toContain('teaching: School')
    expect(content).toContain('calendar: Calendar')
    expect(content).toContain('conduct: Users')
  })

  it('getModuleIcon falls back to CheckSquare', () => {
    expect(content).toContain('MODULE_ICONS[code] || CheckSquare')
  })
})

describe('SchoolSettingsPage segments tab removed', () => {
  it('no longer contains ScoreSegmentSettings', () => {
    expect(content).not.toContain('<ScoreSegmentSettings />')
    expect(content).not.toContain('ScoreSegmentSettings')
  })
})

describe('SchoolSettingsPage settings tab', () => {
  it('contains settings card with data table', () => {
    expect(content).toContain('title="配置项"')
    expect(content).toContain(':columns="settingsColumns"')
    expect(content).toContain(':data="settings"')
    expect(content).toContain(':loading="loadingSettings"')
  })

  it('defines settings columns with category, key, and editable value', () => {
    expect(content).toContain("title: '分类', key: 'category'")
    expect(content).toContain("title: '键', key: 'key'")
    expect(content).toContain("title: '值', key: 'value'")
  })

  it('value column is clickable for inline edit', () => {
    expect(content).toContain('onClick: () => startEditSetting(row)')
    expect(content).toContain("row.value || '(空)'")
  })

  it('contains inline edit modal for settings', () => {
    expect(content).toContain('v-model:show="showEditSetting"')
    expect(content).toContain('title="编辑配置值"')
    expect(content).toContain('positive-text="保存"')
    expect(content).toContain('@positive-click="handleSaveSetting"')
  })

  it('edit modal shows category and key label', () => {
    expect(content).toContain("`${editingSettingRow?.category} / ${editingSettingRow?.key}`")
  })

  it('edit modal uses textarea with autosize', () => {
    expect(content).toContain('v-model:value="editingSettingValue"')
    expect(content).toContain('type="textarea"')
    expect(content).toContain(':autosize="{ minRows: 2, maxRows: 6 }"')
  })
})

describe('SchoolSettingsPage capabilities tab', () => {
  it('contains capability matrix card', () => {
    expect(content).toContain('title="角色能力矩阵"')
  })

  it('has init button', () => {
    expect(content).toContain('@click="handleInitCapabilities"')
    expect(content).toContain('初始化默认')
  })

  it('has role filter select', () => {
    expect(content).toContain('v-model:value="capRoleFilter"')
    expect(content).toContain('placeholder="全部角色"')
  })

  it('shows loading spinner', () => {
    expect(content).toContain('v-if="loadingCaps"')
    expect(content).toContain('<n-spin />')
  })

  it('shows empty state prompt', () => {
    expect(content).toContain('v-else-if="capMatrix.length === 0"')
    expect(content).toContain('暂无能力配置，请点击"初始化默认"')
  })

  it('renders matrix table with domain/action rows and role columns', () => {
    expect(content).toContain('class="cap-matrix"')
    expect(content).toContain('域 / 操作')
    expect(content).toContain('v-for="role in capRoles"')
    expect(content).toContain('v-for="da in capDomainActions"')
  })

  it('uses n-checkbox for capability toggles', () => {
    expect(content).toContain(':checked="getCapValue(role, da.domain, da.action)"')
    expect(content).toContain('@update:checked="(v) => handleSetCapability(role, da.domain, da.action, v)"')
  })
})

describe('SchoolSettingsPage API imports', () => {
  it('imports all schoolSettings API functions', () => {
    expect(content).toContain('getSchoolModules')
    expect(content).toContain('toggleModule')
    expect(content).toContain('getSchoolSettings')
    expect(content).toContain('updateSchoolSetting')
    expect(content).toContain('getCapabilities')
    expect(content).toContain('setCapability')
    expect(content).toContain('initCapabilities')
  })

  it('imports from correct path', () => {
    expect(content).toContain("from '../api/schoolSettings.js'")
  })

  it('imports useAuthStore', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
  })

  it('imports icon components from lucide-vue-next', () => {
    expect(content).toContain("from 'lucide-vue-next'")
    expect(content).toContain('FileText')
    expect(content).toContain('School')
    expect(content).toContain('PenTool')
    expect(content).toContain('BarChart3')
    expect(content).toContain('FlaskConical')
    expect(content).toContain('Calendar')
    expect(content).toContain('Users')
    expect(content).toContain('CheckSquare')
  })
})

describe('SchoolSettingsPage reactive state', () => {
  it('declares modules, settings, and toggling refs', () => {
    expect(content).toContain('const modules = ref([])')
    expect(content).toContain('const settings = ref([])')
    expect(content).toContain('const toggling = ref(null)')
    expect(content).toContain('const loadingSettings = ref(false)')
  })

  it('declares capabilities state', () => {
    expect(content).toContain('const capabilities = ref([])')
    expect(content).toContain('const loadingCaps = ref(false)')
    expect(content).toContain('const capRoleFilter = ref(null)')
  })

  it('declares inline edit state for settings', () => {
    expect(content).toContain('const showEditSetting = ref(false)')
    expect(content).toContain('const editingSettingRow = ref(null)')
    expect(content).toContain("const editingSettingValue = ref('')")
  })

  it('derives schoolId from auth store', () => {
    expect(content).toContain('auth.currentRole?.school_id')
  })
})

describe('SchoolSettingsPage capRoleOptions', () => {
  it('lists all 8 role options including school_admin', () => {
    const roles = [
      'school_admin', 'principal', 'academic_director', 'teaching_research_leader',
      'grade_leader', 'lesson_prep_leader', 'homeroom_teacher', 'subject_teacher',
    ]
    for (const role of roles) {
      expect(content).toContain(`'${role}'`)
    }
  })

  it('uses ROLE_LABELS for display', () => {
    expect(content).toContain('ROLE_LABELS[r] || r')
  })
})

describe('SchoolSettingsPage computed properties', () => {
  it('enabledCount filters modules by enabled', () => {
    expect(content).toContain('modules.value.filter((m) => m.enabled).length')
  })

  it('capMatrix filters by capRoleFilter', () => {
    expect(content).toContain('capabilities.value.filter((c) => c.role === capRoleFilter.value)')
  })

  it('capRoles extracts unique sorted roles', () => {
    expect(content).toContain("new Set(capMatrix.value.map((c) => c.role))")
  })

  it('capDomainActions extracts unique domain::action pairs', () => {
    expect(content).toContain('`${c.domain}::${c.action}`')
  })

  it('getCapValue looks up capability by role, domain, action', () => {
    expect(content).toContain('c.role === role && c.domain === domain && c.action === action')
    expect(content).toContain('cap ? cap.enabled : false')
  })
})

describe('SchoolSettingsPage loadModules', () => {
  it('guards on schoolId before calling API', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadModules'),
      content.indexOf('async function loadSettings')
    )
    expect(fnBlock).toContain('if (!schoolId()) return')
    expect(fnBlock).toContain('getSchoolModules(schoolId())')
  })

  it('assigns response data to modules ref', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadModules'),
      content.indexOf('async function loadSettings')
    )
    expect(fnBlock).toContain('modules.value = data')
  })

  it('shows error message on failure', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadModules'),
      content.indexOf('async function loadSettings')
    )
    expect(fnBlock).toContain("message.error('加载模块失败')")
  })
})

describe('SchoolSettingsPage loadSettings', () => {
  it('guards on schoolId and manages loading state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSettings'),
      content.indexOf('async function loadCapabilities')
    )
    expect(fnBlock).toContain('if (!schoolId()) return')
    expect(fnBlock).toContain('loadingSettings.value = true')
    expect(fnBlock).toContain('loadingSettings.value = false')
  })

  it('calls getSchoolSettings API', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSettings'),
      content.indexOf('async function loadCapabilities')
    )
    expect(fnBlock).toContain('getSchoolSettings(schoolId())')
  })

  it('wraps in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSettings'),
      content.indexOf('async function loadCapabilities')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })
})

describe('SchoolSettingsPage loadCapabilities', () => {
  it('passes role filter to API call', () => {
    expect(content).toContain('getCapabilities(schoolId(), capRoleFilter.value || undefined)')
  })

  it('manages loadingCaps state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadCapabilities'),
      content.indexOf('async function handleToggle')
    )
    expect(fnBlock).toContain('loadingCaps.value = true')
    expect(fnBlock).toContain('loadingCaps.value = false')
  })
})

describe('SchoolSettingsPage handleToggle', () => {
  it('sets toggling to module code during operation', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleToggle'),
      content.indexOf('async function handleSetCapability')
    )
    expect(fnBlock).toContain('toggling.value = code')
    expect(fnBlock).toContain('toggling.value = null')
  })

  it('calls toggleModule API then reloads', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleToggle'),
      content.indexOf('async function handleSetCapability')
    )
    expect(fnBlock).toContain('await toggleModule(schoolId(), code, enabled)')
    expect(fnBlock).toContain('await loadModules()')
    expect(fnBlock).toContain('await auth.loadModules()')
  })

  it('shows success message with module code and state', () => {
    expect(content).toContain("message.success(`模块「${code}」已${enabled ? '启用' : '禁用'}`)")
  })

  it('shows error message on failure', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleToggle'),
      content.indexOf('async function handleSetCapability')
    )
    expect(fnBlock).toContain("e.response?.data?.detail || '操作失败'")
  })
})

describe('SchoolSettingsPage handleSetCapability', () => {
  it('calls setCapability API with role, domain, action, enabled', () => {
    expect(content).toContain('await setCapability(schoolId(), { role, domain, action, enabled })')
  })

  it('updates local state optimistically', () => {
    expect(content).toContain('capabilities.value[idx].enabled = enabled')
  })

  it('reloads capabilities on error (rollback)', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSetCapability'),
      content.indexOf('async function handleInitCapabilities')
    )
    expect(fnBlock).toContain('await loadCapabilities()')
  })
})

describe('SchoolSettingsPage handleInitCapabilities', () => {
  it('calls initCapabilities API', () => {
    expect(content).toContain('await initCapabilities(schoolId())')
  })

  it('shows success message and reloads', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleInitCapabilities'),
      content.indexOf('onMounted(() => {')
    )
    expect(fnBlock).toContain("message.success('能力矩阵已初始化')")
    expect(fnBlock).toContain('await loadCapabilities()')
  })

  it('shows error message on failure', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleInitCapabilities'),
      content.indexOf('onMounted(() => {')
    )
    expect(fnBlock).toContain("e.response?.data?.detail || '初始化失败'")
  })
})

describe('SchoolSettingsPage handleSaveSetting', () => {
  it('guards on editingSettingRow', () => {
    expect(content).toContain('if (!editingSettingRow.value) return')
  })

  it('calls updateSchoolSetting with correct payload', () => {
    expect(content).toContain('await updateSchoolSetting(schoolId(), {')
    expect(content).toContain('category: editingSettingRow.value.category')
    expect(content).toContain('key: editingSettingRow.value.key')
    expect(content).toContain('value: editingSettingValue.value')
  })

  it('shows success message and closes modal', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSaveSetting'),
      content.indexOf('async function loadModules')
    )
    expect(fnBlock).toContain("message.success('配置已保存')")
    expect(fnBlock).toContain('showEditSetting.value = false')
    expect(fnBlock).toContain('await loadSettings()')
  })

  it('shows error message on failure', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSaveSetting'),
      content.indexOf('async function loadModules')
    )
    expect(fnBlock).toContain("e.response?.data?.detail || '保存失败'")
  })
})

describe('SchoolSettingsPage startEditSetting', () => {
  it('sets editing state from row', () => {
    expect(content).toContain('editingSettingRow.value = row')
    expect(content).toContain("editingSettingValue.value = row.value || ''")
    expect(content).toContain('showEditSetting.value = true')
  })
})

describe('SchoolSettingsPage lifecycle', () => {
  it('loads modules, settings, and capabilities on mount', () => {
    const mountBlock = content.slice(content.indexOf('onMounted('))
    expect(mountBlock).toContain('loadModules()')
    expect(mountBlock).toContain('loadSettings()')
    expect(mountBlock).toContain('loadCapabilities()')
  })
})

describe('SchoolSettingsPage error handling patterns', () => {
  it('handleToggle wraps in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleToggle'),
      content.indexOf('async function handleSetCapability')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('handleSetCapability wraps in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSetCapability'),
      content.indexOf('async function handleInitCapabilities')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('handleInitCapabilities wraps in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleInitCapabilities'),
      content.indexOf('onMounted(() => {')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('handleSaveSetting wraps in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSaveSetting'),
      content.indexOf('async function loadModules')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })
})

describe('SchoolSettingsPage styles', () => {
  it('uses scoped styles', () => {
    expect(content).toContain('<style scoped>')
  })

  it('styles module-row with flex layout', () => {
    expect(content).toContain('.module-row')
    expect(content).toContain('justify-content: space-between')
  })

  it('styles cap-matrix table', () => {
    expect(content).toContain('.cap-matrix-wrapper')
    expect(content).toContain('overflow-x: auto')
    expect(content).toContain('.cap-matrix th')
    expect(content).toContain('.cap-matrix td')
  })

  it('cap-matrix rows have hover effect', () => {
    expect(content).toContain('.cap-matrix tbody tr:hover')
  })
})
