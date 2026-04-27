/**
 * ParentBind.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains 3-step binding flow
 *  3. API call uses bindChild
 *  4. Form fields and validation
 *  5. Error handling and countdown navigation
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentBind.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentBind smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentBind.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentBind template sections', () => {
  it('has 3-step indicator', () => {
    expect(content).toContain(':current="step"')
    expect(content).toContain('<n-step title="填写信息" />')
    expect(content).toContain('<n-step title="验证" />')
    expect(content).toContain('<n-step title="完成" />')
  })

  it('has student name input field', () => {
    expect(content).toContain('v-model:value="form.student_name"')
    expect(content).toContain('请输入孩子姓名')
  })

  it('has verify code input field', () => {
    expect(content).toContain('v-model:value="form.verify_code"')
    expect(content).toContain(':label="verifyLabel"')
    expect(content).toContain(':placeholder="verifyPlaceholder"')
  })

  it('has relationship grid selector', () => {
    expect(content).toContain('class="relationship-grid"')
    expect(content).toContain('v-for="opt in relationshipOptions"')
    expect(content).toContain('@click="form.relationship = opt.value"')
  })

  it('has success area at step 3', () => {
    expect(content).toContain('v-if="step === 3"')
    expect(content).toContain('class="success-area"')
    expect(content).toContain('绑定成功')
    expect(content).toContain('{{ boundChildName }}')
    expect(content).toContain('{{ countdown }} 秒后跳转概览...')
  })

  it('has step navigation buttons', () => {
    expect(content).toContain("step === 1 ? '下一步' : '确认绑定'")
    expect(content).toContain('上一步')
  })

  it('shows existing bound children alert', () => {
    expect(content).toContain('v-if="existingCount > 0 && step === 1"')
    expect(content).toContain('是否继续绑定新孩子？')
  })
})

describe('ParentBind API calls', () => {
  it('imports bindChild from conduct API', () => {
    expect(content).toContain("import { bindChild } from '../../api/conduct'")
  })

  it('calls bindChild with form data', () => {
    expect(content).toContain('await bindChild(form.value)')
  })

  it('navigates to /parent after countdown', () => {
    expect(content).toContain("router.push('/parent')")
  })
})

describe('ParentBind form and validation', () => {
  it('requires student name', () => {
    expect(content).toContain("student_name: { required: true, message: '请输入学生姓名'")
  })

  it('requires verify code', () => {
    expect(content).toContain("verify_code: { required: true, message: '请输入验证信息'")
  })

  it('requires relationship', () => {
    expect(content).toContain("relationship: { required: true, message: '请选择关系'")
  })

  it('defines 5 relationship options with icons', () => {
    expect(content).toContain("{ label: '父亲', value: 'father', icon: '👨' }")
    expect(content).toContain("{ label: '母亲', value: 'mother', icon: '👩' }")
    expect(content).toContain("{ label: '祖父', value: 'grandfather', icon: '👴' }")
    expect(content).toContain("{ label: '祖母', value: 'grandmother', icon: '👵' }")
    expect(content).toContain("{ label: '其他', value: 'other', icon: '👤' }")
  })

  it('supports multiple verify code types', () => {
    expect(content).toContain("id_last6: '身份证后6位'")
    expect(content).toContain("phone: '手机号'")
    expect(content).toContain("code: '验证码'")
  })

  it('has verify hints for each type', () => {
    expect(content).toContain("id_last6: '请输入学生身份证号码的最后6位数字用于验证身份'")
    expect(content).toContain("phone: '请输入注册时使用的家长手机号码'")
    expect(content).toContain("code: '请输入学校或班主任提供的验证码'")
  })
})

describe('ParentBind error handling', () => {
  it('handles bind failure error', () => {
    expect(content).toContain("window.$message?.error(err.response?.data?.detail || '绑定失败')")
  })

  it('wraps handleBind in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleBind'),
      content.indexOf('function startCountdown')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('loading.value = false')
  })

  it('cleans up countdown timer on unmount', () => {
    expect(content).toContain('onUnmounted(() => {')
    expect(content).toContain('clearInterval(countdownTimer)')
  })

  it('injects children from ParentLayout', () => {
    expect(content).toContain("const childrenInjected = inject('children', ref([]))")
  })
})
