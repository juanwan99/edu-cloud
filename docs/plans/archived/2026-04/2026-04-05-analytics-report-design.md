# Phase 3.3 分析报告设计

> [2026-04-05 21:19:11 实现完成] Commits: bdad685..4e70d59

> 设计时间：2026-04-05 16:38
> 前置：analytics 模块已有 5 个 service 函数 + 11 路由 + 8 AI 工具；W1 工作流预计算 exam_analysis_snapshot + class_exam_report；pipeline 产出 student_exam_snapshots
> 范围：分数段配置 + 自定义分析构建器 + 跨考试对比 + PDF 报告导出

## §0 设计决策记录

| # | 决策 | 结论 | 理由 |
|---|------|------|------|
| D1 | 架构模式 | 纯 Service 层扩展（modules/analytics/ 下新增） | 报告是分析的输出形态，不需要独立模块；复用最多改动最小 |
| D2 | 分数段粒度 | 学校级统一 + 科目级可覆盖 | 大多数学校用统一分数段，少数科目需要特殊阈值 |
| D3 | 跨考试维度 | 年级 + 班级 + 学生三维全覆盖 | 数据底座已有（snapshot + class_report + student_snapshot），上层聚合成本低 |
| D4 | 报告导出 | 日常看实时页面 + 正式报告走 Studio PDF | 复用 Studio 已有的文档模板 + Playwright PDF 能力 |
| D5 | 等级赋分 | 不做 | 单校样本量不够，等级赋分依赖全省数据，容易误导 |
| D6 | 角色覆盖 | 全角色（校长→家长），不同角色看不同粒度 | DataScope 自动裁剪，API 层不写权限判断 |

## §1 分数段配置体系

### 数据模型

新增 `score_segment_config` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| school_id | FK→schools | 隔离 |
| subject_code | String(50), nullable | null = 学校默认，非 null = 科目覆盖 |
| boundaries | JSON | `[85, 70, 60]` 降序阈值列表（百分比制） |
| labels | JSON | `["优秀", "良好", "及格", "不及格"]` 比 boundaries 多一个 |
| created_by | FK→users | 谁配置的 |

**唯一约束**: `(school_id, subject_code)` — 每校每科最多一套，subject_code=null 的那行是学校默认。

**默认值**: 学校首次使用时自动初始化 `boundaries=[85, 70, 60]`, `labels=["优秀", "良好", "及格", "不及格"]`。

### 分段计算逻辑

```python
def compute_segments(scores: list[float], max_score: float,
                     boundaries: list[int], labels: list[str]) -> list[dict]:
    """将原始分按百分比阈值分段。
    
    score → percentage = score / max_score * 100
    从高到低匹配第一个 >= boundary 的段。
    返回 [{label, count, percentage, boundary_min, boundary_max}]
    """
```

替换现有 `exam_distribution` 中硬编码的 5 档。现有 API 行为不变（无 segment config 时用默认值），有配置时用学校配置。

