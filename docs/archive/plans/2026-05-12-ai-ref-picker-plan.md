# AI 聊天数据引用系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在 AI 聊天面板通过 📎 按钮选择考试/科目/班级/学生等数据，注入 Agent 上下文，使工具调用直接命中正确数据。

**Architecture:** 后端统一 `/api/v1/ai/refs` 端点 + resolver 模式按角色 scope 过滤；前端 RefPicker 弹出面板 + chip 标签；发送时 refs 注入消息前缀携带精确 ID。

**Tech Stack:** FastAPI (后端) / Vue 3 Composition API + Pinia (前端) / SQLAlchemy async (查询) / Vitest + pytest (测试)

**Spec:** `docs/plans/2026-05-12-ai-chat-ref-picker-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/edu_cloud/ai/ref_types.py` | 新建 | RefType 注册表 + RefItem 数据模型 |
| `src/edu_cloud/ai/ref_resolvers.py` | 新建 | 各实体类型的 scope-filtered 查询 |
| `src/edu_cloud/api/ai.py` | 修改 | +2 端点 + ChatRequest 加 refs 字段 + 注入逻辑 |
| `frontend/src/api/ai.js` | 新建 | refTypes / refs / 查询 API 封装 |
| `frontend/src/components/ai/RefPicker.vue` | 新建 | 📎 弹出面板（Tab + 搜索 + 级联 + 确定） |
| `frontend/src/components/ai/AiSlidePanel.vue` | 修改 | 集成 📎 按钮 + chips + refs 传参 |
| `frontend/src/stores/aiChat.js` | 修改 | sendMessage 接受 refs 参数 |
| `tests/test_api/test_ai_refs.py` | 新建 | 后端 ref API 测试 |
| `frontend/src/__tests__/refPicker.test.js` | 新建 | 前端 RefPicker 测试 |

---

### Task 1: 后端 — RefType 注册表 + RefItem 模型

**Files:**
- Create: `src/edu_cloud/ai/ref_types.py`
- Test: `tests/test_api/test_ai_refs.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_api/test_ai_refs.py
from edu_cloud.ai.ref_types import REF_TYPES, RefType, RefItem

def test_ref_types_registry():
    assert len(REF_TYPES) >= 5
    codes = [t.type_code for t in REF_TYPES]
    assert "exam" in codes
    assert "class" in codes
    assert "student" in codes

def test_exam_has_children_type():
    exam = next(t for t in REF_TYPES if t.type_code == "exam")
    assert exam.children_type == "subject"

def test_ref_item_to_dict():
    item = RefItem(id="abc", label="Test", subtitle="sub", children_type="subject")
    d = item.to_dict()
    assert d == {"id": "abc", "label": "Test", "subtitle": "sub", "children_type": "subject"}

def test_ref_item_minimal():
    item = RefItem(id="x", label="Y")
    d = item.to_dict()
    assert d["children_type"] is None
    assert d["subtitle"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_ai_refs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.ai.ref_types'`

- [ ] **Step 3: 实现 ref_types.py**

```python
# src/edu_cloud/ai/ref_types.py
"""Entity reference type registry for AI chat data picker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefType:
    type_code: str
    label: str
    icon: str
    children_type: str | None = None
    searchable: bool = True

    def to_dict(self) -> dict:
        return {
            "type_code": self.type_code,
            "label": self.label,
            "icon": self.icon,
            "children_type": self.children_type,
            "searchable": self.searchable,
        }


@dataclass
class RefItem:
    id: str
    label: str
    subtitle: str | None = None
    children_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "subtitle": self.subtitle,
            "children_type": self.children_type,
        }


REF_TYPES: list[RefType] = [
    RefType("exam", "考试", "exam", children_type="subject"),
    RefType("subject", "科目", "subject", children_type="question"),
    RefType("class", "班级", "class", children_type="student"),
    RefType("student", "学生", "student"),
    RefType("question", "题目", "question"),
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_ai_refs.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/edu_cloud/ai/ref_types.py tests/test_api/test_ai_refs.py
git commit -m "feat: add RefType registry and RefItem model for AI chat refs"
```

