<template>
  <div>
    <!-- Summary + Filter Bar -->
    <n-card size="small" style="margin-bottom: var(--space-4);">
      <div style="display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3);">
        <span style="font-size: var(--fs-base); color: rgba(255,255,255,0.7);">
          共 {{ totalCount }} 条规则
        </span>
        <n-tag type="success" size="small" :bordered="false">加分 {{ positiveCount }} 条</n-tag>
        <n-tag type="error" size="small" :bordered="false">扣分 {{ negativeCount }} 条</n-tag>
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: var(--space-2);">
        <n-radio-group v-model:value="filterMode" size="small">
          <n-radio-button value="all">全部</n-radio-button>
          <n-radio-button value="positive">加分项</n-radio-button>
          <n-radio-button value="negative">扣分项</n-radio-button>
        </n-radio-group>
        <n-input
          v-model:value="searchText"
          placeholder="搜索规则..."
          clearable
          size="small"
          style="flex: 1; min-width: 120px;"
        />
      </div>
    </n-card>

    <!-- Rules Content -->
    <n-card title="班级规则">
      <n-spin :show="loading">
        <n-collapse v-if="filteredCategories.length > 0">
          <n-collapse-item
            v-for="cat in filteredCategories"
            :key="cat.id"
            :title="categoryTitle(cat)"
            :name="cat.id"
          >
            <n-list v-if="cat.filteredItems && cat.filteredItems.length > 0" bordered size="small">
              <n-list-item v-for="item in cat.filteredItems" :key="item.id">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ item.name }}</span>
                  <n-tag
                    :type="pointsTagType(item.points)"
                    :bordered="isHighValue(item.points)"
                    size="small"
                  >
                    {{ item.points >= 0 ? '+' : '' }}{{ item.points }}
                  </n-tag>
                </div>
                <div v-if="item.description" style="font-size: var(--fs-base); color: rgba(255,255,255,0.4); margin-top: var(--space-1);">
                  {{ item.description }}
                </div>
              </n-list-item>
            </n-list>
            <n-empty v-else description="该分类暂无匹配规则" />
          </n-collapse-item>
        </n-collapse>
        <n-empty v-else-if="categories.length > 0" description="没有匹配的规则" />
        <n-empty v-else description="暂无班级规则" />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch, inject, computed } from 'vue'
import {
  NCard, NCollapse, NCollapseItem, NList, NListItem,
  NTag, NEmpty, NSpin, NRadioGroup, NRadioButton, NInput,
} from 'naive-ui'
import { getClassRulesParent } from '../../api/conduct'

const currentChild = inject('currentChild')
const categories = ref([])
const loading = ref(false)
const filterMode = ref('all')
const searchText = ref('')

// Category icon mapping
const categoryIcons = {
  '学习': '📚',
  '纪律': '📏',
  '卫生': '🧹',
  '劳动': '🔧',
  '体育': '⚽',
  '品德': '🌟',
  '安全': '🛡️',
  '活动': '🎯',
}

function getCategoryIcon(name) {
  for (const [keyword, icon] of Object.entries(categoryIcons)) {
    if (name && name.includes(keyword)) return icon
  }
  return '📋'
}

function categoryTitle(cat) {
  return getCategoryIcon(cat.name) + ' ' + cat.name
}

// Count stats
const allItems = computed(() => {
  return categories.value.flatMap(cat => cat.items || [])
})

const totalCount = computed(() => allItems.value.length)
const positiveCount = computed(() => allItems.value.filter(i => i.points > 0).length)
const negativeCount = computed(() => allItems.value.filter(i => i.points < 0).length)

// Filtering logic
const filteredCategories = computed(() => {
  const search = (searchText.value || '').trim().toLowerCase()
  const mode = filterMode.value

  return categories.value
    .map(cat => {
      const items = (cat.items || []).filter(item => {
        // Filter by mode
        if (mode === 'positive' && item.points < 0) return false
        if (mode === 'negative' && item.points >= 0) return false
        // Filter by search
        if (search && !(item.name || '').toLowerCase().includes(search)) return false
        return true
      })
      return { ...cat, filteredItems: items }
    })
    .filter(cat => cat.filteredItems.length > 0)
})

// Tag type based on points value
function pointsTagType(points) {
  if (points < 0) return 'error'
  if (points >= 5) return 'success'
  if (points > 0) return 'info'
  return 'default'
}

// High value items get a bordered tag for emphasis
function isHighValue(points) {
  return Math.abs(points) >= 5
}

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
