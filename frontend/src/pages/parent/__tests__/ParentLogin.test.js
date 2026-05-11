/**
 * ParentLogin.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains login form elements
 *  3. API call uses parentLogin
 *  4. Form validation rules (phone pattern, required fields)
 *  5. Error handling for login failures
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentLogin.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentLogin smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentLogin.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentLogin template sections', () => {
  it('contains login form with phone and password fields', () => {
    expect(content).toContain('v-model:value="form.phone"')
    expect(content).toContain('v-model:value="form.password"')
  })

  it('contains brand area with platform name', () => {
    expect(content).toContain('class="auth-brand"')
    expect(content).toContain('edu-cloud')
    expect(content).toContain('家校互通')
  })

  it('contains login button with loading state', () => {
    expect(content).toContain(":loading=\"loading\"")
    expect(content).toContain("@click=\"handleLogin\"")
    expect(content).toContain("登录中...")
    expect(content).toContain("登 录")
  })

  it('contains remember phone checkbox', () => {
    expect(content).toContain('v-model:checked="rememberPhone"')
    expect(content).toContain('记住手机号')
  })

  it('contains register link', () => {
    expect(content).toContain('to="/parent/register"')
    expect(content).toContain('还没有账号？立即注册')
  })

  it('contains password reset hint', () => {
    expect(content).toContain('class="login-hint"')
    expect(content).toContain('忘记密码？请联系班主任重置')
  })

  it('contains success overlay with animation', () => {
    expect(content).toContain('v-if="showSuccess"')
    expect(content).toContain('class="success-overlay"')
    expect(content).toContain('登录成功')
  })

  it('contains error alert', () => {
    expect(content).toContain('v-if="loginError"')
    expect(content).toContain('type="error"')
  })
})

describe('ParentLogin API calls', () => {
  it('imports parentLogin from conduct API', () => {
    expect(content).toContain("import { parentLogin } from '../../api/conduct'")
  })

  it('calls parentLogin with form data', () => {
    expect(content).toContain('await parentLogin(form.value)')
  })

  it('stores cp_token after successful login', () => {
    expect(content).toContain("localStorage.setItem('cp_token', res.data.access_token)")
  })

  it('navigates to /parent after login', () => {
    expect(content).toContain("router.push('/parent')")
  })
})

describe('ParentLogin form validation', () => {
  it('requires phone number', () => {
    expect(content).toContain("required: true, message: '请输入手机号'")
  })

  it('validates phone pattern (Chinese mobile)', () => {
    expect(content).toContain('pattern: /^1[3-9]\\d{9}$/')
    expect(content).toContain("message: '请输入正确的手机号'")
  })

  it('requires password', () => {
    expect(content).toContain("password: { required: true, message: '请输入密码'")
  })

  it('has phone field with maxlength 11', () => {
    expect(content).toContain('maxlength="11"')
  })
})

describe('ParentLogin error handling', () => {
  it('handles 401/400 status with specific message', () => {
    expect(content).toContain('err.response?.status === 401')
    expect(content).toContain('err.response?.status === 400')
    expect(content).toContain("'手机号或密码错误，请重试'")
  })

  it('handles generic errors', () => {
    expect(content).toContain("'登录失败，请稍后重试'")
  })

  it('wraps login in try-catch with finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleLogin'),
      content.indexOf('</script>')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('loading.value = false')
  })

  it('reads remembered phone on mount', () => {
    expect(content).toContain("const REMEMBER_KEY = 'parent_remembered_phone'")
    expect(content).toContain('localStorage.getItem(REMEMBER_KEY)')
  })

  it('handles remember phone save/remove logic', () => {
    expect(content).toContain('localStorage.setItem(REMEMBER_KEY, form.value.phone)')
    expect(content).toContain('localStorage.removeItem(REMEMBER_KEY)')
  })
})
