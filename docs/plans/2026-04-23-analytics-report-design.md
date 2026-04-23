# 分析报告前端体系设计（基础 + AI 进阶双层）

## 1. 概述

### 1.1 目标

在 `frontend-nuxt/` 中实现分析报告前端体系，让教师通过 4 个业务页面 + 1 个配置页面完成考后数据分析。每个业务页面分**基础分析**和 **AI 深度诊断**两个 Tab：

- **基础分析**：常规成绩统计（分数分布、排名、趋势），任何阅卷系统都能提供的数据
- **AI 深度诊断**：深度融合 AI 阅卷过程数据（逐空错因、知识点掌握趋势、错误模式分类），edu-cloud 独有

### 1.2 核心理念

好分数给的是**原料**（数据表格），让教师自己分析。edu-cloud 给的是**结论**（AI 已读完每份答卷后的诊断），附上数据支撑。

### 1.3 AI 阅卷数据优势

| 维度 | 传统系统 | edu-cloud AI 阅卷 |
|------|---------|-------------------|
| 分数 | 总分 | 总分 + 逐空评分 + AI 置信度 |
| 错因 | 只知道"错了" | `reason`: AI 说明违反了哪条评分规则 |
| 评语 | 无 | `ai_feedback`: 30-80 字诊断评语 |
| 知识点 | 静态掌握率 | 掌握率 + `trend`: improving/declining/stable |
| 错题本 | 无 | 自动收集 + `mastery_status` + 重试追踪 |
| 题目质量 | 无 | `difficulty` 难度 + `discrimination` 区分度 |
| 错误模式 | 无 | `error_distribution`: {概念混淆: 0.45, 粗心: 0.30, ...} |

数据来源链路：

```
StudentAnswer（原始答题）
    ↓ AI 阅卷 Worker
GradingResult（ai_score + ai_feedback + ai_raw_response.details[].blanks[].reason）
    ↓ Pipeline 聚合
├── BankQuestion（difficulty, discrimination, common_errors）
├── StudentErrorBook（ai_feedback, knowledge_point_ids, mastery_status）
├── StudentExamSnapshot（total_score, class_rank, grade_rank, knowledge_scores）
├── StudentKnowledgeMastery（mastery_level, trend, recent_scores）
└── StudentErrorPattern（error_distribution）
```

## 2. 页面架构

### 2.1 页面清单

| 页面 | 路由 | 基础 Tab | 进阶 Tab |
|------|------|---------|---------|
| 考后总览 | `/report/exam` | 概览卡片 + 分数分布 + 班级排名 + 题目分析 | 题目错因聚合 + AI 诊断文本 + 题目质量散点 |
| 学生追踪 | `/report/students` | 排名表(进退步) + 个体趋势折线 + 逐题得分 | 临界生名单 + 偏科预警 + 知识点雷达 + AI 诊断 |
| 班级对比 | `/report/contrast` | 多班对比表 + 均分柱图 + 箱线图 + 趋势折线 | 知识点热力图 + 错误模式对比 + AI 班级诊断 |
| 等级赋分 | `/report/level-score` | 等级配置 + 转换前后分布 + 统计表 + 学生明细 | （无，纯算法页） |
| 参数配置 | `/report/config` | 分数段设置 + 科目覆盖 + 临界/偏科/进退步阈值 | — |

### 2.2 Tab 切分策略

同一页面内用 Element Plus `el-tabs` 分区。进阶 Tab 数据**懒加载**：`v-if="activeTab === 'advanced'"` 控制，用户不点不请求。

### 2.3 页面入口

所有报告页面共享顶部 `PowerFilter` 组件（年级→班级→科目→考试级联筛选）。选定考试后驱动整页数据加载。

## 3. 页面详细设计

### 3.1 考后总览（report/exam.vue）

教师考完试第一个打开的页面，回答"这次考得怎么样"。

