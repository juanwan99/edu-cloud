<template>
  <main class="role-workbench-preview">
    <section class="preview-head">
      <div>
        <div class="preview-head__eyebrow">多角色工作台预览</div>
        <h1 class="preview-head__title">按岗位职责组织页面，而不是按功能清单堆菜单</h1>
        <p class="preview-head__desc">
          每个角色只展示当前身份下最该处理的业务主线。多身份不是让老师自己找入口，而是系统先识别主身份，再把其他身份事项压缩成可行动摘要。
        </p>
      </div>
      <div class="preview-head__note">
        <strong>预览原则</strong>
        <span>当前页面只用于结构评审，不替换正式首页和侧栏；跨身份动作必须带着身份上下文进入。</span>
      </div>
    </section>

    <section class="role-tabs" aria-label="选择预览角色">
      <button
        v-for="role in roleProfiles"
        :key="role.key"
        type="button"
        :class="['role-tab', { 'role-tab--active': role.key === activeRole.key }]"
        @click="selectRole(role.key)"
      >
        <AppIcon :name="role.icon" :size="18" />
        <span>{{ role.label }}</span>
      </button>
    </section>

    <section class="identity-routing" aria-label="多身份路由规则">
      <article
        v-for="rule in identityRoutingRules"
        :key="rule.title"
        class="routing-rule"
      >
        <span>{{ rule.step }}</span>
        <strong>{{ rule.title }}</strong>
        <small>{{ rule.desc }}</small>
      </article>
    </section>

    <section class="role-hero">
      <div class="role-hero__main">
        <div class="role-hero__label">{{ activeRole.label }}</div>
        <h2>{{ activeRole.title }}</h2>
        <p>{{ activeRole.summary }}</p>
        <div class="role-hero__actions">
          <n-button type="primary" size="large" @click="go(activeRole.primaryAction.route)">
            {{ activeRole.primaryAction.label }}
          </n-button>
          <n-button secondary size="large" @click="go(activeRole.secondaryAction.route)">
            {{ activeRole.secondaryAction.label }}
          </n-button>
        </div>
      </div>
      <div class="role-boundary">
        <div class="boundary-item">
          <span>当前身份只负责</span>
          <strong>{{ activeRole.owns }}</strong>
        </div>
        <div class="boundary-item boundary-item--quiet">
          <span>默认不展示</span>
          <strong>{{ activeRole.hides }}</strong>
        </div>
      </div>
    </section>

    <section class="kpi-grid" aria-label="角色关键指标">
      <article
        v-for="item in activeRole.kpis"
        :key="item.label"
        :class="['kpi-card', `kpi-card--${item.tone}`]"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.meta }}</small>
      </article>
    </section>

    <section class="workspace-layout">
      <article class="panel priority-panel">
        <div class="panel-head">
          <div>
            <h3>今天先处理</h3>
            <p>按岗位动作排序，减少进入系统后的判断成本</p>
          </div>
          <n-tag type="warning" round>优先级</n-tag>
        </div>
        <div class="priority-list">
          <button
            v-for="task in activeRole.priorities"
            :key="task.title"
            type="button"
            class="priority-row"
            @click="go(task.route)"
          >
            <span :class="['priority-row__dot', `priority-row__dot--${task.tone}`]" />
            <span class="priority-row__body">
              <strong>{{ task.title }}</strong>
              <small>{{ task.desc }}</small>
            </span>
            <span class="priority-row__meta">{{ task.meta }}</span>
          </button>
        </div>
      </article>

      <article class="panel workflow-panel">
        <div class="panel-head">
          <div>
            <h3>业务主线</h3>
            <p>{{ activeRole.flowHint }}</p>
          </div>
        </div>
        <div class="flow-list">
          <button
            v-for="(step, index) in activeRole.flow"
            :key="step.title"
            type="button"
            class="flow-step"
            @click="go(step.route)"
          >
            <span class="flow-step__index">{{ index + 1 }}</span>
            <span>
              <strong>{{ step.title }}</strong>
              <small>{{ step.desc }}</small>
            </span>
          </button>
        </div>
      </article>
    </section>

    <section class="workspace-layout workspace-layout--lower">
      <article class="panel module-panel">
        <div class="panel-head">
          <div>
            <h3>核心入口</h3>
            <p>入口按业务含义分组，不让老师先理解系统模块</p>
          </div>
        </div>
        <div class="module-groups">
          <div v-for="group in activeRole.modules" :key="group.title" class="module-group">
            <div class="module-group__title">{{ group.title }}</div>
            <button
              v-for="item in group.items"
              :key="item.title"
              type="button"
              class="module-link"
              @click="go(item.route)"
            >
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.desc }}</small>
              </span>
              <AppIcon name="chevron-right" :size="16" />
            </button>
          </div>
        </div>
      </article>

      <aside class="panel overlap-panel">
        <div class="panel-head">
          <div>
            <h3>多身份协同</h3>
            <p>系统负责提醒和带路，老师只确认要不要切换上下文</p>
          </div>
        </div>
        <div class="identity-stack">
          <button
            v-for="identity in overlapIdentities"
            :key="identity.key"
            type="button"
            :class="['identity-chip', { 'identity-chip--active': identity.key === activeRole.key }]"
            @click="selectRole(identity.key)"
          >
            {{ identity.label }}
          </button>
        </div>
        <div class="overlap-card">
          <span>系统当前上下文</span>
          <strong>{{ activeRole.label }}工作台</strong>
          <p>{{ activeRole.overlap.current }}</p>
        </div>
        <div class="cross-list">
          <button
            v-for="item in activeCrossIdentityTasks"
            :key="item.title"
            type="button"
            class="cross-item"
            @click="switchToTaskIdentity(item)"
          >
            <span>{{ item.role }}</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.desc }}</small>
            <em>切到{{ item.role }}身份处理</em>
          </button>
        </div>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import AppIcon from '../components/AppIcon.vue'
