# Role Workbench Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current permission-driven teacher experience into role-specific workbenches with a single active identity, cross-identity summaries, and explicit context switching.

**Architecture:** Keep the existing RBAC and tenant/scope protection as the source of security truth. Add a front-end workbench model between permissions and navigation so the UI answers "what should this role do now" instead of exposing raw module permissions. Cross-identity tasks remain summarized until the user switches into the target identity context.

**Tech Stack:** Vue 3, Pinia, Vue Router, Naive UI, existing `auth.currentRoleIndex`, existing `UserRole` scope fields (`grade_ids`, `class_ids`, `subject_codes`), Vitest.

---

## Systematic Findings

### Current Strengths

- The system already supports one user with multiple `UserRole` rows.
- The front end already stores `currentRoleIndex` and uses `auth.currentRole` as the active role.
- `auth.switchRole(index)` already calls `/auth/switch-role`, refreshes token, persists state, and reloads school modules.
- Router and sidebar mostly use current-role checks rather than merged permissions.
- Backend scope fields already exist: `school_id`, `grade_ids`, `class_ids`, `subject_codes`.
- Existing security work has tenant isolation and scope filtering; UI optimization should reuse this model.

### Current Gaps

- Permissions and role workbench semantics are mixed. Permission answers "can access"; workbench should answer "should show now".
- Top nav and sidebar are still module-first. Teachers still need to infer the business workflow from menus.
- `DashboardPage.vue` contains role-workflow logic directly, which will grow hard to maintain.
- `RoleWorkbenchPreviewPage.vue` contains a good prototype, but its role model is not reusable by the production dashboard.
- Cross-identity tasks are not a first-class model. The preview simulates them, but production still only has manual role switching.
- Route guards have inconsistencies:
  - `/grading/tasks` is guarded by `roles: GRADING_DISPATCH_ROLES`, and that list currently includes `subject_teacher`. This conflicts with the intended "调度 is not 科任默认入口" model.
  - `/homework` requires `manage_grading`, but teacher-facing configs and permissions treat homework as `view_homework/manage_homework`.
- Backend `get_visible_subject_codes()` does not include `grade_leader` as all-subject visibility. Since 年级组长 should see all subjects in own grade, scoped analytics endpoints need confirmation before UI relies on that behavior.

### Target Product Rule

One user can have multiple identities, but the UI must not merge them into one overloaded dashboard.

- Default into one active identity.
- Show only that identity's workbench, sidebar, nav, KPIs, and priority tasks.
- Other identities can surface urgent summaries.
- Clicking a cross-identity summary switches identity context first, then enters the target workflow.
- Every operation should remain attributable to the active identity for permission, scope, audit, and mental model clarity.

---

## Role Workbench Matrix

| Role | Primary job | Default workbench focus | Hidden by default | Cross-identity summary examples |
| --- | --- | --- | --- | --- |
| `subject_teacher` 科任教师 | Teach own subject and complete assigned grading | Related exams, my grading, subject analysis, homework consolidation | School-wide dispatch, full conduct settings, scheduling | Homeroom conduct records, lesson-prep grading anomalies |
| `homeroom_teacher` 班主任 | Manage own class and student follow-up | Class status, risk students, conduct, parent notifications | Subject resource governance, school scheduling | Own subject grading, grade-level warnings |
| `lesson_prep_leader` 备课组长 | Coordinate same grade and same subject | Subject exam setup, grading coordination, grade-subject analysis, resource consolidation | Class conduct, all-school scheduling | Personal grading, teaching-research review |
| `grade_leader` 年级组长 | Manage grade-level risk and coordination | Grade trend, class comparison, key students, grade conduct | Single question grading detail, subject-only resource building | Homeroom conduct, personal subject work |
| `teaching_research_leader` 教研组长 | Improve subject quality across grades | Subject trend, shared weak points, question bank, knowledge graph | Class conduct, personal homework | Lesson-prep grading anomaly, personal teaching tasks |
| `academic_director` 教务主任 | Govern teaching operations | Scheduling, exams, grading risk, teacher/class config | Personal marking detail, single-class conduct | Personal teacher tasks, homeroom reminders |

---

## File Structure

### Create

- `frontend/src/config/workbenchProfiles.js`
  - Single source for role workbench copy, task groups, role boundaries, and default routes.
- `frontend/src/config/identityRouting.js`
  - Utilities for active identity selection, role priority, cross-identity task normalization, and route query generation.
