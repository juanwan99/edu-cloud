<template>
  <div v-if="data" class="module-map-view">
    <!-- Header -->
    <div class="mmv-header">
      <button
        class="back-btn"
        data-testid="back-btn"
        @click="$emit('back')"
      >
        ← 返回总览
      </button>
      <div class="header-meta">
        <h2 class="module-title">{{ data.module_name }}</h2>
        <p v-if="data.tagline" class="module-tagline">{{ data.tagline }}</p>
      </div>
      <span class="hours-badge">{{ data.total_hours }} 课时</span>
    </div>

    <!-- 3-column layout -->
    <div class="mmv-body">
      <!-- Left sidebar: concept clusters -->
      <aside class="col-left">
        <h3 class="sidebar-title">概念组团</h3>
        <div
          v-for="cluster in data.concept_clusters"
          :key="cluster.big_concept"
          class="cluster-section"
        >
          <button
            class="cluster-toggle"
            @click="toggleCluster(cluster.big_concept)"
          >
            <span class="cluster-arrow">{{ openClusters.has(cluster.big_concept) ? '▾' : '▸' }}</span>
            {{ cluster.big_concept }}
          </button>
          <ul v-if="openClusters.has(cluster.big_concept)" class="cluster-list">
            <li v-for="concept in cluster.concepts" :key="concept" class="cluster-concept">
              {{ concept }}
            </li>
          </ul>
        </div>
      </aside>

      <!-- Center: study unit timeline -->
      <main class="col-center">
        <h3 class="section-title">学习单元</h3>
        <div class="timeline">
          <div
            v-for="unit in data.study_units"
            :key="unit.id"
            class="su-card"
            data-testid="su-card"
            @click="$emit('select-unit', unit.id)"
          >
            <div class="su-card-header">
              <span class="su-name">{{ unit.name }}</span>
              <span class="su-hours">{{ minutesToKeshi(unit.estimated_minutes) }} 课时</span>
            </div>
            <p v-if="unit.description" class="su-desc">{{ unit.description }}</p>
            <p v-if="unit.prerequisites && unit.prerequisites.length" class="su-prereqs">
              先学：{{ unit.prerequisites.join(', ') }}
            </p>
          </div>
        </div>
      </main>

      <!-- Right sidebar: curriculum + exam profile + bridges -->
      <aside class="col-right">
        <!-- Curriculum -->
        <section class="right-section">
          <h3 class="sidebar-title accent">课标要求</h3>
          <div
            v-for="item in data.curriculum"
            :key="item.big_concept"
            class="curriculum-item"
          >
            <div class="curriculum-concept">{{ item.big_concept }}</div>
            <ul class="curriculum-reqs">
              <li v-for="req in item.requirements" :key="req">{{ req }}</li>
            </ul>
          </div>
        </section>

        <!-- Exam profile -->
        <section v-if="data.exam_profile" class="right-section">
          <h3 class="sidebar-title warning">考频分布（{{ data.exam_profile.total_items }} 题）</h3>
          <div class="exam-bars">
            <div class="exam-bar-row">
              <span class="bar-label">近年</span>
              <div class="bar-track">
                <div
                  class="bar-fill near"
                  :style="{ width: pct(data.exam_profile.near_pct) }"
                ></div>
              </div>
              <span class="bar-pct">{{ pctLabel(data.exam_profile.near_pct) }}</span>
            </div>
            <div class="exam-bar-row">
              <span class="bar-label">中期</span>
              <div class="bar-track">
                <div
                  class="bar-fill mid"
                  :style="{ width: pct(data.exam_profile.mid_pct) }"
                ></div>
              </div>
              <span class="bar-pct">{{ pctLabel(data.exam_profile.mid_pct) }}</span>
            </div>
            <div class="exam-bar-row">
              <span class="bar-label">远期</span>
              <div class="bar-track">
                <div
                  class="bar-fill far"
                  :style="{ width: pct(data.exam_profile.far_pct) }"
                ></div>
              </div>
              <span class="bar-pct">{{ pctLabel(data.exam_profile.far_pct) }}</span>
            </div>
          </div>
        </section>

        <!-- Outgoing bridges -->
        <section v-if="data.outgoing_bridges && data.outgoing_bridges.length" class="right-section">
          <h3 class="sidebar-title">跨模块迁移</h3>
          <div
            v-for="(bridge, i) in data.outgoing_bridges"
            :key="i"
            class="bridge-item"
          >
            {{ bridge.source_name }} → {{ bridge.target_name }}
            <span class="bridge-modules">({{ bridge.source_module }} → {{ bridge.target_module }})</span>
          </div>
        </section>
      </aside>
    </div>
  </div>
  <!-- null data graceful empty -->
  <div v-else class="mmv-empty"></div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  data: { type: Object, default: null },
})

defineEmits(['select-unit', 'back'])

// Collapsible cluster state — all open by default
const openClusters = ref(new Set(
  (props.data?.concept_clusters || []).map(c => c.big_concept)
))

function toggleCluster(bigConcept) {
  if (openClusters.value.has(bigConcept)) {
    openClusters.value.delete(bigConcept)
  } else {
    openClusters.value.add(bigConcept)
  }
  // Force reactivity on Set mutation
  openClusters.value = new Set(openClusters.value)
}