---

### Task 2: 后端 — Resolver 函数（scope-filtered 查询）

**Files:**
- Create: `src/edu_cloud/ai/ref_resolvers.py`
- Test: `tests/test_api/test_ai_refs.py` (追加)

- [ ] **Step 1: 写 exam resolver 测试**

在 `tests/test_api/test_ai_refs.py` 追加：

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_resolve_exam(client: AsyncClient, school, db_engine):
    """academic_director 能看到本校考试。"""
    from tests.conftest import login_as
    token = await login_as(client, "admin_academic_director_2")
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "exam"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    # 种子数据有考试，应返回 ≥1 条
    for item in data["items"]:
        assert "id" in item
        assert "label" in item

@pytest.mark.asyncio
async def test_resolve_exam_search(client: AsyncClient, school, db_engine):
    from tests.conftest import login_as
    token = await login_as(client, "admin_academic_director_2")
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "exam", "search": "期中"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert "期中" in item["label"]

@pytest.mark.asyncio
async def test_resolve_unknown_type(client: AsyncClient, school, db_engine):
    from tests.conftest import login_as
    token = await login_as(client, "admin_academic_director_2")
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "nonexistent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_ai_refs.py::test_resolve_exam -v`
Expected: FAIL — 404 (端点不存在)

- [ ] **Step 3: 实现 ref_resolvers.py**

```python
# src/edu_cloud/ai/ref_resolvers.py
"""Scope-filtered entity resolvers for AI ref picker."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.ref_types import RefItem

logger = logging.getLogger(__name__)


async def resolve_exam(db: AsyncSession, school_id: str, search: str | None,
                       parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.modules.exam.models import Exam
    q = select(Exam).where(Exam.school_id == school_id)
    if search:
        q = q.where(Exam.name.ilike(f"%{search}%"))
    q = q.order_by(Exam.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(e.id), label=e.name,
                    subtitle=e.status, children_type="subject") for e in rows]


async def resolve_subject(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    if not parent_id:
        return []
    from edu_cloud.modules.exam.models import Subject
    q = select(Subject).where(Subject.exam_id == parent_id)
    if search:
        q = q.where(Subject.name.ilike(f"%{search}%"))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(s.id), label=s.name,
                    subtitle=s.subject_code, children_type="question") for s in rows]


async def resolve_class(db: AsyncSession, school_id: str, search: str | None,
                        parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.modules.student.models import Class
    q = select(Class).where(Class.school_id == school_id)
    if search:
        q = q.where(Class.name.ilike(f"%{search}%"))
    q = q.order_by(Class.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(c.id), label=c.name,
                    subtitle=getattr(c, "grade", None), children_type="student") for c in rows]


async def resolve_student(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.modules.student.models import Student
    q = select(Student).where(Student.school_id == school_id)
    if parent_id:
        q = q.where(Student.class_id == parent_id)
    if search:
        q = q.where(Student.name.ilike(f"%{search}%"))
    q = q.order_by(Student.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(s.id), label=s.name,
                    subtitle=getattr(s, "student_number", None)) for s in rows]


async def resolve_question(db: AsyncSession, school_id: str, search: str | None,
                           parent_id: str | None, limit: int) -> list[RefItem]:
    if not parent_id:
        return []
    from edu_cloud.modules.exam.models import Question
    q = select(Question).where(Question.subject_id == parent_id)
    if search:
        q = q.where(Question.name.ilike(f"%{search}%"))
    q = q.order_by(Question.sort_order).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(qn.id), label=qn.name or f"题{qn.sort_order}",
                    subtitle=f"{qn.max_score}分") for qn in rows]


RESOLVERS: dict[str, Any] = {
    "exam": resolve_exam,
    "subject": resolve_subject,
    "class": resolve_class,
    "student": resolve_student,
    "question": resolve_question,
}
```

