<template>
  <n-space vertical :size="16">
    <n-card title="学校默认分数段">
      <n-space vertical>
        <n-dynamic-input
          v-model:value="defaultConfig.boundaries"
          :on-create="() => 60"
          placeholder="阈值（如 85）"
        >
          <template #default="{ value, index }">
            <n-input-number
              :value="value"
              @update:value="v => defaultConfig.boundaries[index] = v"
              :min="0" :max="100"
              style="width: 120px"
            />
          </template>
        </n-dynamic-input>
        <n-dynamic-input
          v-model:value="defaultConfig.labels"
          :on-create="() => ''"
          placeholder="标签（如 优秀）"
        />
        <n-button type="primary" @click="saveDefault" :loading="saving" size="small">
          保存
        </n-button>
      </n-space>
    </n-card>

    <n-card title="科目覆盖" v-if="overrides.length">
      <n-data-table :columns="overrideColumns" :data="overrides" :pagination="false" size="small" />
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { getSegmentConfig, updateSegmentConfig } from '../../api/analytics'

const message = useMessage()
const saving = ref(false)
const defaultConfig = ref({ boundaries: [85, 70, 60], labels: ['优秀', '良好', '及格', '不及格'] })
const overrides = ref([])

const overrideColumns = [
  { title: '科目', key: 'subject_code' },
  { title: '阈值', key: 'boundaries', render: row => row.boundaries.join(', ') },
  { title: '标签', key: 'labels', render: row => row.labels.join(', ') },
]

onMounted(async () => {
  try {
    const resp = await getSegmentConfig()
    defaultConfig.value = resp.data.default
    overrides.value = resp.data.overrides
  } catch { /* use defaults */ }
})

async function saveDefault() {
  saving.value = true
  try {
    await updateSegmentConfig({
      boundaries: defaultConfig.value.boundaries,
      labels: defaultConfig.value.labels,
    })
    message.success('保存成功')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
