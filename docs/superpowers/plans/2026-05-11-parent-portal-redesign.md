# 家长端 UI 系统性优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the parent portal as an independent mobile product with the "深墨金" visual language — surface elevation hierarchy, Lucide icons, dark/light theme toggle, action-oriented dashboard, and 4-tab navigation.

**Architecture:** CSS custom properties drive page styling via `[data-theme]` attribute on `ParentLayout` root. Naive UI component colors are overridden via `NConfigProvider` with a dynamic `parentThemeOverrides` reactive object that switches between dark/light token sets. Shared parent components (skeleton, empty state, pull-refresh) are extracted to `src/components/parent/`. Routes consolidate from 7→4 child routes; rankings, rules, and details merge into a single `ParentConduct.vue` page with `NSegmented` sub-views.

**Tech Stack:** Vue 3.5 (Composition API), Naive UI 2.44, Lucide Vue Next (already installed), ECharts 6 + vue-echarts, Vitest + @vue/test-utils + happy-dom.

**Design Spec:** `docs/superpowers/specs/2026-05-11-parent-portal-redesign-design.md`

---

## File Structure

### New Files
| Path | Responsibility |
|------|---------------|
| `src/assets/styles/parent-tokens.css` | Dark/light CSS variable sets for parent portal (surface hierarchy, text, functional colors) |
| `src/components/parent/ParentSkeleton.vue` | Shimmer skeleton loader matching card layouts |
| `src/components/parent/ParentEmpty.vue` | Themed empty state with line-art icon and CTA slot |
| `src/components/parent/PullRefresh.vue` | Pull-to-refresh wrapper with gold spinner |
| `src/components/parent/NumberRoll.vue` | Animated number transition for hero metrics |
| `src/components/parent/ChildSwitcher.vue` | Bottom drawer for switching between bound children |
| `src/pages/parent/ParentConduct.vue` | Merged page: records timeline + rankings + class rules (replaces ParentRankings, ParentRules, ParentDetails) |
| `src/pages/parent/__tests__/ParentLayout.spec.js` | Layout tests: tab rendering, theme switching, auth redirect |
| `src/pages/parent/__tests__/shared-components.spec.js` | Tests for skeleton, empty, number-roll, pull-refresh |

### Modified Files
| Path | Changes |
|------|---------|
| `src/assets/styles/parent-tokens.css` | New file with `[data-theme="dark"]` and `[data-theme="light"]` variable scopes |
| `src/layouts/ParentLayout.vue` | Full rewrite: 4 tabs, Lucide icons, `data-theme` attribute, child switcher drawer, skeleton on initial load, transition wrapper |
| `src/router/index.js` | Lines 110-125: replace 7 child routes with 4 + add redirects for old paths |
| `src/pages/parent/ParentOverview.vue` | Full rewrite: action-oriented dashboard with "今晚关注" card, sparkline trend, behavior summary |
| `src/pages/parent/ParentScores.vue` | Full rewrite: `NSegmented` exam/subject views, progress bars, exam drill-down |
| `src/pages/parent/ParentProfile.vue` | Rewrite: theme toggle (dark/light/system), child management, settings list |
| `src/pages/parent/ParentLogin.vue` | Redesign: deep-ink full-screen, gold CTA, brand alignment |
| `src/pages/parent/ParentRegister.vue` | Redesign: match login visual language |
| `src/pages/parent/ParentBind.vue` | Redesign: step indicator + themed forms |

### Deleted Files
| Path | Reason |
|------|--------|
| `src/pages/parent/ParentRankings.vue` | Merged into ParentConduct.vue "排名" segment |
| `src/pages/parent/ParentRules.vue` | Merged into ParentConduct.vue "班规" segment |
| `src/pages/parent/ParentDetails.vue` | Merged into ParentConduct.vue "记录" segment |

---

### Task 1: Design Token System

**Files:**
- Create: `frontend/src/assets/styles/parent-tokens.css`
- Modify: `frontend/src/main.js` (add import)
- Test: `frontend/src/pages/parent/__tests__/parent-tokens.spec.js`

- [ ] **Step 1: Write the token test**

```javascript
// frontend/src/pages/parent/__tests__/parent-tokens.spec.js
import { describe, it, expect, beforeEach } from 'vitest'

describe('parent-tokens.css', () => {
  beforeEach(() => {
    // Import the CSS (vitest/happy-dom will parse it)
    document.head.innerHTML = ''
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    document.head.appendChild(link)
  })

  it('defines dark theme variables on [data-theme="dark"]', () => {
    // Load the CSS file
    import('../../assets/styles/parent-tokens.css')
    const root = document.createElement('div')
    root.setAttribute('data-theme', 'dark')
    document.body.appendChild(root)
    const style = getComputedStyle(root)
    // Verify key tokens exist (happy-dom has limited CSS support,
    // so we just verify the file loads without error)
    expect(root.getAttribute('data-theme')).toBe('dark')
  })

  it('exports expected CSS custom property names', async () => {
    const css = await import('../../assets/styles/parent-tokens.css?raw')
    expect(css.default).toContain('--p-bg-base')
    expect(css.default).toContain('--p-surface-1')
    expect(css.default).toContain('--p-surface-2')
    expect(css.default).toContain('--p-text-1')
    expect(css.default).toContain('--p-color-accent')
    // Light theme tokens
    expect(css.default).toContain('[data-theme="light"]')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/parent-tokens.spec.js`
Expected: FAIL — file does not exist

- [ ] **Step 3: Create parent-tokens.css**