import {
  WORKBENCH_PROFILE_KEYS,
  WORKBENCH_PROFILES,
  getWorkbenchProfile,
} from '../config/workbenchProfiles.js'
import { getRoleKeyByLabel, toRoleQuery } from '../config/identityRouting.js'

const router = useRouter()
const route = useRoute()

const identityRoutingRules = [
  {
    step: '01',
    title: '默认主身份',
    desc: '系统按岗位优先级、近期任务和组织任命确定进入哪个工作台。',
  },
  {
    step: '02',
    title: '跨身份摘要',
    desc: '其他身份只冒泡关键待办，不展开完整功能区。',
  },
  {
    step: '03',
    title: '带上下文切换',
    desc: '点击跨身份任务时，页面切换身份并记录本次操作归属。',
  },
]

const roleProfiles = WORKBENCH_PROFILE_KEYS.map(key => WORKBENCH_PROFILES[key])
const validRoleKeys = new Set(roleProfiles.map(role => role.key))
const initialRole = validRoleKeys.has(String(route.query.role)) ? String(route.query.role) : 'subject_teacher'
const activeRoleKey = ref(initialRole)
const activeRole = computed(() => getWorkbenchProfile(activeRoleKey.value))
const overlapIdentities = computed(() =>
  roleProfiles.filter(role => ['subject_teacher', 'homeroom_teacher', 'lesson_prep_leader', 'grade_leader'].includes(role.key))
)
const activeCrossIdentityTasks = computed(() =>
  activeRole.value.overlap.other.map(item => ({
    ...item,
    roleKey: getRoleKeyByLabel(item.role) || activeRoleKey.value,
  }))
)

watch(() => route.query.role, roleKey => {
  if (validRoleKeys.has(String(roleKey))) {
    activeRoleKey.value = String(roleKey)
  }
})

function selectRole(key) {
  if (!validRoleKeys.has(key)) return
  activeRoleKey.value = key
  router.replace({ path: route.path, query: { ...route.query, ...toRoleQuery(key) } })
}

function switchToTaskIdentity(item) {
  selectRole(item.roleKey)
}

function go(routePath) {
  router.push(routePath)
}
</script>

<style scoped>
.role-workbench-preview {
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.preview-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 24px;
  padding: 26px;
  border-radius: var(--radius-lg);
  background: var(--surface-header-gradient);
  color: #ffffff;
  box-shadow: var(--shadow-lg);
}