- `frontend/src/__tests__/workbenchProfiles.test.js`
  - Validates profile coverage, route consistency, and no invalid permission references.
- `frontend/src/__tests__/identityRouting.test.js`
  - Validates default role selection and cross-identity routing behavior.

### Modify

- `frontend/src/pages/RoleWorkbenchPreviewPage.vue`
  - Remove duplicated role data and consume `workbenchProfiles.js`.
- `frontend/src/pages/DashboardPage.vue`
  - Consume role profile model instead of local hardcoded workflow definitions.
- `frontend/src/components/shell/AppHeader.vue`
  - Use active workbench top-nav rules rather than raw permission-derived nav labels.
- `frontend/src/config/sidebarConfig.js`
  - Use workbench sections to group visible entries by role intent.
- `frontend/src/router/index.js`
  - Replace role-only guards on operational pages with permission-based guards where appropriate.
- `frontend/src/stores/auth.js`
  - Add helper methods for switching by role key/id without forcing components to know role array indexes.
- `frontend/src/components/shell/RoleSwitcher.vue`
  - Make primary identity and cross-identity state clearer in the switcher.

### Confirm Before Backend Work

- `src/edu_cloud/api/permissions.py`
  - Confirm whether `grade_leader` should return `None` from `get_visible_subject_codes()` and be constrained by grade/class scope elsewhere.
- Existing dashboard and analytics APIs
  - Confirm whether enough data exists to build real cross-identity summaries or whether Phase 1 should use front-end placeholders.

---

## Task 1: Centralize Workbench Profiles

**Files:**
- Create: `frontend/src/config/workbenchProfiles.js`
- Create: `frontend/src/__tests__/workbenchProfiles.test.js`
- Modify: `frontend/src/pages/RoleWorkbenchPreviewPage.vue`

- [ ] **Step 1: Write profile coverage tests**

Create `frontend/src/__tests__/workbenchProfiles.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { CANONICAL_ROLES } from '../config/roles.js'
import { WORKBENCH_PROFILES, getWorkbenchProfile } from '../config/workbenchProfiles.js'

const TEACHER_WORKBENCH_ROLES = [
  'subject_teacher',
  'homeroom_teacher',
  'lesson_prep_leader',
  'grade_leader',
  'teaching_research_leader',
  'academic_director',
]

describe('workbench profiles', () => {
  it('covers all teacher-facing workbench roles', () => {
    for (const role of TEACHER_WORKBENCH_ROLES) {
      expect(WORKBENCH_PROFILES[role], role).toBeTruthy()
      expect(CANONICAL_ROLES).toContain(role)
    }
  })

  it('returns subject teacher profile as fallback', () => {
    expect(getWorkbenchProfile('unknown_role').key).toBe('subject_teacher')
  })

  it('defines boundaries, actions, priorities, flow, modules, and overlap for each profile', () => {
    for (const role of TEACHER_WORKBENCH_ROLES) {
      const profile = getWorkbenchProfile(role)
      expect(profile.label).toBeTruthy()
      expect(profile.owns).toBeTruthy()
      expect(profile.hides).toBeTruthy()
      expect(profile.primaryAction.route).toMatch(/^\\//)
      expect(profile.secondaryAction.route).toMatch(/^\\//)
      expect(profile.priorities.length).toBeGreaterThan(0)
      expect(profile.flow.length).toBeGreaterThan(0)
      expect(profile.modules.length).toBeGreaterThan(0)
      expect(profile.overlap.other.length).toBeGreaterThan(0)
    }
  })
})
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/workbenchProfiles.test.js
```

Expected: FAIL because `../config/workbenchProfiles.js` does not exist.

- [ ] **Step 3: Move preview profile data into `workbenchProfiles.js`**

Create `frontend/src/config/workbenchProfiles.js` with this structure:

