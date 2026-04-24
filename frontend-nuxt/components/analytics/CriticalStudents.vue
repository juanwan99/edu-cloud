<template>
  <el-card>
    <template #header>临界生名单</template>
    <el-tabs v-model="activeGroup">
      <el-tab-pane :label="`差${threshold}分及格 (${nearPass.length})`" name="pass">
        <el-table :data="nearPass" stripe size="small" v-if="nearPass.length">
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column label="总分" width="80" align="center">
            <template #default="{ row }">{{ row.score }}</template>
          </el-table-column>
          <el-table-column label="差距" width="80" align="center">
            <template #default="{ row }">
              <el-tag type="danger" size="small">差 {{ row.gap }} 分</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="丢分最多题目">
            <template #default="{ row }">
              <span v-if="row.worst_question">
                第{{ row.worst_question.question_name }}题（丢 {{ row.worst_question.loss }} 分）
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="无临界生" :image-size="60" />
      </el-tab-pane>
      <el-tab-pane :label="`差${threshold}分优秀 (${nearExcellent.length})`" name="excellent">
        <el-table :data="nearExcellent" stripe size="small" v-if="nearExcellent.length">
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column label="总分" width="80" align="center">
            <template #default="{ row }">{{ row.score }}</template>
          </el-table-column>
          <el-table-column label="差距" width="80" align="center">
            <template #default="{ row }">
              <el-tag type="warning" size="small">差 {{ row.gap }} 分</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="丢分最多题目">
            <template #default="{ row }">
              <span v-if="row.worst_question">
                第{{ row.worst_question.question_name }}题（丢 {{ row.worst_question.loss }} 分）
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="无临界生" :image-size="60" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  nearPass: any[]
  nearExcellent: any[]
  threshold?: number
}>()

const activeGroup = ref('pass')
</script>