- [ ] **Step 4: 不提交，等 Task 3 一起（resolver 需要 API 端点才能集成测试）**

---

### Task 3: 后端 — API 端点 + ChatRequest refs 注入

**Files:**
- Modify: `src/edu_cloud/api/ai.py` (第 78 行 ChatRequest + 第 92-96 行新端点 + 第 104-106 行 message 注入)
- Test: `tests/test_api/test_ai_refs.py` (追加)

- [ ] **Step 1: 写 ref-types 端点测试**

在 `tests/test_api/test_ai_refs.py` 追加：

```python
@pytest.mark.asyncio
async def test_ref_types_endpoint(client: AsyncClient, school, db_engine):
    from tests.conftest import login_as
    token = await login_as(client, "admin_academic_director_2")
    resp = await client.get(
        "/api/v1/ai/ref-types",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    types = resp.json()
    assert isinstance(types, list)
    codes = [t["type_code"] for t in types]
    assert "exam" in codes
    assert "class" in codes
```

- [ ] **Step 2: 在 ai.py 添加端点和修改 ChatRequest**

在 `src/edu_cloud/api/ai.py` 做以下修改：

**2a. ChatRequest 加 refs 字段（第 78 行附近）：**

```python
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    refs: list[dict] | None = None  # [{"type": "exam", "id": "uuid", "label": "..."}]

    @property
    def validated_message(self) -> str:
        msg = self.message.strip()
        if not msg:
            raise ValueError("消息不能为空")
        if len(msg) > 2000:
            raise ValueError("消息长度不能超过 2000 字符")
        return msg
```

**2b. 在 health 端点之后（第 96 行附近）添加两个新端点：**

```python
@router.get("/ref-types")
async def ai_ref_types(current=Depends(get_current_user)):
    from edu_cloud.ai.ref_types import REF_TYPES
    return [t.to_dict() for t in REF_TYPES]


@router.get("/refs")
async def ai_refs(
    type: str,
    search: str | None = None,
    parent_id: str | None = None,
    limit: int = 20,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from edu_cloud.ai.ref_resolvers import RESOLVERS
    resolver = RESOLVERS.get(type)
    if not resolver:
        raise HTTPException(400, f"Unknown ref type: {type}")

    role_obj = current["current_role"]
    school_id = getattr(role_obj, "school_id", None) or ""
    items = await resolver(db, school_id, search, parent_id, min(limit, 50))
    return {"items": [item.to_dict() for item in items], "total": len(items)}
```

**2c. 在 ai_chat 函数中（message 构造处，约第 106 行），注入 refs 上下文：**

在 `message = req.validated_message` 之后添加：

```python
    # Inject ref context
    if req.refs:
        ref_lines = [f"[引用数据: {r.get('label','')}（{r.get('type','')}_id={r.get('id','')}）]"
                     for r in req.refs if r.get("id")]
        if ref_lines:
            message = "\n".join(ref_lines) + "\n\n" + message
```

- [ ] **Step 3: 运行全部 refs 测试**

Run: `.venv/bin/python -m pytest tests/test_api/test_ai_refs.py -v`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add src/edu_cloud/ai/ref_types.py src/edu_cloud/ai/ref_resolvers.py src/edu_cloud/api/ai.py tests/test_api/test_ai_refs.py
git commit -m "feat: AI ref picker backend — types registry, resolvers, API endpoints"
```

---

### Task 4: 前端 — API 封装

**Files:**
- Create: `frontend/src/api/ai.js`

- [ ] **Step 1: 创建 ai.js**

```javascript
// frontend/src/api/ai.js
import client from './client'

export const getRefTypes = () => client.get('/ai/ref-types')