```js
export const WORKBENCH_PROFILE_KEYS = [
  'subject_teacher',
  'homeroom_teacher',
  'lesson_prep_leader',
  'grade_leader',
  'teaching_research_leader',
  'academic_director',
]

export const WORKBENCH_PROFILES = {
  subject_teacher: {
    key: 'subject_teacher',
    label: '科任教师',
    icon: 'person',
    title: '从考试结果进入教学改进',
    summary: '科任教师不需要看到全校调度入口，首页应围绕相关考试、我的阅卷、班级分析、讲评巩固四步展开。',
    owns: '自己任教学科、被分配阅卷、任教班级成绩与作业巩固',
    hides: '全校考试配置、阅卷分派、德育规则、教务排课',
    primaryAction: { label: '进入我的阅卷', route: '/marking' },
    secondaryAction: { label: '查看成绩分析', route: '/analytics/report' },
    priorities: [
      { title: '完成被分配的阅卷题目', desc: '只进入本人负责题目，不暴露调度和分派动作。', meta: '18 题', route: '/marking', tone: 'yellow' },
      { title: '查看本班本学科薄弱点', desc: '先看结论，再下钻题目和学生名单。', meta: '7 项', route: '/analytics/report', tone: 'purple' },
      { title: '把错因生成巩固作业', desc: '报告后的动作入口，不让老师重新找作业模块。', meta: '2 份', route: '/homework', tone: 'orange' },
    ],
    flow: [
      { title: '看相关考试', desc: '只列出与任教学科和班级相关的考试。', route: '/exams' },
      { title: '处理我的阅卷', desc: '按分配题目进入，不出现阅卷组织权限。', route: '/marking' },
      { title: '阅读教学报告', desc: '优先展示知识点、题目、学生分层。', route: '/analytics/report' },
      { title: '生成巩固动作', desc: '作业、错题、题库沉淀承接分析结论。', route: '/homework' },
    ],
    modules: [
      {
        title: '我的教学任务',
        items: [
          { title: '相关考试', desc: '查看与我相关的考试和科目', route: '/exams' },
          { title: '我的阅卷', desc: '处理已分配的人工阅卷', route: '/marking' },
          { title: '成绩分析', desc: '查看任教班级和学生表现', route: '/analytics/report' },
        ],
      },
      {
        title: '讲评和沉淀',
        items: [
          { title: '作业巩固', desc: '把薄弱点转成练习', route: '/homework' },
          { title: '题库管理', desc: '沉淀讲评题目', route: '/question-bank' },
          { title: '知识图谱', desc: '定位知识点覆盖', route: '/knowledge-tree' },
        ],
      },
    ],
    overlap: {
      current: '当前只显示科任任务；班主任或备课组长事项用摘要提醒，不直接展开管理入口。',
      other: [
        { role: '班主任', title: '班级德育待确认 4 条', desc: '点击身份切换后再处理规则和记录。' },
        { role: '备课组长', title: '阅卷进度异常 1 项', desc: '不在科任页直接显示分派按钮。' },
      ],
    },
  },
}

export function getWorkbenchProfile(role) {
  return WORKBENCH_PROFILES[role] || WORKBENCH_PROFILES.subject_teacher
}
```

Then move the remaining five profiles from `RoleWorkbenchPreviewPage.vue` into this object without changing their existing copy.

- [ ] **Step 4: Update preview page to import profiles**

In `frontend/src/pages/RoleWorkbenchPreviewPage.vue`, replace the local `roleProfiles` array with:

```js
import {
  WORKBENCH_PROFILE_KEYS,
  WORKBENCH_PROFILES,
  getWorkbenchProfile,
} from '../config/workbenchProfiles.js'

const roleProfiles = WORKBENCH_PROFILE_KEYS.map(key => WORKBENCH_PROFILES[key])
const activeRole = computed(() => getWorkbenchProfile(activeRoleKey.value))
```

- [ ] **Step 5: Run profile tests**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/workbenchProfiles.test.js
```

Expected: PASS.

---

## Task 2: Add Identity Routing Utilities

**Files:**
- Create: `frontend/src/config/identityRouting.js`
- Create: `frontend/src/__tests__/identityRouting.test.js`
- Modify: `frontend/src/pages/RoleWorkbenchPreviewPage.vue`

- [ ] **Step 1: Write identity routing tests**

Create `frontend/src/__tests__/identityRouting.test.js`:

```js
import { describe, expect, it } from 'vitest'
import {
  chooseDefaultRoleIndex,
  getRoleKeyByLabel,
  toRoleQuery,
} from '../config/identityRouting.js'

const roles = [
  { id: 'r1', role: 'subject_teacher', is_primary: false },
  { id: 'r2', role: 'grade_leader', is_primary: true },
  { id: 'r3', role: 'homeroom_teacher', is_primary: false },
]