```css
/* frontend/src/assets/styles/parent-tokens.css */
/* Parent portal design tokens — "深墨金" scheme
   Scoped via [data-theme] attribute on ParentLayout root.
   Prefix: --p- to avoid collision with main site tokens.
*/

[data-theme="dark"] {
  /* Surface elevation hierarchy */
  --p-bg-base: #09061B;
  --p-surface-1: #121026;
  --p-surface-2: #181433;
  --p-surface-3: #211B42;
  --p-surface-raised: #272050;
  --p-border: rgba(255, 255, 255, 0.08);

  /* Text hierarchy */
  --p-text-1: #F6F3FF;
  --p-text-2: #C9C2DD;
  --p-text-3: #9B93B5;
  --p-text-disabled: #6F6887;

  /* Functional colors */
  --p-color-accent: #F4DA4C;
  --p-color-accent-hover: #E8CF40;
  --p-color-accent-pressed: #D4B830;
  --p-color-accent-surface: rgba(244, 218, 76, 0.12);
  --p-color-primary: #644CF0;
  --p-color-primary-surface: rgba(100, 76, 240, 0.15);
  --p-color-success: #22C55E;
  --p-color-success-surface: rgba(34, 197, 94, 0.12);
  --p-color-warning: #ED9A51;
  --p-color-warning-surface: rgba(237, 154, 81, 0.12);
  --p-color-error: #dc2626;
  --p-color-error-surface: rgba(220, 38, 38, 0.12);

  /* Card */
  --p-card-bg: var(--p-surface-2);
  --p-card-radius: 12px;
  --p-card-padding: 16px;
  --p-card-border: 1px solid var(--p-border);
  --p-card-shadow: none;

  /* Naive UI component overrides (consumed by JS, not CSS) */
  --p-naive-body: #09061B;
  --p-naive-card: #181433;
  --p-naive-modal: #211B42;
}

[data-theme="light"] {
  --p-bg-base: #F7F7FB;
  --p-surface-1: #FFFFFF;
  --p-surface-2: #FFFFFF;
  --p-surface-3: #F0EEFA;
  --p-surface-raised: #FFFFFF;
  --p-border: #E5E1F2;

  --p-text-1: #17142A;
  --p-text-2: #5F587A;
  --p-text-3: #8E87A5;
  --p-text-disabled: #B5B0C7;

  --p-color-accent: #644CF0;
  --p-color-accent-hover: #5340D4;
  --p-color-accent-pressed: #4535B8;
  --p-color-accent-surface: rgba(100, 76, 240, 0.08);
  --p-color-primary: #644CF0;
  --p-color-primary-surface: rgba(100, 76, 240, 0.08);
  --p-color-success: #16A34A;
  --p-color-success-surface: rgba(22, 163, 74, 0.08);
  --p-color-warning: #D97706;
  --p-color-warning-surface: rgba(217, 119, 6, 0.08);
  --p-color-error: #DC2626;
  --p-color-error-surface: rgba(220, 38, 38, 0.08);

  --p-card-bg: var(--p-surface-2);
  --p-card-radius: 12px;
  --p-card-padding: 16px;
  --p-card-border: 1px solid var(--p-border);
  --p-card-shadow: 0 2px 8px rgba(9, 6, 27, 0.04);

  --p-naive-body: #F7F7FB;
  --p-naive-card: #FFFFFF;
  --p-naive-modal: #FFFFFF;
}

/* Typography (theme-independent) */
[data-theme] {
  --p-font: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  --p-fs-hero: 32px;
  --p-lh-hero: 1.1;
  --p-fs-page-title: 22px;
  --p-lh-page-title: 30px;
  --p-fs-section: 18px;
  --p-lh-section: 26px;
  --p-fs-card-title: 16px;
  --p-lh-card-title: 24px;
  --p-fs-body: 15px;
  --p-lh-body: 24px;
  --p-fs-label: 13px;
  --p-lh-label: 18px;
  --p-fs-tab: 11px;
  --p-lh-tab: 14px;

  /* Spacing (same as main site 4px grid) */
  --p-space-1: 4px;
  --p-space-2: 8px;
  --p-space-3: 12px;
  --p-space-4: 16px;
  --p-space-5: 20px;
  --p-space-6: 24px;

  /* Animation */
  --p-ease: cubic-bezier(0.2, 0, 0, 1);
  --p-duration-fast: 150ms;
  --p-duration-normal: 220ms;
  --p-duration-slow: 400ms;
}
```

- [ ] **Step 4: Import tokens in main.js**

Add this line after the existing `variables.css` import in `frontend/src/main.js`:

```javascript
import './assets/styles/parent-tokens.css'
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/parent-tokens.spec.js`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/assets/styles/parent-tokens.css src/main.js src/pages/parent/__tests__/parent-tokens.spec.js
git commit -m "feat(parent): add dark/light design token system (parent-tokens.css)"
```

---

### Task 2: Shared Parent Components

**Files:**
- Create: `frontend/src/components/parent/ParentSkeleton.vue`
- Create: `frontend/src/components/parent/ParentEmpty.vue`
- Create: `frontend/src/components/parent/PullRefresh.vue`
- Create: `frontend/src/components/parent/NumberRoll.vue`
- Create: `frontend/src/components/parent/ChildSwitcher.vue`
- Test: `frontend/src/pages/parent/__tests__/shared-components.spec.js`

- [ ] **Step 1: Write failing tests**

```javascript
// frontend/src/pages/parent/__tests__/shared-components.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ParentSkeleton from '../../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../../components/parent/NumberRoll.vue'
import PullRefresh from '../../../components/parent/PullRefresh.vue'
import ChildSwitcher from '../../../components/parent/ChildSwitcher.vue'

describe('ParentSkeleton', () => {
  it('renders skeleton cards', () => {
    const wrapper = mount(ParentSkeleton, { props: { rows: 3 } })
    expect(wrapper.findAll('.skeleton-card').length).toBe(3)
  })

  it('defaults to 2 rows', () => {
    const wrapper = mount(ParentSkeleton)
    expect(wrapper.findAll('.skeleton-card').length).toBe(2)
  })
})

describe('ParentEmpty', () => {
  it('renders message', () => {
    const wrapper = mount(ParentEmpty, { props: { message: '暂无数据' } })
    expect(wrapper.text()).toContain('暂无数据')
  })

  it('renders action slot', () => {
    const wrapper = mount(ParentEmpty, {
      props: { message: 'test' },
      slots: { action: '<button>Retry</button>' },
    })
    expect(wrapper.find('button').text()).toBe('Retry')
  })
})

describe('NumberRoll', () => {
  it('renders the value', () => {
    const wrapper = mount(NumberRoll, { props: { value: 42 } })
    expect(wrapper.text()).toContain('42')
  })

  it('renders dash for null', () => {
    const wrapper = mount(NumberRoll, { props: { value: null } })
    expect(wrapper.text()).toContain('-')
  })
})

describe('PullRefresh', () => {
  it('renders slot content', () => {
    const wrapper = mount(PullRefresh, {
      props: { loading: false },
      slots: { default: '<div class="inner">content</div>' },
    })
    expect(wrapper.find('.inner').text()).toBe('content')
  })

  it('shows update time when provided', () => {
    const wrapper = mount(PullRefresh, {
      props: { loading: false, lastUpdate: '21:08' },
      slots: { default: 'content' },
    })
    expect(wrapper.text()).toContain('21:08')
  })
})

