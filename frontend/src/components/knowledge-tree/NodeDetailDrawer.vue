<template>
  <n-drawer v-model:show="visible" :width="420" placement="right">
    <n-drawer-content :title="node?.name || ''" closable>
      <template v-if="node">
        <n-descriptions :column="1" label-placement="left" size="small">
          <n-descriptions-item label="ID">
            <n-text code>{{ node.id }}</n-text>
          </n-descriptions-item>
          <n-descriptions-item label="层级">{{ node.level }}</n-descriptions-item>
          <n-descriptions-item label="模块">{{ node.module }}</n-descriptions-item>
          <n-descriptions-item label="掌握度">
            <n-tag :type="stateTagType" size="small">
              {{ node.mastery_state }} · {{ Math.round((node.mastery ?? 0) * 100) }}%
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="DA 数量">{{ node.da_count ?? 0 }}</n-descriptions-item>
        </n-descriptions>

        <!-- 详情数据（课标/教材/DA/真题） -->
        <n-spin v-if="detailLoading" style="margin: 24px auto; display: block;" />
        <n-tabs type="line" v-if="detail" style="margin-top: 12px;">
          <n-tab-pane name="curriculum" tab="课标要求">
            <div v-for="req in detail.curriculum" :key="req.requirement_id" class="detail-item">
              {{ req.content }}
            </div>
            <n-empty v-if="!detail.curriculum.length" description="暂无课标数据" />
          </n-tab-pane>
          <n-tab-pane name="textbook" tab="教材定位">
            <div v-for="tb in detail.textbook" :key="tb.section_title" class="detail-item">
              <strong>{{ tb.book }}</strong> — {{ tb.section_title }}
            </div>
            <n-empty v-if="!detail.textbook.length" description="暂无教材数据" />
          </n-tab-pane>
          <n-tab-pane name="das" tab="诊断属性">
            <div v-for="da in detail.das" :key="da.da_id" class="detail-item">
              <strong>{{ da.name }}</strong>
              <ul><li v-for="b in da.observable_behaviors" :key="b">{{ b }}</li></ul>
            </div>
            <n-empty v-if="!detail.das.length" description="暂无 DA 数据" />
          </n-tab-pane>
          <n-tab-pane name="evidence" tab="教材证据">
            <div v-for="ev in (detail.evidence || [])" :key="ev.id" class="detail-item evidence-item">
              {{ ev.text }}
            </div>
            <n-empty v-if="!detail.evidence?.length" description="暂无教材证据" />
          </n-tab-pane>
          <n-tab-pane name="questions" tab="典型真题">
            <div v-for="band in ['near', 'mid', 'far']" :key="band">
              <h4>{{ {near:'基础',mid:'中等',far:'拓展'}[band] }}</h4>
              <div v-for="q in (detail.questions[band] || [])" :key="q.id" class="detail-item">
                <p>{{ q.stem }}</p>
                <p class="answer">答案: {{ q.answer }}</p>
              </div>
            </div>
            <n-empty v-if="!Object.keys(detail.questions).length" description="暂无真题数据" />
          </n-tab-pane>
        </n-tabs>

        <!-- 教师编辑表单 -->
        <template v-if="canEdit">
          <n-divider />
          <n-form ref="formRef" :model="editForm" size="small">
            <n-form-item label="概念名称">
              <n-input v-model:value="editForm.name" />
            </n-form-item>
            <n-form-item label="描述">
              <n-input v-model:value="editForm.description" type="textarea" :rows="3" />
            </n-form-item>
            <n-form-item label="难度">
              <n-rate :value="editForm.difficulty" @update:value="v => editForm.difficulty = v" :count="5" />
            </n-form-item>
            <n-form-item label="认知层级">
              <n-select v-model:value="editForm.bloom_level" :options="bloomOptions" clearable />
            </n-form-item>
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 12px;">
              <n-button type="primary" size="small" @click="handleSave" :loading="saving">
                保存修改
              </n-button>
              <n-button
                v-if="node.review_status === 'ai_draft'"
                size="small"
                @click="handleReview('teacher_reviewed')"
              >
                标记已审核
              </n-button>
              <n-tag v-if="node.review_status" size="small" :type="reviewTagType">
                {{ reviewStatusLabel }}
              </n-tag>
            </div>
          </n-form>
        </template>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  NDrawer, NDrawerContent, NDescriptions, NDescriptionsItem,
  NTag, NText, NForm, NFormItem, NInput, NButton, NDivider,
  NTabs, NTabPane, NEmpty, NSpin, NRate, NSelect,
  useMessage,
} from 'naive-ui'
import { getNodeDetail } from '../../api/knowledgeTree'