describe('identity routing', () => {
  it('prefers primary role', () => {
    expect(chooseDefaultRoleIndex(roles)).toBe(1)
  })

  it('falls back to first role', () => {
    expect(chooseDefaultRoleIndex([{ role: 'subject_teacher' }])).toBe(0)
  })

  it('maps Chinese labels to role keys', () => {
    expect(getRoleKeyByLabel('班主任')).toBe('homeroom_teacher')
    expect(getRoleKeyByLabel('科任教师')).toBe('subject_teacher')
  })

  it('generates route query for a target role', () => {
    expect(toRoleQuery('grade_leader')).toEqual({ role: 'grade_leader' })
  })
})
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/identityRouting.test.js
```

Expected: FAIL because `identityRouting.js` does not exist.

- [ ] **Step 3: Implement identity routing utilities**

Create `frontend/src/config/identityRouting.js`:

```js
import { normalizeRole } from './roles.js'

export const ROLE_PRIORITY = [
  'academic_director',
  'grade_leader',
  'teaching_research_leader',
  'lesson_prep_leader',
  'homeroom_teacher',
  'subject_teacher',
]

export const ROLE_KEY_BY_LABEL = {
  教务主任: 'academic_director',
  年级组长: 'grade_leader',
  教研组长: 'teaching_research_leader',
  备课组长: 'lesson_prep_leader',
  班主任: 'homeroom_teacher',
  科任教师: 'subject_teacher',
}

export function chooseDefaultRoleIndex(roles = []) {
  const primaryIndex = roles.findIndex(role => role.is_primary)
  if (primaryIndex >= 0) return primaryIndex

  let bestIndex = 0
  let bestRank = Number.POSITIVE_INFINITY
  roles.forEach((role, index) => {
    const normalized = normalizeRole(role.role)
    const rank = ROLE_PRIORITY.indexOf(normalized)
    if (rank >= 0 && rank < bestRank) {
      bestRank = rank
      bestIndex = index
    }
  })
  return bestIndex
}

export function getRoleKeyByLabel(label) {
  return ROLE_KEY_BY_LABEL[label] || ''
}

export function toRoleQuery(roleKey) {
  return { role: roleKey }
}
```

- [ ] **Step 4: Update preview page to use utility**

In `RoleWorkbenchPreviewPage.vue`, replace local label mapping:

```js
import { getRoleKeyByLabel, toRoleQuery } from '../config/identityRouting.js'

const activeCrossIdentityTasks = computed(() =>
  activeRole.value.overlap.other.map(item => ({
    ...item,
    roleKey: getRoleKeyByLabel(item.role) || activeRoleKey.value,
  }))
)

function selectRole(key) {
  if (!validRoleKeys.has(key)) return
  activeRoleKey.value = key
  router.replace({ path: route.path, query: { ...route.query, ...toRoleQuery(key) } })
}
```

- [ ] **Step 5: Run identity routing tests**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/identityRouting.test.js
```

Expected: PASS.

---

## Task 3: Align Router Guards With Permissions

**Files:**
- Modify: `frontend/src/config/roles.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/__tests__/router.test.js`

- [ ] **Step 1: Add router tests for grading dispatch and homework**

In `frontend/src/__tests__/router.test.js`, add tests that assert:

```js
it('does not allow subject teacher to access grading dispatch', async () => {
  localStorage.setItem('token', 'valid-token')
  localStorage.setItem('auth_state', JSON.stringify({
    roles: [{ role: 'subject_teacher' }],
    currentRoleIndex: 0,
  }))
  const next = vi.fn()
  authGuard({ path: '/grading/tasks', meta: { permissions: ['manage_grading'] }, matched: [{ meta: { requiresAuth: true } }] }, {}, next)
  expect(next).toHaveBeenCalledWith('/')
})

it('allows subject teacher to access homework by homework permission', async () => {
  localStorage.setItem('token', 'valid-token')
  localStorage.setItem('auth_state', JSON.stringify({
    roles: [{ role: 'subject_teacher' }],
    currentRoleIndex: 0,
  }))
  const next = vi.fn()
  authGuard({ path: '/homework', meta: { permissions: ['view_homework'] }, matched: [{ meta: { requiresAuth: true } }] }, {}, next)
  expect(next).toHaveBeenCalledWith()
})
```

