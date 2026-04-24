<template>
  <div class="config-page">
    <el-card class="section-card">
      <template #header>默认分数段</template>
      <div class="boundaries-row">
        <div v-for="(b, i) in defaultBoundaries" :key="i" class="boundary-item">
          <el-input-number v-model="defaultBoundaries[i]" :min="0" :max="100" size="small" />
          <span class="boundary-label">{{ defaultLabels[i] ?? '' }}</span>
        </div>
        <span class="boundary-label">{{ defaultLabels[defaultLabels.length - 1] }}</span>
      </div>
      <el-button type="primary" size="small" @click="saveDefault" style="margin-top: 12px">
        保存默认配置
      </el-button>
    </el-card>

    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>科目覆盖</span>
          <el-button size="small" @click="showAddOverride = true">新增覆盖</el-button>
        </div>
      </template>

      <el-table :data="overrides" stripe>
        <el-table-column prop="subject_code" label="科目代码" width="120" />
        <el-table-column label="分数段边界">
          <template #default="{ row }">{{ row.boundaries?.join(' / ') }}</template>
        </el-table-column>
        <el-table-column label="标签">
          <template #default="{ row }">{{ row.labels?.join(' / ') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" text @click="deleteOverride(row.subject_code)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddOverride" title="新增科目覆盖" width="400">
      <el-form label-width="80px">
        <el-form-item label="科目代码">
          <el-input v-model="newOverride.subject_code" placeholder="如 math" />
        </el-form-item>
        <el-form-item label="边界">
          <el-input v-model="newOverride.boundariesStr" placeholder="85,70,60" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="newOverride.labelsStr" placeholder="优秀,良好,及格,不及格" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddOverride = false">取消</el-button>
        <el-button type="primary" @click="addOverride">确定</el-button>
      </template>
    </el-dialog>
    <el-card class="section-card">
      <template #header>分析报告阈值</template>
      <el-form label-width="140px" size="small">
        <el-form-item label="临界生阈值（分）">
          <el-input-number v-model="thresholds.critical" :min="1" :max="20" />
          <span class="threshold-hint">差几分及格/优秀时标记为临界生</span>
        </el-form-item>
        <el-form-item label="偏科预警（名次）">
          <el-input-number v-model="thresholds.imbalance" :min="5" :max="50" />
          <span class="threshold-hint">某科排名与其他科均值差超过此值时预警</span>
        </el-form-item>
        <el-form-item label="进退步标记（名次）">
          <el-input-number v-model="thresholds.rankChange" :min="1" :max="30" />
          <span class="threshold-hint">排名变动超过此值时标红/标绿</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveThresholds">保存阈值</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
const api = useApi()

const defaultBoundaries = ref<number[]>([85, 70, 60])
const defaultLabels = ref<string[]>(['优秀', '良好', '及格', '不及格'])
const overrides = ref<any[]>([])
const showAddOverride = ref(false)
const newOverride = reactive({
  subject_code: '',
  boundariesStr: '85,70,60',
  labelsStr: '优秀,良好,及格,不及格',
})

async function loadConfig() {
  try {
    const data = await api.getScoreSegments()
    defaultBoundaries.value = data.default?.boundaries ?? [85, 70, 60]
    defaultLabels.value = data.default?.labels ?? ['优秀', '良好', '及格', '不及格']
    overrides.value = data.overrides ?? []
  } catch {
    // use defaults
  }
}

async function saveDefault() {
  await api.upsertSegmentsConfig({
    boundaries: defaultBoundaries.value,
    labels: defaultLabels.value,
  })
  ElMessage.success('默认配置已保存')
}

async function deleteOverride(subjectCode: string) {
  await api.deleteSegmentOverride(subjectCode)
  overrides.value = overrides.value.filter(o => o.subject_code !== subjectCode)
  ElMessage.success('已删除')
}

async function addOverride() {
  const boundaries = newOverride.boundariesStr.split(',').map(Number)
  const labels = newOverride.labelsStr.split(',').map(s => s.trim())
  await api.upsertSegmentsConfig({
    subject_code: newOverride.subject_code,
    boundaries,
    labels,
  })
  showAddOverride.value = false
  await loadConfig()
  ElMessage.success('已添加')
}

const thresholds = reactive({
  critical: 3,
  imbalance: 15,
  rankChange: 5,
})

async function loadThresholds() {
  try {
    const settings = await api.raw('/schools/current/settings', { query: { category: 'analytics' } })
    const items = Array.isArray(settings) ? settings : settings?.settings ?? []
    for (const s of items) {
      if (s.key === 'analytics.critical_threshold') thresholds.critical = Number(s.value) || 3
      if (s.key === 'analytics.imbalance_threshold') thresholds.imbalance = Number(s.value) || 15
      if (s.key === 'analytics.rank_change_threshold') thresholds.rankChange = Number(s.value) || 5
    }
  } catch { /* use defaults */ }
}

async function saveThresholds() {
  const pairs = [
    { category: 'analytics', key: 'analytics.critical_threshold', value: String(thresholds.critical) },
    { category: 'analytics', key: 'analytics.imbalance_threshold', value: String(thresholds.imbalance) },
    { category: 'analytics', key: 'analytics.rank_change_threshold', value: String(thresholds.rankChange) },
  ]
  for (const p of pairs) {
    await api.raw('/schools/current/settings', { method: 'PATCH', body: p })
  }
  ElMessage.success('阈值已保存')
}

onMounted(() => { loadConfig(); loadThresholds() })
</script>

<style scoped>
.config-page { padding: 16px; max-width: 800px; }
.section-card { margin-bottom: 16px; }
.section-header { display: flex; justify-content: space-between; align-items: center; }
.boundaries-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.boundary-item { display: flex; align-items: center; gap: 4px; }
.boundary-label { color: #909399; font-size: 13px; }
.threshold-hint { color: #909399; font-size: 12px; margin-left: 8px; }
</style>