#### 基础 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 统计卡片（4 张） | `StatCard` | `GET /analytics/exam/{id}/summary` | 参考人数、平均分、及格率、优秀率。趋势箭头通过前端对比上次考试 delta 计算 |
| 成绩分布柱状图 | `ScoreDistChart` | `GET /analytics/exam/{id}/distribution` | 动态分数段（boundaries 来自 segments/config），及格线/优秀线标注 |
| 班级排名表 | `ClassRankTable` | `GET /analytics/exam/{id}/grade-aggregates` | class_rankings 数组：班级名、均分、及格率、优秀率、排名。低于年级均分标红 |
| 题目分析表 | `QuestionAnalysis` | `GET /analytics/subject/{id}/questions` | 逐题均分/得分率，得分率条件着色（<50% 红、50-80% 黄、>80% 绿），按得分率升序 |

#### 进阶 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| AI 诊断摘要 | `AiDiagnosisCard` | `GET /analytics/exam/{id}/diagnosis` **（新）** | 2-4 句自然语言结论：均分对比 + 主要失分题 + 高频错因 + 教学建议 |
| 题目错因聚合 | `ErrorCausePanel` | `GET /analytics/exam/{id}/question-insights` **（新）** | 每题的 top 错因 + 错误人数 + 全局错因分布饼图 |
| 题目质量评估 | ECharts scatter | 同 question-insights | 难度×区分度散点图，异常题标记（区分度<0.15 或 难度<0.3） |

#### AI 诊断文本生成规则

模板拼接（不调 LLM），毫秒级响应，无幻觉风险：

```python
parts = []
if class_avg < grade_avg:
    parts.append(f"本次考试均分 {class_avg:.1f}，低于年级 {grade_avg - class_avg:.1f} 分。")
if weak_questions:
    q = weak_questions[0]
    parts.append(f"主要失分集中在第 {q['name']} 题（得分率 {q['score_rate']:.0%}）。")
if top_error_cause:
    e = top_error_cause
    parts.append(f"{e['pct']:.0%} 学生因{e['cause']}扣分。")
if suggestion:
    parts.append(f"建议{suggestion}。")
```

### 3.2 学生追踪（report/students.vue）

回答"谁需要关注"——班主任和科任老师高频使用。

#### 基础 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 学生排名表 | `StudentRankTable` | `GET /analytics/exam/{id}/student-rankings` **（新）** | 姓名、总分、班名次、年名次、vs 上次（delta）。退步 ≥N 名标红，进步标绿。及格线/优秀线分隔行。可搜索、可导出 |
| 个体趋势（展开区域） | `TrendLine` ×2 | `GET /analytics/report/trend/student` | 点击学生行展开：成绩折线（分数+班均分）+ 排名折线（班名次+年名次） |
| 逐题得分 | 行内标签 | `getStudentExamScores`（已有） | 展开区域底部：[1:3/3 ✓] [2:2/3 △] [8:0/4 ✗] 逐题色块 |

#### 进阶 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 临界生名单 | `CriticalStudents` | `GET /analytics/exam/{id}/critical-students` **（新）** | 差 N 分及格 / 差 N 分优秀的学生列表 + 丢分最多的题目。N 来自 config 页配置（默认 3） |
| 偏科预警 | `el-table` | **前端计算** | 多科 class_rank 标准差，某科排名与其他科均值差 ≥N 名标记。N 来自 config（默认 15） |
| 知识点雷达 + AI 诊断（展开区域） | `RadarChart` + `AiDiagnosisCard` | `GET /profile/students/{id}/knowledge`（已有）+ `GET /profile/students/{id}/ai-diagnosis` **（新）** | 点击学生展开：各知识点掌握率雷达图 + 趋势方向箭头 + 2-3 句 AI 诊断文本 |

### 3.3 班级对比（report/contrast.vue）

回答"我的班在什么水平"——科任老师跨班对比、年级组长全局视角。

PowerFilter 此页**不选班级**，默认展示该年级全部班。

#### 基础 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 班级对比表 | `el-table` | `GET /analytics/exam/{id}/grade-aggregates` | 班级、人数、均分、最高、最低、及格率、优秀率、排名。低于年级均分标红底色 |
| 均分柱状图 | ECharts bar | 同上 | 各班均分柱图 + 年级均分参考线 |
| 分数箱线图 | ECharts boxplot | `GET /analytics/exam/{id}/class-boxplot` **（新）** | 各班 min/p25/median/p75/max，直观看离散度 |
| 趋势对比折线 | `TrendLine` | `GET /analytics/report/trend/class` ×N 班 | 多条折线 + 年级均分虚线 |

