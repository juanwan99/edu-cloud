import { ref, computed } from 'vue'

export function useImageZoom() {
  const scale = ref(1)
  const translateX = ref(0)
  const translateY = ref(0)
  const dragging = ref(false)
  const dragMoved = ref(false)
  const dragStart = ref({ x: 0, y: 0 })
  const dragOrigin = ref({ x: 0, y: 0 })

  const imageTransform = computed(() => ({
    transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
    cursor: dragging.value ? 'grabbing' : 'grab',
  }))

  function resetZoom() {
    scale.value = 1
    translateX.value = 0
    translateY.value = 0
  }

  function zoomIn() {
    scale.value = Math.min(5, scale.value + 0.2)
  }

  function zoomOut() {
    scale.value = Math.max(0.3, scale.value - 0.2)
  }

  function handleWheel(e) {
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    scale.value = Math.max(0.3, Math.min(5, scale.value + delta))
  }

  function handleFloatingWheel(e) {
    if (!e.ctrlKey) return
    e.preventDefault()
    handleWheel(e)
  }

  function startDrag(e) {
    if (e.button !== 0) return
    e.preventDefault()
    dragging.value = true
    dragMoved.value = false
    dragOrigin.value = { x: e.clientX, y: e.clientY }
    dragStart.value = { x: e.clientX - translateX.value, y: e.clientY - translateY.value }
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
  }

  function onDrag(e) {
    if (!dragging.value) return
    if (Math.abs(e.clientX - dragOrigin.value.x) > 4 || Math.abs(e.clientY - dragOrigin.value.y) > 4) {
      dragMoved.value = true
    }
    translateX.value = e.clientX - dragStart.value.x
    translateY.value = e.clientY - dragStart.value.y
  }

  function stopDrag() {
    dragging.value = false
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  }

  function cleanup() {
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  }

  return {
    scale, translateX, translateY, dragging, dragMoved,
    imageTransform,
    resetZoom, zoomIn, zoomOut,
    handleWheel, handleFloatingWheel,
    startDrag, stopDrag, cleanup,
  }
}
