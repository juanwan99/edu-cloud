<template>
  <div>
    <n-card v-if="currentChild" title="学生信息" style="margin-bottom: 16px;">
      <n-descriptions :column="1" label-placement="left" bordered size="small">
        <n-descriptions-item label="姓名">{{ currentChild.student_name }}</n-descriptions-item>
        <n-descriptions-item label="班级">{{ currentChild.class_name || '-' }}</n-descriptions-item>
        <n-descriptions-item label="总积分">{{ currentChild.total_points ?? 0 }}</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <n-card title="操行记录">
      <n-data-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :pagination="pagination"
        remote
        @update:page="handlePageChange"
        size="small"
      />
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch, h } from 'vue'
import { NCard, NDataTable, NDescriptions, NDescriptionsItem, NTag } from 'naive-ui'
import { getChildRecords } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const records = ref([])
const loading = ref(false)
const pagination = ref({ page: 1, pageSize: 15, itemCount: 0 })

const columns = [
  {
    title: '日期',
    key: 'created_at',
    width: 120,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
  { title: '项目', key: 'rule_name', ellipsis: true },
  {
    title: '分值',
    key: 'points',
    width: 80,
    render: (row) => h(NTag, {
      type: row.points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => (row.points >= 0 ? '+' : '') + row.points),
  },
  { title: '备注', key: 'note', ellipsis: true },
]

async function fetchRecords() {
  if (!props.currentChild) return
  loading.value = true
  try {
    const res = await getChildRecords(props.currentChild.student_id, {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    })
    const data = res.data
    records.value = data.items || data || []
    pagination.value.itemCount = data.total || records.value.length
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

function handlePageChange(page) {
  pagination.value.page = page
  fetchRecords()
}

watch(() => props.currentChild, () => {
  pagination.value.page = 1
  fetchRecords()
}, { immediate: true })
</script>
