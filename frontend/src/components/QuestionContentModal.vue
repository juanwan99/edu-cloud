<template>
  <n-modal
    :show="show"
    preset="card"
    :title="title"
    style="width: 600px; max-width: 90vw;"
    @update:show="emit('update:show', $event)"
  >
    <n-space vertical size="medium">
      <div>
        <div class="field-label">文字内容</div>
        <n-input
          v-model:value="localContent"
          type="textarea"
          :rows="6"
          placeholder="请输入内容，支持 Ctrl+V 粘贴图片..."
          @paste="onPaste"
        />
      </div>

      <div v-if="allImages.length">
        <div class="field-label">图片 ({{ allImages.length }})</div>
        <div class="image-list">
          <div v-for="(img, idx) in allImages" :key="idx" class="preview-wrapper">
            <img :src="img.src" class="preview-img" alt="图片" />
            <span class="preview-seq">{{ idx + 1 }}</span>
            <span v-if="img.fromPaste" class="paste-badge">粘贴</span>
            <n-button class="preview-delete" size="tiny" circle type="error"
                      @click="removePreviewImage(idx)">✕</n-button>
          </div>
        </div>
      </div>

      <div>
        <div class="field-label">上传图片</div>
        <n-upload accept="image/*" :show-file-list="false" :custom-request="onUploadSelect">
          <n-button size="small">选择图片</n-button>
        </n-upload>
      </div>
    </n-space>

    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" @click="handleSave">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage, NModal, NInput, NUpload, NButton, NSpace } from 'naive-ui'

const props = defineProps({
  show: Boolean,
  title: String,
  content: String,
  images: Array,
})

const emit = defineEmits(['update:show', 'save'])
const message = useMessage()

const localContent = ref('')
const newFiles = ref([])

watch(() => props.show, (val) => {
  if (val) {
    localContent.value = props.content || ''
    newFiles.value = []
  }
})

const allImages = computed(() => {
  const existing = (props.images || []).map(src => ({ src, fromPaste: false, file: null }))
  const added = newFiles.value.map(f => ({
    src: URL.createObjectURL(f.file),
    fromPaste: f.fromPaste,
    file: f.file,
  }))
  return [...existing, ...added]
})

async function onPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) {
        newFiles.value.push({ file, fromPaste: true })
        message.success('已粘贴图片')
      }
      return
    }
  }
  const html = e.clipboardData?.getData('text/html')
  if (html && /<(table|img|div)\b/i.test(html)) {
    e.preventDefault()
    message.info('正在将富文本转为图片...')
    try {
      const file = await htmlToImageFile(html)
      newFiles.value.push({ file, fromPaste: true })
      message.success('已将富文本粘贴为图片')
    } catch (err) {
      message.warning('富文本转图片失败，已粘贴为纯文本')
      localContent.value += e.clipboardData?.getData('text/plain') || ''
    }
  }
}

async function htmlToImageFile(html) {
  const { default: html2canvas } = await import('html2canvas')
  const container = document.createElement('div')
  Object.assign(container.style, {
    position: 'fixed', left: '-9999px', top: '0',
    background: '#fff', color: '#1a1a1a', padding: 'var(--space-4)',
    fontSize: 'var(--fs-base)', lineHeight: '1.6', maxWidth: '800px',
  })
  container.innerHTML = html
  document.body.appendChild(container)
  try {
    const canvas = await html2canvas(container, { scale: 2, useCORS: true })
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'))
    return new File([blob], `paste-${Date.now()}.png`, { type: 'image/png' })
  } finally {
    document.body.removeChild(container)
  }
}

function onUploadSelect({ file }) {
  if (file.file) {
    newFiles.value.push({ file: file.file, fromPaste: false })
  }
}

function removePreviewImage(idx) {
  const existingCount = (props.images || []).length
  if (idx < existingCount) {
    return
  }
  newFiles.value.splice(idx - existingCount, 1)
}

function handleSave() {
  emit('save', {
    content: localContent.value,
    files: newFiles.value.map(f => f.file),
  })
  emit('update:show', false)
}
</script>

<style scoped>
.field-label {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-bottom: 6px;
  font-weight: var(--fw-medium);
}
.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.preview-wrapper {
  position: relative;
  display: inline-block;
}
.preview-wrapper:hover .preview-delete { opacity: 1; }
.preview-img {
  max-width: 200px;
  max-height: 160px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e2e8e4);
  object-fit: contain;
}
.preview-seq {
  position: absolute; top: var(--space-1); left: var(--space-1);
  background: rgba(0,0,0,0.6); color: var(--color-bg, #fff);
  font-size: var(--fs-base); padding: 1px 5px; border-radius: 3px;
}
.paste-badge {
  position: absolute; bottom: var(--space-1); left: var(--space-1);
  background: var(--color-primary, #409eff); color: var(--color-bg, #fff);
  font-size: var(--fs-base); padding: 1px 4px; border-radius: 3px;
}
.preview-delete {
  position: absolute; top: var(--space-1); right: var(--space-1);
  opacity: 0; transition: opacity 0.15s;
}
</style>
