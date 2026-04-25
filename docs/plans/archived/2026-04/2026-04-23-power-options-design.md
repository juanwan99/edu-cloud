# PowerOptions 级联筛选器 + 分析报告模块 — 设计文档

> 创建: 2026-04-23
> 状态: 设计完成，待计划
> 范围: 后端 PowerOptionsService + 等级赋分端点 + Nuxt 前端 composable/组件 + 6 个报告页面

## §0 背景与目标

edu-cloud 分析模块后端有 11 个端点（概览/分布/题目/排名/趋势/导出），但**前端缺少统一的数据筛选入口**。教师无法按"年级→班级→科目→考试"逐级定位要分析的数据。好分数的 PowerOptions 级联筛选器是其分析模块的核心 UX 骨架，所有分析页面共用同一个筛选器。

**目标**：在 frontend-nuxt/ 中实现 PowerOptions 级联筛选器 + 6 个分析报告页面，后端新增 PowerOptionsService 和等级赋分端点。

**非目标**：不改现有 frontend/（Vite + Naive UI）的分析页面；不做 study/ 学情页面（作为后续自然延伸）。

## §1 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| API 风格 | edu-cloud 原生（id+name，非复合键） | 前端选中后直接传给现有 analytics 端点，零解码 |
| 树加载方式 | 单次全量加载 | 学校规模（几十个班×几十场考试）数据量小，避免多次网络往返 |
| "全部班级"节点 | 每个年级自动插入 `id="all"` 伪节点 | 年级组长/校长需要年级汇总视图 |
| 前端框架 | frontend-nuxt/（Nuxt 3 + Element Plus） | 好分数复刻目标框架，彻底整合 |
| 等级赋分 | 后端计算（百分位+线性插值） | 涉及全年级排序，前端算不了 |

## §2 后端设计

### 2.1 PowerOptions 端点

