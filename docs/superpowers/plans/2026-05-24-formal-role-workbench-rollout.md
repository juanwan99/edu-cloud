# Formal Role Workbench Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the role-specific workbench model from preview into the formal site so `/`, sidebar navigation, and role switching all follow the current active identity instead of exposing every permitted feature.

**Architecture:** Keep backend RBAC and `auth.checkPermission()` as the security truth. Add a front-end role workbench layer that decides what should be visible for the current identity, then reuse it from the formal dashboard, sidebar, and role switcher safety path. Multi-identity users keep one active identity at a time; overlapping work appears only as a summary or requires switching identity first.

**Tech Stack:** Vue 3, Pinia, Vue Router, Naive UI, existing `workbenchProfiles.js`, existing `auth.currentRoleIndex`, existing `permissions.js`, Vitest, Vite build.

---

## Product Decision

当前策略固定为：**不合并多身份功能，不做一个“超级教师首页”。**

- 当前激活身份决定首页、侧栏、快捷入口、待办主线。
- 权限只回答“能不能访问”，工作台回答“此身份默认应不应该展示”。
- 校管理员的首页主线是学校运行治理，不是个人教学闭环。
- 如果一个人同时是校管理员、班主任、科任教师，默认页面只展示当前身份；其他身份通过右上角切换。
- 切换身份后，如果当前路由不属于新身份工作流，应回到 `/`，避免用户停留在不合适的页面。

---

## File Structure

### Create

- `frontend/src/config/routeAccess.js`
  - Central route permission/module requirements used by dashboard and role switch safety.
- `frontend/src/__tests__/routeAccess.test.js`
  - Verifies route requirement behavior without mounting pages.
- `frontend/src/__tests__/sidebarConfig.rolePolicy.test.js`
  - Verifies each role sees a role-appropriate sidebar, not every permitted item.

### Modify

- `frontend/src/stores/auth.js`
  - Use `chooseDefaultRoleIndex()` on login and return success/failure from `switchRole()`.
- `frontend/src/__tests__/auth-store.test.js`
  - Cover default role selection and switch result.
- `frontend/src/config/sidebarConfig.js`
  - Add role-level sidebar policy on top of existing permission/module filtering.
- `frontend/src/pages/DashboardPage.vue`
  - Replace teacher-biased action panels with role-aware workbench panels.
  - Import route access from `routeAccess.js`.
- `frontend/src/pages/__tests__/DashboardPage.test.js`
  - Assert school admin formal dashboard does not retain teacher-only action copy.
- `frontend/src/components/shell/RoleSwitcher.vue`
  - After successful role switch, redirect to `/` when current route no longer belongs to the new active identity.

---

## Task 1: Make Active Identity Selection Explicit

**Files:**
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/__tests__/auth-store.test.js`

- [ ] **Step 1: Add failing tests for login default role selection**

Add these tests under `describe('auth store login()', ...)` in `frontend/src/__tests__/auth-store.test.js`:

```js
  it('login prefers highest-priority admin identity when no primary role exists', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-admin',
        user: { id: 'u3', display_name: 'Chen' },
        roles: [
          { id: 'r1', role: 'subject_teacher', is_primary: false, context: null },
          { id: 'r2', role: 'school_admin', is_primary: false, context: { type: 'school', name: '育才实验中学' } },
        ],
      },
    })
    const store = useAuthStore()
    await store.login('chen', 'pass')
    expect(store.currentRoleIndex).toBe(1)
    expect(store.currentRole.role).toBe('school_admin')
  })

  it('login still respects backend primary role over local priority', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-primary',
        user: { id: 'u4', display_name: 'Gao' },
        roles: [
          { id: 'r1', role: 'school_admin', is_primary: false, context: null },
          { id: 'r2', role: 'subject_teacher', is_primary: true, context: null },
        ],
      },
    })
    const store = useAuthStore()
    await store.login('gao', 'pass')
    expect(store.currentRoleIndex).toBe(1)
    expect(store.currentRole.role).toBe('subject_teacher')
  })
```

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/auth-store.test.js
```

Expected: FAIL because `auth.js` still implements role selection inline.

- [ ] **Step 2: Use the shared role selector in auth store**

In `frontend/src/stores/auth.js`, update the import:

```js
import { chooseDefaultRoleIndex } from '../config/identityRouting.js'
```

Then replace the login role selection block:

```js
    roles.value = data.roles
    currentRoleIndex.value = chooseDefaultRoleIndex(roles.value)
```

Do not remove the existing `chooseDefaultRoleIndex()` primary-role behavior; it already preserves backend `is_primary`.

- [ ] **Step 3: Return switch success from `switchRole()`**

Change `switchRole()` so callers can safely redirect only after a real switch:

```js
  async function switchRole(index) {
    const oldIndex = currentRoleIndex.value
    const roleId = roles.value[index]?.id
    if (roleId) {
      try {
        const { data } = await client.post('/auth/switch-role', { role_id: roleId })
        currentRoleIndex.value = index
        token.value = data.access_token
        localStorage.setItem('token', data.access_token)
      } catch {
        currentRoleIndex.value = oldIndex
        return false
      }
    } else {
      currentRoleIndex.value = index
    }
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
    await loadModules()
    return true
  }
```

- [ ] **Step 4: Add switch result tests**

In `frontend/src/__tests__/auth-store.test.js`, update the existing switch tests:

```js
    const ok = await store.switchRole(1)
    expect(ok).toBe(true)
```

and:

```js
    const ok = await store.switchRole(1)
    expect(ok).toBe(false)
```

- [ ] **Step 5: Verify**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/identityRouting.test.js src/__tests__/auth-store.test.js
```

Expected: PASS.

---

## Task 2: Centralize Route Access Rules

**Files:**
- Create: `frontend/src/config/routeAccess.js`
- Create: `frontend/src/__tests__/routeAccess.test.js`
- Modify: `frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: Add route access tests**

Create `frontend/src/__tests__/routeAccess.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { getRouteAccessRequirement, canAccessRouteForRole } from '../config/routeAccess.js'

describe('route access requirements', () => {
  it('guards school settings with school config permission', () => {
    expect(getRouteAccessRequirement('/school-settings')).toEqual({
      permission: 'manage_school_config',
    })
  })

  it('guards grading dispatch separately from personal marking', () => {
    expect(getRouteAccessRequirement('/grading/tasks')).toEqual({
      permission: 'manage_grading',
      moduleCode: 'grading',
    })
    expect(getRouteAccessRequirement('/marking')).toEqual({
      permission: 'view_grading',
      moduleCode: 'grading',
    })
  })

  it('allows school admin into school settings but not parent', () => {
    expect(canAccessRouteForRole('school_admin', '/school-settings', [])).toBe(true)
    expect(canAccessRouteForRole('parent', '/school-settings', [])).toBe(false)
  })

  it('requires enabled module when module list is loaded', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', ['exam'])).toBe(false)
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', ['grading'])).toBe(true)
  })

  it('treats empty enabledModules as no module filter', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', [])).toBe(true)
  })
})
```

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/routeAccess.test.js
```

Expected: FAIL because the file does not exist.

- [ ] **Step 2: Create route access config**

Create `frontend/src/config/routeAccess.js`:

```js
import { hasPermission } from './permissions.js'
import { normalizeRole } from './roles.js'

export const ROUTE_ACCESS_REQUIREMENTS = {
  '/exams': { permission: 'view_exams', moduleCode: 'exam' },
  '/exam-import': { permission: 'import_exams', moduleCode: 'exam' },
  '/marking': { permission: 'view_grading', moduleCode: 'grading' },
  '/grading/tasks': { permission: 'manage_grading', moduleCode: 'grading' },
  '/ai-grading': { permission: 'manage_grading', moduleCode: 'grading' },
  '/analytics/report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/analytics/ai-report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/homework': { permission: ['view_homework', 'manage_homework'], moduleCode: 'homework' },
  '/question-bank': { permission: 'view_question_bank' },
  '/knowledge-tree': { permission: 'view_knowledge_tree' },
  '/students': { permission: ['view_students', 'manage_scheduling'] },
  '/conduct': { permission: 'view_conduct', moduleCode: 'conduct' },
  '/joint-exams': { permission: 'view_joint_exam' },
  '/school-settings': { permission: 'manage_school_config' },
  '/academic/teaching-plans': { permission: 'manage_scheduling' },
  '/academic/timetable': { permission: 'manage_scheduling' },
  '/academic/semesters': { permission: 'manage_scheduling' },
  '/assignments': { permission: 'manage_scheduling' },
  '/teachers': { permission: ['manage_scheduling', 'manage_school_config'] },
  '/calendar': { moduleCode: 'calendar' },
}