function minutesToKeshi(minutes) {
  if (!minutes) return 0
  return (minutes / 45).toFixed(1).replace(/\.0$/, '')
}

function pct(v) {
  if (v == null) return '0%'
  return `${Math.round(v * 100)}%`
}

function pctLabel(v) {
  if (v == null) return '0%'
  return `${Math.round(v * 100)}%`
}
</script>

<style scoped>
.module-map-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg, #F4F5F9);
  color: var(--color-text, #09061B);
  font-size: 14px;
}

/* Header */
.mmv-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--color-bg-card, #ffffff);
  border-bottom: 1px solid var(--color-border, #E8E8EF);
  flex-shrink: 0;
}

.back-btn {
  padding: 6px 12px;
  background: var(--surface-primary, #ede9fe);
  color: var(--color-primary, #644CF0);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.15s;
}
.back-btn:hover {
  background: var(--color-primary-light, #7B68F5);
  color: #fff;
}

.header-meta {
  flex: 1;
  min-width: 0;
}

.module-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text, #09061B);
}

.module-tagline {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary, #5a5a68);
}

.hours-badge {
  padding: 4px 12px;
  background: var(--surface-primary, #ede9fe);
  color: var(--color-primary, #644CF0);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

/* 3-column body */
.mmv-body {
  display: grid;
  grid-template-columns: 20% 50% 30%;
  flex: 1;
  overflow: hidden;
}

/* Shared sidebar styles */
.col-left,
.col-right {
  overflow-y: auto;
  padding: 16px 12px;
  border-right: 1px solid var(--color-border, #E8E8EF);
}
.col-right {
  border-right: none;
  border-left: 1px solid var(--color-border, #E8E8EF);
}
.col-center {
  overflow-y: auto;
  padding: 16px 20px;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary, #5a5a68);
  margin: 0 0 12px;
}
.sidebar-title.accent {
  color: var(--color-accent, #F4DA4C);
  filter: brightness(0.75);
}
.sidebar-title.warning {
  color: var(--color-warning, #ED9A51);
}

/* Concept clusters */
.cluster-section {
  margin-bottom: 8px;
}
.cluster-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text, #09061B);
  padding: 4px 0;
}
.cluster-arrow {
  font-size: 11px;
  color: var(--color-primary, #644CF0);
}
.cluster-list {
  margin: 4px 0 4px 18px;
  padding: 0;
  list-style: disc;
}
.cluster-concept {
  font-size: 12px;
  color: var(--color-text-secondary, #5a5a68);
  padding: 2px 0;
}

/* Timeline / center */
.section-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary, #5a5a68);
  margin: 0 0 16px;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.su-card {
  background: var(--color-bg-card, #ffffff);
  border: 1px solid var(--color-border, #E8E8EF);
  border-left: 3px solid var(--color-primary, #644CF0);
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.12s;
}
.su-card:hover {
  box-shadow: 0 4px 16px rgba(100, 76, 240, 0.12);
  transform: translateX(2px);
}

.su-card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}
.su-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text, #09061B);
}
.su-hours {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary, #644CF0);
  white-space: nowrap;
}
.su-desc {
  font-size: 12px;
  color: var(--color-text-secondary, #5a5a68);
  margin: 0 0 6px;
  line-height: 1.5;
}
.su-prereqs {
  font-size: 11px;
  color: var(--color-text-muted, #A0A0A8);
  margin: 0;
  font-style: italic;
}

/* Right sidebar sections */
.right-section {
  margin-bottom: 24px;
}

.curriculum-item {
  margin-bottom: 10px;
}
.curriculum-concept {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text, #09061B);
  margin-bottom: 4px;
}
.curriculum-reqs {
  margin: 0;
  padding-left: 16px;
  list-style: disc;
}
.curriculum-reqs li {
  font-size: 11px;
  color: var(--color-text-secondary, #5a5a68);
  line-height: 1.5;
  padding: 1px 0;
}

/* Exam bars */
.exam-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.exam-bar-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bar-label {
  font-size: 11px;
  width: 26px;
  color: var(--color-text-secondary, #5a5a68);
  flex-shrink: 0;
}
.bar-track {
  flex: 1;
  height: 8px;
  background: var(--color-border, #E8E8EF);
  border-radius: 4px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.bar-fill.near {
  background: var(--color-success, #22C55E);
}
.bar-fill.mid {
  background: var(--color-warning, #ED9A51);
}
.bar-fill.far {
  background: var(--color-danger, #dc2626);
}
.bar-pct {
  font-size: 11px;
  width: 30px;
  text-align: right;
  color: var(--color-text-secondary, #5a5a68);
  flex-shrink: 0;
}

/* Bridges */
.bridge-item {
  font-size: 12px;
  padding: 6px 10px;
  background: var(--color-bg, #F4F5F9);
  border-radius: 6px;
  margin-bottom: 6px;
  color: var(--color-text, #09061B);
}
.bridge-modules {
  font-size: 11px;
  color: var(--color-text-muted, #A0A0A8);
  margin-left: 4px;
}

/* Null/empty state */
.mmv-empty {
  width: 100%;
  height: 100%;
}
</style>
