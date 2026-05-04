<template>
  <div class="study-unit-detail">
    <div v-if="!data" class="empty-state">请选择一个学习单元</div>
    <template v-else>
      <!-- Header -->
      <div class="detail-header">
        <div class="header-top">
          <button
            class="back-btn"
            data-testid="back-btn"
            @click="$emit('back')"
          >← 返回模块</button>
          <div class="hours-badge">{{ estimatedHours }} 课时</div>
        </div>
        <h2 class="unit-name">{{ data.name }}</h2>
        <p v-if="data.description" class="unit-desc">{{ data.description }}</p>
        <div class="textbook-pills">
          <span
            v-for="(tb, i) in data.textbook || []"
            :key="i"
            class="textbook-pill"
          >{{ tb.book }} · {{ tb.section }} {{ tb.page_range }}</span>
        </div>
      </div>

      <!-- Body: two-column -->
      <div class="detail-body">
        <!-- Left: Relations -->
        <div class="col-left">
          <!-- Prerequisites -->
          <div v-if="prerequisites.length" class="relation-section">
            <div class="section-title">前置关系</div>
            <div
              v-for="(rel, i) in prerequisites"
              :key="i"
              class="relation-card"
            >
              <span class="rel-category prereq">{{ rel.category }}</span>
              <span class="rel-name">{{ rel.target_name }}</span>
              <span v-if="rel.target_module" class="rel-module">{{ rel.target_module }}</span>
              <details v-if="rel.evidence" class="rel-evidence">
                <summary>为什么</summary>
                <p>{{ rel.evidence }}</p>
              </details>
            </div>
          </div>

          <!-- Successors -->
          <div v-if="successors.length" class="relation-section">
            <div class="section-title">后续单元</div>
            <div
              v-for="(rel, i) in successors"
              :key="i"
              class="relation-card"
            >
              <span class="rel-category successor">{{ rel.category }}</span>
              <span class="rel-name">{{ rel.target_name }}</span>
              <span v-if="rel.target_module" class="rel-module">{{ rel.target_module }}</span>
            </div>
          </div>

          <!-- Contrasts -->
          <div v-if="contrasts.length" class="relation-section">
            <div class="section-title">对比关系</div>
            <div
              v-for="(rel, i) in contrasts"
              :key="i"
              class="relation-card"
            >
              <span class="rel-category contrast">{{ rel.category }}</span>
              <span class="rel-name">{{ rel.target_name }}</span>
              <details v-if="rel.evidence" class="rel-evidence">
                <summary>对比依据</summary>
                <p>{{ rel.evidence }}</p>
              </details>
            </div>
          </div>

          <div
            v-if="!prerequisites.length && !successors.length && !contrasts.length"
            class="empty-relations"
          >暂无关联关系</div>
        </div>

        <!-- Right: Curriculum + Exam Patterns -->
        <div class="col-right">
          <!-- Curriculum requirements -->
          <div v-if="data.curriculum && data.curriculum.length" class="curriculum-section">
            <div class="section-title">课标要求</div>
            <div
              v-for="(req, i) in data.curriculum"
              :key="i"
              class="curriculum-item"
            >
              <span class="mastery-verb">{{ req.mastery_verb }}</span>
              <span class="req-text">{{ req.text }}</span>
            </div>
          </div>

          <!-- Exam patterns -->
          <div v-if="data.exam_patterns && data.exam_patterns.length" class="exam-patterns-section">
            <div class="section-title">题目分布</div>
            <div
              v-for="band in data.exam_patterns"
              :key="band.band"
              class="band-group"
              :class="bandClass(band.band)"
            >
              <div class="band-header">
                <span class="band-name">{{ band.band }}</span>
                <span class="band-count">{{ band.count }} 题</span>
              </div>
              <div
                v-for="item in (band.sample_items || []).slice(0, 2)"
                :key="item.id"
                class="sample-item"
              >{{ truncate(item.stem, 60) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Concepts (bottom) -->
      <div v-if="data.concepts && data.concepts.length" class="concepts-section">
        <div class="section-title">关联概念</div>
        <div class="concepts-pills">
          <span
            v-for="concept in data.concepts"
            :key="concept.id"
            class="concept-pill"
            data-testid="concept-pill"
            @click="$emit('select-concept', concept.id)"
          >
            <span class="concept-level">{{ concept.level }}</span>
            {{ concept.name }}
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, default: null },
})

defineEmits(['select-concept', 'back'])

const estimatedHours = computed(() => {
  const mins = props.data?.estimated_minutes || 0
  return Math.max(1, Math.round(mins / 45))
})

const prerequisites = computed(() =>
  (props.data?.prerequisites || []).filter((r) => r.category === '必经前置' || r.category?.includes('前置'))
)

const successors = computed(() =>
  (props.data?.successors || []).filter((r) => r.category === '后续单元' || r.category?.includes('后续'))
)