export function getRouteAccessRequirement(route) {
  return ROUTE_ACCESS_REQUIREMENTS[route] || null
}

export function permissionMatches(role, permission) {
  if (!permission) return true
  const normalized = normalizeRole(role)
  const required = Array.isArray(permission) ? permission : [permission]
  return required.some(perm => hasPermission(normalized, perm))
}

export function moduleMatches(moduleCode, enabledModules = []) {
  if (!moduleCode) return true
  if (!enabledModules || enabledModules.length === 0) return true
  return enabledModules.includes(moduleCode)
}

export function canAccessRequirementForRole(role, requirement, enabledModules = []) {
  if (!requirement) return true
  return permissionMatches(role, requirement.permission) && moduleMatches(requirement.moduleCode, enabledModules)
}

export function canAccessRouteForRole(role, route, enabledModules = []) {
  return canAccessRequirementForRole(role, getRouteAccessRequirement(route), enabledModules)
}
```

- [ ] **Step 3: Make `DashboardPage.vue` consume route access config**

In `frontend/src/pages/DashboardPage.vue`, add:

```js
import {
  ROUTE_ACCESS_REQUIREMENTS,
  canAccessRequirementForRole,
} from '../config/routeAccess.js'
```

Replace the local `routeAccessRequirements` object with:

```js
const routeAccessRequirements = ROUTE_ACCESS_REQUIREMENTS
```

Replace `canAccess(item)`:

```js
function canAccess(item) {
  return canAccessRequirementForRole(role.value, item, auth.modulesLoaded ? auth.enabledModules : [])
}
```

Keep `canAccessRoute(route)` as:

```js
function canAccessRoute(route) {
  const requirement = routeAccessRequirements[route]
  return requirement ? canAccess(requirement) : true
}
```

- [ ] **Step 4: Verify**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/routeAccess.test.js src/pages/__tests__/DashboardPage.test.js
```

Expected: PASS.

---

## Task 3: Add Role-Aware Sidebar Policy

**Files:**
- Modify: `frontend/src/config/sidebarConfig.js`
- Create: `frontend/src/__tests__/sidebarConfig.rolePolicy.test.js`
- Modify: `frontend/src/__tests__/config.test.js`

- [ ] **Step 1: Add failing sidebar policy tests**

