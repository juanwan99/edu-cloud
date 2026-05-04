import { describe, it, expect } from 'vitest'
import { getSidebarGroups } from '../config/sidebarConfig.js'

describe('AppSidebar conduct 入口级渲染', () => {
  it('academic_director 侧边栏 conduct 段渲染 2 项', () => {
    const groups = getSidebarGroups('academic_director', ['conduct'])
    const studentGroup = groups.find(g => g.key === 'student')
    const conductItems = studentGroup.children.filter(c => c.moduleCode === 'conduct')
    expect(conductItems.length).toBe(2)
  })
})
