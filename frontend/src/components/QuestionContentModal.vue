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
          placeholder="请输入内容..."
        />
      </div>

      <div v-if="images && images.length > 0">
        <div class="field-label">图片</div>
        <div class="image-list">
          <img
            v-for="(img, idx) in images"
            :key="idx"
            :src="img"
            class="preview-img"
            alt="题目图片"
          />
        </div>
      </div>

      <div>
        <div class="field-label">上传图片</div>
        <n-upload accept="image/*" :show-file-list="true" @change="onUploadChange">
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
import { ref, watch } from 'vue'
import { NModal, NInput, NUpload, NButton, NSpace } from 'naive-ui'

const props = defineProps({
  show: Boolean,
  title: String,
  content: String,
  images: Array,
})

const emit = defineEmits(['update:show', 'save'])

const localContent = ref('')
const uploadedFiles = ref([])

watch(() => props.show, (val) => {
  if (val) {
    localContent.value = props.content || ''
    uploadedFiles.value = []
  }
})

function onUploadChange({ fileList }) {
  uploadedFiles.value = fileList.map(f => f.file).filter(Boolean)
}

function handleSave() {
  emit('save', {
    content: localContent.value,
    files: uploadedFiles.value,
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
.preview-img {
  max-width: 200px;
  max-height: 160px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e2e8e4);
  object-fit: contain;
}
</style>