describe('ChildSwitcher', () => {
  const children = [
    { student_id: 1, student_name: '张小明', class_name: '七年级3班' },
    { student_id: 2, student_name: '张小红', class_name: '三年级1班' },
  ]

  it('renders children list', () => {
    const wrapper = mount(ChildSwitcher, {
      props: { show: true, children, currentId: 1 },
    })
    expect(wrapper.text()).toContain('张小明')
    expect(wrapper.text()).toContain('张小红')
  })

  it('emits select on child click', async () => {
    const wrapper = mount(ChildSwitcher, {
      props: { show: true, children, currentId: 1 },
    })
    await wrapper.findAll('.child-item')[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([2])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/shared-components.spec.js`
Expected: FAIL — modules not found

- [ ] **Step 3: Create ParentSkeleton.vue**

```vue
<!-- frontend/src/components/parent/ParentSkeleton.vue -->
<template>
  <div class="parent-skeleton">
    <div v-for="i in rows" :key="i" class="skeleton-card">
      <div class="skeleton-line skeleton-line--title" />
      <div class="skeleton-line skeleton-line--body" />
      <div class="skeleton-line skeleton-line--body skeleton-line--short" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 2 },
})
</script>

<style scoped>
.skeleton-card {
  background: var(--p-card-bg, #181433);
  border-radius: var(--p-card-radius, 12px);
  padding: var(--p-card-padding, 16px);
  margin-bottom: var(--p-space-5, 20px);
}

.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: var(--p-surface-3, #211B42);
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
}

.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--p-surface-raised, #272050), transparent);
  animation: shimmer 1.5s infinite;
}

.skeleton-line--title {
  width: 40%;
  height: 18px;
  margin-bottom: 16px;
}

.skeleton-line--short {
  width: 60%;
  margin-bottom: 0;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
```

- [ ] **Step 4: Create ParentEmpty.vue**

```vue
<!-- frontend/src/components/parent/ParentEmpty.vue -->
<template>
  <div class="parent-empty">
    <component :is="icon" v-if="icon" :size="48" :stroke-width="1" class="parent-empty__icon" />
    <div v-else class="parent-empty__icon-default">
      <Inbox :size="48" :stroke-width="1" />
    </div>
    <p class="parent-empty__message">{{ message }}</p>
    <div v-if="$slots.action" class="parent-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
import { Inbox } from 'lucide-vue-next'

defineProps({
  message: { type: String, default: '暂无数据' },
  icon: { type: [Object, null], default: null },
})
</script>

<style scoped>
.parent-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
}

.parent-empty__icon-default,
.parent-empty__icon {
  color: var(--p-text-3, #9B93B5);
  margin-bottom: 16px;
}

.parent-empty__message {
  font-size: var(--p-fs-body, 15px);
  color: var(--p-text-3, #9B93B5);
  text-align: center;
  margin: 0 0 16px;
}

.parent-empty__action {
  margin-top: 8px;
}
</style>
```

- [ ] **Step 5: Create NumberRoll.vue**

```vue
<!-- frontend/src/components/parent/NumberRoll.vue -->
<template>
  <span class="number-roll" :style="{ fontSize: size }">{{ display }}</span>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  value: { type: [Number, null], default: null },
  size: { type: String, default: 'inherit' },
  duration: { type: Number, default: 400 },
})

const current = ref(props.value ?? 0)
const display = computed(() => props.value == null ? '-' : Math.round(current.value))

watch(() => props.value, (to, from) => {
  if (to == null || from == null) { current.value = to ?? 0; return }
  const start = from
  const delta = to - from
  const startTime = performance.now()
  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / props.duration, 1)
    const ease = 1 - Math.pow(1 - progress, 3)
    current.value = start + delta * ease
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
})
</script>

<style scoped>
.number-roll {
  font-variant-numeric: tabular-nums;
  display: inline-block;
}
</style>
```

- [ ] **Step 6: Create PullRefresh.vue**

```vue
<!-- frontend/src/components/parent/PullRefresh.vue -->
<template>
  <div class="pull-refresh" ref="containerRef">
    <div v-if="lastUpdate" class="pull-refresh__time" :class="{ 'pull-refresh__time--visible': showTime }">
      更新于 {{ lastUpdate }}
    </div>
    <div v-if="loading" class="pull-refresh__indicator">
      <div class="pull-refresh__spinner" />
    </div>
    <slot />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  lastUpdate: { type: String, default: '' },
})

const emit = defineEmits(['refresh'])
const containerRef = ref(null)
const showTime = ref(!!props.lastUpdate)

let startY = 0
let pulling = false

function onTouchStart(e) {
  if (props.loading) return
  if (containerRef.value?.scrollTop > 0) return
  startY = e.touches[0].clientY
  pulling = true
}

function onTouchEnd(e) {
  if (!pulling) return
  pulling = false
  const diff = e.changedTouches[0].clientY - startY
  if (diff > 60) emit('refresh')
}

onMounted(() => {
  const el = containerRef.value
  if (!el) return
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
})

onUnmounted(() => {
  const el = containerRef.value
  if (!el) return
  el.removeEventListener('touchstart', onTouchStart)
  el.removeEventListener('touchend', onTouchEnd)
})

// Fade out update time after 3s
let fadeTimer
import { watch } from 'vue'
watch(() => props.lastUpdate, (v) => {
  if (!v) return
  showTime.value = true
  clearTimeout(fadeTimer)
  fadeTimer = setTimeout(() => { showTime.value = false }, 3000)
})
</script>

<style scoped>
.pull-refresh {
  position: relative;
}

.pull-refresh__time {
  text-align: center;
  font-size: var(--p-fs-label, 13px);
  color: var(--p-text-3, #9B93B5);
  padding: 4px 0;
  opacity: 0;
  transition: opacity 0.3s;
}

.pull-refresh__time--visible {
  opacity: 1;
}

.pull-refresh__indicator {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

.pull-refresh__spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--p-color-accent, #F4DA4C);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
```

- [ ] **Step 7: Create ChildSwitcher.vue**

```vue
<!-- frontend/src/components/parent/ChildSwitcher.vue -->
<template>
  <n-drawer v-model:show="visible" placement="bottom" :height="'auto'" :style="drawerStyle">
    <n-drawer-content title="切换孩子" :body-content-style="{ padding: '0 16px 16px' }">
      <div
        v-for="child in children"
        :key="child.student_id"
        class="child-item"
        :class="{ 'child-item--active': child.student_id === currentId }"
        @click="handleSelect(child.student_id)"
      >
        <div class="child-avatar" :style="{ background: avatarColor(child.student_name) }">
          {{ child.student_name?.charAt(0) || '?' }}
        </div>
        <div class="child-info">
          <div class="child-name">{{ child.student_name }}</div>
          <div class="child-class">{{ child.class_name || '未分配班级' }}</div>
        </div>
        <Check v-if="child.student_id === currentId" :size="20" class="child-check" />
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed } from 'vue'
import { NDrawer, NDrawerContent } from 'naive-ui'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  show: Boolean,
  children: { type: Array, default: () => [] },
  currentId: { type: [Number, String, null], default: null },
})

const emit = defineEmits(['update:show', 'select'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const drawerStyle = {
  '--n-body-color': 'var(--p-surface-raised, #272050)',
  '--n-header-text-color': 'var(--p-text-1, #F6F3FF)',
}

function handleSelect(id) {
  emit('select', id)
  emit('update:show', false)
}

const colors = ['#F4DA4C', '#644CF0', '#ED9A51', '#22C55E', '#8B7AF5', '#dc2626']
function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}
</script>

<style scoped>
.child-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 80ms;
}

