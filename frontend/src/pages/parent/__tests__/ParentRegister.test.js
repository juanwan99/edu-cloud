/**
 * ParentRegister.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains two-step registration flow
 *  3. API calls for invite validation and registration
 *  4. Form validation rules
 *  5. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentRegister.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentRegister smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentRegister.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentRegister template sections', () => {
  it('has step 1: invite code input', () => {
    expect(content).toContain('v-if="step === 1"')
    expect(content).toContain('v-model:value="inviteForm.code"')
    expect(content).toContain('请输入班级邀请码')
  })

  it('has step 2: registration form', () => {
    expect(content).toContain('v-if="step === 2"')
    expect(content).toContain('v-model:value="regForm.display_name"')
    expect(content).toContain('v-model:value="regForm.phone"')
    expect(content).toContain('v-model:value="regForm.password"')
  })

  it('shows class info after invite validation', () => {
    expect(content).toContain('classInfo.school_name')
    expect(content).toContain('classInfo.class_name')
    expect(content).toContain('type="success"')
  })

  it('has relationship selector', () => {
    expect(content).toContain('v-model:value="regForm.relationship"')
    expect(content).toContain(':options="relationshipOptions"')
  })

  it('has login link for existing users', () => {
    expect(content).toContain('to="/parent/login"')
    expect(content).toContain('已有账号？去登录')
  })

  it('has page header', () => {
    expect(content).toContain('家长注册')
  })
})

describe('ParentRegister API calls', () => {
  it('imports getInviteInfo and parentRegister from conduct API', () => {
    expect(content).toContain("import { getInviteInfo, parentRegister } from '../../api/conduct'")
  })

  it('calls getInviteInfo with invite code', () => {
    expect(content).toContain('await getInviteInfo(inviteForm.value.code)')
  })

  it('calls parentRegister with form data and invite code', () => {
    expect(content).toContain('await parentRegister({')
    expect(content).toContain('invite_code: inviteForm.value.code')
  })

  it('stores cp_token after registration', () => {
    expect(content).toContain("localStorage.setItem('cp_token', res.data.access_token)")
  })

  it('navigates to bind page after registration', () => {
    expect(content).toContain("router.push('/parent/bind')")
  })
})

describe('ParentRegister form validation', () => {
  it('requires invite code', () => {
    expect(content).toContain("code: { required: true, message: '请输入邀请码'")
  })

  it('requires name', () => {
    expect(content).toContain("name: { required: true, message: '请输入姓名'")
  })

  it('requires phone', () => {
    expect(content).toContain("phone: { required: true, message: '请输入手机号'")
  })

  it('requires password with min length', () => {
    expect(content).toContain("password: { required: true, message: '请输入密码', trigger: 'blur', min: 6 }")
  })

  it('requires relationship selection', () => {
    expect(content).toContain("relationship: { required: true, message: '请选择关系'")
  })

  it('defines 5 relationship options', () => {
    expect(content).toContain("{ label: '父亲', value: 'father' }")
    expect(content).toContain("{ label: '母亲', value: 'mother' }")
    expect(content).toContain("{ label: '祖父', value: 'grandfather' }")
    expect(content).toContain("{ label: '祖母', value: 'grandmother' }")
    expect(content).toContain("{ label: '其他', value: 'other' }")
  })
})

describe('ParentRegister error handling', () => {
  it('handles invalid invite code error', () => {
    expect(content).toContain("window.$message?.error(err.response?.data?.detail || '邀请码无效')")
  })

  it('handles registration failure error', () => {
    expect(content).toContain("window.$message?.error(err.response?.data?.detail || '注册失败')")
  })

  it('wraps validateInvite in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function validateInvite'),
      content.indexOf('async function handleRegister')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
  })

  it('wraps handleRegister in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleRegister'),
      content.indexOf('</script>')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
  })

  it('auto-fills invite code from URL query parameter', () => {
    expect(content).toContain('const code = route.query.code')
    expect(content).toContain('inviteForm.value.code = code')
  })
})
