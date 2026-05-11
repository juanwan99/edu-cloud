/**
 * ParentProfile.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains avatar header, bound children, settings list, logout
 *  3. API calls for profile, password change
 *  4. Form validation rules
 *  5. Error handling
 *  6. Theme toggle injection
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentProfile.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentProfile smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentProfile.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentProfile template sections', () => {
  it('contains avatar and basic info header', () => {
    expect(content).toContain('class="profile-header"')
    expect(content).toContain('class="profile-avatar"')
    expect(content).toContain('{{ avatarLetter }}')
    expect(content).toContain("parentInfo?.display_name || '家长'")
    expect(content).toContain('{{ maskedPhone }}')
  })

  it('contains bound children section with p-card', () => {
    expect(content).toContain('已绑定孩子')
    expect(content).toContain('v-for="child in childrenList"')
    expect(content).toContain('class="child-row"')
    expect(content).toContain('{{ child.student_name }}')
  })

  it('contains bind child button', () => {
    expect(content).toContain("'/parent/bind'")
    expect(content).toContain('绑定孩子')
  })

  it('contains settings items with chevron', () => {
    expect(content).toContain('class="settings-item"')
    expect(content).toContain('外观模式')
    expect(content).toContain('修改密码')
    expect(content).toContain('ChevronRight')
  })

  it('contains collapsible password form', () => {
    expect(content).toContain('v-if="showPasswordForm"')
    expect(content).toContain('v-model:value="pwdForm.old_password"')
    expect(content).toContain('v-model:value="pwdForm.new_password"')
    expect(content).toContain('v-model:value="pwdForm.confirm_password"')
  })

  it('contains theme selector modal', () => {
    expect(content).toContain('v-model:show="showThemeModal"')
    expect(content).toContain('n-radio-group')
    expect(content).toContain('value="dark"')
    expect(content).toContain('value="light"')
    expect(content).toContain('value="system"')
  })

  it('contains logout button with confirmation', () => {
    expect(content).toContain('<n-popconfirm')
    expect(content).toContain('@positive-click="handleLogout"')
    expect(content).toContain('确定退出登录？')
    expect(content).toContain('退出登录')
  })

  it('contains version info', () => {
    expect(content).toContain('class="profile-version"')
    expect(content).toContain('v1.0')
  })
})

describe('ParentProfile theme toggle', () => {
  it('injects parentTheme and setParentTheme', () => {
    expect(content).toContain("inject('parentTheme'")
    expect(content).toContain("inject('setParentTheme'")
  })

  it('computes themeLabel from parentTheme', () => {
    expect(content).toContain('const themeLabel = computed')
    expect(content).toContain("'深色'")
    expect(content).toContain("'浅色'")
    expect(content).toContain("'跟随系统'")
  })

  it('uses computed themeValue with get/set', () => {
    expect(content).toContain('const themeValue = computed({')
    expect(content).toContain('get: () => parentTheme.value')
    expect(content).toContain('setParentTheme(v)')
  })
})

describe('ParentProfile API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { changeParentPassword, getParentMe } from '../../api/conduct'")
  })

  it('fetches profile on mount', () => {
    expect(content).toContain('await getParentMe()')
    expect(content).toContain('parentInfo.value = res.data')
  })

  it('calls changeParentPassword on password change', () => {
    expect(content).toContain('await changeParentPassword({')
    expect(content).toContain('old_password: pwdForm.value.old_password')
    expect(content).toContain('new_password: pwdForm.value.new_password')
  })
})

describe('ParentProfile form validation', () => {
  it('requires old password', () => {
    expect(content).toContain("old_password: { required: true, message: '请输入旧密码'")
  })

  it('requires new password with min length', () => {
    expect(content).toContain("new_password: { required: true, message: '请输入新密码', min: 6 }")
  })

  it('validates password match', () => {
    expect(content).toContain('v === pwdForm.value.new_password')
    expect(content).toContain("new Error('两次密码不一致')")
  })
})

describe('ParentProfile computed properties', () => {
  it('computes avatar letter from display name', () => {
    expect(content).toContain('const avatarLetter = computed')
    expect(content).toContain("display_name?.charAt(0) || '家'")
  })

  it('masks phone number for display', () => {
    expect(content).toContain('const maskedPhone = computed')
    expect(content).toContain("phone.slice(0, 3) + '****' + phone.slice(-4)")
  })
})

describe('ParentProfile error handling', () => {
  it('wraps changePassword in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleChangePassword'),
      content.indexOf('function handleLogout')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
  })

  it('handles password change error', () => {
    expect(content).toContain("message.error(err.response?.data?.detail || '修改失败')")
  })

  it('clears password form after successful change', () => {
    expect(content).toContain("pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }")
  })

  it('handles logout by removing cp_token', () => {
    expect(content).toContain("localStorage.removeItem('cp_token')")
    expect(content).toContain("router.replace('/parent/login')")
  })

  it('injects children from ParentLayout', () => {
    expect(content).toContain("inject('children'")
  })
})
