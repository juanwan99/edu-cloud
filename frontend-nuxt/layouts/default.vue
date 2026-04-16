<template>
  <div class="app-layout">
    <TopNav @toggle-ai="showAi = !showAi" />
    <SubNav />
    <main
      class="main-content"
      :style="{ marginTop: hasSubNav ? '88px' : '50px' }"
    >
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import { AuthError } from '~/composables/useApi'

const authStore = useAuthStore()
const { loadMenus, currentSubMenus } = useMenus()
const showAi = ref(false)

const hasSubNav = computed(() => currentSubMenus.value.length > 0)

const token = useCookie('edu_token')

authStore.restoreFromStorage()

watch(
  token,
  async (val) => {
    if (val && !authStore.user) {
      authStore.restoreFromStorage()
      try {
        await loadMenus()
      } catch (err) {
        if (err instanceof AuthError) {
          authStore.logout()
        }
        // 非 AuthError 错误（网络/500/解析失败等）静默保留 session（ORC-menu-degrade），Phase 2 接入 logger 模块
        void err
      }
    } else if (val && authStore.user) {
      try {
        await loadMenus()
      } catch (err) {
        if (err instanceof AuthError) {
          authStore.logout()
        }
        // 非 AuthError 错误（网络/500/解析失败等）静默保留 session（ORC-menu-degrade），Phase 2 接入 logger 模块
        void err
      }
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.main-content {
  padding: 16px 20px;
  min-height: calc(100vh - var(--hfs-header-height));
}
</style>