Create `frontend/src/__tests__/sidebarConfig.rolePolicy.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { getSidebarGroups, getSidebarItems } from '../config/sidebarConfig.js'

const routesFor = (role, modules = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'conduct']) =>
  getSidebarItems(role, modules).map(item => item.route)

describe('role-aware sidebar policy', () => {
  it('school admin starts from school operation and hides personal teaching entries', () => {
    const groups = getSidebarGroups('school_admin', ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'conduct'])
    expect(groups.map(group => group.key).slice(0, 2)).toEqual(['school', 'academic'])
    const routes = routesFor('school_admin')
    expect(routes).toContain('/school-settings')
    expect(routes).toContain('/assignments')
    expect(routes).toContain('/grading/tasks')
    expect(routes).not.toContain('/marking')
    expect(routes).not.toContain('/homework')
    expect(routes).not.toContain('/question-bank')
    expect(routes).not.toContain('/knowledge-tree')
  })

  it('lesson prep leader sees subject organization but not school administration', () => {
    const routes = routesFor('lesson_prep_leader')
    expect(routes).toContain('/exams')
    expect(routes).toContain('/grading/tasks')
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/question-bank')
    expect(routes).not.toContain('/school-settings')
    expect(routes).not.toContain('/assignments')
    expect(routes).not.toContain('/conduct')
  })

  it('homeroom teacher sees class and conduct work but not school configuration', () => {
    const routes = routesFor('homeroom_teacher')
    expect(routes).toContain('/students')
    expect(routes).toContain('/conduct')
    expect(routes).toContain('/homework')
    expect(routes).not.toContain('/school-settings')
    expect(routes).not.toContain('/academic/timetable')
  })

  it('subject teacher sees personal teaching flow and no dispatch entry', () => {
    const routes = routesFor('subject_teacher')
    expect(routes).toContain('/exams')
    expect(routes).toContain('/marking')
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/homework')
    expect(routes).not.toContain('/grading/tasks')
    expect(routes).not.toContain('/school-settings')
  })
})
```

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/sidebarConfig.rolePolicy.test.js
```

Expected: FAIL because sidebar still only filters by permission/module.

- [ ] **Step 2: Add role sidebar policy**

In `frontend/src/config/sidebarConfig.js`, add after `SIDEBAR_GROUPS`:

```js
const ROLE_SIDEBAR_POLICY = {
  platform_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
  },
  district_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
  },
  school_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
  },
  principal: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
  },
  academic_director: {
    groups: ['academic', 'exam', 'student', 'school', 'research'],
    hiddenRoutes: ['/marking', '/error-book'],
  },
  teaching_research_leader: {
    groups: ['research', 'exam'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct'],
  },
  grade_leader: {
    groups: ['student', 'exam', 'school'],
    hiddenRoutes: ['/marking', '/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/question-bank', '/knowledge-tree'],
  },
  lesson_prep_leader: {
    groups: ['exam', 'research'],
    hiddenRoutes: ['/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
  },
  homeroom_teacher: {
    groups: ['student', 'exam', 'research'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/academic/timetable', '/academic/semesters'],
  },
  subject_teacher: {
    groups: ['exam', 'research'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
  },
  parent: {
    groups: ['student', 'research'],
    hiddenRoutes: ['/exams', '/exam-import', '/grading/tasks', '/ai-grading', '/marking', '/school-settings', '/assignments', '/teachers'],
  },
}
```

Add helper functions:

```js
function policyFor(role) {
  return ROLE_SIDEBAR_POLICY[role] || null
}

function applyRolePolicy(role, groups) {
  const policy = policyFor(role)
  if (!policy) return groups
  const groupRank = new Map(policy.groups.map((key, index) => [key, index]))
  const hiddenRoutes = new Set(policy.hiddenRoutes || [])
  return groups
    .filter(group => groupRank.has(group.key))
    .map(group => ({
      ...group,
      children: group.children.filter(item => !hiddenRoutes.has(item.route)),
    }))
    .filter(group => group.children.length > 0)
    .sort((a, b) => groupRank.get(a.key) - groupRank.get(b.key))
}
```

Then update `getSidebarGroups()`:

```js
export function getSidebarGroups(role, enabledModules = []) {
  const enabled = new Set(enabledModules)
  const permissionFiltered = SIDEBAR_GROUPS
    .map(group => {
      const visibleChildren = group.children.filter(item => {
        if (item.perm && !hasPermission(role, item.perm)) return false
        if (item.moduleCode && enabled.size > 0 && !enabled.has(item.moduleCode)) return false
        return true
      })
      if (visibleChildren.length === 0) return null
      return { ...group, children: visibleChildren }
    })
    .filter(Boolean)
  return applyRolePolicy(role, permissionFiltered)
}
```

Update `getSidebarItems()` signature:

```js
export function getSidebarItems(role, enabledModules = []) {
  const groups = getSidebarGroups(role, enabledModules)
```

- [ ] **Step 3: Adjust broad config test**

In `frontend/src/__tests__/config.test.js`, keep the existing canonical role smoke test but call:

```js
const items = getSidebarItems(role, ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'conduct'])
```

- [ ] **Step 4: Verify**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/sidebarConfig.rolePolicy.test.js src/__tests__/sidebarConfig.conduct.test.js src/__tests__/config.test.js src/__tests__/AppSidebar.test.js
```

Expected: PASS. If `sidebarConfig.conduct.test.js` now conflicts with the intended policy, update it to assert the new role policy instead of the old permission-only behavior.

---

## Task 4: Make Formal Dashboard Role-First

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue`
- Modify: `frontend/src/pages/__tests__/DashboardPage.test.js`
- Modify: `frontend/src/__tests__/workbenchProfiles.test.js`

- [ ] **Step 1: Add failing tests for school admin formal dashboard copy**

In `frontend/src/pages/__tests__/DashboardPage.test.js`, add:

```js
describe('DashboardPage role-first formal workbench', () => {
  it('defines a school governance panel instead of a teacher report action panel for school admin', () => {
    expect(content).toContain('const roleActionPanel = computed')
    expect(content).toContain('运行治理中心')
    expect(content).toContain('学校配置、人员关系、考试流程和数据权限')
  })

  it('uses workbench profile priorities for today actions', () => {
    expect(content).toContain('workbenchProfile.value.priorities')
    expect(content).toContain('profilePriorityActions')
  })

  it('does not hard-code teacher-only report copy as the only second panel', () => {
    expect(content).not.toContain('报告不再只是查看结果，而是讲评和巩固的入口')
  })
})
```

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/pages/__tests__/DashboardPage.test.js
```

Expected: FAIL.

- [ ] **Step 2: Use profile priorities for the left action panel**

In `DashboardPage.vue`, replace the `priorityActions` computed block with:

```js
const profilePriorityActions = computed(() =>
  workbenchProfile.value.priorities
    .filter(action => canAccessRoute(action.route))
    .map(action => ({
      ...action,
      tag: action.meta,
      tagType: action.tone === 'orange' ? 'warning' : action.tone === 'yellow' ? 'success' : 'default',
    })),
)

const priorityActions = computed(() => profilePriorityActions.value)
```

This keeps the template stable while making the content role-first.

- [ ] **Step 3: Replace hard-coded report panel with role action panel**

Add this computed below `reportActionItems`:

```js
const roleActionPanel = computed(() => {
  const adminRoles = new Set(['platform_admin', 'district_admin', 'school_admin', 'principal'])
  if (adminRoles.has(role.value)) {
    return {
      title: '运行治理中心',
      sub: '学校配置、人员关系、考试流程和数据权限',
      actionLabel: '进入学校配置 →',
      actionRoute: '/school-settings',
      items: workbenchProfile.value.modules
        .flatMap(group => group.items.map(item => ({
          label: group.title.slice(0, 2),
          title: item.title,
          desc: item.desc,
          route: item.route,
          tone: item.route.includes('school') ? 'yellow' : item.route.includes('assignments') || item.route.includes('teachers') ? 'purple' : 'coral',
        })))
        .filter(item => canAccessRoute(item.route))
        .slice(0, 4),
    }
  }

  return {
    title: '报告行动中心',
    sub: '报告承接讲评、巩固和资源沉淀',
    actionLabel: '进入分析 →',
    actionRoute: '/analytics/report',
    items: reportActionItems.value,
  }
})
```

Update template `report-action-panel` header:

```vue
<div class="card-title">{{ roleActionPanel.title }}</div>
<div class="card-sub">{{ roleActionPanel.sub }}</div>
```

Update button:

```vue
<n-button text type="primary" @click="router.push(roleActionPanel.actionRoute)">
  {{ roleActionPanel.actionLabel }}
</n-button>
```

Update item loop:

```vue
v-for="item in roleActionPanel.items"
```

- [ ] **Step 4: Prevent empty right panel**

Wrap the right panel:

```vue
<article v-if="roleActionPanel.items.length > 0" class="card report-action-panel">
```

- [ ] **Step 5: Verify**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/pages/__tests__/DashboardPage.test.js src/__tests__/workbenchProfiles.test.js
```

Expected: PASS.

---

## Task 5: Make Role Switching Route-Safe

**Files:**
- Modify: `frontend/src/components/shell/RoleSwitcher.vue`
- Modify: `frontend/src/__tests__/AppSidebar.test.js` if sidebar mocks need updating
- Create or modify: `frontend/src/__tests__/RoleSwitcher.test.js`

- [ ] **Step 1: Add role switcher route safety test**

If `frontend/src/__tests__/RoleSwitcher.test.js` does not exist, create it:

```js
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import RoleSwitcher from '../components/shell/RoleSwitcher.vue'

const push = vi.fn()
const route = reactive({ path: '/marking' })
const switchRole = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => route,
}))

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => ({
    displayName: '高睿皓',
    roles: [
      { id: 'r1', role: 'subject_teacher', context: { name: '育才实验中学' } },
      { id: 'r2', role: 'school_admin', context: { name: '育才实验中学' } },
    ],
    currentRoleIndex: 0,
    currentRole: { id: 'r1', role: 'subject_teacher', context: { name: '育才实验中学' } },
    currentContext: { name: '育才实验中学' },
    switchRole,
    logout: vi.fn(),
  }),
}))

