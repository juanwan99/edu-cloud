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
            <div v-if="loadError" class="load-error">
              <p>{{ loadError }}</p>
              <n-button size="small" @click="retryInit">重试</n-button>
            </div>
            <router-view v-else v-slot="{ Component }">
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
  NConfigProvider, NLayout, NMessageProvider, NButton
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
const loadError = ref('')

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

async function retryInit() {
  loadError.value = ''
  await initLayout()
}

async function initLayout() {
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
    } else {
      loadError.value = '加载失败，请下拉刷新重试'
    }
  }
}

onMounted(initLayout)
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

/* Load error */
.load-error {
  text-align: center;
  padding: 60px var(--p-space-4);
  color: var(--p-text-3);
  font-size: var(--p-fs-body);
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