### 分数段 API

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/analytics/segments/config` | MANAGE_SCHOOL_SETTINGS | 获取本校分数段配置（默认 + 科目覆盖列表） |
| PUT | `/api/v1/analytics/segments/config` | MANAGE_SCHOOL_SETTINGS | 更新分数段配置（upsert 语义） |

## §2 自定义分析构建器

### 核心概念

用户选择一组维度，系统返回组合分析结果。不是"报告模板"，而是查询参数组合器。

### 查询维度

| 维度 | 可选值 | 默认 |
|------|-------|------|
| exam_ids | 1~N 次考试 | 必选至少 1 个 |
| subject_codes | 全科 / 指定科目 | 全科 |
| class_ids | 全年级 / 指定班级 | 角色可见范围 |
| metrics | 可勾选组合（见下表） | 全选 |

### 指标菜单

| 指标 key | 名称 | 数据来源 |
|----------|------|---------|
| summary | 考试总览（参考人数/均分/最高/最低/得分率） | analytics.exam_summary |
| segments | 分数段分布 | segment_service + exam_distribution |
| ranking | 班级排名表 | analytics.grade_aggregates |
| questions | 题目得分率分析 | analytics.subject_question_analysis |
| top_bottom | 尖子生/临界生名单（前10%/后10%） | rank_students 基础上切片 |
| weakness | 薄弱知识点 TOP N | profile 模块已有 class_weakness |

### API

```
POST /api/v1/analytics/report/query
Body: {
    "exam_ids": ["id1", "id2"],
    "subject_codes": ["math", "chinese"],  // 可选
    "class_ids": ["cls1"],                 // 可选，默认角色可见
    "metrics": ["summary", "segments", "ranking"]  // 可选，默认全部
}
Response: {
    "exams": [...],
    "metrics": {
        "summary": {...},
        "segments": {...},
        "ranking": {...}
    }
}
```

单个 exam 查询 = 即时分析页面；多个 exam_ids = 跨考试对比的前置数据。

**权限**: DataScope 自动注入，班主任只看自己班，家长只看自己孩子的指标子集（summary + segments，不含 ranking/top_bottom）。

## §3 跨考试对比

### 三个维度

**1. 年级趋势（校长/教务/年级组长）**

```
GET /api/v1/analytics/report/trend/grade
Query: exam_ids=id1,id2,id3&subject_code=math
Response: {
    "points": [
        {"exam_id": "id1", "exam_name": "月考1", "exam_date": "2026-03-15",
         "avg": 78.5, "median": 80, "pass_rate": 0.85, "excellent_rate": 0.32},
        ...
    ]
}
```

数据来源：`exam_analysis_snapshot`（W1 预计算），无快照的实时聚合。

**2. 班级趋势（年级组长/班主任）**

```
GET /api/v1/analytics/report/trend/class
Query: exam_ids=id1,id2,id3&class_id=cls1&subject_code=math
Response: {
    "points": [
        {"exam_id": "id1", "exam_name": "月考1",
         "class_avg": 82.1, "grade_avg": 78.5, "grade_rank": 2,
         "vs_prev": +3.6},
        ...
    ]
}
```

数据来源：`class_exam_report`（W1 预计算 grade_rank / class_avg / grade_avg / vs_last_exam）。

**3. 学生趋势（班主任/家长）**

```
GET /api/v1/analytics/report/trend/student
Query: exam_ids=id1,id2,id3&student_id=stu1&subject_code=math
Response: {
    "points": [
        {"exam_id": "id1", "exam_name": "月考1",
         "score": 92, "class_rank": 3, "grade_rank": 15,
         "class_avg": 82.1, "grade_avg": 78.5},
        ...
    ]
}
```

数据来源：`student_exam_snapshots`（pipeline 产出）。

### 考试排序

所有趋势 API 按 `exam.date` 升序排列，前端直接画折线图。exam_ids 传入顺序不影响结果。

### 权限控制

| 角色 | grade 趋势 | class 趋势 | student 趋势 |
|------|-----------|------------|-------------|
| 校长/教务 | 全部 | 全部 | 全部 |
| 年级组长 | 本年级 | 本年级班级 | 本年级学生 |
| 班主任 | 不可见 | 本班 | 本班学生 |
| 科任教师 | 不可见 | 任教班 | 任教班学生 |
| 家长 | 不可见 | 不可见 | 自己孩子 |

全部通过 DataScope 自动裁剪，API 层不写权限判断逻辑。

## §4 报告导出（Studio PDF 集成）

### 流程

```
用户点"生成报告" → 创建 Studio Document (type=analysis_report)
→ report_service 填充 content_json → Studio 渲染 HTML → Playwright 导出 PDF
```

复用现有 Studio 文档流程，不新建导出管道。

### 报告模板

新增 Studio 模板类型 `analysis_report`，content_json 结构：

```json
{
    "report_type": "exam_analysis",
    "title": "2026年春季期中考试分析报告",
    "school_name": "育才实验中学",
    "generated_at": "2026-04-05T15:00:00+08:00",
    "config": {
        "exam_ids": ["id1"],
        "subject_codes": null,
        "class_ids": null,
        "metrics": ["summary", "segments", "ranking", "questions"]
    },
    "sections": {
        "summary": { "..." : "..." },
        "segments": { "..." : "..." },
        "ranking": { "..." : "..." },
        "questions": { "..." : "..." }
    }
}
```

### 导出 API

```
POST /api/v1/analytics/report/export
Body: {
    "exam_ids": ["id1"],
    "subject_codes": null,
    "class_ids": null,
    "metrics": ["summary", "segments", "ranking"],
    "title": "期中考试分析报告"
}
Response: {
    "document_id": "doc-xxx",
    "status": "draft"
}
```

创建后走 Studio 已有的 `transition` 接口 → 状态流转到 `executed` → 前端下载 PDF。

### 权限

- 生成报告需要 `GENERATE_REPORT` 权限（校长/教务/年级组长已有）
- 班主任可生成本班报告，家长不能生成报告（只看页面数据）

## §5 AI Agent 工具

新增 3 个工具，放入 `ai/tools/analytics_report.py`：

| 工具名 | 描述 | 域 | 输入 |
|--------|------|---|------|
| get_score_segments | 获取分数段配置和某次考试的分段统计 | analytics | exam_id, subject_code(可选) |
| compare_exams | 跨考试对比趋势（年级/班级/学生） | analytics | exam_ids, target_type(grade/class/student), target_id(可选), subject_code(可选) |
| generate_analysis_report | 生成分析报告文档（走 Studio） | analytics | exam_ids, metrics, title(可选) |

全部复用 DataScope 权限裁剪。

## §6 前端页面

### AnalyticsReportPage.vue（新增）

路径: `/analytics/report`，权限: `VIEW_SCORES`

- 顶部：考试多选下拉 + 科目过滤 + 班级过滤 + 指标勾选
- 中部：结果区域（按指标分 Tab 或卡片）— 总览卡片 / 分数段柱状图(ECharts) / 班级排名表 / 题目得分率热力图 / 尖子生临界生表格
- 右上角："导出 PDF" 按钮

### AnalyticsTrendPage.vue（新增）

路径: `/analytics/trend`，权限: `VIEW_SCORES`

- 顶部：考试多选 + 维度切换（年级/班级/学生）
- 中部：ECharts 折线图（多次考试趋势）
- 选中班级/学生时下钻到明细

### ScoreSegmentSettings（嵌入 SchoolSettingsPage）

在学校配置页新增"分数段配置" Tab：学校默认分数段编辑 + 科目覆盖列表（添加/编辑/删除）。

### 路由 + 侧栏

```javascript
// sidebarConfig.js
{ label: '分析报告', path: '/analytics/report', icon: 'BarChart', permission: 'VIEW_SCORES' },
{ label: '成绩趋势', path: '/analytics/trend', icon: 'TrendingUp', permission: 'VIEW_SCORES' },
```

对 principal / academic_director / grade_leader / homeroom_teacher 可见。家长不展示（通过 AI 对话获取趋势）。

## §7 不做什么

- 不做等级赋分（单校样本量不够）
- 不做定时自动生成报告
- 不做报告模板编辑器（固定模板）
- 不做 Word/Excel 导出
- 不做跨校对比（联考模块职责）
- 不新增 module_code（归属 `study_analytics` 模块）

## §8 预估规模

- 后端：~800 行新代码 + ~100 行修改
- 前端：~600 行（2 页面 + 1 设置 Tab + API 层）
- 测试：~400 行（service 层 + API 层）
- 新增 1 表（score_segment_config）+ 1 Alembic migration
- 新增 ~7 API 路由 + 3 AI 工具
