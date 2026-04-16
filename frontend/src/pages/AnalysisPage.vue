<template>
  <WorkbenchLayout>
    <template #header>
      <n-h3 style="margin: 0">AI 分析工作台</n-h3>
    </template>
    <template #left>
      <ContextPanel />
    </template>
    <template #center>
      <DataView />
    </template>
    <template #right>
      <StudioPanel />
    </template>
  </WorkbenchLayout>
</template>

<script setup>
import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'
import ContextPanel from '../components/context/ContextPanel.vue'
import DataView from '../components/workspace/DataView.vue'
import StudioPanel from '../components/studio/StudioPanel.vue'
</script>
