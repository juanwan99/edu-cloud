<template>
  <div class="dashboard-layout">
    <AppNavbar />
    <main class="dashboard-main">
      <div class="page-container">
        <n-breadcrumb v-if="breadcrumbs.length > 1" style="margin-bottom: 24px;">
          <n-breadcrumb-item v-for="b in breadcrumbs" :key="b.path" @click="b.path && $router.push(b.path)">
            {{ b.label }}
          </n-breadcrumb-item>
        </n-breadcrumb>
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from '../components/AppNavbar.vue'

const route = useRoute()

const breadcrumbs = computed(() => {
  const crumbs = [{ label: '首页', path: '/' }]
  if (route.meta.breadcrumb) {
    crumbs.push(...route.meta.breadcrumb)
  }
  return crumbs
})
</script>

<style scoped>
.dashboard-main {
  padding-top: 68px;
  min-height: 100vh;
  background: var(--color-bg-alt);
}
</style>
