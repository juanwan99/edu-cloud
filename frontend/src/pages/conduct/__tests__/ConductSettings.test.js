/**
 * ConductSettings source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (invite code, verification settings, module switch, semester management)
 *  3. API calls via conduct.js (getConductConfig, updateConductConfig, regenerateInviteCode, getSemesters, etc.)
 *  4. Operations (config save, regenerate code, create semester, activate semester)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductSettings.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductSettings smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductSettings.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductSettings template sections', () => {
  it('contains class-not-selected alert and invite code management', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('title="邀请码管理"')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains invite code management section', () => {
    expect(content).toContain('title="邀请码管理"')
    expect(content).toContain("config.invite_code || '未生成'")
    expect(content).toContain('刷新邀请码')
    expect(content).toContain('家长使用此邀请码注册并绑定学生')
  })

  it('contains verification type radio group', () => {
    expect(content).toContain('title="家长验证方式"')
    expect(content).toContain('v-model:value="config.verify_code_type"')
    expect(content).toContain('value="id_card"')
    expect(content).toContain('value="phone"')
    expect(content).toContain('value="custom"')
    expect(content).toContain('身份证后六位')
    expect(content).toContain('手机号后四位')
    expect(content).toContain('自定义验证码')
  })

  it('contains module switch section', () => {
    expect(content).toContain('title="模块状态"')
    expect(content).toContain('德育模块')
    expect(content).toContain('config.is_active !== false')
    expect(content).toContain('已启用')
    expect(content).toContain('已停用')
  })

  it('contains semester management section', () => {
    expect(content).toContain('title="学期管理"')
    expect(content).toContain('新建学期')
    expect(content).toContain('v-for="s in semesters"')
    expect(content).toContain('v-if="s.is_active"')
    expect(content).toContain('设为当前学期')
  })

  it('contains create semester modal', () => {
    expect(content).toContain('v-model:show="showCreateSemester"')
    expect(content).toContain('title="新建学期"')
    expect(content).toContain('v-model:value="semesterForm.name"')
    expect(content).toContain('v-model:value="semesterForm.start_date"')
    expect(content).toContain('v-model:value="semesterForm.end_date"')
    expect(content).toContain("placeholder=\"例：2025-2026 第二学期\"")
  })
})

describe('ConductSettings API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getConductConfig')
    expect(content).toContain('updateConductConfig')
    expect(content).toContain('regenerateInviteCode')
    expect(content).toContain('getSemesters')
    expect(content).toContain('createSemester')
    expect(content).toContain('activateSemester')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getConductConfig to load config', () => {
    expect(content).toContain('getConductConfig(classId.value)')
  })

  it('calls updateConductConfig to save settings', () => {
    expect(content).toContain('updateConductConfig(classId.value, {')
    expect(content).toContain('verify_code_type: config.value.verify_code_type')
    expect(content).toContain('is_active: config.value.is_active')
  })

  it('calls regenerateInviteCode', () => {
    expect(content).toContain('regenerateInviteCode(classId.value)')
  })

  it('calls getSemesters to load semesters', () => {
    expect(content).toContain('getSemesters(classId.value)')
  })

  it('calls createSemester with form data', () => {
    expect(content).toContain('createSemester(classId.value, payload)')
  })

  it('calls activateSemester', () => {
    expect(content).toContain('activateSemester(classId.value, semId)')
  })
})

describe('ConductSettings operations', () => {
  it('initializes config with defaults', () => {
    expect(content).toContain("invite_code: ''")
    expect(content).toContain("verify_code_type: 'id_card'")
    expect(content).toContain('is_active: true')
  })

  it('saves config on verification type change', () => {
    expect(content).toContain('@update:value="saveConfig"')
  })

  it('saves config on module switch toggle', () => {
    expect(content).toContain('config.is_active = v; saveConfig()')
  })

  it('validates semester name before creation', () => {
    expect(content).toContain("semesterForm.value.name.trim()")
    expect(content).toContain("请输入学期名称")
  })

  it('formats dates for semester creation payload', () => {
    expect(content).toContain("new Date(semesterForm.value.start_date).toISOString().split('T')[0]")
    expect(content).toContain("new Date(semesterForm.value.end_date).toISOString().split('T')[0]")
  })

  it('resets semester form after creation', () => {
    expect(content).toContain("semesterForm.value = { name: '', start_date: null, end_date: null }")
  })

  it('reloads config after regeneration', () => {
    expect(content).toContain('await loadConfig()')
  })

  it('tracks which semester is being activated', () => {
    expect(content).toContain('activating.value = semId')
    expect(content).toContain('activating.value = null')
  })

  it('loads config and semesters on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadConfig()')
    expect(content).toContain('loadSemesters()')
  })
})

describe('ConductSettings error handling', () => {
  it('wraps loadConfig in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadConfig'),
      content.indexOf('async function saveConfig')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps saveConfig in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function saveConfig'),
      content.indexOf('async function handleRegenerate')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '保存失败'")
  })

  it('wraps handleRegenerate in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleRegenerate'),
      content.indexOf('async function loadSemesters')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '刷新失败'")
  })

  it('wraps loadSemesters in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadSemesters'),
      content.indexOf('async function handleCreateSemester')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps handleCreateSemester in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleCreateSemester'),
      content.indexOf('async function handleActivate')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('wraps handleActivate in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleActivate'),
      content.indexOf('onMounted(')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '操作失败'")
  })
})