vi.mock('naive-ui', () => ({
  NDropdown: {
    template: '<div><slot /></div>',
    props: ['options', 'value'],
  },
  NTag: {
    template: '<span><slot /></span>',
  },
}))

describe('RoleSwitcher route safety', () => {
  it('returns to dashboard after switching identity away from a personal-only route', async () => {
    switchRole.mockResolvedValueOnce(true)
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })
    await wrapper.vm.handleSwitch?.(1)
    expect(push).toHaveBeenCalledWith('/')
  })
})
```

If `<script setup>` prevents direct method access, expose the method for tests with:

```js
defineExpose({ handleSwitch })
```

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/RoleSwitcher.test.js
```

Expected: FAIL until route safety is implemented.

- [ ] **Step 2: Implement route safety in `RoleSwitcher.vue`**

Add imports:

```js
import { useRoute, useRouter } from 'vue-router'
import { canAccessRouteForRole } from '../../config/routeAccess.js'
```

Add:

```js
const route = useRoute()
const router = useRouter()
```

Update `handleSwitch()`:

```js
async function handleSwitch(key) {
  if (key === 'logout') {
    auth.logout()
    return
  }
  if (key === 'header' || key === 'divider') return
  if (typeof key === 'number' && key !== auth.currentRoleIndex) {
    const targetRole = auth.roles[key]?.role
    const switched = await auth.switchRole(key)
    if (!switched) return
    const enabledModules = auth.modulesLoaded ? auth.enabledModules : []
    if (targetRole && !canAccessRouteForRole(normalizeRole(targetRole), route.path, enabledModules)) {
      router.push('/')
    }
  }
}
```

