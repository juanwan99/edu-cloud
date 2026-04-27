/**
 * ConductGroups source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (group cards, create modal, detail drawer, add member)
 *  3. API calls via conduct.js (getGroups, createGroup, deleteGroup, addGroupMembers, removeGroupMember)
 *  4. CRUD operations (create, delete groups; add, remove members)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductGroups.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductGroups smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductGroups.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductGroups template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('title="小组管理"')
    expect(content).toContain('创建和管理班级小组')
  })

  it('contains create group button in header', () => {
    expect(content).toContain('@click="openCreateGroup"')
    expect(content).toContain('创建小组')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains group cards in a 3-column grid', () => {
    expect(content).toContain(':cols="3"')
    expect(content).toContain('v-for="group in groups"')
    expect(content).toContain(':title="group.name"')
    expect(content).toContain('hoverable')
  })

  it('shows member count and member name tags', () => {
    expect(content).toContain('名成员')
    expect(content).toContain('v-for="m in group.members"')
    expect(content).toContain('m.student_name')
  })

  it('contains manage members and delete buttons per group', () => {
    expect(content).toContain('管理成员')
    expect(content).toContain('@click="openGroupDetail(group)"')
    expect(content).toContain('@positive-click="handleDeleteGroup(group.id)"')
  })

  it('contains create group modal with name input', () => {
    expect(content).toContain('v-model:show="showCreateModal"')
    expect(content).toContain('title="创建小组"')
    expect(content).toContain('v-model:value="createForm.name"')
    expect(content).toContain("placeholder=\"例：第一组\"")
  })

  it('contains detail drawer with member list', () => {
    expect(content).toContain('v-model:show="showDetailDrawer"')
    expect(content).toContain(':width="400"')
    expect(content).toContain("detailGroup?.name || '小组详情'")
    expect(content).toContain('v-for="m in detailGroup.members"')
  })

  it('contains add member section with student select', () => {
    expect(content).toContain('v-if="showAddMember"')
    expect(content).toContain('添加成员')
    expect(content).toContain('v-model:value="newMemberIds"')
    expect(content).toContain(':options="availableStudents"')
    expect(content).toContain('确认添加')
  })

  it('contains remove member confirmation', () => {
    expect(content).toContain('@positive-click="handleRemoveMember(m.student_id)"')
    expect(content).toContain('移除')
  })
})

describe('ConductGroups API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getGroups')
    expect(content).toContain('createGroup')
    expect(content).toContain('deleteGroup')
    expect(content).toContain('addGroupMembers')
    expect(content).toContain('removeGroupMember')
    expect(content).toContain('getStudentRankings')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getGroups to load groups', () => {
    expect(content).toContain('getGroups(classId.value)')
  })

  it('calls createGroup with form data', () => {
    expect(content).toContain('createGroup(classId.value, createForm.value)')
  })

  it('calls deleteGroup with group ID', () => {
    expect(content).toContain('deleteGroup(classId.value, groupId)')
  })

  it('calls addGroupMembers with student IDs', () => {
    expect(content).toContain('addGroupMembers(classId.value, detailGroup.value.id, {')
    expect(content).toContain('student_ids: newMemberIds.value')
  })

  it('calls removeGroupMember with student ID', () => {
    expect(content).toContain('removeGroupMember(classId.value, detailGroup.value.id, studentId)')
  })

  it('calls getStudentRankings to get available students', () => {
    expect(content).toContain('getStudentRankings(classId.value, {})')
  })
})

describe('ConductGroups CRUD operations', () => {
  it('validates group name before creation', () => {
    expect(content).toContain("createForm.value.name.trim()")
    expect(content).toContain("请输入小组名称")
  })

  it('shows success message after group creation', () => {
    expect(content).toContain("message.success('小组已创建')")
  })

  it('shows success message after group deletion', () => {
    expect(content).toContain("message.success('小组已删除')")
  })

  it('shows success message after member addition', () => {
    expect(content).toContain("message.success('成员已添加')")
  })

  it('shows success message after member removal', () => {
    expect(content).toContain("message.success('成员已移除')")
  })

  it('reloads groups after each mutation', () => {
    // After create, delete, add members, remove members
    const loadGroupsCalls = (content.match(/await loadGroups\(\)/g) || []).length
    expect(loadGroupsCalls).toBeGreaterThanOrEqual(4)
  })

  it('refreshes detail group after member changes', () => {
    expect(content).toContain('groups.value.find(g => g.id === detailGroup.value.id)')
  })

  it('loads groups and students on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadGroups()')
    expect(content).toContain('loadAllStudents()')
  })
})

describe('ConductGroups error handling', () => {
  it('wraps loadGroups in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadGroups'),
      content.indexOf('async function loadAllStudents')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadAllStudents in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadAllStudents'),
      content.indexOf('function openCreateGroup')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps handleCreateGroup in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleCreateGroup'),
      content.indexOf('async function handleDeleteGroup')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('wraps handleDeleteGroup in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleDeleteGroup'),
      content.indexOf('function openGroupDetail')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '删除失败'")
  })

  it('wraps handleAddMembers in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleAddMembers'),
      content.indexOf('async function handleRemoveMember')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '添加失败'")
  })

  it('wraps handleRemoveMember in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleRemoveMember'),
      content.indexOf('onMounted(')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '移除失败'")
  })
})