#### 进阶 Tab

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 知识点热力图 | `KnowledgeHeatmap` | `GET /analytics/exam/{id}/class-knowledge` **（新）** | 行=班级、列=知识点、色值=掌握率。≥80% 深绿、60-79% 黄、<60% 红 |
| 错误模式对比 | `el-table` 着色 | `GET /analytics/exam/{id}/class-error-patterns` **（新）** | 行=班级、列=错误类型（概念/计算/步骤/审题）、值=占比。异常高占比标红 |
| AI 班级诊断 | `AiDiagnosisCard` | `GET /analytics/exam/{id}/diagnosis?class_id=X` **（新，复用 §3.1 端点）** | 针对特定班级的诊断文本 |

### 3.4 等级赋分（report/level-score.vue）

新高考选科赋分刚需。纯算法页，无进阶 Tab。

| 区块 | 组件 | 数据来源 API | 说明 |
|------|------|-------------|------|
| 等级配置表 | `el-form` | 前端内置默认值 | 5 个等级：百分位区间 + 赋分区间。支持浙江/山东等省份预设和自定义 |
| 转换前后分布对比 | `ScoreDistChart` ×2 | `POST /analytics/level-score/convert`（已有） | 左：原始分柱状图（偏态）。右：赋分后柱状图（趋近正态） |
| 等级统计表 | `el-table` | 同上 response.level_stats | 等级、人数、占比、原始分范围、赋分范围 |
| 学生明细表 | `el-table` | 同上 response.students | 排名、姓名、原始分、等级、赋分、同分人数。ORC-005：同分同级。可导出 Excel |

### 3.5 参数配置（report/config.vue）

管理分析报告全局参数。仅 `MANAGE_EXAM_RESULTS` 权限可见。

| 区块 | 数据来源 API | 说明 |
|------|-------------|------|
| 分数段配置（学校默认） | `GET/PUT /analytics/segments/config`（已有） | boundaries 滑块 + labels 输入。默认 85/70/60 |
| 科目覆盖配置 | `GET/PUT/DELETE /analytics/segments/config`（已有） | 列表展示已有覆盖 + 添加新覆盖 + 删除 |
| 临界生阈值 | `PATCH /schools/{id}/settings`（已有 KV API） | key: `analytics.critical_threshold`，默认 3 |
| 偏科预警阈值 | 同上 | key: `analytics.imbalance_threshold`，默认 15 |
| 进退步标记阈值 | 同上 | key: `analytics.rank_change_threshold`，默认 5 |

阈值存入 SchoolSettings KV 表，前端通过 `GET /schools/{id}/settings?category=analytics` 读取。

## 4. 后端新增 API

### 4.1 完整清单

| # | 端点 | 方法 | 入参 | 返回结构 | 数据来源 |
|---|------|------|------|---------|---------|
| 1 | `/analytics/exam/{exam_id}/question-insights` | GET | `subject_id?: str` | `{questions: [{question_id, name, score_rate, error_causes: [{cause, count, pct}], difficulty, discrimination}]}` | GradingResult.ai_raw_response 聚合 + BankQuestion |
| 2 | `/analytics/exam/{exam_id}/diagnosis` | GET | `subject_id?: str, class_id?: str` | `{summary_text: str, weak_questions: [{name, score_rate}], error_distribution: {cause: pct}, suggestions: [str]}` | 聚合低分题 + reason 高频词 → 模板拼接 |
| 3 | `/analytics/exam/{exam_id}/student-rankings` | GET | `subject_id?: str, class_id?: str` | `{students: [{student_id, name, score, class_rank, grade_rank, prev_class_rank, prev_grade_rank, delta_class, delta_grade}]}` | StudentExamSnapshot 当前 vs 上一次 |
| 4 | `/analytics/exam/{exam_id}/critical-students` | GET | `subject_id?: str, class_id?: str, threshold?: int = 3` | `{near_pass: [{student_id, name, score, gap, worst_question}], near_excellent: [{...}]}` | 排名数据 + ScoreSegmentConfig 阈值 |
| 5 | `/profile/students/{id}/ai-diagnosis` | GET | `exam_id?: str, subject_id?: str` | `{summary: str, improving: [{kp_name, recent_scores, trend}], declining: [{...}], weak_points: [{...}]}` | KnowledgeMastery + ErrorBook → 模板拼接 |
| 6 | `/analytics/exam/{exam_id}/class-boxplot` | GET | `subject_id?: str` | `{classes: [{class_id, name, min, p25, median, p75, max, count}]}` | StudentAnswer/GradingResult 按班聚合 |
| 7 | `/analytics/exam/{exam_id}/class-knowledge` | GET | `subject_id?: str` | `{knowledge_points: [str], classes: [{class_id, name, mastery: [{kp_name, rate}]}]}` | StudentKnowledgeMastery 按班聚合 |
| 8 | `/analytics/exam/{exam_id}/class-error-patterns` | GET | `subject_id?: str` | `{error_types: [str], classes: [{class_id, name, distribution: {type: pct}}]}` | StudentErrorPattern 按班聚合 |

