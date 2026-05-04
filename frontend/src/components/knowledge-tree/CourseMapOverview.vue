<template>
  <div class="course-map-overview">
    <template v-if="data">
      <div class="layout-two-col">
        <!-- Left: module cards -->
        <div class="col-left">
          <div
            v-for="mod in data.modules"
            :key="mod.id"
            class="module-card"
            data-testid="module-card"
            @click="$emit('select-module', mod.id)"
          >
            <div class="module-card-header">
              <span class="module-id-badge">{{ mod.id }}</span>
              <span class="module-name">{{ mod.name }}</span>
            </div>
            <p class="module-tagline">{{ mod.tagline }}</p>
            <div class="module-stats-row">
              <span>{{ mod.study_unit_count }} 个单元</span>
              <span class="dot-sep">·</span>
              <span>{{ mod.concept_count }} 个概念</span>
              <span class="dot-sep">·</span>
              <span>{{ mod.total_hours }} 课时</span>
            </div>
            <div v-if="mod.exam_tags && mod.exam_tags.length > 0" class="exam-tags-row">
              <span
                v-for="tag in mod.exam_tags"
                :key="tag"
                class="exam-tag"
              >{{ tag }}</span>
            </div>
          </div>
        </div>

        <!-- Right: bridges + curriculum/exam summary -->
        <div class="col-right">
          <!-- Cross-module bridges -->
          <div v-if="data.bridges && data.bridges.length > 0" class="section bridges-section">
            <h3 class="section-title">跨模块关联</h3>
            <div class="bridge-list">
              <div
                v-for="(bridge, idx) in data.bridges"
                :key="idx"
                class="bridge-item"
                :title="bridge.evidence"
              >
                <span class="bridge-source">{{ bridge.source_name }}</span>
                <span class="bridge-arrow">→</span>
                <span class="bridge-target">{{ bridge.target_name }}</span>
              </div>
            </div>
          </div>

          <!-- Curriculum summary -->
          <div v-if="data.curriculum" class="section curriculum-section">
            <h3 class="section-title">课标概况</h3>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-value">{{ data.curriculum.content_count }}</span>
                <span class="summary-label">内容要求</span>
              </div>
              <div class="summary-item">
                <span class="summary-value">{{ data.curriculum.academic_count }}</span>
                <span class="summary-label">学业要求</span>
              </div>
            </div>
            <div v-if="data.curriculum.big_concepts && data.curriculum.big_concepts.length > 0" class="big-concepts-list">
              <span
                v-for="(concept, idx) in data.curriculum.big_concepts"
                :key="idx"
                class="big-concept-tag"
              >{{ concept }}</span>
            </div>
          </div>

          <!-- Exam summary -->
          <div v-if="data.exam" class="section exam-section">
            <h3 class="section-title">高考真题</h3>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-value">{{ data.exam.total_items }}</span>
                <span class="summary-label">总题目</span>
              </div>
              <div class="summary-item">
                <span class="summary-value">{{ data.exam.near_count }}</span>
                <span class="summary-label">近五年</span>
              </div>
              <div class="summary-item">
                <span class="summary-value">{{ data.exam.mid_count }}</span>
                <span class="summary-label">五至十年</span>
              </div>
              <div class="summary-item">
                <span class="summary-value">{{ data.exam.far_count }}</span>
                <span class="summary-label">十年以上</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template v-else>
      <n-empty description="暂无数据" />
    </template>
  </div>
</template>

<script setup>
import { NEmpty } from 'naive-ui'

defineProps({
  data: { type: Object, default: null },
})

defineEmits(['select-module'])
</script>

<style scoped>
.course-map-overview {
  padding: var(--space-6);
  height: 100%;
  overflow-y: auto;
}

.layout-two-col {
  display: flex;
  gap: var(--space-6);
  align-items: flex-start;
}

.col-left {
  flex: 0 0 65%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.col-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* Module card */
.module-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  cursor: pointer;
  transition: var(--transition);
  box-shadow: var(--shadow-card);
}

.module-card:hover {
  box-shadow: var(--shadow-card-hover);
  border-color: var(--color-primary-light);
  transform: translateY(-1px);
}

.module-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.module-id-badge {
  background: var(--color-primary);
  color: #ffffff;
  font-size: var(--fs-xs);
  font-weight: var(--fw-semibold);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  flex-shrink: 0;
}

.module-name {
  font-size: var(--fs-lg);
  font-weight: var(--fw-bold);
  color: var(--color-text);
}

.module-tagline {
  font-size: var(--fs-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-3);
}

.module-stats-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--fs-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.dot-sep {
  color: var(--color-text-muted);
}

.exam-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.exam-tag {
  background: var(--color-warning);
  color: #ffffff;
  font-size: var(--fs-xs);
  font-weight: var(--fw-medium);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
}

/* Right column sections */
.section {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.section-title {
  font-size: var(--fs-sm);
  font-weight: var(--fw-semibold);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* Bridges */
.bridge-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.bridge-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--fs-sm);
  padding: var(--space-2) var(--space-3);
  background: var(--surface-primary-light);
  border-radius: var(--radius-sm);
  cursor: default;
}

.bridge-source,
.bridge-target {
  color: var(--color-text);
  font-weight: var(--fw-medium);
}

.bridge-arrow {
  color: var(--color-primary);
  font-weight: var(--fw-bold);
}

/* Summary grid */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.summary-grid:last-child {
  margin-bottom: 0;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-2);
}

.summary-value {
  font-size: var(--fs-xl);
  font-weight: var(--fw-bold);
  color: var(--color-text);
  line-height: var(--lh-tight);
}

.summary-label {
  font-size: var(--fs-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

/* Curriculum big concept tags */
.big-concepts-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.big-concept-tag {
  background: var(--surface-accent);
  color: var(--color-text);
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--color-accent);
}
</style>
