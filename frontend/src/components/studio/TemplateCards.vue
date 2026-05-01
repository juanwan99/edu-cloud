<template>
  <div>
    <n-h4 style="margin-bottom: var(--space-3)">生成</n-h4>
    <n-grid :cols="2" :x-gap="8" :y-gap="8">
      <n-gi v-for="tmpl in studioStore.templates" :key="tmpl.key">
        <n-card size="small" hoverable style="cursor: pointer" @click="$emit('select', tmpl)">
          <template #header>
            <n-text style="font-size: var(--fs-base)">{{ tmpl.name }}</n-text>
          </template>
          <n-tag v-if="tmpl.requires_approval" size="tiny" type="warning">需审批</n-tag>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const studioStore = useStudioStore()
defineEmits(['select'])
onMounted(() => studioStore.loadTemplates())
</script>