### 4.2 诊断文本生成策略

端点 #2 和 #5 生成自然语言诊断文本。**不调用 LLM**，使用模板拼接：

- 响应时间：毫秒级（vs LLM 2-5 秒）
- 幻觉风险：零（每句话都基于确切数据）
- 模板覆盖场景：均分对比（高于/低于年级）、主要失分题、高频错因、知识点趋势（上升/下降）、教学建议

模板存放在 service 层（`analytics/diagnosis_service.py`），不硬编码到 router。

### 4.3 错因聚合算法（question-insights 核心）

```python
async def aggregate_error_causes(db, exam_id, subject_id, school_id):
    # 1. 查询该科所有 GradingResult（status=confirmed 或 ai_done）
    # 2. 解析 ai_raw_response.details[].blanks[].reason
    # 3. 对 reason 文本做关键词提取：
    #    - 含"概念"/"混淆"/"误写" → 分类为"概念混淆"
    #    - 含"计算"/"运算"/"数值" → 分类为"计算错误"
    #    - 含"步骤"/"不完整"/"缺少" → 分类为"步骤不完整"
    #    - 含"审题"/"理解" → 分类为"审题不清"
    #    - 其他 → "其他"
    # 4. 按题目聚合：{question_id: {cause: count}}
    # 5. 合并 BankQuestion 的 difficulty/discrimination
```

关键词分类是 V1 策略。未来可升级为 LLM 分类（离线批处理，Pipeline 阶段写入 `error_type` 字段）。

### 4.4 进退步计算算法（student-rankings 核心）

```python
async def compute_rank_delta(db, exam_id, school_id, subject_id, class_id):
    # 1. 查当前考试的 StudentExamSnapshot
    # 2. 查同校同年级上一次考试（按 exam_date 倒序取第 2 条）
    # 3. 对同一学生，delta = prev_rank - current_rank（正数=进步）
    # 4. 若无上次考试数据，delta = None
```

### 4.5 权限模型

所有新端点沿用现有 analytics router 的权限模式：
- 登录即可访问（`get_current_user` 依赖）
- 数据可见性通过 `visible_class_ids` + `visible_subject_codes` 过滤
- 诊断文本只包含用户可见范围内的数据

## 5. 前端架构

### 5.1 文件结构

```
frontend-nuxt/
  composables/
    useApi.ts              # 已有，追加 8 个新方法
    usePowerOptions.ts     # 级联筛选（PowerOptions plan 已设计）
    useAnalytics.ts        # 新增：分析数据请求 + 缓存 + 懒加载控制
  components/
    shell/                 # 已有（TopNav/SubNav/UserDropdown）
    analytics/
      PowerFilter.vue      # 级联筛选器（年级→班级→科目→考试）
      StatCard.vue          # 统计卡片（数字 + 趋势箭头 + 副标题）
      ScoreDistChart.vue    # 成绩分布柱状图（ECharts bar + 及格/优秀线）
      ClassRankTable.vue    # 班级排名表（el-table + 条件着色）
      QuestionAnalysis.vue  # 题目分析表（得分率进度条 + 着色）
      TrendLine.vue         # 趋势折线图（ECharts line，通用）
      StudentRankTable.vue  # 学生排名表（进退步标记 + 临界生标记 + 展开行）
      RadarChart.vue        # 雷达图（ECharts radar，科目/知识点通用）
      KnowledgeHeatmap.vue  # 知识点热力图（ECharts heatmap，班级×知识点）
      AiDiagnosisCard.vue   # AI 诊断卡片（蓝色左边框 + 自然语言文本）
      ErrorCausePanel.vue   # 错因聚合面板（表格 + 饼图）
      CriticalStudents.vue  # 临界生列表（分及格/优秀两组）
  pages/
    report/
      exam.vue             # 考后总览
      students.vue         # 学生追踪
      contrast.vue         # 班级对比
      level-score.vue      # 等级赋分
      config.vue           # 参数配置
```

