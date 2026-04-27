/**
 * ParentProfile.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains profile form, password change, bound children, logout
 *  3. API calls for profile, password change
 *  4. Form validation rules
 *  5. Error handling
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
    expect(content).toContain('class="avatar-circle"')
    expect(content).toContain('{{ avatarLetter }}')
    expect(content).toContain("profileForm.display_name || '未设置姓名'")
    expect(content).toContain('{{ maskedPhone }}')
  })

  it('contains profile edit form', () => {
    expect(content).toContain('title="个人信息"')
    expect(content).toContain('v-model:value="profileForm.display_name"')
    expect(content).toContain(':value="profileForm.phone" disabled')
  })

  it('contains password change form', () => {
    expect(content).toContain('title="修改密码"')
    expect(content).toContain('v-model:value="pwdForm.old_password"')
    expect(content).toContain('v-model:value="pwdForm.new_password"')
    expect(content).toContain('v-model:value="pwdForm.confirm_password"')
  })

  it('contains security hint after password change', () => {
    expect(content).toContain('v-if="showSecurityHint"')
    expect(content).toContain('账号安全提示')
    expect(content).toContain('密码修改成功，所有设备已退出登录，请重新登录。')
  })

  it('contains bound children list', () => {
    expect(content).toContain('title="已绑定孩子"')
    expect(content).toContain('v-for="child in children"')
    expect(content).toContain('class="child-card"')
    expect(content).toContain('{{ child.student_name }}')
    expect(content).toContain('child.total_points')
  })

  it('contains empty state for no children', () => {
    expect(content).toContain('description="暂未绑定孩子"')
  })

  it('contains bind new child button', () => {
    expect(content).toContain("'/parent/bind'")
    expect(content).toContain('绑定新孩子')
  })

  it('contains logout button with confirmation', () => {
    expect(content).toContain('<n-popconfirm')
    expect(content).toContain('@positive-click="handleLogout"')
    expect(content).toContain('确定要退出登录吗？')
    expect(content).toContain('退出登录')
  })

  it('contains version info', () => {
    expect(content).toContain('class="version-info"')
    expect(content).toContain('v1.0')
  })

  it('shows child exam score and recent change', () => {
    expect(content).toContain('v-if="child.recent_change != null"')
    expect(content).toContain('v-if="child.last_exam_score != null"')
    expect(content).toContain('最近考试:')
  })
})

describe('ParentProfile API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { getParentMe, updateParentProfile, changeParentPassword } from '../../api/conduct'")
  })

  it('fetches profile on mount', () => {
    expect(content).toContain('await getParentMe()')
    expect(content).toContain('profileForm.value.display_name = res.data.display_name')
    expect(content).toContain('profileForm.value.phone = res.data.phone')
  })

  it('calls updateParentProfile on save', () => {
    expect(content).toContain('await updateParentProfile({ display_name: profileForm.value.display_name })')
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
    expect(content).toContain("new_password: { required: true, message: '请输入新密码', trigger: 'blur', min: 6 }")
  })

  it('requires password confirmation', () => {
    expect(content).toContain("{ required: true, message: '请确认新密码'")
  })

  it('validates password match', () => {
    expect(content).toContain('value === pwdForm.value.new_password')
    expect(content).toContain("message: '两次输入的密码不一致'")
  })
})

describe('ParentProfile computed properties', () => {
  it('computes avatar letter from display name', () => {
    expect(content).toContain('const avatarLetter = computed')
    expect(content).toContain("return name ? name.charAt(0) : '?'")
  })

  it('masks phone number for display', () => {
    expect(content).toContain('const maskedPhone = computed')
    expect(content).toContain("phone.substring(0, 3) + '****' + phone.substring(7)")
    expect(content).toContain("return phone || '未设置'")
  })
})

describe('ParentProfile error handling', () => {
  it('wraps updateProfile in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleUpdateProfile'),
      content.indexOf('async function handleChangePassword')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
  })

  it('wraps changePassword in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleChangePassword'),
      content.indexOf('function handleLogout')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
  })

  it('handles profile update error', () => {
    expect(content).toContain("window.$message?.error(err.response?.data?.detail || '保存失败')")
  })

  it('handles password change error', () => {
    expect(content).toContain("window.$message?.error(err.response?.data?.detail || '修改失败')")
  })

  it('clears password form after successful change', () => {
    expect(content).toContain("pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }")
  })

  it('handles logout by removing cp_token', () => {
    expect(content).toContain("localStorage.removeItem('cp_token')")
    expect(content).toContain("router.push('/parent/login')")
  })

  it('injects children from ParentLayout', () => {
    expect(content).toContain("const childrenInjected = inject('children')")
  })
})
