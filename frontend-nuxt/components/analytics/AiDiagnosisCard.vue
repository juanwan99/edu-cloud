<template>
  <el-card class="diagnosis-card" v-if="!empty">
    <template #header>
      <div class="header-row">
        <el-icon><MagicStick /></el-icon>
        <span>AI 诊断</span>
      </div>
    </template>
    <p class="diagnosis-text">{{ text }}</p>
    <div v-if="suggestions.length" class="suggestions">
      <div v-for="(s, i) in suggestions" :key="i" class="suggestion-item">
        <el-tag size="small" type="warning">建议 {{ i + 1 }}</el-tag>
        <span>{{ s }}</span>
      </div>
    </div>
    <div v-if="weakQuestions.length" class="weak-section">
      <div class="weak-title">薄弱题目</div>
      <el-tag v-for="q in weakQuestions" :key="q.name" type="danger" size="small" class="weak-tag">
        第{{ q.name }}题 ({{ (q.score_rate * 100).toFixed(0) }}%)
      </el-tag>
    </div>
  </el-card>
  <el-empty v-else description="暂无 AI 诊断数据（需要 AI 阅卷数据支持）" />
</template>

<script setup lang="ts">
import { MagicStick } from '@element-plus/icons-vue'

const props = defineProps<{
  text?: string
  suggestions?: string[]
  weakQuestions?: { name: string; score_rate: number }[]
}>()

const empty = computed(() => !props.text || props.text === '暂无诊断数据。')
</script>

<style scoped>
.diagnosis-card { border-left: 4px solid var(--el-color-primary); }
.header-row { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.diagnosis-text { font-size: 15px; line-height: 1.8; color: var(--el-text-color-regular); margin: 0; }
.suggestions { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.suggestion-item { display: flex; align-items: center; gap: 8px; }
.weak-section { margin-top: 12px; }
.weak-title { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 6px; }
.weak-tag { margin-right: 6px; }
</style>
