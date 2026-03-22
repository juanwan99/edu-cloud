<template>
  <n-modal v-model:show="visible" preset="card" style="width: 700px" :title="doc?.title || '文档预览'">
    <template v-if="doc">
      <div v-for="(section, key) in doc.content_json" :key="key" style="margin-bottom: 16px">
        <n-h4>{{ section.title || key }}</n-h4>
        <n-input
          v-model:value="editableContent[key]"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 10 }"
          placeholder="AI 将在此生成内容..."
        />
      </div>
      <n-space justify="end" style="margin-top: 16px">
        <n-button @click="handleSave">保存修改</n-button>
        <n-button type="primary" @click="handleConfirm">
          {{ doc.status === 'draft' ? '确认审阅' : '导出 PDF' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const props = defineProps({ doc: Object })
const visible = defineModel('show', { type: Boolean })
const studioStore = useStudioStore()
const editableContent = ref({})

watch(() => props.doc, (newDoc) => {
  if (newDoc?.content_json) {
    const content = {}
    for (const [key, section] of Object.entries(newDoc.content_json)) {
      content[key] = section.content || section || ''
    }
    editableContent.value = content
  }
}, { immediate: true })

async function handleSave() {
  const updated = { ...props.doc.content_json }
  for (const [key, val] of Object.entries(editableContent.value)) {
    if (typeof updated[key] === 'object') updated[key].content = val
    else updated[key] = val
  }
  await studioStore.updateDocument(props.doc.id, updated, '手动编辑')
}

async function handleConfirm() {
  if (props.doc.status === 'draft') {
    await studioStore.transitionStatus(props.doc.id, 'reviewed')
  }
}
</script>