const props = defineProps({
  node: { type: Object, default: null },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'edit'])

const visible = defineModel('show', { type: Boolean, default: false })
const message = useMessage()
const saving = ref(false)
const editForm = ref({ name: '', description: '', difficulty: null, bloom_level: null })
const detail = ref(null)

const bloomOptions = [
  { label: '记忆', value: 'remember' },
  { label: '理解', value: 'understand' },
  { label: '应用', value: 'apply' },
  { label: '分析', value: 'analyze' },
  { label: '评价', value: 'evaluate' },
  { label: '创造', value: 'create' },
]

const reviewStatusLabels = {
  ai_draft: 'AI 草稿',
  teacher_reviewed: '已审核',
  published: '已发布',
}
const reviewStatusLabel = computed(() => reviewStatusLabels[props.node?.review_status] || props.node?.review_status)
const reviewTagType = computed(() => {
  const map = { ai_draft: 'default', teacher_reviewed: 'info', published: 'success' }
  return map[props.node?.review_status] || 'default'
})
const detailLoading = ref(false)
let abortController = null
let fetchSeq = 0  // 序号守卫：防止旧请求 finally 覆盖新请求状态

const stateTagType = computed(() => {
  const map = { solid: 'success', fragile: 'warning', weak: 'error', unseen: 'default' }
  return map[props.node?.mastery_state] || 'default'
})

watch(() => props.node, (n) => {
  if (n) {
    editForm.value = {
      name: n.name || '',
      description: n.description || '',
      difficulty: n.difficulty ?? null,
      bloom_level: n.bloom_level ?? null,
    }
  }
})

watch(() => props.node?.id, async (nodeId) => {
  if (!nodeId) return
  if (abortController) abortController.abort()
  abortController = new AbortController()
  const mySeq = ++fetchSeq  // 每次 watch 递增
  detailLoading.value = true
  detail.value = null
  try {
    const { data } = await getNodeDetail(nodeId, abortController.signal)
    if (mySeq === fetchSeq) detail.value = data  // 只有最新请求写入
  } catch (e) {
    if (e.name !== 'CanceledError' && e.name !== 'AbortError') {
      console.warn('Failed to load node detail:', e)
    }
  } finally {
    if (mySeq === fetchSeq) detailLoading.value = false  // 只有最新请求关 loading
  }
})

async function handleSave() {
  if (!props.node) return
  saving.value = true
  try {
    const fields = {}
    if (editForm.value.name !== props.node.name) fields.name = editForm.value.name
    if (editForm.value.description !== (props.node.description || '')) {
      fields.description = editForm.value.description
    }
    if (editForm.value.difficulty !== (props.node.difficulty ?? null)) {
      fields.difficulty = editForm.value.difficulty
    }
    if (editForm.value.bloom_level !== (props.node.bloom_level ?? null)) {
      fields.bloom_level = editForm.value.bloom_level
    }
    if (Object.keys(fields).length === 0) {
      message.info('没有变更')
      return
    }
    emit('edit', [{
      op: 'update_node',
      id: props.node.id,
      fields,
    }])
    message.success('已保存')
  } finally {
    saving.value = false
  }
}

function handleReview(status) {
  emit('edit', [{
    op: 'set_review_status',
    id: props.node.id,
    status,
  }])
  message.success('审核状态已更新')
}
</script>

<style scoped>
.detail-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--n-border-color);
}
.detail-item:last-child {
  border-bottom: none;
}
.answer {
  color: var(--n-text-color-3);
  font-size: 13px;
}
.evidence-item {
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}
</style>
