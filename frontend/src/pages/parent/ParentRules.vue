<template>
  <div>
    <n-card title="班级规则">
      <n-spin :show="loading">
        <n-collapse v-if="categories.length > 0">
          <n-collapse-item
            v-for="cat in categories"
            :key="cat.id"
            :title="cat.name"
            :name="cat.id"
          >
            <n-list v-if="cat.items && cat.items.length > 0" bordered size="small">
              <n-list-item v-for="item in cat.items" :key="item.id">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ item.name }}</span>
                  <n-tag
                    :type="item.points >= 0 ? 'success' : 'error'"
                    size="small"
                  >
                    {{ item.points >= 0 ? '+' : '' }}{{ item.points }}
                  </n-tag>
                </div>
                <div v-if="item.description" style="font-size: 12px; color: rgba(255,255,255,0.4); margin-top: 4px;">
                  {{ item.description }}
                </div>
              </n-list-item>
            </n-list>
            <n-empty v-else description="该分类暂无规则" />
          </n-collapse-item>
        </n-collapse>
        <n-empty v-else description="暂无班级规则" />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch, inject } from 'vue'
import { NCard, NCollapse, NCollapseItem, NList, NListItem, NTag, NEmpty, NSpin } from 'naive-ui'
import { getClassRulesParent } from '../../api/conduct'

const currentChild = inject('currentChild')
const categories = ref([])
const loading = ref(false)

watch(currentChild, async (child) => {
  if (!child?.class_id) return
  loading.value = true
  try {
    const res = await getClassRulesParent(child.class_id)
    categories.value = res.data.categories || res.data || []
  } catch {
    categories.value = []
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>