.preview-head__eyebrow,
.role-hero__label {
  font-size: var(--fs-xs);
  font-weight: var(--fw-bold);
  color: var(--color-accent);
}

.preview-head__title {
  max-width: 820px;
  margin-top: 8px;
  font-size: clamp(28px, 3vw, 42px);
  line-height: 1.12;
  font-weight: var(--fw-heavy);
  letter-spacing: 0;
}

.preview-head__desc {
  max-width: 860px;
  margin-top: 14px;
  color: rgba(255, 255, 255, 0.74);
  font-size: var(--fs-base);
  line-height: 1.7;
}

.preview-head__note {
  align-self: stretch;
  padding: 18px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.preview-head__note strong {
  color: var(--color-accent);
  font-size: var(--fs-lg);
}

.preview-head__note span {
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.6;
}

.role-tabs {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.identity-routing {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.routing-rule {
  min-height: 118px;
  padding: 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  background: #ffffff;
  box-shadow: var(--shadow-card);
}

.routing-rule span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 28px;
  margin-bottom: 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-stat-yellow);
  color: var(--color-bg-deep);
  font-size: var(--fs-xs);
  font-weight: var(--fw-heavy);
  font-variant-numeric: tabular-nums;
}

.routing-rule strong {
  display: block;
  margin-bottom: 6px;
  color: var(--color-text);
  font-size: var(--fs-base);
  font-weight: var(--fw-bold);
}

.routing-rule small {
  display: block;
  color: var(--color-text-secondary);
  line-height: 1.55;
}

.role-tab {
  min-height: 48px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #ffffff;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: var(--fw-semibold);
  cursor: pointer;
  transition: var(--transition);
}

.role-tab:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary-dark);
}

.role-tab--active {
  background: var(--color-accent);
  color: var(--color-bg-deep);
  border-color: var(--color-accent);
  box-shadow: var(--shadow-stat-yellow);
}

.role-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 20px;
}

.role-hero__main,
.role-boundary,
.panel,
.kpi-card {
  background: #ffffff;
  border: 1px solid var(--color-border-light);
  box-shadow: var(--shadow-card);
  border-radius: var(--radius-lg);
}

.role-hero__main {
  padding: 28px;
}

.role-hero__main h2 {
  margin-top: 8px;
  font-size: var(--fs-3xl);
  line-height: 1.18;
  font-weight: var(--fw-heavy);
  letter-spacing: 0;
}

