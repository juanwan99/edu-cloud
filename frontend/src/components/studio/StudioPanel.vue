<template>
  <div style="padding: 12px; height: 100%; display: flex; flex-direction: column; overflow-y: auto;">
    <TemplateCards @select="handleTemplateSelect" />

    <n-divider />

    <n-h4>文档</n-h4>
    <n-list v-if="studioStore.documents.length">
      <n-list-item v-for="doc in studioStore.documents" :key="doc.id" style="cursor: pointer" @click="openDoc(doc)">
        <n-thing :title="doc.title">
          <template #description>
            <n-space size="small">
              <n-tag :type="statusType(doc.status)" size="small">{{ doc.status }}</n-tag>
              <n-text depth="3" style="font-size: 12px">v{{ doc.version }}</n-text>
            </n-space>
          </template>
        </n-thing>
      </n-list-item>
    </n-list>
    <n-empty v-else description="暂无文档" size="small" />

    <DocumentPreview v-model:show="showPreview" :doc="studioStore.currentDoc" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'
import { useAiChatStore } from '../../stores/aiChat.js'
import TemplateCards from './TemplateCards.vue'
import DocumentPreview from './DocumentPreview.vue'

const studioStore = useStudioStore()
const chatStore = useAiChatStore()
const showPreview = ref(false)

function statusType(status) {
  const map = { draft: 'default', reviewed: 'info', pending: 'warning', approved: 'success', executed: 'success' }
  return map[status] || 'default'
}

async function handleTemplateSelect(tmpl) {
  await chatStore.sendMessage(`请帮我生成${tmpl.name}`)
  studioStore.loadDocuments()
}

async function openDoc(doc) {
  await studioStore.getDocument(doc.id)
  showPreview.value = true
}

onMounted(() => studioStore.loadDocuments())
</script>
