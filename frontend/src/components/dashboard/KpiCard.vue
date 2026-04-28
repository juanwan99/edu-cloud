<template>
  <div :class="['kpi-card', `kpi-card--${color}`]">
    <div class="kpi-card__value">{{ displayValue }}</div>
    <div class="kpi-card__label">{{ label }}</div>
    <div v-if="sublabel" class="kpi-card__sublabel">{{ sublabel }}</div>
    <div v-if="trend" :class="['kpi-card__trend', `kpi-card__trend--${trend}`]">
      {{ trend === 'up' ? '\u2191' : '\u2193' }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: [String, Number], default: null },
  label: { type: String, required: true },
  sublabel: { type: String, default: '' },
  color: {
    type: String,
    default: 'mint',
    validator: v => ['mint', 'yellow', 'coral', 'purple'].includes(v),
  },
  trend: {
    type: String,
    default: '',
    validator: v => !v || ['up', 'down'].includes(v),
  },
})

const displayValue = computed(() =>
  props.value == null || props.value === '' ? '--' : props.value
)
</script>

<style scoped>
.kpi-card {
  padding: 18px 20px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}

.kpi-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

/* Color variants */
.kpi-card--mint { background: var(--macaron-mint-light); }
.kpi-card--yellow { background: var(--macaron-yellow-light); }
.kpi-card--coral { background: var(--macaron-coral-light); }
.kpi-card--purple { background: var(--macaron-purple-light); }

.kpi-card__value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-primary);
  letter-spacing: -0.02em;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.kpi-card__label {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.kpi-card__sublabel {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.kpi-card__trend {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}

.kpi-card__trend--up { color: var(--color-success, #16a34a); }
.kpi-card__trend--down { color: var(--color-danger, #dc2626); }
</style>