export const getRefs = (type, { search, parentId, limit } = {}) => {
  const params = { type }
  if (search) params.search = search
  if (parentId) params.parent_id = parentId
  if (limit) params.limit = limit
  return client.get('/ai/refs', { params })
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/ai.js
git commit -m "feat: frontend AI ref picker API layer"
```

---

### Task 5: 前端 — RefPicker 组件

**Files:**
- Create: `frontend/src/components/ai/RefPicker.vue`
- Test: `frontend/src/__tests__/refPicker.test.js`

- [ ] **Step 1: 写测试**

```javascript
// frontend/src/__tests__/refPicker.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RefPicker from '../components/ai/RefPicker.vue'

vi.mock('../api/ai.js', () => ({
  getRefTypes: vi.fn().mockResolvedValue({
    data: [
      { type_code: 'exam', label: '考试', icon: 'exam', children_type: 'subject', searchable: true },
      { type_code: 'class', label: '班级', icon: 'class', children_type: 'student', searchable: true },
    ],
  }),
  getRefs: vi.fn().mockResolvedValue({
    data: {
      items: [
        { id: 'e1', label: '2026春季期中', subtitle: 'completed', children_type: 'subject' },
        { id: 'e2', label: '2026春季月考', subtitle: 'draft', children_type: 'subject' },
      ],
      total: 2,
    },
  }),
}))

describe('RefPicker', () => {
  it('renders tabs from ref types', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    expect(wrapper.text()).toContain('考试')
    expect(wrapper.text()).toContain('班级')
  })

  it('loads items when tab selected', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    expect(wrapper.text()).toContain('2026春季期中')
  })

  it('emits select on confirm', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    // click first item
    const items = wrapper.findAll('.ref-item')
    await items[0].trigger('click')
    // click confirm
    await wrapper.find('.ref-confirm').trigger('click')
    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0].id).toBe('e1')
  })

  it('emits close on backdrop click', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    await wrapper.find('.ref-backdrop').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/refPicker.test.js`
Expected: FAIL — module not found

- [ ] **Step 3: 实现 RefPicker.vue**

```vue
<!-- frontend/src/components/ai/RefPicker.vue -->
<template>
  <div class="ref-backdrop" @click.self="$emit('close')">
    <div class="ref-picker">
      <div class="ref-tabs">
        <button v-for="t in types" :key="t.type_code"
                :class="['ref-tab', { active: activeType === t.type_code }]"
                @click="switchType(t.type_code)">
          {{ t.label }}
        </button>
      </div>

      <div class="ref-search">
        <input v-model="searchText" type="text" placeholder="搜索..." @input="onSearch" />
      </div>

      <div class="ref-list">
        <div v-for="item in items" :key="item.id"
             :class="['ref-item', { selected: selectedId === item.id }]"
             @click="selectItem(item)">
          <span class="ref-item-label">{{ item.label }}</span>
          <span v-if="item.subtitle" class="ref-item-sub">{{ item.subtitle }}</span>
        </div>
        <div v-if="!items.length && !loading" class="ref-empty">暂无数据</div>
        <div v-if="loading" class="ref-loading">加载中...</div>
      </div>

      <div v-if="children.length" class="ref-children">
        <div class="ref-children-label">选择{{ childLabel }}（可选）</div>
        <div v-for="c in children" :key="c.id"
             :class="['ref-item ref-child', { selected: selectedChildId === c.id }]"
             @click="selectedChildId = selectedChildId === c.id ? null : c.id">
          <span class="ref-item-label">{{ c.label }}</span>
          <span v-if="c.subtitle" class="ref-item-sub">{{ c.subtitle }}</span>
        </div>
      </div>

      <div class="ref-footer">
        <button class="ref-confirm" :disabled="!selectedId" @click="confirm">确定引用</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getRefTypes, getRefs } from '../../api/ai.js'

const emit = defineEmits(['select', 'close'])

const types = ref([])
const activeType = ref('')
const items = ref([])
const children = ref([])
const searchText = ref('')
const selectedId = ref(null)
const selectedChildId = ref(null)
const loading = ref(false)
const childLabel = ref('')

let searchTimer = null

onMounted(async () => {
  const { data } = await getRefTypes()
  types.value = data
  if (data.length) switchType(data[0].type_code)
})

async function switchType(code) {
  activeType.value = code
  searchText.value = ''
  selectedId.value = null
  selectedChildId.value = null
  children.value = []
  await loadItems()
}