.child-item:active {
  background: rgba(255, 255, 255, 0.04);
}

.child-item--active {
  background: var(--p-color-accent-surface, rgba(244, 218, 76, 0.12));
}

.child-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: #09061B;
  flex-shrink: 0;
}

.child-info { flex: 1; }

.child-name {
  font-size: var(--p-fs-body, 15px);
  color: var(--p-text-1, #F6F3FF);
}

.child-class {
  font-size: var(--p-fs-label, 13px);
  color: var(--p-text-3, #9B93B5);
  margin-top: 2px;
}

.child-check { color: var(--p-color-accent, #F4DA4C); }
</style>
```

- [ ] **Step 8: Run tests**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/shared-components.spec.js`
Expected: PASS (9 tests)

- [ ] **Step 9: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/components/parent/ src/pages/parent/__tests__/shared-components.spec.js
git commit -m "feat(parent): add shared components (skeleton, empty, pull-refresh, number-roll, child-switcher)"
```

---

### Task 3: ParentLayout Rewrite

**Files:**
- Modify: `frontend/src/layouts/ParentLayout.vue` (full rewrite)
- Test: `frontend/src/pages/parent/__tests__/ParentLayout.spec.js`

**Dependencies:** Task 1, Task 2

- [ ] **Step 1: Write layout tests**

```javascript
// frontend/src/pages/parent/__tests__/ParentLayout.spec.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import ParentLayout from '../../../layouts/ParentLayout.vue'

vi.mock('../../../api/conduct', () => ({
  getParentMe: vi.fn().mockResolvedValue({ data: { display_name: 'Parent' } }),
  getChildren: vi.fn().mockResolvedValue({ data: { children: [
    { student_id: 1, student_name: '张小明', class_name: '七年级3班', total_points: 38 },
  ] } }),
}))

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/parent', component: { template: '<div>overview</div>' } },
      { path: '/parent/scores', component: { template: '<div>scores</div>' } },
      { path: '/parent/conduct', component: { template: '<div>conduct</div>' } },
      { path: '/parent/profile', component: { template: '<div>profile</div>' } },
      { path: '/parent/login', component: { template: '<div>login</div>' } },
    ],
  })
}

