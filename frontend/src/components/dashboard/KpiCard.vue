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
  padding: 22px 26px;
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
.kpi-card--mint { background: linear-gradient(145deg, var(--macaron-mint-light) 0%, #a7f3d0 130%); }
.kpi-card--yellow { background: linear-gradient(145deg, var(--macaron-yellow-light) 0%, #fde68a 130%); }
.kpi-card--coral { background: linear-gradient(145deg, var(--macaron-coral-light) 0%, #fecaca 130%); }
.kpi-card--purple { background: linear-gradient(145deg, var(--macaron-purple-light) 0%, #c4b5fd 130%); }

.kpi-card__value {
  font-size: 36px;
  font-weight: 800;
  color: var(--color-primary);
  letter-spacing: -0.03em;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.kpi-card__label {
  font-size: 16px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}

.kpi-card__sublabel {
  font-size: 16px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.kpi-card__trend {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255,255,255,0.7);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
}

.kpi-card__trend--up { color: var(--color-success, #16a34a); }
.kpi-card__trend--down { color: var(--color-danger, #dc2626); }
</style>