```
GET /api/v1/analytics/power-options
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| exam_type | string | 否 | 筛选考试类型 |
| year | int | 否 | 筛选年份 |

school_id 和 RBAC 从 JWT 自动注入。

**响应**：

```json
{
  "grades": [
    {
      "name": "高一",
      "classes": [
        {
          "id": "all",
          "name": "全部班级",
          "subjects": [
            {
              "id": "subj-uuid",
              "code": "math",
              "name": "数学",
              "exams": [
                {
                  "exam_id": "exam-uuid",
                  "subject_id": "subj-uuid",
                  "name": "2026 期中考试",
                  "exam_date": "2026-04-15",
                  "student_count": 180
                }
              ]
            }
          ]
        },
        {
          "id": "cls-uuid-1",
          "name": "高一(1)班",
          "subjects": [
            {
              "id": "subj-uuid",
              "code": "math",
              "name": "数学",
              "exams": [
                {
                  "exam_id": "exam-uuid",
                  "subject_id": "subj-uuid",
                  "name": "2026 期中考试",
                  "exam_date": "2026-04-15",
                  "student_count": 45
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**设计要点**：
- 每层直接用 `id` + `name`，前端无需解码
- `"all"` 伪班级：聚合该年级所有班级的科目和考试，student_count 为年级总人数
- exams 按 exam_date 倒序（最近优先）
- RBAC 透明过滤：科目教师只看到任教科目，校长看全部

### 2.2 PowerOptionsService

**文件**：`src/edu_cloud/modules/analytics/power_options_service.py`

**核心查询**：

```sql
SELECT DISTINCT
    c.grade,
    c.id AS class_id,
    c.name AS class_name,
    s.id AS subject_id,
    s.code AS subject_code,
    s.name AS subject_name,
    e.id AS exam_id,
    e.name AS exam_name,
    e.exam_date,
    COUNT(DISTINCT er.student_id) AS student_count
FROM exams e
JOIN subjects s ON s.exam_id = e.id
JOIN exam_results er ON er.exam_id = e.id
JOIN students st ON st.id = er.student_id
JOIN classes c ON c.id = st.class_id
WHERE e.school_id = :school_id
    AND e.status = 'completed'
    [AND c.id IN :visible_class_ids]
    [AND s.code IN :visible_subject_codes]
    [AND e.exam_type = :exam_type]
    [AND EXTRACT(YEAR FROM e.exam_date) = :year]
GROUP BY c.grade, c.id, c.name, s.id, s.code, s.name, e.id, e.name, e.exam_date
ORDER BY c.grade, c.name, s.name, e.exam_date DESC
```

**树构建算法**（Python 侧）：

1. 执行查询拿到扁平行
2. 遍历行，按 grade → class_id → subject_id → exam_id 嵌套分组到 dict
3. 对每个 grade，插入 `id="all"` 伪班级，其 subjects 为该年级所有班级的 subjects 去重并集，每个考试的 student_count 为该年级所有班级之和
4. 返回嵌套结构

**函数签名**：

```python
async def get_power_options(
    db: AsyncSession,
    school_id: str,
    visible_class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
    exam_type: str | None = None,
    year: int | None = None,
) -> dict:
```

### 2.3 等级赋分端点

```
POST /api/v1/analytics/level-score/convert
```

**请求体**：

```json
{
  "exam_id": "exam-uuid",
  "subject_id": "subj-uuid",
  "class_id": "cls-uuid | null",
  "levels": [
    { "level": "A", "start_pct": 0, "end_pct": 15, "score_min": 86, "score_max": 100 },
    { "level": "B", "start_pct": 15, "end_pct": 50, "score_min": 71, "score_max": 85 },
    { "level": "C", "start_pct": 50, "end_pct": 75, "score_min": 56, "score_max": 70 },
    { "level": "D", "start_pct": 75, "end_pct": 90, "score_min": 41, "score_max": 55 },
    { "level": "E", "start_pct": 90, "end_pct": 100, "score_min": 30, "score_max": 40 }
  ]
}
```

**响应**：

```json
{
  "total_students": 180,
  "level_stats": [
    { "level": "A", "count": 27, "pct": 15.0, "raw_min": 92, "raw_max": 100, "assigned_range": [86, 100] },
    { "level": "B", "count": 63, "pct": 35.0, "raw_min": 78, "raw_max": 91, "assigned_range": [71, 85] }
  ],
  "students": [
    { "student_id": "...", "name": "张三", "raw_score": 95, "level": "A", "assigned_score": 98, "rank": 3 }
  ],
  "distribution_before": { "segments": [...], "counts": [...] },
  "distribution_after": { "segments": [...], "counts": [...] }
}
```

**算法**：
1. 查询该考试该科目所有学生原始分，按分数降序排列
2. 按百分位划分等级（前 15% 为 A，15-50% 为 B...）
3. 每个等级内，线性插值：`assigned = score_min + (score_max - score_min) * (rank_in_level - 1) / (level_count - 1)`
4. 返回转换结果 + 赋分前后分布对比

**权限**：`MANAGE_EXAM_RESULTS`

**文件**：`src/edu_cloud/modules/analytics/level_score_service.py`

## §3 前端设计（frontend-nuxt/）

### 3.1 usePowerOptions composable

**文件**：`frontend-nuxt/composables/usePowerOptions.ts`

**状态**：

```typescript
interface GradeNode {
  name: string
  classes: ClassNode[]
}
interface ClassNode {
  id: string        // UUID 或 "all"
  name: string
  subjects: SubjectNode[]
}
interface SubjectNode {
  id: string
  code: string
  name: string
  exams: ExamNode[]
}
interface ExamNode {
  exam_id: string
  subject_id: string
  name: string
  exam_date: string
  student_count: number
}
```

**核心逻辑**：

```typescript
export function usePowerOptions() {
  const tree = ref<GradeNode[]>([])

  const selectedGrade = ref('')
  const selectedClassId = ref('all')
  const selectedSubjectId = ref('')
  const selectedExamId = ref('')

  // 派生选项——每层从树中过滤
  const gradeOptions = computed(() => tree.value.map(g => g.name))

  const classOptions = computed(() => {
    const grade = tree.value.find(g => g.name === selectedGrade.value)
    return grade?.classes ?? []
  })

  const subjectOptions = computed(() => {
    const cls = classOptions.value.find(c => c.id === selectedClassId.value)
    return cls?.subjects ?? []
  })

  const examOptions = computed(() => {
    const subj = subjectOptions.value.find(s => s.id === selectedSubjectId.value)
    return subj?.exams ?? []
  })

  // 级联重置：上层变化 → 重置下层 → 自动选中首项
  watch(selectedGrade, () => {
    selectedClassId.value = classOptions.value[0]?.id ?? 'all'
  })
  watch(selectedClassId, () => {
    selectedSubjectId.value = subjectOptions.value[0]?.id ?? ''
  })
  watch(selectedSubjectId, () => {
    selectedExamId.value = examOptions.value[0]?.exam_id ?? ''
  })

  // 核心输出：直接可传给 analytics API
  const analysisParams = computed(() => ({
    exam_id: selectedExamId.value,
    subject_id: subjectOptions.value.find(
      s => s.id === selectedSubjectId.value
    )?.id ?? '',
    class_id: selectedClassId.value === 'all' ? null : selectedClassId.value,
  }))

  async function load(examType?: string, year?: number) {
    const api = useApi()
    const data = await api.getPowerOptions({ examType, year })
    tree.value = data.grades
    if (tree.value.length) {
      selectedGrade.value = tree.value[0].name
    }
  }

  return {
    load, tree,
    selectedGrade, selectedClassId, selectedSubjectId, selectedExamId,
    gradeOptions, classOptions, subjectOptions, examOptions,
    analysisParams,
  }
}
```

### 3.2 PowerFilter 组件

**文件**：`frontend-nuxt/components/common/PowerFilter.vue`

4 个 ElSelect 水平排列，通过 props 接收 `usePowerOptions()` 的返回值或通过 `provide/inject` 共享。

**布局**：

```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐
│  年级 ▾  │ │  班级 ▾  │ │  科目 ▾  │ │   考试 ▾      │
└─────────┘ └─────────┘ └─────────┘ └──────────────┘
```

考试选择器宽度更大（名称较长），其余等宽。响应式布局：移动端纵向堆叠。

**交互规则**：
- 每层选择变化触发下层重置并选中首项
- 考试选择器显示考试名称 + 日期（如 "期中考试 2026-04-15"）
- 数据为空时该选择器 disabled 并显示"暂无数据"
- 加载中状态：ElSelect 的 loading prop

### 3.3 useApi 扩展

在 `frontend-nuxt/composables/useApi.ts` 中新增方法：

```typescript
// PowerOptions
getPowerOptions: (params?) =>
  request('/analytics/power-options', { query: params }),

// 等级赋分
convertLevelScore: (data) =>
  request('/analytics/level-score/convert', { method: 'POST', body: data }),

// 分析端点（复用现有后端）
getExamSummary: (examId) =>
  request(`/analytics/exam/${examId}/summary`),
getExamDistribution: (examId, params?) =>
  request(`/analytics/exam/${examId}/distribution`, { query: params }),
getExamGradeAggregates: (examId, params?) =>
  request(`/analytics/exam/${examId}/grade-aggregates`, { query: params }),
getSubjectQuestions: (subjectId) =>
  request(`/analytics/subject/${subjectId}/questions`),
queryReport: (data) =>
  request('/analytics/report/query', { method: 'POST', body: data }),
getSegmentsConfig: () =>
  request('/analytics/segments/config'),
upsertSegmentsConfig: (data) =>
  request('/analytics/segments/config', { method: 'PUT', body: data }),
```

## §4 报告页面设计

6 个页面均在 `frontend-nuxt/pages/report/` 下，共享 PowerFilter 组件。

### 4.1 exam.vue — 考试报告

**数据源**：`/analytics/exam/{id}/summary` + `/distribution`

**布局**：
```
┌─ PowerFilter ─────────────────────────────────────────┐
├─ 统计卡片行 ──────────────────────────────────────────┤
│ [平均分 72.5] [最高分 98] [最低分 23] [及格率 68%]    │
├─ 分数分布 ────────────────────────────────────────────┤
│ ECharts 柱状图（分数段分布）                           │
├─ 题目分析表 ──────────────────────────────────────────┤
│ ElTable: 题号/题型/满分/均分/得分率/区分度              │
└───────────────────────────────────────────────────────┘
```

**交互**：PowerFilter 选择变化 → watch analysisParams → 重新加载数据 → 图表刷新

### 4.2 contrast.vue — 班级对比

**数据源**：`/analytics/exam/{id}/grade-aggregates`

**布局**：
```
┌─ PowerFilter（班级选"全部班级"时启用对比模式）─────────┐
├─ 对比柱状图 ──────────────────────────────────────────┤
│ ECharts 分组柱状图：各班均分/及格率/优秀率并列          │
├─ 对比表格 ────────────────────────────────────────────┤
│ ElTable: 班级/人数/均分/最高/最低/及格率/优秀率/排名    │
└───────────────────────────────────────────────────────┘
```

**交互**：班级选"全部班级" → 展示对比视图；选具体班级 → 跳转到 exam.vue 带参数

### 4.3 custom.vue — 自定义分析

**数据源**：`POST /analytics/report/query`

**布局**：
```
┌─ PowerFilter ─────────────────────────────────────────┐
├─ 指标选择区 ──────────────────────────────────────────┤
│ ElCheckboxGroup: 总览/分数段/排名/班级对比/趋势         │
├─ 分析结果区 ──────────────────────────────────────────┤
│ 按选中指标动态渲染 ECharts 图表和 ElTable              │
└───────────────────────────────────────────────────────┘
```

**权限**：按角色过滤可选指标（`report_service.RESTRICTED_METRICS`）

### 4.4 table.vue — 自定义表格

**数据源**：同 custom.vue

**区别**：纯表格视图（ElTable 全屏），支持 Excel 导出（xlsx）。提供列选择器（勾选要显示的字段）。

### 4.5 level-score.vue — 等级赋分

**数据源**：`POST /analytics/level-score/convert`

**布局**：
```
┌─ PowerFilter ─────────────────────────────────────────┐
├─ 等级配置区 ──────────────────────────────────────────┤
│ ElTable(editable): 等级/百分位区间/赋分区间             │
│ [预设: 广东新高考] [预设: 浙江] [自定义]               │
├─ 转换结果 ────────────────────────────────────────────┤
│ 左: 赋分前分布图  右: 赋分后分布图（ECharts 对比）      │
├─ 学生明细表 ──────────────────────────────────────────┤
│ ElTable: 姓名/原始分/等级/赋分/排名                    │
│ [导出 Excel]                                          │
└───────────────────────────────────────────────────────┘
```

### 4.6 config.vue — 指标配置

**数据源**：`GET/PUT /analytics/segments/config`

**布局**：
```
┌─ 默认分数段 ──────────────────────────────────────────┐
│ 可编辑边界和标签: [85] 优秀 / [70] 良好 / [60] 及格    │
├─ 科目覆盖 ────────────────────────────────────────────┤
│ 科目列表 + 每个科目可设置独立边界                       │
│ [新增覆盖] [删除覆盖]                                  │
├─ [保存配置]                                            │
└───────────────────────────────────────────────────────┘
```

**注意**：此页面不依赖 PowerFilter（全校级配置）。

## §5 文件清单

### 后端新增

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/modules/analytics/power_options_service.py` | PowerOptionsService（树构建） |
| `src/edu_cloud/modules/analytics/level_score_service.py` | LevelScoreService（赋分算法） |
| `src/edu_cloud/modules/analytics/router.py` | 新增 2 个端点（power-options + level-score/convert） |
| `tests/test_api/test_analytics_power_options.py` | PowerOptions 端点测试 |
| `tests/test_api/test_analytics_level_score.py` | 等级赋分端点测试 |

### 前端新增（frontend-nuxt/）

| 文件 | 职责 |
|------|------|
| `composables/usePowerOptions.ts` | 级联筛选 composable |
| `composables/useApi.ts` | 扩展 analytics 方法（追加，不重写） |
| `components/common/PowerFilter.vue` | 级联筛选 UI 组件 |
| `pages/report/exam.vue` | 考试报告 |
| `pages/report/contrast.vue` | 班级对比 |
| `pages/report/custom.vue` | 自定义分析 |
| `pages/report/table.vue` | 自定义表格 |
| `pages/report/level-score.vue` | 等级赋分 |
| `pages/report/config.vue` | 指标配置 |
| `tests/composables/usePowerOptions.test.ts` | composable 单测 |
| `tests/components/PowerFilter.test.ts` | 组件单测 |

### 不变

- 现有 `frontend/` 分析页面不动
- 现有 analytics 后端端点不动
- 现有数据模型不动（无 migration）

## §6 测试策略

### 后端

| 测试 | 覆盖 |
|------|------|
| PowerOptions 空数据 | 无完成考试 → 返回 `{"grades": []}` |
| PowerOptions 单年级单班 | 1 班 1 考试 → 树结构正确 + "all" 节点存在 |
| PowerOptions 多年级多班 | 2 年级 × 3 班 × 2 科目 → 树嵌套正确 |
| PowerOptions RBAC | 科目教师只看到任教科目 |
| 等级赋分基本转换 | 10 学生 + 5 级 → 等级划分 + 赋分值正确 |
| 等级赋分边界 | 同分学生、1 人等级、空数据 |

### 前端

| 测试 | 覆盖 |
|------|------|
| usePowerOptions 级联重置 | 年级变化 → 班级/科目/考试重置 |
| usePowerOptions analysisParams | 选择 → 输出正确的 API 参数 |
| PowerFilter 渲染 | 4 个选择器正确渲染选项 |
| PowerFilter 禁用态 | 无数据时 disabled |

## §7 不变量（semantic_regression）

| ID | 不可违反的设计决策 |
|------|------|
| ORC-001 | PowerOptions 树中每个节点必须带 id + name，禁止复合键 |
| ORC-002 | "all" 伪班级的 student_count 必须等于该年级所有真实班级的 student_count 之和 |
| ORC-003 | analysisParams 输出的 class_id 当选择"全部班级"时为 null，现有 analytics API 接收 null 表示不过滤班级 |
| ORC-004 | RBAC 过滤在 Service 层完成，前端拿到的树已经是过滤后的，不做二次过滤 |
| ORC-005 | 等级赋分算法必须按原始分降序排列后按百分位切分，同分学生归入同一等级 |
