<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>学生排名</span>
        <el-input v-model="search" placeholder="搜索姓名" size="small" clearable style="width: 200px" />
      </div>
    </template>
    <el-table :data="filtered" stripe row-key="student_id" :expand-row-keys="expandedKeys" @expand-change="onExpand">
      <el-table-column type="expand">
        <template #default="{ row }">
          <slot name="expand" :student="row" />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column label="总分" width="80" align="center" sortable :sort-by="(r: any) => r.score">
        <template #default="{ row }">{{ row.score }}</template>
      </el-table-column>
      <el-table-column label="班名次" width="90" align="center">
        <template #default="{ row }">{{ row.class_rank ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="年名次" width="90" align="center">
        <template #default="{ row }">{{ row.grade_rank }}</template>
      </el-table-column>
      <el-table-column label="进退步" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.delta_grade != null" :class="deltaClass(row.delta_grade)">
            {{ row.delta_grade > 0 ? '↑' + row.delta_grade : row.delta_grade < 0 ? '↓' + Math.abs(row.delta_grade) : '→' }}
          </span>
          <span v-else class="no-data">-</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
const props = defineProps<{ students: any[] }>()
const emit = defineEmits<{ (e: 'expand', student: any): void }>()

const search = ref('')
const expandedKeys = ref<string[]>([])

const filtered = computed(() => {
  if (!search.value) return props.students
  const q = search.value.toLowerCase()
  return props.students.filter((s: any) => s.name?.toLowerCase().includes(q))
})

function deltaClass(delta: number): string {
  if (delta > 0) return 'delta up'
  if (delta < 0) return 'delta down'
  return 'delta'
}

function onExpand(row: any, expanded: any[]) {
  expandedKeys.value = expanded.map((r: any) => r.student_id)
  if (expanded.includes(row)) emit('expand', row)
}
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.delta { font-weight: 600; }
.delta.up { color: var(--el-color-success); }
.delta.down { color: var(--el-color-danger); }
.no-data { color: var(--el-text-color-placeholder); }
</style>