Add:

```js
defineExpose({ handleSwitch })
```

- [ ] **Step 3: Verify**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/RoleSwitcher.test.js src/__tests__/auth-store.test.js
```

Expected: PASS.

---

## Task 6: Full Focused Verification and Browser Check

**Files:**
- No new files unless a visual regression is found.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- \
  src/__tests__/identityRouting.test.js \
  src/__tests__/auth-store.test.js \
  src/__tests__/routeAccess.test.js \
  src/__tests__/workbenchProfiles.test.js \
  src/__tests__/sidebarConfig.rolePolicy.test.js \
  src/__tests__/sidebarConfig.conduct.test.js \
  src/__tests__/config.test.js \
  src/__tests__/AppSidebar.test.js \
  src/__tests__/RoleSwitcher.test.js \
  src/pages/__tests__/DashboardPage.test.js \
  src/__tests__/router.test.js
```

Expected: PASS. If the repository-wide test suite still fails on pre-existing `MarkingSelectPage.test.js` or `ReviewPage.test.js`, record that separately and do not mix it with this work.

- [ ] **Step 2: Build**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Verify deployed version**

Run:

```bash
cat /home/ops/projects/edu-cloud/frontend/dist/version.json
curl -fsS https://mcu.asia/version.json
```

Expected: same `build_id`, `build_time`, and `git_hash`.

- [ ] **Step 4: Browser verification**

Use the in-app browser to check:

```text
https://mcu.asia/?_v=<build_id>
https://mcu.asia/workbench-preview?role=school_admin&_v=<build_id>
https://mcu.asia/workbench-preview?role=subject_teacher&_v=<build_id>
https://mcu.asia/workbench-preview?role=homeroom_teacher&_v=<build_id>
https://mcu.asia/workbench-preview?role=lesson_prep_leader&_v=<build_id>
```

Expected visual checks:

- School admin workbench headline is about school operation governance.
- School admin sidebar prioritizes school/academic/exam/student, not personal marking/homework/question-bank.
- Subject teacher sidebar includes personal teaching flow and excludes `/grading/tasks`.
- Homeroom teacher sidebar includes students/conduct and excludes school configuration.
- Lesson prep leader sidebar includes subject exam/grading/resource work and excludes school configuration/conduct.
- Header still shows active identity label in compact mode.

---

## Execution Order

1. Task 1 first, because role selection and switch return value affect later safety logic.
2. Task 2 second, because dashboard and switcher should share route access rules.
3. Task 3 third, because sidebar policy is the largest visible cognitive-load reduction.
4. Task 4 fourth, because formal homepage content should reuse the same role boundaries.
5. Task 5 fifth, because route safety depends on route access and `switchRole()` returning success.
6. Task 6 last, because this is a live frontend change and must be verified on the deployed site.

---

## Self-Review

- Spec coverage: The plan covers active identity, school admin formal homepage, sidebar contraction, multi-identity switching, route safety, tests, build, and browser verification.
- Placeholder scan: No `TBD`, `TODO`, or generic “add tests” steps remain; each test task includes concrete assertions and commands.
- Type consistency: Role keys match `roles.js`; route strings match existing routes; route access fields use `permission` and `moduleCode`; sidebar policy uses existing `group.key` and child `route`.
