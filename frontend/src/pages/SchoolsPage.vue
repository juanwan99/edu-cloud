<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">学校管理</h1>
        <p class="page-subtitle">管理系统中的学校信息</p>
      </div>
      <n-button type="primary" class="btn-pill" @click="showCreate = true">添加学校</n-button>
    </div>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon stat-icon--yellow">
          <AppIcon name="school" :size="20" />
        </div>
        <div class="stat-label">学校总数</div>
        <div class="stat-value">{{ stats.total ?? '--' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon--purple">
          <AppIcon name="marking" :size="20" />
        </div>
        <div class="stat-label">活跃学校</div>
        <div class="stat-value">{{ stats.active ?? '--' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon--orange">
          <AppIcon name="chart" :size="20" />
        </div>
        <div class="stat-label">学区数</div>
        <div class="stat-value">{{ stats.districts ?? '--' }}</div>
      </div>
    </div>

    <!-- Search + Filter + View Toggle -->
    <div class="filter-bar">
      <n-input v-model:value="searchQuery" placeholder="搜索学校名称…" clearable style="width: 240px" />
      <n-select
        v-model:value="districtFilter"
        :options="districtOptions"
        placeholder="按学区筛选"
        clearable
        style="width: 200px"
      />
      <div style="flex: 1" />
      <n-radio-group v-model:value="viewMode" size="small">
        <n-radio-button value="table">表格</n-radio-button>
        <n-radio-button value="card">卡片</n-radio-button>
      </n-radio-group>
    </div>

    <!-- Table View -->
    <n-data-table v-if="viewMode === 'table'" :columns="columns" :data="filteredSchools" :loading="loading" />

    <!-- Card View -->
    <div v-else class="card-grid">
      <n-card v-for="s in filteredSchools" :key="s.id" size="small" hoverable class="school-card">
        <template #header>
          <div style="display: flex; align-items: center; gap: 8px;">
            <n-text strong>{{ s.name }}</n-text>
            <n-tag v-if="s.is_active" size="tiny" type="success" round>活跃</n-tag>
            <n-tag v-else size="tiny" type="error" round>停用</n-tag>
          </div>
        </template>
        <n-space vertical :size="4">
          <n-text depth="3">代码：{{ s.code }}</n-text>
          <n-text depth="3">学区：{{ s.district || '-' }}</n-text>
          <n-text depth="3">联系人：{{ s.contact_name || '-' }}</n-text>
          <n-text depth="3">电话：{{ s.contact_phone || '-' }}</n-text>
          <n-text depth="3">创建：{{ s.created_at ? new Date(s.created_at).toLocaleDateString('zh-CN') : '-' }}</n-text>
        </n-space>
      </n-card>
    </div>

    <n-modal v-model:show="showCreate" preset="dialog" title="添加学校" positive-text="添加"
      negative-text="取消" :positive-button-props="{ class: 'btn-pill' }"
      :negative-button-props="{ class: 'btn-pill' }" @positive-click="handleCreate">
      <n-form :model="form" label-placement="top">
        <n-form-item label="学校名称">
          <n-input v-model:value="form.name" placeholder="例如：第一中学" />
        </n-form-item>
        <n-form-item label="学校代码">
          <n-input v-model:value="form.code" placeholder="例如：SCHOOL01" />
        </n-form-item>
        <n-form-item label="学区">
          <n-input v-model:value="form.district" placeholder="例如：河源市源城区" />
        </n-form-item>
        <n-form-item label="联系人">
          <n-input v-model:value="form.contact_name" placeholder="例如：张主任" />
        </n-form-item>
        <n-form-item label="联系电话">
          <n-input v-model:value="form.contact_phone" placeholder="例如：13800138000" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import { NTag } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { listSchools, createSchool } from '../api/schools'
import AppIcon from '../components/AppIcon.vue'

const message = useMessage()
const loading = ref(true)
const schools = ref([])
const showCreate = ref(false)
const form = reactive({ name: '', code: '', district: '', contact_name: '', contact_phone: '' })

const searchQuery = ref('')
const districtFilter = ref(null)
const viewMode = ref('table')

const stats = computed(() => {
  const all = schools.value
  const districtSet = new Set(all.map((s) => s.district).filter(Boolean))
  return {
    total: all.length,
    active: all.filter((s) => s.is_active).length,
    districts: districtSet.size,
  }
})

const districtOptions = computed(() => {
  const set = new Set(schools.value.map((s) => s.district).filter(Boolean))
  return [...set].sort().map((d) => ({ label: d, value: d }))
})

const filteredSchools = computed(() => {
  let list = schools.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter((s) => s.name?.toLowerCase().includes(q))
  }
  if (districtFilter.value) {
    list = list.filter((s) => s.district === districtFilter.value)
  }
  return list
})

const columns = [
  { title: '学校名称', key: 'name' },
  { title: '学校代码', key: 'code', width: 130 },
  { title: '学区', key: 'district', width: 150, render: (row) => row.district || '-' },
  {
    title: '状态', key: 'is_active', width: 80,
    render: (row) => h(NTag, { size: 'small', type: row.is_active ? 'success' : 'error', round: true }, () => row.is_active ? '活跃' : '停用'),
  },
  {
    title: '创建时间', key: 'created_at', width: 140,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
]

async function loadSchools() {
  loading.value = true
  try {
    const { data } = await listSchools()
    schools.value = data
  } catch { /* interceptor */ }
  loading.value = false
}

async function handleCreate() {
  if (!form.name || !form.code || !form.district) { message.warning('请填写完整'); return false }
  try {
    await createSchool({
      name: form.name,
      code: form.code,
      district: form.district,
      contact_name: form.contact_name || undefined,
      contact_phone: form.contact_phone || undefined,
    })
    message.success('学校添加成功')
    Object.assign(form, { name: '', code: '', district: '', contact_name: '', contact_phone: '' })
    showCreate.value = false
    await loadSchools()
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
    return false
  }
}

onMounted(loadSchools)
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-icon--yellow {
  background: var(--color-accent);
  color: var(--color-bg-deep);
}

.stat-icon--purple {
  background: var(--color-primary);
  color: #ffffff;
}

.stat-icon--orange {
  background: var(--color-warning);
  color: #ffffff;
}
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.school-card {
  transition: transform 0.15s;
}
.school-card:hover {
  transform: translateY(-2px);
}
</style>
