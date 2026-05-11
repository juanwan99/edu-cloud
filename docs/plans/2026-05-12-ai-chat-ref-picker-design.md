# AI 聊天数据引用系统设计

> 状态：设计中 | 日期：2026-05-12

## 1. 问题

用户在 AI 面板提问时（如"分析语文默写情况"），Agent 不知道具体指哪次考试、哪个科目。
它需要多轮工具调用去"猜"，浪费时间且经常猜错。
用户需要一种方式在提问前把数据范围"钉"死。

## 2. 设计原则

1. **角色即边界** — 用户只能引用自己权限 scope 内的数据
2. **实体可扩展** — 新业务领域（行政/课表/操行）加一个 resolver 即可
3. **级联可选不强制** — 选了考试可以继续选科目，但不必须
4. **前端驱动、后端校验** — picker 在前端渲染，发送时后端再验 scope

## 3. 实体类型注册表

每种可引用数据是一个 `RefType`，后端注册：

```python
# src/edu_cloud/ai/ref_types.py

@dataclass(frozen=True)
class RefType:
    type_code: str          # "exam", "class", "student", "question"
    label: str              # "考试", "班级", "学生", "题目"
    icon: str               # emoji 或 icon name
    children_type: str | None = None  # 级联子类型（exam → subject）
    searchable: bool = True

REF_TYPES: list[RefType] = [
    RefType("exam",     "考试", "📝", children_type="subject"),
    RefType("subject",  "科目", "📖", children_type="question"),
    RefType("class",    "班级", "🏫", children_type="student"),
    RefType("student",  "学生", "👤"),
    RefType("question", "题目", "❓"),
]
```

扩展时只需在 `REF_TYPES` 加一行 + 在 `ref_resolvers.py` 加一个 resolver 函数。

## 4. 后端 API

### 4.1 获取可用实体类型

```
GET /api/v1/ai/ref-types
→ [{ type_code, label, icon, children_type, searchable }]
```

返回当前角色可用的实体类型列表（platform_admin 无 school → 不返回 school-scoped 类型）。

### 4.2 查询实体列表

```
GET /api/v1/ai/refs?type=exam&search=期中&parent_id=&limit=20
→ {
    items: [
      { id: "uuid", label: "2026春季期中考试", subtitle: "已完成 · 6科", 
        children_type: "subject" }
    ],
    total: 3
  }
```

- `type`：实体类型（必填）
- `search`：模糊搜索（可选）
- `parent_id`：父级 ID，用于级联（可选，如 exam_id 查 subjects）
- `limit`：分页大小（默认 20）

内部按角色 scope 自动过滤（school_id, class_ids, subject_codes）。

### 4.3 Resolver 模式

```python
# src/edu_cloud/ai/ref_resolvers.py

async def resolve_exam(db, scope, search, parent_id, limit):
    query = select(Exam).where(Exam.school_id == scope.school_id)
    if search:
        query = query.where(Exam.name.ilike(f"%{search}%"))
    query = query.order_by(Exam.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return [RefItem(id=str(e.id), label=e.name, 
                    subtitle=f"{e.status} · {len(e.subjects)}科",
                    children_type="subject") for e in rows]

async def resolve_subject(db, scope, search, parent_id, limit):
    # parent_id = exam_id
    ...

async def resolve_class(db, scope, search, parent_id, limit):
    ...

async def resolve_student(db, scope, search, parent_id, limit):
    ...

async def resolve_question(db, scope, search, parent_id, limit):
    # parent_id = subject_id
    ...

RESOLVERS = {
    "exam": resolve_exam,
    "subject": resolve_subject,
    "class": resolve_class,
    "student": resolve_student,
    "question": resolve_question,
}
```

新增实体类型：加 `REF_TYPES` 一行 + `RESOLVERS` 一个函数。

### 4.4 scope 过滤矩阵

| 角色 | exam | class | student | question |
|------|------|-------|---------|----------|
| platform_admin | 全部 | 全部 | 全部 | 全部 |
| academic_director | 本校 | 本校 | 本校 | 本校考试下 |
| grade_leader | 本校 | 本年级 | 本年级 | 本校考试下 |
| homeroom_teacher | 本校 | 本班+任教班 | 本班+任教班 | 本校考试下 |
| subject_teacher | 本校 | 任教班 | 任教班 | 本科考试下 |

复用现有 `core/scope_filter.py` 的 ScopeFilter 逻辑。

## 5. 前端组件

### 5.1 RefPicker.vue

📎 按钮触发的弹出面板，放在输入框左侧。