- [ ] **Step 2: Run router tests and confirm failure**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/router.test.js
```

Expected: FAIL until route meta is corrected.

- [ ] **Step 3: Update route meta**

In `frontend/src/router/index.js`, change:

```js
{ path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { roles: GRADING_DISPATCH_ROLES } },
```

to:

```js
{ path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { permissions: ['manage_grading'] } },
```

Change:

```js
{ path: 'homework', name: 'Homework', component: () => import('../pages/HomeworkPage.vue'), meta: { permissions: ['manage_grading'] } },
```

to:

```js
{ path: 'homework', name: 'Homework', component: () => import('../pages/HomeworkPage.vue'), meta: { permissions: ['view_homework', 'manage_homework'] } },
```

- [ ] **Step 4: Remove misleading dispatch role export**

In `frontend/src/config/roles.js`, either delete `GRADING_DISPATCH_ROLES` if unused after the route change, or redefine it as:

```js
export const GRADING_DISPATCH_ROLES = [...SCHOOL_ADMIN_ROLES, ...TEACHING_LEADER_ROLES, 'lesson_prep_leader', 'homeroom_teacher']
```

Prefer deleting if no callers remain.

- [ ] **Step 5: Run router and config tests**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/router.test.js src/__tests__/config.test.js
```

Expected: PASS.

---

## Task 4: Convert Dashboard To Workbench Profile

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue`
- Modify: `frontend/src/config/dashboardConfig.js`
- Modify: `frontend/src/pages/__tests__/DashboardPage.test.js`

- [ ] **Step 1: Add dashboard regression tests**

In `frontend/src/pages/__tests__/DashboardPage.test.js`, add content-level tests:

```js
it('subject teacher dashboard does not show grading dispatch wording', async () => {
  const wrapper = mountDashboardWithRole('subject_teacher')
  expect(wrapper.text()).toContain('我的阅卷')
  expect(wrapper.text()).not.toContain('阅卷调度')
})

it('grade leader dashboard shows grade-focused workbench language', async () => {
  const wrapper = mountDashboardWithRole('grade_leader')
  expect(wrapper.text()).toContain('年级')
  expect(wrapper.text()).toContain('重点学生')
})
```

Use the existing test helpers in that file. If no helper exists, add a local helper that stubs `useAuthStore()` with `currentRole.role`.

- [ ] **Step 2: Run dashboard tests and record current result**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/pages/__tests__/DashboardPage.test.js
```

Expected: current tests may fail until the profile model is wired.

- [ ] **Step 3: Import workbench profile**

In `DashboardPage.vue`, add:

```js
import { getWorkbenchProfile } from '../config/workbenchProfiles.js'
```

Add:

```js
const workbenchProfile = computed(() => getWorkbenchProfile(role.value))
```

Replace hardcoded hero title/body, workflow stages, business groups, and priority labels with `workbenchProfile.value` where possible.

- [ ] **Step 4: Keep data KPIs separate from profile copy**

Do not move live API calls into profile config. Keep:

```js
const kpiData = ref({})
const recentExams = ref([])
const todoItems = ref([])
```

Profile config should only define labels, routes, grouping, and default fallback copy.

- [ ] **Step 5: Run tests and build**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/pages/__tests__/DashboardPage.test.js src/__tests__/workbenchProfiles.test.js
npm run build
```

Expected: tests pass and production build succeeds.

---

## Task 5: Make Role Switcher Explain Context

**Files:**
- Modify: `frontend/src/components/shell/RoleSwitcher.vue`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/__tests__/auth-store.test.js`

- [ ] **Step 1: Add auth helper tests**

In `frontend/src/__tests__/auth-store.test.js`, add:

```js
it('finds role index by role key', () => {
  const store = useAuthStore()
  store.roles = [
    { id: 'r1', role: 'subject_teacher' },
    { id: 'r2', role: 'homeroom_teacher' },
  ]
  expect(store.findRoleIndex('homeroom_teacher')).toBe(1)
  expect(store.findRoleIndex('grade_leader')).toBe(-1)
})
```

- [ ] **Step 2: Implement store helper**

In `frontend/src/stores/auth.js`, add:

```js
function findRoleIndex(roleKey) {
  return roles.value.findIndex(role => normalizeRole(role.role) === roleKey)
}
```

Return it from the store:

```js
findRoleIndex,
```

- [ ] **Step 3: Update switcher labels**

In `RoleSwitcher.vue`, change header subtext from:

```js
`${auth.roles.length} 个角色`
```

to:

```js
`当前以 ${displayLabel.value || '默认身份'} 处理事项`
```

For each role option, show primary marker:

```js
role.is_primary ? h(NTag, { size: 'small', type: 'warning', round: true }, { default: () => '主身份' }) : null
```

- [ ] **Step 4: Run auth tests**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/auth-store.test.js
```

Expected: PASS.

---

## Task 6: Prepare Cross-Identity Summary Model

**Files:**
- Create: `frontend/src/config/crossIdentityTasks.js`
- Create: `frontend/src/__tests__/crossIdentityTasks.test.js`
- Modify: `frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: Add normalization tests**

Create `frontend/src/__tests__/crossIdentityTasks.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { normalizeCrossIdentityTasks } from '../config/crossIdentityTasks.js'

describe('cross identity tasks', () => {
  it('filters out tasks for the active role', () => {
    const result = normalizeCrossIdentityTasks([
      { roleKey: 'grade_leader', title: '年级风险' },
      { roleKey: 'homeroom_teacher', title: '班级德育' },
    ], 'grade_leader')
    expect(result).toEqual([{ roleKey: 'homeroom_teacher', title: '班级德育', severity: 'normal' }])
  })
})
```

- [ ] **Step 2: Implement normalizer**

Create `frontend/src/config/crossIdentityTasks.js`:

```js
export function normalizeCrossIdentityTasks(tasks = [], activeRoleKey) {
  return tasks
    .filter(task => task.roleKey && task.roleKey !== activeRoleKey)
    .map(task => ({
      severity: 'normal',
      ...task,
    }))
}
```

- [ ] **Step 3: Wire dashboard with static fallback**

In `DashboardPage.vue`, add a computed fallback based on profile overlap:

```js
const crossIdentityTasks = computed(() =>
  normalizeCrossIdentityTasks(
    workbenchProfile.value.overlap.other.map(item => ({
      roleKey: getRoleKeyByLabel(item.role),
      title: item.title,
      desc: item.desc,
      source: item.role,
    })),
    role.value,
  )
)
```

Use it only as a UI section. Do not treat fallback preview counts as backend truth.

- [ ] **Step 4: Run tests**

Run:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/crossIdentityTasks.test.js
```

Expected: PASS.

---

## Backend Confirmation Checklist

Before replacing all preview summaries with real data, confirm these backend points:

- `grade_leader` subject visibility: should be all subjects within grade, not empty `subject_codes`.
- Homeroom scope nuance: own homeroom class should see all subjects, teaching classes should see own subject only.
- Cross-identity summaries should not require merged permissions. The API should compute summaries per role and return `{ role_id, role, context, tasks }`.
- Switching identity should remain a token refresh through `/auth/switch-role`; front-end should not fake a role switch for production operations.

Suggested future API:

```json
{
  "active_role_id": "role-grade",
  "summaries": [
    {
      "role_id": "role-homeroom",
      "role": "homeroom_teacher",
      "label": "班主任",
      "tasks": [
        {
          "type": "conduct_pending",
          "title": "本班德育待确认 9 条",
          "route": "/conduct",
          "severity": "warning"
        }
      ]
    }
  ]
}
```

---

## Verification

Run after each implementation batch:

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run test -- src/__tests__/config.test.js src/__tests__/router.test.js src/__tests__/auth-store.test.js
npm run build
```

Run browser smoke checks:

```text
https://mcu.asia/
https://mcu.asia/workbench-preview?role=subject_teacher
https://mcu.asia/workbench-preview?role=homeroom_teacher
https://mcu.asia/workbench-preview?role=grade_leader
https://mcu.asia/workbench-preview?role=academic_director
```

Expected behavior:

- Subject teacher sees "我的阅卷", not "阅卷调度".
- Grade leader sees grade status and cross-identity summaries.
- Clicking a cross-identity task switches to the target role context.
- Sidebar/top nav do not expose hidden operational modules by default.
- Direct route to `/grading/tasks` is denied unless active role has `manage_grading`.

---

## Execution Order

1. Centralize workbench profiles.
2. Add identity routing helpers.
3. Fix route guard inconsistencies.
4. Convert dashboard to consume workbench profiles.
5. Improve role switcher context copy.
6. Add cross-identity task summary model.
7. Revisit backend scope issues before replacing static summary with real cross-role task data.

This order keeps the hidden preview page working while moving production pages toward the same model.