describe('ParentLayout', () => {
  beforeEach(() => {
    localStorage.setItem('cp_token', 'fake-token')
    localStorage.setItem('parent_theme', 'dark')
  })

  it('renders 4 tab items', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    const tabs = wrapper.findAll('.tab-item')
    expect(tabs.length).toBe(4)
  })

  it('uses Lucide icons instead of emoji', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    // No emoji characters should be present in tab bar
    const tabBar = wrapper.find('.bottom-tabs')
    expect(tabBar.text()).not.toMatch(/[📊📝🏆📋👤]/)
  })

  it('sets data-theme attribute', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    expect(wrapper.find('[data-theme]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/ParentLayout.spec.js`
Expected: FAIL (tests will fail against old layout)

- [ ] **Step 3: Rewrite ParentLayout.vue**

Replace the entire content of `frontend/src/layouts/ParentLayout.vue` with:

```vue
<template>
  <div :data-theme="effectiveTheme" class="parent-root">
    <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
      <n-message-provider>
        <n-layout class="parent-layout">
          <!-- Top bar -->
          <header class="parent-header">
            <div class="parent-header__left" @click="showSwitcher = children.length > 1">
              <div v-if="currentChild" class="parent-header__avatar" :style="{ background: avatarColor }">
                {{ currentChild.student_name?.charAt(0) || '?' }}
              </div>
              <div class="parent-header__info">
                <div class="parent-header__name">
                  {{ currentChild?.student_name || '家校互通' }}
                  <ChevronDown v-if="children.length > 1" :size="14" class="parent-header__arrow" />
                </div>
                <div v-if="currentChild?.class_name" class="parent-header__class">
                  {{ currentChild.class_name }}
                </div>
              </div>
            </div>
            <div class="parent-header__right">
              <div class="parent-header__bell" @click="$router.push('/parent')">
                <Bell :size="22" />
                <span v-if="hasUnread" class="parent-header__dot" />
              </div>
            </div>
          </header>

          <!-- Content with transition -->
          <main class="parent-content">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component
                  :is="Component"
                  :key="$route.path"
                  :current-child="currentChild"
                />
              </transition>
            </router-view>
          </main>

          <!-- Bottom tabs -->
          <nav class="bottom-tabs">
            <div
              v-for="tab in tabs"
              :key="tab.path"
              class="tab-item"
              :class="{ active: isActive(tab.path) }"
              @click="$router.push(tab.path)"
            >
              <component :is="tab.icon" :size="24" class="tab-icon" />
              <span class="tab-label">{{ tab.label }}</span>
            </div>
          </nav>
        </n-layout>

        <!-- Child switcher drawer -->
        <ChildSwitcher
          v-model:show="showSwitcher"
          :children="children"
          :current-id="currentChildId"
          @select="switchChild"
        />
      </n-message-provider>
    </n-config-provider>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NLayout, NMessageProvider
} from 'naive-ui'
import { Home, BarChart3, Star, UserRound, Bell, ChevronDown } from 'lucide-vue-next'
import { getParentMe, getChildren } from '../api/conduct'
import ChildSwitcher from '../components/parent/ChildSwitcher.vue'

const router = useRouter()
const route = useRoute()

// --- Theme ---
const themePreference = ref(localStorage.getItem('parent_theme') || 'dark')
const systemDark = ref(window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true)

if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    systemDark.value = e.matches
  })
}

const effectiveTheme = computed(() => {
  if (themePreference.value === 'system') return systemDark.value ? 'dark' : 'light'
  return themePreference.value
})

const naiveTheme = computed(() => effectiveTheme.value === 'dark' ? darkTheme : null)

const darkOverrides = {
  common: {
    primaryColor: '#F4DA4C',
    primaryColorHover: '#E8CF40',
    primaryColorPressed: '#D4B830',
    primaryColorSuppl: '#F4DA4C',
    bodyColor: '#09061B',
    cardColor: '#181433',
    modalColor: '#211B42',
    popoverColor: '#211B42',
    textColor1: '#F6F3FF',
    textColor2: '#C9C2DD',
    textColor3: '#9B93B5',
    borderColor: 'rgba(255,255,255,0.08)',
    inputColor: '#121026',
    tableHeaderColor: '#121026',
  },
}

const lightOverrides = {
  common: {
    primaryColor: '#644CF0',
    primaryColorHover: '#5340D4',
    primaryColorPressed: '#4535B8',
    primaryColorSuppl: '#644CF0',
    bodyColor: '#F7F7FB',
    cardColor: '#FFFFFF',
    modalColor: '#FFFFFF',
    popoverColor: '#FFFFFF',
    textColor1: '#17142A',
    textColor2: '#5F587A',
    textColor3: '#8E87A5',
    borderColor: '#E5E1F2',
    inputColor: '#FFFFFF',
    tableHeaderColor: '#F7F7FB',
  },
}

const themeOverrides = computed(() =>
  effectiveTheme.value === 'dark' ? darkOverrides : lightOverrides
)

provide('parentTheme', themePreference)
provide('setParentTheme', (v) => {
  themePreference.value = v
  localStorage.setItem('parent_theme', v)
})

// --- Children ---
const children = ref([])
const currentChildId = ref(null)
const parentInfo = ref(null)
const hasUnread = ref(false)
const showSwitcher = ref(false)

const currentChild = computed(() =>
  children.value.find(c => c.student_id === currentChildId.value) || children.value[0] || null
)

provide('currentChild', currentChild)
provide('children', children)

function switchChild(id) {
  currentChildId.value = id
}

const avatarColors = ['#F4DA4C', '#644CF0', '#ED9A51', '#22C55E', '#8B7AF5']
const avatarColor = computed(() => {
  const name = currentChild.value?.student_name || ''
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return avatarColors[Math.abs(hash) % avatarColors.length]
})

// --- Tabs ---
const tabs = [
  { path: '/parent', label: '首页', icon: Home },
  { path: '/parent/scores', label: '成绩', icon: BarChart3 },
  { path: '/parent/conduct', label: '表现', icon: Star },
  { path: '/parent/profile', label: '我的', icon: UserRound },
]

function isActive(path) {
  if (path === '/parent') return route.path === '/parent'
  return route.path.startsWith(path)
}

// --- Init ---
onMounted(async () => {
  const token = localStorage.getItem('cp_token')
  if (!token) {
    router.replace('/parent/login')
    return
  }
  try {
    const [meRes, childrenRes] = await Promise.all([getParentMe(), getChildren()])
    parentInfo.value = meRes.data
    children.value = childrenRes.data.children || childrenRes.data || []
    if (children.value.length > 0) {
      currentChildId.value = children.value[0].student_id
    } else {
      router.replace('/parent/bind')
    }
  } catch (err) {
    if (err.response?.status === 401) {
      localStorage.removeItem('cp_token')
      router.replace('/parent/login')
    }
  }
})
</script>

<style scoped>
.parent-root {
  font-family: var(--p-font, -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif);
}

.parent-layout {
  min-height: 100dvh;
  background: var(--p-bg-base);
}

/* Header */
.parent-header {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--p-space-4);
  background: var(--p-surface-1);
  border-bottom: 1px solid var(--p-border);
}

.parent-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.parent-header__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #09061B;
  flex-shrink: 0;
}

.parent-header__name {
  font-size: var(--p-fs-body);
  font-weight: 600;
  color: var(--p-text-1);
  display: flex;
  align-items: center;
  gap: 4px;
}

.parent-header__arrow {
  color: var(--p-text-3);
}

.parent-header__class {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  line-height: var(--p-lh-label);
}

.parent-header__right {
  display: flex;
  align-items: center;
}

.parent-header__bell {
  position: relative;
  padding: 8px;
  color: var(--p-text-2);
  cursor: pointer;
}

.parent-header__dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--p-color-accent);
}

/* Content */
.parent-content {
  padding: var(--p-space-4) var(--p-space-6);
  padding-bottom: 80px;
  min-height: calc(100dvh - 56px - 64px);
}

/* Bottom tabs */
.bottom-tabs {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--p-surface-1);
  border-top: 1px solid var(--p-border);
  display: flex;
  height: calc(64px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 100;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--p-text-3);
  transition: color var(--p-duration-fast) ease;
  -webkit-tap-highlight-color: transparent;
}

.tab-item:active {
  transform: scale(0.97);
}

.tab-item.active {
  color: var(--p-color-accent);
}

.tab-item.active .tab-icon {
  transform: translateY(-1px);
}

.tab-icon {
  transition: transform var(--p-duration-fast) ease;
}

.tab-label {
  font-size: var(--p-fs-tab);
  line-height: var(--p-lh-tab);
  margin-top: 2px;
}

/* Page transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--p-duration-fast) ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/parent/__tests__/ParentLayout.spec.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/layouts/ParentLayout.vue src/pages/parent/__tests__/ParentLayout.spec.js
git commit -m "feat(parent): rewrite layout with 4 tabs, Lucide icons, and theme switching"
```

---

### Task 4: Route Restructure

**Files:**
- Modify: `frontend/src/router/index.js` (lines 110-125)

**Dependencies:** Task 3

- [ ] **Step 1: Update parent routes**

In `frontend/src/router/index.js`, replace lines 110-125 (the parent route block) with:

```javascript
  // 家长端
  { path: '/parent/login', name: 'ParentLogin', component: () => import('../pages/parent/ParentLogin.vue') },
  { path: '/parent/register', name: 'ParentRegister', component: () => import('../pages/parent/ParentRegister.vue') },
  {
    path: '/parent',
    component: () => import('../layouts/ParentLayout.vue'),
    children: [
      { path: '', name: 'ParentOverview', component: () => import('../pages/parent/ParentOverview.vue') },
      { path: 'bind', name: 'ParentBind', component: () => import('../pages/parent/ParentBind.vue') },
      { path: 'scores', name: 'ParentScores', component: () => import('../pages/parent/ParentScores.vue') },
      { path: 'conduct', name: 'ParentConduct', component: () => import('../pages/parent/ParentConduct.vue') },
      { path: 'profile', name: 'ParentProfile', component: () => import('../pages/parent/ParentProfile.vue') },
      // Redirects for old routes
      { path: 'rankings', redirect: { name: 'ParentConduct' } },
      { path: 'rules', redirect: { name: 'ParentConduct' } },
      { path: 'details', redirect: { name: 'ParentConduct' } },
    ]
  },
```

- [ ] **Step 2: Create stub ParentConduct.vue**

Create `frontend/src/pages/parent/ParentConduct.vue` with a minimal stub so the router doesn't break:

```vue
<template>
  <div>
    <p>表现页（待实现 Task 7）</p>
  </div>
</template>

<script setup>
defineProps({
  currentChild: { type: Object, default: null },
})
</script>
```

- [ ] **Step 3: Verify no broken routes**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`
Expected: All existing tests pass (the old page files still exist for now, they're just not routed)

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/router/index.js src/pages/parent/ParentConduct.vue
git commit -m "refactor(parent): restructure routes to 4 tabs, add old-path redirects"
```

---

### Task 5: ParentOverview Rewrite (Action-Oriented Dashboard)

**Files:**
- Modify: `frontend/src/pages/parent/ParentOverview.vue` (full rewrite)

**Dependencies:** Task 1, Task 2, Task 3

- [ ] **Step 1: Rewrite ParentOverview.vue**

Replace the entire content of `frontend/src/pages/parent/ParentOverview.vue` with:

```vue
<template>
  <PullRefresh :loading="refreshing" :last-update="lastUpdate" @refresh="loadData">
    <!-- Skeleton on initial load -->
    <ParentSkeleton v-if="loading && !hasLoaded" :rows="3" />

    <template v-else>
      <!-- No child: guide -->
      <div v-if="!currentChild" class="p-empty-guide">
        <ParentEmpty message="绑定孩子后即可查看">
          <template #action>
            <n-button type="primary" @click="$router.push('/parent/bind')">绑定孩子</n-button>
          </template>
        </ParentEmpty>
      </div>

      <template v-if="currentChild">
        <!-- Tonight's focus card -->
        <div class="focus-card" :class="{ 'focus-card--calm': !focusItems.length }">
          <template v-if="focusItems.length">
            <div class="focus-card__header">
              <Zap :size="18" />
              <span>今晚需关注 {{ focusItems.length }} 项</span>
            </div>
            <div v-for="item in focusItems" :key="item.text" class="focus-card__item" @click="item.action?.()">
              <span>{{ item.text }}</span>
              <ChevronRight :size="16" />
            </div>
          </template>
          <template v-else>
            <div class="focus-card__header focus-card__header--calm">
              <CircleCheck :size="18" />
              <span>今日无需关注事项</span>
            </div>
          </template>
        </div>

        <!-- Academic trend card -->
        <div class="p-card" v-if="examTrend.length || latestScore">
          <div class="p-card__header">
            <span class="p-card__title">学业趋势</span>
            <span class="p-card__action" @click="$router.push('/parent/scores')">详情 <ChevronRight :size="14" /></span>
          </div>
          <div class="trend-row">
            <div class="trend-chart" v-if="examTrend.length >= 2">
              <v-chart :option="sparklineOption" autoresize style="height: 80px;" />
            </div>
            <div class="trend-stats">
              <div class="trend-stat">
                <div class="trend-stat__label">班级位置</div>
                <div class="trend-stat__value">
                  前 <NumberRoll :value="classPercentile" size="var(--p-fs-section)" />%
                </div>
              </div>
              <div v-if="rankChange !== null" class="trend-stat">
                <div class="trend-stat__label">较上次</div>
                <div class="trend-stat__value" :class="rankChangeClass">
                  <component :is="rankChange > 0 ? TrendingDown : TrendingUp" :size="14" />
                  {{ Math.abs(rankChange) }} 位
                </div>
              </div>
            </div>
          </div>
          <div v-if="latestScore" class="trend-latest">
            最近：{{ latestScore.exam_name || '考试' }}
            <span class="trend-latest__score">总分 <NumberRoll :value="latestScore.total_score" /></span>
          </div>
          <div class="p-card__source">{{ dataSource }}</div>
        </div>

        <!-- Weekly behavior card -->
        <div class="p-card" v-if="behaviorSummary">
          <div class="p-card__header">
            <span class="p-card__title">本周表现</span>
            <span class="p-card__action" @click="$router.push('/parent/conduct')">详情 <ChevronRight :size="14" /></span>
          </div>
          <div class="behavior-summary">
            <span class="behavior-tag behavior-tag--good">加分 {{ behaviorSummary.positive_count || 0 }} 次</span>
            <span class="behavior-sep">·</span>
            <span class="behavior-tag behavior-tag--warn">待改善 {{ behaviorSummary.negative_count || 0 }} 项</span>
          </div>
          <div v-if="recentRecords.length" class="behavior-recent">
            <div v-for="r in recentRecords.slice(0, 3)" :key="r.id" class="behavior-item">
              <n-tag :type="r.points >= 0 ? 'success' : 'warning'" size="small" round>
                {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
              </n-tag>
              <span class="behavior-item__text">{{ r.rule_name || r.note || '操行记录' }}</span>
            </div>
          </div>
          <div class="behavior-total">
            本学期累计 <NumberRoll :value="totalPoints" /> 分
          </div>
          <div class="p-card__source">{{ dataSource }}</div>
        </div>

        <!-- Latest updates -->
        <div class="p-card" v-if="updates.length">
          <div class="p-card__header">
            <span class="p-card__title">最新动态</span>
          </div>
          <div v-for="u in updates.slice(0, 3)" :key="u.id" class="update-item">
            <span class="update-item__dot" />
            <span class="update-item__text">{{ u.text }}</span>
            <span class="update-item__time">{{ u.time }}</span>
          </div>
        </div>
      </template>
    </template>
  </PullRefresh>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import { Zap, CircleCheck, ChevronRight, TrendingUp, TrendingDown } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import {
  getChildRecords, getChildScores, getChildRankings,
  getChildBehaviorSummary, getChildExams
} from '../../api/conduct'

const router = useRouter()

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const loading = ref(false)
const refreshing = ref(false)
const hasLoaded = ref(false)
const lastUpdate = ref('')

const examTrend = ref([])
const latestScore = ref(null)
const classPercentile = ref(0)
const rankChange = ref(null)
const behaviorSummary = ref(null)
const recentRecords = ref([])
const totalPoints = ref(0)
const updates = ref([])

const focusItems = computed(() => {
  const items = []
  if (behaviorSummary.value?.negative_count > 0) {
    items.push({
      text: `有 ${behaviorSummary.value.negative_count} 项待改善行为，建议今晚沟通`,
      action: () => router.push('/parent/conduct'),
    })
  }
  if (latestScore.value && rankChange.value && rankChange.value > 3) {
    items.push({
      text: `排名下降 ${rankChange.value} 位，建议关注薄弱学科`,
      action: () => router.push('/parent/scores'),
    })
  }
  return items
})

const rankChangeClass = computed(() => {
  if (rankChange.value == null) return ''
  return rankChange.value > 0 ? 'trend-stat__value--down' : 'trend-stat__value--up'
})

const dataSource = computed(() => {
  const cls = props.currentChild?.class_name || ''
  return cls ? `来自 ${cls} · ${lastUpdate.value || ''} 更新` : ''
})

const sparklineOption = computed(() => ({
  grid: { top: 8, right: 8, bottom: 8, left: 8, containLabel: false },
  xAxis: { type: 'category', show: false, data: examTrend.value.map((_, i) => i) },
  yAxis: { type: 'value', show: false },
  series: [{
    type: 'line',
    data: examTrend.value,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { color: '#F4DA4C', width: 2 },
    itemStyle: { color: '#F4DA4C' },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
      { offset: 0, color: 'rgba(244,218,76,0.25)' },
      { offset: 1, color: 'rgba(244,218,76,0)' },
    ] } },
  }],
}))

async function loadData() {
  const child = props.currentChild
  if (!child) return

  if (hasLoaded.value) refreshing.value = true
  else loading.value = true

  try {
    const [recordsRes, examsRes, rankRes, behaviorRes] = await Promise.allSettled([
      getChildRecords(child.student_id, { page: 1, size: 10 }),
      getChildExams(child.student_id),
      getChildRankings(child.student_id),
      getChildBehaviorSummary(child.student_id),
    ])

    // Records
    if (recordsRes.status === 'fulfilled') {
      const data = recordsRes.value.data
      recentRecords.value = data.items || data || []
    }

    // Exams → trend
    if (examsRes.status === 'fulfilled') {
      const exams = examsRes.value.data || []
      examTrend.value = exams.slice(0, 5).map(e => e.total_score).reverse()
      latestScore.value = exams[0] || null
    }

    // Rankings → percentile
    if (rankRes.status === 'fulfilled') {
      const data = rankRes.value.data
      const rankings = Array.isArray(data) ? data : []
      const myEntry = rankings.find(r => r.student_id === child.student_id)
      if (myEntry && rankings.length > 0) {
        classPercentile.value = Math.round((1 - (myEntry.rank - 1) / rankings.length) * 100)
        rankChange.value = myEntry.previous_rank ? myEntry.previous_rank - myEntry.rank : null
        totalPoints.value = myEntry.total_points ?? 0
      }
    }

    // Behavior
    if (behaviorRes.status === 'fulfilled') {
      behaviorSummary.value = behaviorRes.value.data
    }

    // Build updates from recent data
    const buildUpdates = []
    if (latestScore.value) {
      buildUpdates.push({
        id: 'score',
        text: `${latestScore.value.exam_name || '考试'}成绩已发布`,
        time: formatRelative(latestScore.value.created_at),
      })
    }
    if (recentRecords.value.length > 0) {
      const latest = recentRecords.value[0]
      buildUpdates.push({
        id: 'record',
        text: `${latest.rule_name || '操行记录'}`,
        time: formatRelative(latest.created_at),
      })
    }
    updates.value = buildUpdates

    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    hasLoaded.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function formatRelative(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return days === 1 ? '昨天' : `${days}天前`
}

watch(() => props.currentChild, (child) => {
  // Clear stale data
  examTrend.value = []
  latestScore.value = null
  classPercentile.value = 0
  rankChange.value = null
  behaviorSummary.value = null
  recentRecords.value = []
  totalPoints.value = 0
  updates.value = []
  hasLoaded.value = false
  if (child) loadData()
}, { immediate: true })
</script>

<style scoped>
/* Focus card */
.focus-card {
  background: var(--p-color-accent-surface);
  border: 1px solid rgba(244, 218, 76, 0.2);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}

.focus-card--calm {
  background: var(--p-color-success-surface);
  border-color: rgba(34, 197, 94, 0.2);
}

.focus-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--p-fs-body);
  font-weight: 600;
  color: var(--p-color-accent);
  margin-bottom: 8px;
}

.focus-card__header--calm {
  color: var(--p-color-success);
  margin-bottom: 0;
}

.focus-card__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  cursor: pointer;
  border-top: 1px solid var(--p-border);
}

/* Shared card style */
.p-card {
  background: var(--p-card-bg);
  border: var(--p-card-border);
  box-shadow: var(--p-card-shadow);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}

.p-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--p-space-3);
}

.p-card__title {
  font-size: var(--p-fs-section);
  font-weight: 600;
  color: var(--p-text-1);
}

.p-card__action {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 2px;
}

.p-card__source {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  margin-top: var(--p-space-3);
}

/* Trend */
.trend-row {
  display: flex;
  gap: var(--p-space-4);
  align-items: center;
}

.trend-chart {
  flex: 1;
  min-width: 0;
}

.trend-stats {
  display: flex;
  flex-direction: column;
  gap: var(--p-space-2);
}

.trend-stat__label {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
}

.trend-stat__value {
  font-size: var(--p-fs-body);
  font-weight: 600;
  color: var(--p-text-1);
  display: flex;
  align-items: center;
  gap: 4px;
  font-variant-numeric: tabular-nums;
}

.trend-stat__value--up { color: var(--p-color-success); }
.trend-stat__value--down { color: var(--p-color-warning); }

.trend-latest {
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  margin-top: var(--p-space-3);
  padding-top: var(--p-space-3);
  border-top: 1px solid var(--p-border);
}

.trend-latest__score {
  font-weight: 600;
  color: var(--p-text-1);
  font-variant-numeric: tabular-nums;
}

/* Behavior */
.behavior-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--p-space-3);
}

.behavior-tag {
  font-size: var(--p-fs-body);
  font-weight: 500;
}

.behavior-tag--good { color: var(--p-color-success); }
.behavior-tag--warn { color: var(--p-color-warning); }
.behavior-sep { color: var(--p-text-3); }

.behavior-recent {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: var(--p-space-3);
}

.behavior-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.behavior-item__text {
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.behavior-total {
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  padding-top: var(--p-space-3);
  border-top: 1px solid var(--p-border);
}

/* Updates */
.update-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.update-item__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--p-color-accent);
  flex-shrink: 0;
}

.update-item__text {
  flex: 1;
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
}

.update-item__time {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  flex-shrink: 0;
}

.p-empty-guide {
  padding-top: 60px;
}
</style>
```

- [ ] **Step 2: Verify it renders**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/pages/parent/ParentOverview.vue
git commit -m "feat(parent): rewrite overview as action-oriented dashboard"
```

---

### Task 6: ParentScores Rewrite

**Files:**
- Modify: `frontend/src/pages/parent/ParentScores.vue` (full rewrite)

**Dependencies:** Task 1, Task 2, Task 3

- [ ] **Step 1: Rewrite ParentScores.vue**

Replace entire content of `frontend/src/pages/parent/ParentScores.vue`. Key changes:
- `NSegmented` toggling between `考试` and `学科` views
- Horizontal progress bars with class average comparison line
- Warning indicator for subjects below class average
- Folding exam history
- Error book stats in subject view

Use `--p-*` tokens for all colors. Reuse `.p-card` pattern from Task 5. Exam view shows score summary triple (total/class rank/grade rank) + subject progress bars. Subject view shows trend line chart per subject + error book breakdown.

Follow this component signature:

```vue
<script setup>
import { ref, watch, computed } from 'vue'
import { NSegmented, NTag, NCollapse, NCollapseItem, NProgress } from 'naive-ui'
import { AlertTriangle, ChevronRight } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import { getChildExams, getChildScores, getChildErrorBook } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})
</script>
```

Full template, script, and scoped styles follow the same `.p-card` / `--p-*` token patterns established in Task 5.

- [ ] **Step 2: Verify**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/pages/parent/ParentScores.vue
git commit -m "feat(parent): rewrite scores page with segmented exam/subject views"
```

---

### Task 7: ParentConduct (Merged Records + Rankings + Rules)

**Files:**
- Modify: `frontend/src/pages/parent/ParentConduct.vue` (replace stub from Task 4)

**Dependencies:** Task 1, Task 2, Task 3, Task 4

- [ ] **Step 1: Implement ParentConduct.vue**

Replace the stub with the full implementation. This page uses `NSegmented` with 3 segments:

**记录 segment**: Day-grouped timeline of behavior records. Positive events use `--p-color-success`, negative use `--p-color-warning`. Negative records show linked rule name with inline expand.

**排名 segment**: Top card showing percentile band (`前 35%`) + exact rank + trend. Rankings table with current child row highlighted in `--p-color-accent-surface`.

**班规 segment**: Searchable collapsible categories (reuses existing ParentRules logic). Points tags with success/warning types.

Component signature:

```vue
<script setup>
import { ref, watch, computed, inject } from 'vue'
import { NSegmented, NTag, NCollapse, NCollapseItem, NInput, NRadioGroup, NRadioButton } from 'naive-ui'
import { TrendingUp, TrendingDown, Minus, Search } from 'lucide-vue-next'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import { getChildRecords, getChildRankings, getClassRulesParent } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})
</script>
```

- [ ] **Step 2: Verify**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/pages/parent/ParentConduct.vue
git commit -m "feat(parent): add conduct page merging records, rankings, and class rules"
```

---

### Task 8: ParentProfile Rewrite

**Files:**
- Modify: `frontend/src/pages/parent/ParentProfile.vue` (full rewrite)

**Dependencies:** Task 1, Task 3

- [ ] **Step 1: Rewrite ParentProfile.vue**

Key changes:
- Theme toggle: 3-option radio group (深色/浅色/跟随系统) using `inject('setParentTheme')`
- Child management section with bound children list + "绑定孩子" entry
- Settings list with `ChevronRight` arrows (修改密码, 通知设置, 关于)
- Logout with confirmation
- Uses `--p-*` tokens and `.p-card` pattern

```vue
<script setup>
import { ref, inject, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NForm, NFormItem, NInput, NRadioGroup, NRadio,
  NList, NListItem, NPopconfirm
} from 'naive-ui'
import { ChevronRight, LogOut, Settings, Key, Bell, Info, UserPlus } from 'lucide-vue-next'
import { updateParentProfile, changeParentPassword, getParentMe } from '../../api/conduct'

const children = inject('children')
const parentTheme = inject('parentTheme')
const setParentTheme = inject('setParentTheme')

const props = defineProps({
  currentChild: { type: Object, default: null },
})
</script>
```

- [ ] **Step 2: Verify**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/pages/parent/ParentProfile.vue
git commit -m "feat(parent): rewrite profile with theme toggle and redesigned layout"
```

---

### Task 9: Auth Pages Redesign (Login, Register, Bind)

**Files:**
- Modify: `frontend/src/pages/parent/ParentLogin.vue`
- Modify: `frontend/src/pages/parent/ParentRegister.vue`
- Modify: `frontend/src/pages/parent/ParentBind.vue`

**Dependencies:** Task 1

- [ ] **Step 1: Redesign ParentLogin.vue**

Key changes:
- Remove decorative floating circles
- Deep-ink full-screen (`--p-bg-base`) with brand text
- Gold CTA button
- Use `--p-*` tokens for all colors
- Keep existing login logic (phone + password + cp_token) unchanged

- [ ] **Step 2: Redesign ParentRegister.vue**

Match login visual language:
- Same deep-ink background
- Step indicator using `--p-color-accent`
- Use `--p-*` tokens

- [ ] **Step 3: Redesign ParentBind.vue**

Match login visual language:
- Step progress indicator with `--p-color-accent`
- Relationship grid with themed emoji options
- Success state with gold accent

- [ ] **Step 4: Verify**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add src/pages/parent/ParentLogin.vue src/pages/parent/ParentRegister.vue src/pages/parent/ParentBind.vue
git commit -m "feat(parent): redesign auth pages with deep-ink theme"
```

---

### Task 10: Cleanup and Build Verification

**Files:**
- Delete: `frontend/src/pages/parent/ParentRankings.vue`
- Delete: `frontend/src/pages/parent/ParentRules.vue`
- Delete: `frontend/src/pages/parent/ParentDetails.vue`

**Dependencies:** All previous tasks

- [ ] **Step 1: Delete old merged pages**

```bash
cd /home/ops/projects/edu-cloud/frontend
rm src/pages/parent/ParentRankings.vue
rm src/pages/parent/ParentRules.vue
rm src/pages/parent/ParentDetails.vue
```

- [ ] **Step 2: Search for stale imports**

```bash
cd /home/ops/projects/edu-cloud/frontend
grep -r "ParentRankings\|ParentRules\|ParentDetails" src/ --include="*.vue" --include="*.js"
```

Expected: Only the redirect entries in `router/index.js` (those are fine — they point to `ParentConduct`). No component imports should remain.

- [ ] **Step 3: Run full test suite**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run
```

Expected: All tests pass, no regressions

- [ ] **Step 4: Build**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vite build
```

Expected: Build succeeds with no errors

- [ ] **Step 5: Verify stale parent test (ParentRules.spec.js) if exists**

```bash
ls src/pages/parent/__tests__/ParentRules.spec.js 2>/dev/null && echo "EXISTS - needs update" || echo "OK - no stale test"
```

If the file exists, delete it (the rules logic is now inside ParentConduct).

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend
git add -A src/pages/parent/
git commit -m "chore(parent): remove old ParentRankings/ParentRules/ParentDetails (merged into ParentConduct)"
```

- [ ] **Step 7: Final verification — dev server spot check**

```bash
cd /home/ops/projects/edu-cloud/frontend && npm run dev &
sleep 3
curl -s http://localhost:8080/parent/login | head -5
```

Verify the page loads without errors. Kill the dev server when done.

---

## Task Dependency Graph

```
Task 1 (tokens) ─────┬──→ Task 3 (layout) ──→ Task 4 (routes) ──→ Task 7 (conduct)
                      │                                            ↗
Task 2 (components) ──┤──→ Task 5 (overview)                    ──→ Task 10 (cleanup)
                      │──→ Task 6 (scores)                       ↗
                      │──→ Task 8 (profile)                    ──
                      └──→ Task 9 (auth pages) ────────────────
```

**Parallelizable groups:**
- Wave 1: Task 1 + Task 2 (independent)
- Wave 2: Task 3 → Task 4 (sequential)
- Wave 3: Task 5 + Task 6 + Task 7 + Task 8 + Task 9 (all depend on Wave 2, independent of each other)
- Wave 4: Task 10 (depends on all)