**结构：**
```
┌──────────────────────────┐
│ 📝考试  🏫班级  👤学生   │ ← Tab 行（从 /ref-types 动态渲染）
├──────────────────────────┤
│ 🔍 搜索...               │
├──────────────────────────┤
│ ✅ 2026春季期中           │ ← 列表（从 /refs?type=exam 加载）
│    2026春季月考           │
│    2026第一次月考         │
├──────────────────────────┤
│ 选择科目（可选）          │ ← 级联区（选中有 children_type 的项后出现）
│ ○ 全部  ● 语文  ○ 数学   │
├──────────────────────────┤
│              [确定引用]   │
└──────────────────────────┘
```

**行为：**
- 打开时调 `/ref-types` 获取 Tab 列表
- 切换 Tab 时调 `/refs?type=xxx` 加载列表
- 选中有 `children_type` 的项 → 显示级联区域
- 搜索框 debounce 300ms
- 确定后 emit `{ type, id, label, children: [{ type, id, label }] }`

### 5.2 RefChip 展示

选中的引用以 chip 形式显示在输入框上方：

```
┌─────────────────────────────────┐
│ [2026春季期中 · 语文]  ✕        │ ← chips 区
├─────────────────────────────────┤
│ 📎  输入问题...          [发送]  │
└─────────────────────────────────┘
```

chip 可删除（✕）。多个引用横向排列，溢出换行。

### 5.3 AiSlidePanel 集成

```vue
<!-- AiSlidePanel.vue footer 改造 -->
<div v-if="refs.length" class="ai-ref-chips">
  <span v-for="r in refs" :key="r.id" class="ai-ref-chip">
    {{ r.label }}
    <button @click="removeRef(r)">✕</button>
  </span>
</div>
<form class="ai-panel-footer" @submit.prevent="send">
  <button type="button" class="ai-ref-btn" @click="pickerOpen = true">📎</button>
  <input ... />
  <button type="submit" ...>发送</button>
</form>
<RefPicker v-if="pickerOpen" @select="addRef" @close="pickerOpen = false" />
```

## 6. Agent 注入方式

### 6.1 消息格式

前端发送：

```json
POST /api/v1/ai/chat
{
  "message": "分析默写情况",
  "refs": [
    { "type": "exam", "id": "uuid-1", "label": "2026春季期中" },
    { "type": "subject", "id": "uuid-2", "label": "语文" }
  ]
}
```

### 6.2 后端处理

`api/ai.py` 在构造 AgentContext 前，验证 refs 的 scope 合法性并转换为上下文前缀：

```python
# 验证 + 构造引用上下文
ref_context = ""
if req.refs:
    validated = await validate_refs(db, req.refs, school_id=school_id)
    ref_lines = [f"[引用数据: {r['label']}（{r['type']}_id={r['id']}）]" for r in validated]
    ref_context = "\n".join(ref_lines) + "\n\n"
    message = ref_context + message
```

Agent 收到的消息变成：
```
[引用数据: 2026春季期中（exam_id=uuid-1）]
[引用数据: 语文（subject_id=uuid-2）]

分析默写情况
```

这样 Agent 直接拿到精确 ID，第一次工具调用就能命中正确数据。

### 6.3 scope 校验

`validate_refs` 检查每个 ref 是否在用户 scope 内（school_id 匹配、class 归属等）。
非法引用静默丢弃 + 日志 WARNING。

## 7. 文件清单

| 文件 | 类型 | 职责 |
|------|------|------|
| `src/edu_cloud/ai/ref_types.py` | 新建 | RefType 注册表 |
| `src/edu_cloud/ai/ref_resolvers.py` | 新建 | 各实体类型的查询 resolver |
| `src/edu_cloud/api/ai.py` | 修改 | +2 端点 (ref-types, refs) + chat 接收 refs 参数 |
| `frontend/src/components/ai/RefPicker.vue` | 新建 | 📎 弹出面板 |
| `frontend/src/components/ai/AiSlidePanel.vue` | 修改 | 集成 📎 按钮 + chips + refs 传参 |
| `frontend/src/stores/aiChat.js` | 修改 | sendMessage 传 refs |
| `frontend/src/api/ai.js` | 新建/修改 | ref-types / refs API 调用 |

## 8. 不做什么

- 不做 @ 行内触发（复杂度高，留后续迭代）
- 不做"当前页面自动上下文"（需路由→实体映射，耦合高）
- 不做 refs 持久化（每次对话独立，不跨 session）
- 不做 refs 的多选（一次选一个实体，但可以多次 📎 添加多个 chip）

## 9. 测试策略

| 层 | 测试内容 |
|----|---------|
| 后端 resolver | 各 resolver 按 scope 过滤正确，搜索/级联/分页 |
| 后端 API | ref-types 返回格式、refs 参数校验、scope 越权拒绝 |
| 后端注入 | refs 转上下文前缀格式正确 |
| 前端组件 | RefPicker Tab 切换、搜索、级联、chip 添加/删除 |
| 端到端 | 选考试+科目 → 发消息 → Agent 第一次工具调用用对 ID |