const contrasts = computed(() =>
  (props.data?.contrasts || []).filter((r) => r.category === '对比关系' || r.category?.includes('对比'))
)

function bandClass(band) {
  if (band === '基础调用') return 'band-basic'
  if (band === '情境应用') return 'band-context'
  if (band === '综合迁移') return 'band-transfer'
  return ''
}

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}
</script>

<style scoped>
.study-unit-detail {
  padding: var(--space-4, 16px);
  height: 100%;
  overflow-y: auto;
  color: var(--color-text, #09061B);
  background: var(--color-bg-card, #ffffff);
}

.empty-state {
  text-align: center;
  color: var(--color-text-secondary, #5a5a68);
  padding: 40px;
}

/* Header */
.detail-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border, #E8E8EF);
}

.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.back-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary, #644CF0);
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}
.back-btn:hover {
  background: rgba(100, 76, 240, 0.08);
}

.hours-badge {
  background: var(--color-primary, #644CF0);
  color: #fff;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 600;
}

.unit-name {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text, #09061B);
}

.unit-desc {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--color-text-secondary, #5a5a68);
  line-height: 1.5;
}

.textbook-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.textbook-pill {
  background: rgba(100, 76, 240, 0.08);
  color: var(--color-primary, #644CF0);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 10px;
  border: 1px solid rgba(100, 76, 240, 0.2);
}

/* Body layout */
.detail-body {
  display: grid;
  grid-template-columns: 40% 60%;
  gap: 20px;
  margin-bottom: 20px;
}

/* Section title */
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary, #5a5a68);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

/* Relations */
.relation-section {
  margin-bottom: 16px;
}

.relation-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--color-bg-card, #ffffff);
  border: 1px solid var(--color-border, #E8E8EF);
  border-radius: 6px;
  margin-bottom: 6px;
}

.rel-category {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 8px;
}
.rel-category.prereq {
  background: rgba(220, 38, 38, 0.1);
  color: var(--color-danger, #dc2626);
}
.rel-category.successor {
  background: rgba(34, 197, 94, 0.1);
  color: var(--color-success, #22C55E);
}
.rel-category.contrast {
  background: rgba(237, 154, 81, 0.1);
  color: var(--color-warning, #ED9A51);
}

.rel-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text, #09061B);
}

.rel-module {
  font-size: 11px;
  color: var(--color-text-secondary, #5a5a68);
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px;
  border-radius: 4px;
}

.rel-evidence {
  width: 100%;
  font-size: 12px;
  color: var(--color-text-secondary, #5a5a68);
}
.rel-evidence summary {
  cursor: pointer;
  color: var(--color-primary, #644CF0);
}
.rel-evidence p {
  margin: 4px 0 0;
  padding-left: 8px;
  border-left: 2px solid var(--color-border, #E8E8EF);
}

.empty-relations {
  font-size: 13px;
  color: var(--color-text-secondary, #5a5a68);
  text-align: center;
  padding: 20px;
}

/* Curriculum */
.curriculum-section {
  margin-bottom: 16px;
}

.curriculum-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(244, 218, 76, 0.08);
  border: 1px solid rgba(244, 218, 76, 0.3);
  border-radius: 6px;
  margin-bottom: 6px;
}

.mastery-verb {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--color-accent, #F4DA4C);
  color: var(--color-text, #09061B);
}

.req-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text, #09061B);
}

/* Exam patterns */
.exam-patterns-section {
  margin-bottom: 16px;
}

.band-group {
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
  border-left: 3px solid transparent;
}
.band-basic {
  background: rgba(34, 197, 94, 0.06);
  border-left-color: var(--color-success, #22C55E);
}
.band-context {
  background: rgba(237, 154, 81, 0.06);
  border-left-color: var(--color-warning, #ED9A51);
}
.band-transfer {
  background: rgba(220, 38, 38, 0.06);
  border-left-color: var(--color-danger, #dc2626);
}

.band-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.band-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text, #09061B);
}

.band-count {
  font-size: 12px;
  color: var(--color-text-secondary, #5a5a68);
}

.sample-item {
  font-size: 12px;
  color: var(--color-text-secondary, #5a5a68);
  margin-top: 3px;
  line-height: 1.4;
  padding-left: 4px;
}

/* Concepts */
.concepts-section {
  border-top: 1px solid var(--color-border, #E8E8EF);
  padding-top: 16px;
}

.concepts-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.concept-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: var(--color-bg-card, #ffffff);
  border: 1px solid var(--color-border, #E8E8EF);
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  color: var(--color-text, #09061B);
}
.concept-pill:hover {
  border-color: var(--color-primary, #644CF0);
  background: rgba(100, 76, 240, 0.05);
}

.concept-level {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 6px;
  background: var(--color-primary, #644CF0);
  color: #fff;
}

@media (max-width: 768px) {
  .detail-body {
    grid-template-columns: 1fr;
  }
}
</style>