async function loadItems(search) {
  loading.value = true
  try {
    const { data } = await getRefs(activeType.value, { search, limit: 30 })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadItems(searchText.value || undefined), 300)
}

async function selectItem(item) {
  selectedId.value = item.id
  selectedChildId.value = null
  children.value = []
  if (item.children_type) {
    childLabel.value = types.value.find(t => t.type_code === item.children_type)?.label || ''
    const { data } = await getRefs(item.children_type, { parentId: item.id, limit: 30 })
    children.value = data.items
  }
}

function confirm() {
  const item = items.value.find(i => i.id === selectedId.value)
  if (!item) return
  const result = { type: activeType.value, id: item.id, label: item.label }
  if (selectedChildId.value) {
    const child = children.value.find(c => c.id === selectedChildId.value)
    if (child) {
      const childType = types.value.find(t => t.type_code === activeType.value)?.children_type
      result.label += ` · ${child.label}`
      result.children = [{ type: childType, id: child.id, label: child.label }]
    }
  }
  emit('select', result)
}
</script>

<style scoped>
.ref-backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-modal) + 1);
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ref-picker {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  width: 340px;
  max-height: 480px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ref-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ref-tab {
  flex: 1;
  padding: 10px 4px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: var(--transition);
}

.ref-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: var(--fw-semibold);
}

.ref-search {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ref-search input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  background: var(--color-bg-alt);
  color: var(--color-text);
}

.ref-search input:focus {
  border-color: var(--color-primary);
}

.ref-list {
  flex: 1;
  overflow-y: auto;
  max-height: 200px;
}

.ref-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  transition: background 0.15s;
}

.ref-item:hover { background: var(--color-bg-alt); }
.ref-item.selected { background: rgba(100, 76, 240, 0.08); color: var(--color-primary); }

.ref-item-label { font-weight: var(--fw-medium); }
.ref-item-sub { font-size: 12px; color: var(--color-text-secondary); }

.ref-children {
  border-top: 1px solid var(--color-border-light);
  max-height: 150px;
  overflow-y: auto;
}

.ref-children-label {
  padding: 6px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--fw-semibold);
}

.ref-empty, .ref-loading {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.ref-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--color-border-light);
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

.ref-confirm {
  padding: 6px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition);
}

.ref-confirm:hover:not(:disabled) { opacity: 0.9; }
.ref-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run src/__tests__/refPicker.test.js`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ai/RefPicker.vue frontend/src/__tests__/refPicker.test.js
git commit -m "feat: RefPicker component — tab/search/cascade/confirm"
```

---

### Task 6: 前端 — AiSlidePanel + aiChat store 集成

**Files:**
- Modify: `frontend/src/components/ai/AiSlidePanel.vue` (footer 区域)
- Modify: `frontend/src/stores/aiChat.js` (sendMessage 加 refs 参数)

- [ ] **Step 1: 修改 aiChat.js — sendMessage 接受 refs**

在 `frontend/src/stores/aiChat.js` 第 25 行，修改函数签名和 fetch body：

```javascript
  async function sendMessage(content, refs = []) {
    if (!content.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content, refs: refs.length ? refs : undefined })
    isLoading.value = true
    error.value = null

    try {
      const body = { message: content, session_id: sessionId.value }
      if (refs.length) body.refs = refs
      const resp = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
```

注意：只改函数签名 `sendMessage(content, refs = [])` 和 body 构建逻辑。其余 SSE 处理保持不变。

- [ ] **Step 2: 修改 AiSlidePanel.vue — 添加 📎 按钮、chips、RefPicker**

**2a. 在 template 的 footer form 之前添加 chips 区域和 RefPicker：**

在 `<form class="ai-panel-footer"` 之前插入：

