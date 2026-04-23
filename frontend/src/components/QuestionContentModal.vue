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

function onPaste(e) {
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
  font-size: 12px;
  color: #8a9a8e;
  margin-bottom: 6px;
  font-weight: 500;
}
.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
  position: absolute; top: 4px; left: 4px;
  background: rgba(0,0,0,0.6); color: #fff;
  font-size: 10px; padding: 1px 5px; border-radius: 3px;
}
.paste-badge {
  position: absolute; bottom: 4px; left: 4px;
  background: #409eff; color: #fff;
  font-size: 9px; padding: 1px 4px; border-radius: 3px;
}
.preview-delete {
  position: absolute; top: 4px; right: 4px;
  opacity: 0; transition: opacity 0.15s;
}
</style>
