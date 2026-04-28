<script setup>
defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
})
</script>

<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" fill="none">
    <!-- dashboard -->
    <template v-if="name === 'dashboard'">
      <rect x="1" y="1" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/>
      <rect x="10" y="1" width="7" height="4" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
      <rect x="10" y="7" width="7" height="10" rx="2" stroke="currentColor" stroke-width="1.3"/>
      <rect x="1" y="10" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/>
    </template>
    <!-- exam -->
    <template v-else-if="name === 'exam'">
      <rect x="3" y="1" width="12" height="16" rx="2" stroke="currentColor" stroke-width="1.3"/>
      <path d="M6 5h6M6 8h6M6 11h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </template>
    <!-- book -->
    <template v-else-if="name === 'book'">
      <path d="M2 3h5a2 2 0 012 2v10a1.5 1.5 0 00-1.5-1.5H2V3z" stroke="currentColor" stroke-width="1.3"/>
      <path d="M16 3h-5a2 2 0 00-2 2v10a1.5 1.5 0 011.5-1.5H16V3z" stroke="currentColor" stroke-width="1.3"/>
    </template>
    <!-- academic -->
    <template v-else-if="name === 'academic'">
      <path d="M9 1L1 5l8 4 8-4-8-4z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
      <path d="M3 7v5c0 2 2.7 3 6 3s6-1 6-3V7" stroke="currentColor" stroke-width="1.3"/>
      <path d="M15 5v7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </template>
    <!-- people -->
    <template v-else-if="name === 'people'">
      <circle cx="7" cy="5" r="2.5" stroke="currentColor" stroke-width="1.3"/>
      <path d="M2 15a5 5 0 0110 0" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
      <circle cx="13" cy="6" r="2" stroke="currentColor" stroke-width="1.3"/>
      <path d="M13 10c2 0 4 1.5 4 4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </template>
    <!-- school -->
    <template v-else-if="name === 'school'">
      <path d="M9 2L2 6v2h14V6L9 2z" stroke="currentColor" stroke-width="1.3"/>
      <path d="M3 9v6h12V9" stroke="currentColor" stroke-width="1.3"/>
      <rect x="7" y="11" width="4" height="4" stroke="currentColor" stroke-width="1.3"/>
    </template>
    <!-- marking -->
    <template v-else-if="name === 'marking'">
      <path d="M4 9l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    </template>
    <!-- chart -->
    <template v-else-if="name === 'chart'">
      <rect x="2" y="10" width="3" height="6" rx="1" stroke="currentColor" stroke-width="1.3"/>
      <rect x="7.5" y="6" width="3" height="10" rx="1" stroke="currentColor" stroke-width="1.3"/>
      <rect x="13" y="2" width="3" height="14" rx="1" stroke="currentColor" stroke-width="1.3"/>
    </template>
    <!-- settings -->
    <template v-else-if="name === 'settings'">
      <circle cx="9" cy="9" r="3" stroke="currentColor" stroke-width="1.3"/>
      <path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.3 3.3l1.4 1.4M13.3 13.3l1.4 1.4M3.3 14.7l1.4-1.4M13.3 4.7l1.4-1.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </template>
    <!-- calendar -->
    <template v-else-if="name === 'calendar'">
      <rect x="2" y="3" width="14" height="13" rx="2" stroke="currentColor" stroke-width="1.3"/>
      <path d="M2 7h14M6 1v4M12 1v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </template>
  </svg>
</template>