```vue
        <div v-if="refs.length" class="ai-ref-chips">
          <span v-for="(r, i) in refs" :key="i" class="ai-ref-chip">
            {{ r.label }}
            <button class="ai-ref-chip-x" @click="refs.splice(i, 1)">✕</button>
          </span>
        </div>

        <RefPicker v-if="pickerOpen" @select="addRef" @close="pickerOpen = false" />
```

**2b. 在 form 内 input 之前添加 📎 按钮：**

```vue
          <button type="button" class="ai-ref-btn" title="引用数据" @click="pickerOpen = true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16.5 6v11.5a4 4 0 01-8 0V5a2.5 2.5 0 015 0v10.5a1 1 0 01-2 0V6h-1.5v9.5a2.5 2.5 0 005 0V5a4 4 0 00-8 0v12.5a5.5 5.5 0 0011 0V6H16.5z"/>
            </svg>
          </button>
```

**2c. 在 script setup 中添加状态和方法：**

```javascript
import RefPicker from './RefPicker.vue'

const refs = ref([])
const pickerOpen = ref(false)

function addRef(refData) {
  // 避免重复
  if (!refs.value.find(r => r.id === refData.id && r.type === refData.type)) {
    refs.value.push(refData)
  }
  // 如果有 children，也展开加入
  if (refData.children) {
    for (const child of refData.children) {
      if (!refs.value.find(r => r.id === child.id && r.type === child.type)) {
        refs.value.push(child)
      }
    }
  }
  pickerOpen.value = false
}
```

**2d. 修改 send 函数传 refs：**

```javascript
async function send() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  const currentRefs = [...refs.value]
  refs.value = []
  await chat.sendMessage(text, currentRefs)
}
```

**2e. 添加样式：**

```css
.ai-ref-chips {
  padding: 4px 20px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: rgba(100, 76, 240, 0.1);
  color: var(--color-primary);
  border-radius: 12px;
  font-size: 12px;
  font-weight: var(--fw-medium);
}

.ai-ref-chip-x {
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 11px;
  padding: 0 2px;
  line-height: 1;
}

.ai-ref-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--transition);
}

.ai-ref-btn:hover {
  background: var(--color-bg-alt);
  color: var(--color-primary);
}
```

- [ ] **Step 3: Build 验证**

Run: `cd frontend && npx vite build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ai/AiSlidePanel.vue frontend/src/stores/aiChat.js frontend/src/api/ai.js
git commit -m "feat: integrate RefPicker into AI chat panel — 📎 button, chips, refs passing"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 重启后端**

```bash
kill -9 $(pgrep -f "edu_cloud.api.app") 2>/dev/null
nohup .venv/bin/python3 -m uvicorn edu_cloud.api.app:create_app --factory --host 127.0.0.1 --port 9000 >> /tmp/edu-cloud.log 2>&1 &
sleep 5
```

- [ ] **Step 2: 验证 ref-types 端点**

```bash
TOKEN=$(curl -s http://localhost:9000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin_academic_director_2","password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

curl -s http://localhost:9000/api/v1/ai/ref-types -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 5 个类型的 JSON 数组

- [ ] **Step 3: 验证 refs 端点**

```bash
curl -s "http://localhost:9000/api/v1/ai/refs?type=exam" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 本校考试列表

- [ ] **Step 4: 验证 refs 注入 chat**

```bash
curl -sN http://localhost:9000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"分析默写情况","refs":[{"type":"exam","id":"EXAM_ID_HERE","label":"2026春季期中"}]}' \
  --max-time 60
```

Expected: Agent 第一次工具调用直接使用 EXAM_ID_HERE，不再盲猜

- [ ] **Step 5: Build + push**

```bash
cd frontend && npx vite build
cd .. && git push origin master
```

---

## 风险点

| 风险 | 缓解 |
|------|------|
| Subject/Question 模型字段名可能不同 | Task 2 resolver 按实际 ORM 字段调整，不依赖假设 |
| conftest.py 里 `login_as` 可能不存在 | 检查现有测试的 auth helper 模式，用相同方式 |
| Vitest mount 可能缺 global plugins | 参考现有 `__tests__/` 文件的 mount 配置 |
