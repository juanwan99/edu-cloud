/**
 * ConductRules source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (collapse categories, rule items, modals for category/item CRUD)
 *  3. API calls via conduct.js (getRules, createCategory, updateCategory, deleteCategory, createRuleItem, etc.)
 *  4. CRUD operations (create/edit/delete categories and rule items)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductRules.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductRules smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductRules.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductRules template sections', () => {
  it('contains add category button in top bar', () => {
    expect(content).toContain('display: flex')
    expect(content).toContain('@click="showAddCategory = true"')
    expect(content).toContain('添加分类')
  })

  it('contains add category button in header', () => {
    expect(content).toContain('@click="showAddCategory = true"')
    expect(content).toContain('添加分类')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains collapsible category list', () => {
    expect(content).toContain('v-for="cat in categories"')
    expect(content).toContain('accordion')
    expect(content).toContain('cat.name')
    expect(content).toContain("(cat.items || []).length")
  })

  it('contains category header actions (edit, delete, add rule)', () => {
    expect(content).toContain('@click="openEditCategory(cat)"')
    expect(content).toContain('@positive-click="handleDeleteCategory(cat.id)"')
    expect(content).toContain('@click="openAddItem(cat)"')
    expect(content).toContain('添加规则')
  })

  it('contains rule item list with points tag', () => {
    expect(content).toContain('v-for="item in cat.items"')
    expect(content).toContain('item.name')
    expect(content).toContain('item.description')
    expect(content).toContain('item.default_points')
  })

  it('contains rule item actions (edit, delete)', () => {
    expect(content).toContain('@click="openEditItem(cat, item)"')
    expect(content).toContain('@positive-click="handleDeleteItem(cat.id, item.id)"')
  })

  it('contains category modal with name and sort_order fields', () => {
    expect(content).toContain('v-model:show="showCategoryModal"')
    expect(content).toContain('v-model:value="categoryForm.name"')
    expect(content).toContain('v-model:value="categoryForm.sort_order"')
    expect(content).toContain("placeholder=\"例：课堂表现\"")
  })

  it('contains rule item modal with name, points, description fields', () => {
    expect(content).toContain('v-model:show="showItemModal"')
    expect(content).toContain('v-model:value="itemForm.name"')
    expect(content).toContain('v-model:value="itemForm.default_points"')
    expect(content).toContain('v-model:value="itemForm.description"')
    expect(content).toContain("placeholder=\"例：课堂积极发言\"")
  })
})

describe('ConductRules API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getRules')
    expect(content).toContain('createCategory')
    expect(content).toContain('updateCategory')
    expect(content).toContain('deleteCategory')
    expect(content).toContain('createRuleItem')
    expect(content).toContain('updateRuleItem')
    expect(content).toContain('deleteRuleItem')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getRules to load categories', () => {
    expect(content).toContain('getRules(classId.value)')
  })

  it('calls createCategory for new category', () => {
    expect(content).toContain('createCategory(classId.value, categoryForm.value)')
  })

  it('calls updateCategory for editing existing category', () => {
    expect(content).toContain('updateCategory(classId.value, editingCategory.value.id, categoryForm.value)')
  })

  it('calls deleteCategory', () => {
    expect(content).toContain('deleteCategory(classId.value, catId)')
  })

  it('calls createRuleItem for new rule item', () => {
    expect(content).toContain('createRuleItem(classId.value, itemCategoryId.value, itemForm.value)')
  })

  it('calls updateRuleItem for editing existing rule item', () => {
    expect(content).toContain('updateRuleItem(classId.value, itemCategoryId.value, editingItem.value.id, itemForm.value)')
  })

  it('calls deleteRuleItem', () => {
    expect(content).toContain('deleteRuleItem(classId.value, catId, itemId)')
  })
})

describe('ConductRules CRUD operations', () => {
  it('has form validation rules for category name', () => {
    expect(content).toContain("name: { required: true, message: '请输入分类名称', trigger: 'blur' }")
  })

  it('has form validation rules for item name and points', () => {
    expect(content).toContain("name: { required: true, message: '请输入规则名称', trigger: 'blur' }")
    expect(content).toContain("default_points: { required: true, type: 'number', message: '请输入积分值', trigger: 'blur' }")
  })

  it('distinguishes create vs edit mode for category modal', () => {
    expect(content).toContain("editingCategory ? '编辑分类' : '添加分类'")
  })

  it('distinguishes create vs edit mode for item modal', () => {
    expect(content).toContain("editingItem ? '编辑规则' : '添加规则'")
  })

  it('opens edit category with existing data', () => {
    expect(content).toContain('function openEditCategory(cat)')
    expect(content).toContain('editingCategory.value = cat')
    expect(content).toContain('name: cat.name')
    expect(content).toContain('sort_order: cat.sort_order || 0')
  })

  it('opens add item with reset form', () => {
    expect(content).toContain('function openAddItem(cat)')
    expect(content).toContain('editingItem.value = null')
    expect(content).toContain("itemForm.value = { name: '', default_points: 1, description: '' }")
  })

  it('opens edit item with existing data', () => {
    expect(content).toContain('function openEditItem(cat, item)')
    expect(content).toContain('editingItem.value = item')
    expect(content).toContain('name: item.name')
    expect(content).toContain('default_points: item.default_points')
  })

  it('reloads rules after each mutation', () => {
    const loadRulesCalls = (content.match(/await loadRules\(\)/g) || []).length
    expect(loadRulesCalls).toBeGreaterThanOrEqual(4)
  })

  it('shows appropriate success messages for each operation', () => {
    expect(content).toContain("message.success('分类已更新')")
    expect(content).toContain("message.success('分类已创建')")
    expect(content).toContain("message.success('分类已删除')")
    expect(content).toContain("message.success('规则已更新')")
    expect(content).toContain("message.success('规则已创建')")
    expect(content).toContain("message.success('规则已删除')")
  })

  it('loads rules on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('if (classId.value) loadRules()')
  })
})

describe('ConductRules error handling', () => {
  it('wraps loadRules in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadRules'),
      content.indexOf('function openEditCategory')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps saveCategory in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function saveCategory'),
      content.indexOf('async function handleDeleteCategory')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '操作失败'")
  })

  it('wraps handleDeleteCategory in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleDeleteCategory'),
      content.indexOf('async function saveItem')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '删除失败'")
  })

  it('wraps saveItem in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function saveItem'),
      content.indexOf('async function handleDeleteItem')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '操作失败'")
  })

  it('wraps handleDeleteItem in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleDeleteItem'),
      content.indexOf('onMounted(')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '删除失败'")
  })
})
