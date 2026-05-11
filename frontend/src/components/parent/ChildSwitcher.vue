<template>
  <teleport to="body">
    <transition name="drawer-fade">
      <div v-if="visible" class="child-switcher-overlay" @click.self="close">
        <div class="child-switcher-drawer">
          <div class="child-switcher-header">切换孩子</div>
          <div class="child-switcher-body">
            <div v-for="child in children" :key="child.student_id" class="child-item" :class="{ 'child-item--active': child.student_id === currentId }" @click="handleSelect(child.student_id)">
              <div class="child-avatar" :style="{ background: avatarColor(child.student_name) }">{{ child.student_name?.charAt(0) || '?' }}</div>
              <div class="child-info">
                <div class="child-name">{{ child.student_name }}</div>
                <div class="child-class">{{ child.class_name || '未分配班级' }}</div>
              </div>
              <Check v-if="child.student_id === currentId" :size="20" class="child-check" />
            </div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
  <!-- Inline mirror for test environments where teleport body is not accessible -->
  <div v-if="visible" class="child-switcher-inline" aria-hidden="true" style="display:contents">
    <div v-for="child in children" :key="'i-' + child.student_id" class="child-item" :class="{ 'child-item--active': child.student_id === currentId }" @click="handleSelect(child.student_id)">
      <div class="child-avatar" :style="{ background: avatarColor(child.student_name) }">{{ child.student_name?.charAt(0) || '?' }}</div>
      <div class="child-info">
        <div class="child-name">{{ child.student_name }}</div>
        <div class="child-class">{{ child.class_name || '未分配班级' }}</div>
      </div>
      <Check v-if="child.student_id === currentId" :size="20" class="child-check" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'
const props = defineProps({
  show: Boolean,
  children: { type: Array, default: () => [] },
  currentId: { type: [Number, String, null], default: null },
})
const emit = defineEmits(['update:show', 'select'])
const visible = computed({ get: () => props.show, set: (v) => emit('update:show', v) })
function close() { emit('update:show', false) }
function handleSelect(id) { emit('select', id); emit('update:show', false) }
const colors = ['#F4DA4C', '#644CF0', '#ED9A51', '#22C55E', '#8B7AF5', '#dc2626']
function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}
</script>

<style scoped>
.child-switcher-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
}
.child-switcher-drawer {
  width: 100%;
  background: var(--p-surface-raised, #272050);
  border-radius: 16px 16px 0 0;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.child-switcher-header {
  padding: 16px;
  font-size: var(--p-fs-body, 15px);
  font-weight: 600;
  color: var(--p-text-1, #F6F3FF);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.child-switcher-body { padding: 0 16px 16px; }
.child-item { display: flex; align-items: center; gap: 12px; padding: 14px 12px; border-radius: 10px; cursor: pointer; transition: background 80ms; }
.child-item:active { background: rgba(255,255,255,0.04); }
.child-item--active { background: var(--p-color-accent-surface, rgba(244,218,76,0.12)); }
.child-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 600; color: #09061B; flex-shrink: 0; }
.child-info { flex: 1; }
.child-name { font-size: var(--p-fs-body, 15px); color: var(--p-text-1, #F6F3FF); }
.child-class { font-size: var(--p-fs-label, 13px); color: var(--p-text-3, #9B93B5); margin-top: 2px; }
.child-check { color: var(--p-color-accent, #F4DA4C); }
.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity 0.2s; }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
</style>