### 5.2 核心数据流

```
PowerFilter emit analysisParams: { exam_id, subject_id?, class_id? }
    ↓
useAnalytics.loadBasicData(params)
    ↓ 并行请求
    ├── getExamSummary        → StatCard ×4
    ├── getExamDistribution   → ScoreDistChart
    ├── getGradeAggregates    → ClassRankTable
    └── getSubjectQuestions   → QuestionAnalysis
    ↓
渲染基础 Tab
    ↓ 用户点击进阶 Tab
    ↓ v-if 触发懒加载
useAnalytics.loadAdvancedData(params)
    ├── getQuestionInsights    → ErrorCausePanel + 散点图
    ├── getExamDiagnosis       → AiDiagnosisCard
    └── (页面特定的其他请求)
```

### 5.3 useAnalytics composable 设计

```typescript
export function useAnalytics() {
  const loading = ref(false)
  const advancedLoading = ref(false)
  
  // 基础数据（切换考试时自动刷新）
  const summary = ref(null)
  const distribution = ref(null)
  const gradeAggregates = ref(null)
  const questions = ref(null)
  
  // 进阶数据（懒加载，切换考试时清空）
  const questionInsights = ref(null)
  const diagnosis = ref(null)
  
  async function loadBasicData(params) {
    loading.value = true
    clearAdvancedData()
    const [s, d, g, q] = await Promise.all([
      getExamSummary(params.exam_id),
      getExamDistribution(params.exam_id, params.subject_id),
      getExamGradeAggregates(params.exam_id, params.subject_id),
      params.subject_id ? getSubjectQuestions(params.subject_id) : null,
    ])
    summary.value = s; distribution.value = d
    gradeAggregates.value = g; questions.value = q
    loading.value = false
  }
  
  async function loadAdvancedData(params) {
    if (questionInsights.value) return  // 已加载则跳过
    advancedLoading.value = true
    const [qi, diag] = await Promise.all([
      getQuestionInsights(params.exam_id, params.subject_id),
      getExamDiagnosis(params.exam_id, params.subject_id, params.class_id),
    ])
    questionInsights.value = qi; diagnosis.value = diag
    advancedLoading.value = false
  }
  
  function clearAdvancedData() {
    questionInsights.value = null
    diagnosis.value = null
  }
  
  return { loading, advancedLoading, summary, distribution,
           gradeAggregates, questions, questionInsights, diagnosis,
           loadBasicData, loadAdvancedData }
}
```

### 5.4 技术选型

| 决策 | 选择 | 理由 |
|------|------|------|
| 图表库 | `echarts` + `vue-echarts` | frontend/ 已用 ECharts 6，保持一致 |
| 图表引入 | 按需 import（BarChart, LineChart, ScatterChart, RadarChart, HeatmapChart, BoxplotChart） | 控制 bundle 体积 |
| 状态管理 | composable（不用 Pinia store） | 分析数据是页面级，非全局共享 |
| 表格 | Element Plus `el-table` | 已有依赖，排序/筛选/导出内置 |
| 响应式 | 桌面优先，最小宽度 1200px | 教师用电脑看报告 |
| 进阶 Tab 加载 | `v-if="activeTab === 'advanced'"` | 不点不请求 |

### 5.5 useApi.ts 追加方法

