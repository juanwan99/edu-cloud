<template>
  <div class="study-unit-tab">
    <div v-if="!node.study_unit_id" class="empty">该概念暂无关联学习单元</div>
    <div v-else>
      <div class="field-row">
        <span class="label">学习单元 ID：</span>
        <span class="value">{{ node.study_unit_id }}</span>
      </div>
      <div class="field-row">
        <span class="label">建议学习时间：</span>
        <span class="value">{{ node.estimated_minutes }} 分钟</span>
      </div>
      <div class="field-row">
        <span class="label">前置深度：</span>
        <span class="value">{{ node.prerequisite_depth }}</span>
      </div>
      <div v-if="node.planning_weight" class="weight-section">
        <div class="section-title">规划权重</div>
        <div class="weight-grid">
          <div class="weight-item">
            <span class="weight-label">考频</span>
            <span class="weight-value">{{ node.planning_weight.exam_frequency ?? '—' }}</span>
          </div>
          <div class="weight-item">
            <span class="weight-label">易错度</span>
            <span class="weight-value">{{ node.planning_weight.error_prone ?? '—' }}</span>
          </div>
          <div class="weight-item">
            <span class="weight-label">迁移价值</span>
            <span class="weight-value">{{ node.planning_weight.transfer_value ?? '—' }}</span>
          </div>
          <div class="weight-item priority">
            <span class="weight-label">综合优先级</span>
            <span class="weight-value">{{ node.planning_weight.priority_score ?? '—' }}</span>
          </div>
        </div>
      </div>
      <div v-if="node.textbook_chapters && node.textbook_chapters.length" class="chapters-section">
        <div class="section-title">教材定位</div>
        <div v-for="(ch, i) in node.textbook_chapters" :key="i" class="chapter-item">
          {{ ch.book }} / {{ ch.chapter }} / {{ ch.title }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  node: { type: Object, required: true },
})
</script>

<style scoped>
.study-unit-tab { padding: 8px; }
.empty { text-align: center; color: var(--text-color-3); padding: 20px; }
.field-row { display: flex; margin-bottom: 8px; }
.label { color: var(--text-color-2); width: 100px; }
.value { color: var(--text-color-1); }
.section-title { font-weight: 600; margin: 14px 0 6px; color: var(--text-color-1); }
.weight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.weight-item { display: flex; justify-content: space-between; padding: 4px 8px; background: var(--card-color); border-radius: 3px; }
.weight-item.priority { grid-column: 1 / -1; background: var(--primary-color-hover); color: white; }
.weight-label { font-size: 16px; }
.weight-value { font-weight: 600; }
.chapter-item { padding: 4px 8px; background: var(--card-color); border-radius: 3px; margin-bottom: 4px; font-size: 16px; }
</style>