.role-hero__main p {
  max-width: 820px;
  margin-top: 12px;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.role-hero__actions {
  margin-top: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.role-boundary {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.boundary-item {
  flex: 1;
  padding: 18px;
  border-radius: var(--radius-md);
  background: var(--surface-stat-yellow);
}

.boundary-item--quiet {
  background: var(--surface-stat-ink);
}

.boundary-item span {
  display: block;
  color: var(--color-text-muted);
  font-size: var(--fs-sm);
  font-weight: var(--fw-semibold);
  margin-bottom: 8px;
}

.boundary-item strong {
  display: block;
  color: var(--color-text);
  line-height: 1.55;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.kpi-card {
  padding: 22px;
}

.kpi-card--yellow {
  background: var(--surface-stat-yellow);
  box-shadow: var(--shadow-stat-yellow);
}

.kpi-card--purple {
  background: var(--surface-stat-purple);
  box-shadow: var(--shadow-stat-purple);
}

.kpi-card--orange {
  background: var(--surface-stat-orange);
  box-shadow: var(--shadow-stat-orange);
}

.kpi-card--ink {
  background: var(--surface-stat-ink);
  box-shadow: var(--shadow-stat-ink);
}

.kpi-card span,
.kpi-card small {
  display: block;
  color: var(--color-text-secondary);
  font-size: var(--fs-sm);
}

.kpi-card strong {
  display: block;
  margin: 10px 0 8px;
  font-size: 34px;
  line-height: 1;
  font-weight: var(--fw-heavy);
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.workspace-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.82fr);
  gap: 20px;
}

.workspace-layout--lower {
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.7fr);
  align-items: start;
}

.panel {
  padding: 22px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-head h3 {
  font-size: var(--fs-xl);
  font-weight: var(--fw-heavy);
  line-height: 1.2;
}

.panel-head p {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: var(--fs-sm);
}

.priority-list,
.flow-list,
.cross-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.priority-row,
.flow-step,
.module-link {
  width: 100%;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: #ffffff;
  color: var(--color-text);
  cursor: pointer;
  transition: var(--transition);
  text-align: left;
}

.priority-row:hover,
.flow-step:hover,
.module-link:hover {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.priority-row {
  min-height: 82px;
  padding: 14px 14px;
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
}

.priority-row__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  background: var(--color-accent);
}

.priority-row__dot--purple {
  background: var(--color-primary);
}

.priority-row__dot--orange {
  background: var(--color-warning);
}

.priority-row__body strong,
.flow-step strong,
.module-link strong,
.cross-item strong {
  display: block;
  font-size: var(--fs-base);
  font-weight: var(--fw-bold);
  line-height: 1.3;
}

.priority-row__body small,
.flow-step small,
.module-link small,
.cross-item small {
  display: block;
  margin-top: 5px;
  color: var(--color-text-muted);
  line-height: 1.45;
}

.priority-row__meta {
  color: var(--color-primary-dark);
  background: var(--surface-primary);
  border-radius: var(--radius-pill);
  padding: 5px 10px;
  font-size: var(--fs-xs);
  font-weight: var(--fw-bold);
  white-space: nowrap;
}

.flow-step {
  min-height: 72px;
  padding: 14px;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
}

.flow-step__index {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-stat-yellow);
  color: var(--color-bg-deep);
  font-weight: var(--fw-heavy);
  font-variant-numeric: tabular-nums;
}

.module-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.module-group {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px;
  background: var(--color-bg);
}

.module-group__title {
  margin-bottom: 12px;
  color: var(--color-text-secondary);
  font-size: var(--fs-sm);
  font-weight: var(--fw-bold);
}

.module-link {
  min-height: 72px;
  padding: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
}

.module-link + .module-link {
  margin-top: 8px;
}

.identity-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.identity-chip {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: #ffffff;
  padding: 7px 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: var(--fs-sm);
  font-weight: var(--fw-semibold);
}

.identity-chip--active {
  color: var(--color-bg-deep);
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.overlap-card {
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--surface-stat-purple);
  margin-bottom: 12px;
}

.overlap-card span {
  display: block;
  color: var(--color-primary-dark);
  font-size: var(--fs-sm);
  font-weight: var(--fw-bold);
  margin-bottom: 6px;
}

.overlap-card strong {
  display: block;
  color: var(--color-text);
  font-size: var(--fs-lg);
  margin-bottom: 8px;
}

.overlap-card p {
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.cross-item {
  width: 100%;
  text-align: left;
  padding: 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: #ffffff;
  cursor: pointer;
  transition: var(--transition);
}

.cross-item:hover {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.cross-item span {
  display: inline-flex;
  margin-bottom: 6px;
  padding: 3px 8px;
  border-radius: var(--radius-pill);
  background: var(--surface-accent);
  color: #72510c;
  font-size: var(--fs-xs);
  font-weight: var(--fw-bold);
}

.cross-item em {
  display: inline-flex;
  margin-top: 12px;
  color: var(--color-primary-dark);
  font-style: normal;
  font-size: var(--fs-sm);
  font-weight: var(--fw-bold);
}

@media (max-width: 1180px) {
  .preview-head,
  .role-hero,
  .workspace-layout,
  .workspace-layout--lower {
    grid-template-columns: 1fr;
  }

  .role-tabs,
  .identity-routing,
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .role-workbench-preview {
    padding: 16px;
  }

  .preview-head,
  .role-hero__main,
  .role-boundary,
  .panel {
    padding: 18px;
  }

  .role-tabs,
  .identity-routing,
  .kpi-grid,
  .module-groups {
    grid-template-columns: 1fr;
  }

  .priority-row {
    grid-template-columns: 10px minmax(0, 1fr);
  }

  .priority-row__meta {
    grid-column: 2;
    width: max-content;
  }
}
</style>