```typescript
// 进阶分析 API（8 个新方法）
getQuestionInsights: (examId: string, subjectId?: string) =>
  request(`/analytics/exam/${examId}/question-insights`, { params: { subject_id: subjectId } }),

getExamDiagnosis: (examId: string, subjectId?: string, classId?: string) =>
  request(`/analytics/exam/${examId}/diagnosis`, { params: { subject_id: subjectId, class_id: classId } }),

getStudentRankings: (examId: string, subjectId?: string, classId?: string) =>
  request(`/analytics/exam/${examId}/student-rankings`, { params: { subject_id: subjectId, class_id: classId } }),

getCriticalStudents: (examId: string, subjectId?: string, classId?: string, threshold?: number) =>
  request(`/analytics/exam/${examId}/critical-students`, { params: { subject_id: subjectId, class_id: classId, threshold } }),

getStudentAiDiagnosis: (studentId: string, examId?: string, subjectId?: string) =>
  request(`/profile/students/${studentId}/ai-diagnosis`, { params: { exam_id: examId, subject_id: subjectId } }),

getClassBoxplot: (examId: string, subjectId?: string) =>
  request(`/analytics/exam/${examId}/class-boxplot`, { params: { subject_id: subjectId } }),

getClassKnowledge: (examId: string, subjectId?: string) =>
  request(`/analytics/exam/${examId}/class-knowledge`, { params: { subject_id: subjectId } }),

getClassErrorPatterns: (examId: string, subjectId?: string) =>
  request(`/analytics/exam/${examId}/class-error-patterns`, { params: { subject_id: subjectId } }),
```

## 6. 与现有 PowerOptions Plan 的关系

已有 PowerOptions plan（`docs/plans/2026-04-23-power-options-plan.md`，R2 PASS）：

| Plan Task | 状态 | 本设计影响 |
|-----------|------|-----------|
| T1 PowerOptionsService + 端点 | ✅ 已实现 (aae6d50) | 保留 |
| T2 LevelScoreService + 端点 | ✅ 已实现 (aae6d50) | 保留 |
| T3 usePowerOptions composable | 待实现 | **保留**，本设计依赖它 |
| T4-T9 前端 6 个报告页面 | 待实现 | **被本设计替代**（4+1 页，内容更丰富） |
| T10 config + CLAUDE.md | 待实现 | **被本设计吸收** |

本设计是 PowerOptions plan 前端部分的**升级版**，后端基础设施完全兼容。

## 7. 实现分批

| Batch | 范围 | 内容 |
|-------|------|------|
| **Batch 1** | 后端新 API + composable | 8 个新端点 + `useAnalytics.ts` + ECharts 依赖安装 + useApi 追加 |
| **Batch 2** | 考后总览 + 参数配置 | `exam.vue`（基础+进阶 Tab）+ `config.vue` + PowerFilter + StatCard + ScoreDistChart + ClassRankTable + QuestionAnalysis + AiDiagnosisCard + ErrorCausePanel |
| **Batch 3** | 学生追踪 + 班级对比 | `students.vue`（基础+进阶 Tab）+ `contrast.vue`（基础+进阶 Tab）+ StudentRankTable + TrendLine + RadarChart + CriticalStudents + KnowledgeHeatmap |
| **Batch 4** | 等级赋分 + 收尾 | `level-score.vue` + usePowerOptions composable（从 PowerOptions plan T3 搬入） + CLAUDE.md 更新 + 全量测试 |

## 8. 测试策略

### 后端

- 每个新 API 端点至少 3 个测试：空数据、正常数据、权限过滤
- 错因聚合算法：测试 reason 文本分类准确性
- 诊断文本生成：测试各场景模板拼接

### 前端

- 每个 composable 方法：Vitest mock API 调用
- 每个组件：mount 测试（props 传入 + 渲染验证）
- 页面级：PowerFilter 联动 → 数据加载 → 组件渲染的集成测试
- 进阶 Tab 懒加载：验证切 Tab 前不发请求

## 9. 不变量（semantic_regression）

- ORC-001: PowerOptions 树中每个节点必须带 id + name，禁止复合键
- ORC-002: "all" 伪班级的 student_count 等于真实班级之和
- ORC-003: analysisParams.class_id 选"全部班级"时为 null
- ORC-004: RBAC 过滤在 Service 层完成，前端不做二次过滤
- ORC-005: 等级赋分同分学生归入同一等级
- ORC-006: 进阶 Tab 数据必须懒加载，用户不点不请求
- ORC-007: 诊断文本使用模板拼接，不调用 LLM，不产生幻觉
- ORC-008: 错因分类基于 GradingResult.ai_raw_response.details，无 AI 阅卷数据时进阶 Tab 显示空态提示
