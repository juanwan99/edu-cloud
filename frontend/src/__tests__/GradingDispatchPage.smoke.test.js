/**
 * F004 回归: GradingDispatchPage 真实 import smoke test。
 *
 * router.test.js 会 stub 懒加载组件，无法发现组件本体错误。
 * 这个测试真实 import GradingDispatchPage.vue 和 ExamDetailPage.vue，
 * 验证：
 *   1. GradingDispatchPage 组件可挂载（无 import/语法错误）
 *   2. ExamDetailPage 模板中不再包含扫描 tab 相关标记
 */
import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

describe('GradingDispatchPage smoke', () => {
  it('GradingDispatchPage.vue can be imported', async () => {
    // 真实 import — 若 .vue 文件有语法/import 错误，此处抛异常
    // 全量跑时 Naive UI 初始化较慢，放宽超时
    const mod = await import('../pages/GradingDispatchPage.vue')
    expect(mod.default).toBeTruthy()
    // Vue SFC 默认导出应为组件对象/函数
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ExamDetailPage scan tab removal (F004)', () => {
  it('ExamDetailPage.vue template no longer contains scan tab', () => {
    const examDetailPath = resolve(__dirname, '../pages/ExamDetailPage.vue')
    const content = readFileSync(examDetailPath, 'utf-8')

    // 反例: 如果扫描 tab 未移除，以下标记仍会存在
    expect(content).not.toMatch(/<n-tab-pane\s+name="scan"/)
    expect(content).not.toContain('scanRootDir')
    expect(content).not.toContain('scanFoundSubjects')
    expect(content).not.toContain('handleStartPipeline')
    expect(content).not.toContain("from '../api/scan'")
  })
})
