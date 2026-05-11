<template>
  <div class="pull-refresh" ref="containerRef">
    <div v-if="lastUpdate" class="pull-refresh__time" :class="{ 'pull-refresh__time--visible': showTime }">
      更新于 {{ lastUpdate }}
    </div>
    <div v-if="loading" class="pull-refresh__indicator">
      <div class="pull-refresh__spinner" />
    </div>
    <slot />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
const props = defineProps({
  loading: { type: Boolean, default: false },
  lastUpdate: { type: String, default: '' },
})
const emit = defineEmits(['refresh'])
const containerRef = ref(null)
const showTime = ref(!!props.lastUpdate)
let startY = 0
let pulling = false
function onTouchStart(e) {
  if (props.loading) return
  if (containerRef.value?.scrollTop > 0) return
  startY = e.touches[0].clientY
  pulling = true
}
function onTouchEnd(e) {
  if (!pulling) return
  pulling = false
  const diff = e.changedTouches[0].clientY - startY
  if (diff > 60) emit('refresh')
}
onMounted(() => {
  const el = containerRef.value
  if (!el) return
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
})
onUnmounted(() => {
  const el = containerRef.value
  if (!el) return
  el.removeEventListener('touchstart', onTouchStart)
  el.removeEventListener('touchend', onTouchEnd)
})
let fadeTimer
watch(() => props.lastUpdate, (v) => {
  if (!v) return
  showTime.value = true
  clearTimeout(fadeTimer)
  fadeTimer = setTimeout(() => { showTime.value = false }, 3000)
})
</script>

<style scoped>
.pull-refresh { position: relative; }
.pull-refresh__time { text-align: center; font-size: var(--p-fs-label, 13px); color: var(--p-text-3, #9B93B5); padding: 4px 0; opacity: 0; transition: opacity 0.3s; }
.pull-refresh__time--visible { opacity: 1; }
.pull-refresh__indicator { display: flex; justify-content: center; padding: 12px 0; }
.pull-refresh__spinner { width: 24px; height: 24px; border: 2px solid var(--p-color-accent, #F4DA4C); border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
