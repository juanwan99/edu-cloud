/**
 * CalendarPage tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains page header and layout structure
 *  3. Type filter radio buttons for event categories
 *  4. Data table and empty state rendering
 *  5. Statistics grid with type summary
 *  6. Create event modal with form fields
 *  7. API imports from calendar.js (list/create/delete)
 *  8. Event CRUD logic (loadEvents, handleCreate, handleDelete)
 *  9. Date filtering via typeFilter
 * 10. Error handling (try-catch in async functions)
 * 11. CSS classes for styling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../CalendarPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('CalendarPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../CalendarPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('CalendarPage page header', () => {
  it('has page-header with correct title', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('校历管理')
  })

  it('has page subtitle', () => {
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('学期事件与日程安排')
  })
})

describe('CalendarPage type filter radio buttons', () => {
  it('uses n-radio-group bound to typeFilter', () => {
    expect(content).toContain('v-model:value="typeFilter"')
    expect(content).toContain('@update:value="loadEvents"')
  })

  it('has radio button for all events', () => {
    expect(content).toContain('value="">全部')
  })

  it('has radio button for holiday events', () => {
    expect(content).toContain('value="holiday">放假')
  })

  it('has radio button for exam events', () => {
    expect(content).toContain('value="exam">考试')
  })

  it('has radio button for parent_meeting events', () => {
    expect(content).toContain('value="parent_meeting">家长会')
  })

  it('has radio button for deadline events', () => {
    expect(content).toContain('value="deadline">截止日期')
  })
})

describe('CalendarPage create button', () => {
  it('shows create button gated by canCreate permission', () => {
    expect(content).toContain('v-if="canCreate"')
    expect(content).toContain('新增事件')
    expect(content).toContain('@click="showCreate = true"')
  })

  it('canCreate checks generate_notification permission', () => {
    expect(content).toContain("auth.checkPermission('generate_notification')")
  })
})

describe('CalendarPage data table and empty state', () => {
  it('wraps content in n-spin with loading state', () => {
    expect(content).toContain('<n-spin :show="loading">')
  })

  it('shows data table when events exist', () => {
    expect(content).toContain('v-if="events.length"')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="events"')
  })

  it('configures pagination with pageSize 15', () => {
    expect(content).toContain('pageSize: 15')
  })

  it('shows empty state when no events and not loading', () => {
    expect(content).toContain('v-else-if="!loading"')
    expect(content).toContain('暂无校历事件')
  })
})

describe('CalendarPage statistics grid', () => {
  it('has stats-grid container', () => {
    expect(content).toContain('class="stats-grid"')
  })

  it('iterates over typeSummary for stat cards', () => {
    expect(content).toContain('v-for="t in typeSummary"')
    expect(content).toContain(':key="t.type"')
  })

  it('displays stat value and label', () => {
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-value"')
    expect(content).toContain('class="stat-label"')
    expect(content).toContain('{{ t.count }}')
    expect(content).toContain('{{ t.label }}')
  })
})

describe('CalendarPage create event modal', () => {
  it('has modal bound to showCreate', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('新增校历事件')
  })

  it('has type select field', () => {
    expect(content).toContain('v-model:value="form.type"')
    expect(content).toContain(':options="typeOptions"')
  })

  it('has title input field', () => {
    expect(content).toContain('v-model:value="form.title"')
    expect(content).toContain('例：五一劳动节放假')
  })

  it('has date picker field', () => {
    expect(content).toContain('v-model:value="form.date"')
    expect(content).toContain('type="date"')
  })

  it('has days before notification field', () => {
    expect(content).toContain('v-model:value="form.daysBefore"')
    expect(content).toContain(':min="0"')
    expect(content).toContain(':max="30"')
  })

  it('has description textarea', () => {
    expect(content).toContain('v-model:value="form.description"')
    expect(content).toContain('type="textarea"')
  })

  it('has cancel and create buttons in footer', () => {
    expect(content).toContain('@click="showCreate = false">取消')
    expect(content).toContain(':loading="creating"')
    expect(content).toContain('@click="handleCreate">创建')
  })
})

describe('CalendarPage API imports', () => {
  it('imports listCalendarEvents from calendar.js', () => {
    expect(content).toContain('listCalendarEvents')
  })

  it('imports createCalendarEvent from calendar.js', () => {
    expect(content).toContain('createCalendarEvent')
  })

  it('imports deleteCalendarEvent from calendar.js', () => {
    expect(content).toContain('deleteCalendarEvent')
  })

  it('imports from the correct api module path', () => {
    expect(content).toContain("from '../api/calendar.js'")
  })
})

describe('CalendarPage type options and TYPE_MAP', () => {
  it('defines typeOptions with four event types', () => {
    expect(content).toContain("{ label: '放假', value: 'holiday' }")
    expect(content).toContain("{ label: '考试', value: 'exam' }")
    expect(content).toContain("{ label: '家长会', value: 'parent_meeting' }")
    expect(content).toContain("{ label: '截止日期', value: 'deadline' }")
  })

  it('defines TYPE_MAP with label and tag type per event type', () => {
    expect(content).toContain("holiday: { label: '放假', type: 'success' }")
    expect(content).toContain("exam: { label: '考试', type: 'warning' }")
    expect(content).toContain("parent_meeting: { label: '家长会', type: 'info' }")
    expect(content).toContain("deadline: { label: '截止日期', type: 'error' }")
  })
})

describe('CalendarPage typeSummary computed', () => {
  it('counts events by type', () => {
    expect(content).toContain('counts[e.type] = (counts[e.type] || 0) + 1')
  })

  it('maps TYPE_MAP entries to summary objects', () => {
    expect(content).toContain('Object.entries(TYPE_MAP).map')
  })
})

describe('CalendarPage columns definition', () => {
  it('has title column', () => {
    expect(content).toContain("title: '标题', key: 'title'")
  })

  it('has type column with NTag render', () => {
    expect(content).toContain("title: '类型'")
    expect(content).toContain('h(NTag,')
  })

  it('has event_date column', () => {
    expect(content).toContain("title: '日期', key: 'event_date'")
  })

  it('has actions column with delete button', () => {
    expect(content).toContain("title: '操作'")
    expect(content).toContain("() => '删除'")
  })

  it('gates delete button on canCreate permission', () => {
    expect(content).toContain('canCreate.value')
    expect(content).toContain('handleDelete(row.id)')
  })
})

describe('CalendarPage loadEvents function', () => {
  it('sets loading state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadEvents'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('loading.value = true')
    expect(fnBlock).toContain('loading.value = false')
  })

  it('passes typeFilter as params when set', () => {
    expect(content).toContain('if (typeFilter.value) params.type = typeFilter.value')
  })

  it('calls listCalendarEvents with params', () => {
    expect(content).toContain('await listCalendarEvents(params)')
  })

  it('handles non-array response gracefully', () => {
    expect(content).toContain('Array.isArray(data) ? data : []')
  })
})

describe('CalendarPage handleCreate function', () => {
  it('validates title and date before submitting', () => {
    expect(content).toContain('if (!form.value.title || !form.value.date) return')
  })

  it('sets creating state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDelete')
    )
    expect(fnBlock).toContain('creating.value = true')
    expect(fnBlock).toContain('creating.value = false')
  })

  it('converts date to ISO string for API', () => {
    expect(content).toContain("new Date(form.value.date).toISOString().split('T')[0]")
  })

  it('calls createCalendarEvent with form data', () => {
    expect(content).toContain('await createCalendarEvent({')
  })

  it('includes notification_rules in payload', () => {
    expect(content).toContain('notification_rules:')
    expect(content).toContain('days_before:')
    expect(content).toContain('template_type:')
    expect(content).toContain('target_roles:')
    expect(content).toContain('auto_draft: true')
  })

  it('maps event type to template_type for notifications', () => {
    expect(content).toContain("'holiday_safety'")
    expect(content).toContain("'exam_reminder'")
    expect(content).toContain("'meeting_invite'")
  })

  it('resets form after successful creation', () => {
    expect(content).toContain("form.value = { type: 'holiday', title: '', date: null, daysBefore: 7, description: '' }")
  })

  it('reloads events after creation', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDelete')
    )
    expect(fnBlock).toContain('await loadEvents()')
  })
})

describe('CalendarPage handleDelete function', () => {
  it('calls deleteCalendarEvent with eventId', () => {
    expect(content).toContain('await deleteCalendarEvent(eventId)')
  })

  it('reloads events after deletion', () => {
    const fnStart = content.indexOf('async function handleDelete')
    // handleDelete is the last function before onMounted, slice to end of script
    const fnBlock = content.slice(fnStart, content.indexOf('</script>', fnStart))
    expect(fnBlock).toContain('await loadEvents()')
  })
})

describe('CalendarPage lifecycle', () => {
  it('calls loadEvents on mount', () => {
    expect(content).toContain('onMounted(loadEvents)')
  })
})

describe('CalendarPage error handling', () => {
  it('wraps loadEvents in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadEvents'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('resets events to empty array on loadEvents error', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadEvents'),
      content.indexOf('async function handleCreate')
    )
    const catchIndex = fnBlock.indexOf('} catch')
    const afterCatch = fnBlock.slice(catchIndex)
    expect(afterCatch).toContain('events.value = []')
  })

  it('wraps loadEvents in try-finally for loading state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadEvents'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('} finally {')
  })

  it('wraps handleCreate in try-finally for creating state', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDelete')
    )
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('creating.value = false')
  })
})

describe('CalendarPage reactive state', () => {
  it('declares loading ref', () => {
    expect(content).toContain('const loading = ref(false)')
  })

  it('declares creating ref', () => {
    expect(content).toContain('const creating = ref(false)')
  })

  it('declares events ref', () => {
    expect(content).toContain('const events = ref([])')
  })

  it('declares typeFilter ref', () => {
    expect(content).toContain("const typeFilter = ref('')")
  })

  it('declares showCreate ref', () => {
    expect(content).toContain('const showCreate = ref(false)')
  })

  it('declares form ref with default values', () => {
    expect(content).toContain("form = ref({ type: 'holiday', title: '', date: null, daysBefore: 7, description: '' })")
  })
})

describe('CalendarPage Vue imports', () => {
  it('imports h, ref, computed, onMounted from vue', () => {
    expect(content).toContain("import { h, ref, computed, onMounted } from 'vue'")
  })

  it('imports useAuthStore', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
  })

  it('imports NButton and NTag from naive-ui', () => {
    expect(content).toContain("import { NButton, NTag } from 'naive-ui'")
  })
})

describe('CalendarPage CSS classes', () => {
  it('defines page-header styles', () => {
    expect(content).toContain('.page-header {')
  })

  it('uses page-title class from global styles', () => {
    expect(content).toContain('class="page-title"')
  })

  it('defines stats-grid as CSS grid', () => {
    const styleMatch = content.match(/\.stats-grid\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('display: grid')
  })

  it('defines stat-card with centered text', () => {
    const styleMatch = content.match(/\.stat-card\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('text-align: center')
  })

  it('defines stat-value with primary color', () => {
    const styleMatch = content.match(/\.stat-value\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('var(--color-primary)')
  })

  it('uses scoped styles', () => {
    expect(content).toContain('<style scoped>')
  })
})
