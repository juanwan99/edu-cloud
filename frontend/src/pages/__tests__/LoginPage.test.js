/**
 * LoginPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains expected UI sections (brand, tabs, form, success overlay)
 *  3. Form validation rules are defined
 *  4. Auth store integration (login call)
 *  5. Error handling for 401/400/generic failures
 *  6. Remember-username localStorage logic
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../LoginPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('LoginPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../LoginPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('LoginPage template sections', () => {
  it('contains brand area with name and subtitle', () => {
    expect(content).toContain('class="brand-area"')
    expect(content).toContain('class="brand-name"')
    expect(content).toContain('edu-cloud')
    expect(content).toContain('class="brand-subtitle"')
  })

  it('contains login tabs for teacher and admin', () => {
    expect(content).toContain('class="login-tabs"')
    expect(content).toContain("name=\"teacher\"")
    expect(content).toContain("name=\"admin\"")
    expect(content).toContain('tab="教师登录"')
    expect(content).toContain('tab="管理员登录"')
  })

  it('contains login form with username and password inputs', () => {
    expect(content).toContain('class="login-form-area"')
    expect(content).toContain('v-model:value="form.username"')
    expect(content).toContain('v-model:value="form.password"')
    expect(content).toContain('placeholder="请输入用户名…"')
    expect(content).toContain('placeholder="请输入密码…"')
  })

  it('contains remember-username checkbox', () => {
    expect(content).toContain('v-model:checked="rememberUsername"')
    expect(content).toContain('记住用户名')
  })

  it('contains login button with loading state', () => {
    expect(content).toContain('class="login-btn"')
    expect(content).toContain(':loading="loading"')
    expect(content).toContain("'登录中...'")
    expect(content).toContain("'登 录'")
  })

  it('contains success overlay', () => {
    expect(content).toContain('class="success-overlay"')
    expect(content).toContain('class="success-check"')
    expect(content).toContain('class="success-text"')
    expect(content).toContain('登录成功')
  })

  it('contains error alert', () => {
    expect(content).toContain('v-if="error"')
    expect(content).toContain('type="error"')
    expect(content).toContain('closable')
  })

  it('contains login hint for password reset', () => {
    expect(content).toContain('class="login-hint"')
    expect(content).toContain('忘记密码？请联系管理员重置')
  })

  it('contains decorative elements', () => {
    expect(content).toContain('class="decor decor--mint"')
    expect(content).toContain('class="decor decor--cream"')
    expect(content).toContain('class="decor decor--pink-ring"')
    expect(content).toContain('class="decor decor--lavender"')
  })
})

describe('LoginPage form validation rules', () => {
  it('requires username with blur trigger', () => {
    expect(content).toContain("username: { required: true, message: '请输入用户名', trigger: 'blur' }")
  })

  it('requires password with blur trigger', () => {
    expect(content).toContain("password: { required: true, message: '请输入密码', trigger: 'blur' }")
  })
})

describe('LoginPage auth store integration', () => {
  it('imports and uses auth store', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
    expect(content).toContain('const authStore = useAuthStore()')
  })

  it('calls authStore.login with username and password', () => {
    expect(content).toContain('await authStore.login(form.value.username, form.value.password)')
  })

  it('validates form before login', () => {
    expect(content).toContain('await formRef.value?.validate()')
  })
})

describe('LoginPage error handling', () => {
  it('handles 401 and 400 status as credential error', () => {
    expect(content).toContain('e.response?.status === 401')
    expect(content).toContain('e.response?.status === 400')
    expect(content).toContain("'用户名或密码错误'")
  })

  it('handles generic login failure', () => {
    expect(content).toContain("'登录失败，请稍后重试'")
  })

  it('extracts detail from error response', () => {
    expect(content).toContain('e.response?.data?.detail')
  })

  it('wraps handleLogin in try-catch with finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleLogin'),
      content.indexOf('</script>')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('loading.value = false')
  })
})

describe('LoginPage remember username', () => {
  it('defines REMEMBER_KEY constant', () => {
    expect(content).toContain("const REMEMBER_KEY = 'edu_remembered_username'")
  })

  it('loads saved username on mount', () => {
    expect(content).toContain('localStorage.getItem(REMEMBER_KEY)')
    expect(content).toContain('form.value.username = saved')
    expect(content).toContain('rememberUsername.value = true')
  })

  it('saves username when remember is checked', () => {
    expect(content).toContain('localStorage.setItem(REMEMBER_KEY, form.value.username)')
  })

  it('removes saved username when remember is unchecked', () => {
    expect(content).toContain('localStorage.removeItem(REMEMBER_KEY)')
  })
})
