<template>
  <n-layout has-sider style="height: 100vh">
    <!-- Left panel -->
    <n-layout-sider bordered :collapsed="leftCollapsed" :collapsed-width="64" :width="280"
      show-trigger @collapse="leftCollapsed = true" @expand="leftCollapsed = false">
      <slot name="left" />
    </n-layout-sider>
    <!-- Center -->
    <n-layout>
      <n-layout-header bordered style="height: 56px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between;">
        <slot name="header" />
      </n-layout-header>
      <n-layout-content content-style="padding: 16px; height: calc(100vh - 56px); overflow-y: auto;">
        <slot name="center" />
      </n-layout-content>
    </n-layout>
    <!-- Right panel -->
    <n-layout-sider bordered :collapsed="rightCollapsed" :collapsed-width="0" :width="320"
      show-trigger="bar" collapse-mode="transform" @collapse="rightCollapsed = true" @expand="rightCollapsed = false">
      <slot name="right" />
    </n-layout-sider>
  </n-layout>
</template>
<script setup>
import { ref } from 'vue'
const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
</script>
