# 成绩分析模块融合 — 跨会话交接文档

> Session: 2743be7a | 2026-05-08 | Claude Opus 4.6
> commits: 95222e4 → e54c8e1 → e9c9d23（3 个实现 commit + 3 个 plan commit）

---

## 一、全局定位：我们在做什么、为什么

### 战略目标

edu-cloud 要从"统计报表平台"升级为"AI 分析平台"。

好分数（haofenshu）是成熟的商业产品，擅长**给教师数据**——统计维度丰富、信息密度高、交互流畅。但它止步于此：数据摆在那里，教师自己看。

edu-cloud 的差异化是：**给教师数据的同时，告诉他们这些数据意味着什么、应该怎么做。** 这依赖两个独有能力：BKT 知识追踪（StudentKnpMastery，贝叶斯模型，大多数竞品没有）和 LLM 诊断（结构化快照 → Gemini → 证据溯源的教学建议）。

### 产品定位公式

```
好分数的统计深度 + edu-cloud 的 AI 能力 = 差异化竞争力
```

### 三层架构

```
┌─────────────────────────────────────────────────┐
│  Layer 3: AI 洞察层（核心差异化）                  │
│  LLM 诊断 / 教学建议 / 成长预测 / 异常预警        │
├─────────────────────────────────────────────────┤
│  Layer 2: 高级分析（借鉴好分数）                   │
│  KP 三维诊断 / 分层学情 / 对比分析 / 等级赋分      │
├─────────────────────────────────────────────────┤
│  Layer 1: 基础统计（对标好分数，已完成）            │
│  考后报告 / 分布 / 排名 / 趋势 / 导出              │
└─────────────────────────────────────────────────┘
```

---

## 二、调研基础：好分数 vs edu-cloud 对比

完整调研在 `docs/research/2026-05-08-analytics-fusion-proposal.md`。核心发现：

### edu-cloud 强于好分数的

| 能力 | 说明 |
|------|------|
| AI 阅卷质量报告 | 7 区块（置信度/偏差/审计），好分数完全没有 |
| BKT 知识追踪 | StudentKnpMastery 贝叶斯模型，好分数是随机模拟 |
| 成绩趋势 | 独立页面，年级/班级/学生 + 对比模式 + 双 Y 轴 |
| PDF/XLSX 导出 | reportlab + openpyxl |
| 有效分优先级链 | confirmed > ai_done > human > scan，数据可信度保障 |

### 好分数强于 edu-cloud 的

| 能力 | 说明 |
|------|------|
| 知识点展示密度 | 三维诊断面板（难度/覆盖面/方差），edu 数据积压在后端 |
| 学生个人画像 | KP 雷达 + 三线进度条 |
| 分层学情 UI | 4 层可配 + 堆叠图 + 名单 |
| 级联筛选 UX | powerOptions 一次加载全树 |
| 对比分析 | 班级/考次对比 + CV% 变异系数 |
| 自定义报告 | 模板保存（Phase 2-3 暂不纳入） |

### 关键洞察

**edu-cloud 的后端实现超前于前端展示**。layer_service、class_boxplot、class_knowledge、class_diagnosis、power_options_service 都已实现，但前端没有调用或展示。本次融合的核心工作是"前端补债 + AI 增量"。

---

## 三、Claude×GPT 共识（6 项决策）

GPT 5.4 做了 2 轮 design consult，6 项决策达成共识：

| # | 决策 | 结论 |
|---|------|------|
| 1 | Phase 优先级 | 交叉推进（筛选契约→工作台→激活存量→好分数展示→AI 诊断→AI 成长） |
| 2 | AI 数据输入 | 混合策略：预聚合快照为主，LLM 吃结构化 JSON（含 fact_id 可追溯） |
| 3 | AI 缓存 | 数据版本失效 + 7 天软 TTL + 手动重生成按钮 |
| 4 | 自定义报告 | 不进当前 scope，先做章节开关 |
| 5 | 等级赋分 | 纳入但可选专项，不覆盖有效分链路 |
| 6 | 页面结构 | 侧栏 2 入口（成绩分析 + 阅卷质量报告），成绩分析页内 Tab 共享筛选 |

---

## 四、已完成的工作

### Phase 1: 激活存量（commit 95222e4）

| 改动 | 说明 |
|------|------|
| sidebarConfig | 补入口 → 后改为 2 入口（共识对齐） |
| GradeAnalyticsPage | 接入已有 boxplot + class-knowledge API，新增箱线图和热力图 |

### Batch 0: 后端基础设施（commit e54c8e1）

| Task | 产出 |
|------|------|
| T0: snapshot 契约 | `snapshot_schema.py` — 9 输入模型 + 5 输出模型 + compute_snapshot_hash（16 测试） |
| T0.5: API 参数补齐 | 4 个 service 补 subject_id/class_id（全部向后兼容，13 测试） |

**参数补齐详情**：

| API | 补了什么 | 文件 |
|-----|---------|------|
| class_diagnosis | subject_id 通过 concept→subject 映射生效 | diagnosis_service.py |
| question_insights | class_id 按学生所属班级过滤 | insights_service.py |
| layer_analysis | subject_id + class_id | layer_service.py |
| class_error_patterns | class_id 单班过滤 | ranking_service.py |

### Batch 1: 前端工作台（commit e9c9d23）

| Task | 产出 |
|------|------|
| T1: Tab 重构 | AnalyticsReportPage 从 4 Tab 扩展为 8 Tab |
| T1: 新组件 | KnowledgeDiagnosisPanel（三维诊断）+ LayerAnalysisPanel（分层学情） |
| T2: 新组件 | PowerOptionsSelector（级联筛选）+ TrendPanel（趋势面板） |
| T3: 路由整合 | trend/grade 改为 redirect，侧栏回退 2 入口 |

**当前 8 个 Tab**（mcu.asia 已上线）：

| Tab | name | 数据来源 | 状态 |
|-----|------|---------|------|
| 总览 | overview | getBasicReport | 原有 |
| 科目分析 | subjects | getBasicReport | 原有 |
| 班级对比 | classes | getBasicReport | 原有 |
| 学生排名 | students | getBasicReport | 原有 |
| 知识点诊断 | knowledge | getClassDiagnosis + getClassErrorPatterns + getQuestionInsights | **新增** |
| 学生/分层学情 | layers | getBasicReport students + getLayerAnalysis | **新增** |
| 趋势追踪 | trend | getGradeTrend / getClassTrend / getStudentTrend | **新增** |
| AI 综合报告 | ai-report | 占位（Batch 2 实现） | **占位** |

---

## 五、未完成的工作

### Batch 2: AI 诊断 MVP（T4 + T5）

这是核心差异化功能，plan 已写（`docs/plans/2026-05-08-analytics-fusion-phase2-plan.md` v2.1）。

#### T4: AI 诊断后端

**要做的**：
1. 新建 `ai_diagnosis_service.py`
   - `build_snapshot()` — 聚合 exam_summary + class_stats + knowledge_mastery + layer_data → DiagnosisSnapshot
   - `generate_diagnosis()` — snapshot → prompt → Gemini → 结构化 JSON
   - `get_or_generate()` — 缓存查找 → 不存在则生成
2. 新建 Alembic migration: `ai_diagnosis_cache` 表（exam_id, cache_key, result_json, created_at, expires_at）
3. 新增 2 路由：
   - `POST /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 生成（force_refresh=true 可选）
   - `GET /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 获取缓存
4. 缓存 key: `sha256(exam_id + school_id + scope + subject_id + class_id + filters_hash + score_version + knowledge_version + prompt_version + model_version + role_scope)`

**AI prompt 输入 schema** 已定义在 `snapshot_schema.py`（DiagnosisSnapshot）。

**AI 输出 schema** 已定义在 `snapshot_schema.py`（DiagnosisOutput）：
- summary + findings + risk_alerts + teaching_actions + student_followups + data_limits
- **每个条目必须含 evidence_fact_ids + confidence**（ORC-008）

**Gemini 调用**：复用项目已有的 LLM 配置（`config.py` 中的 Gemini 段），参考 `grading/gemini_client.py` 的调用模式。

#### T5: AI 诊断前端

**要做的**：
1. 新建 `AiDiagnosisReport.vue` 组件
2. `api/analytics.js` 新增 `generateAiDiagnosis` / `getAiDiagnosis`
3. 替换 AnalyticsReportPage Tab 8 的占位内容
4. 展示：摘要 → 关键发现（证据引用高亮）→ 教学建议 → 数据局限

### 更远期（未在当前 plan 中）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 学生 KP 雷达画像 | P1 | 个人 KP 雷达 + 三线进度条，数据已有 |
| BKT 成长诊断 | P1 | 跨考试知识点趋势，LLM 生成成长画像 |
| 对比分析页 | P2 | 班级/考次对比 + CV% |
| 等级赋分 | P2 | 已有 level_score_service.py 基础 |
| 自定义报告模板 | P3 | 工作量大，等指标块稳定 |
| PDF 图表嵌入导出 | P3 | 当前 PDF 无图表，仅表格文字 |

---

## 六、文件地图

### 后端 analytics 模块（23 文件）

```
src/edu_cloud/modules/analytics/
├── router.py                    # 基础路由（summary/distribution/questions）
├── analytics_report_router.py   # 高级路由（585行，28 端点）
├── service.py                   # exam_summary / distribution
├── basic_report_service.py      # 综合报告（有效分链路核心）
├── ranking_service.py           # 排名 + boxplot + knowledge + error_patterns
├── diagnosis_service.py         # 三维 KP 诊断（本次补了 subject_id 生效）
├── insights_service.py          # 题目洞察（本次补了 class_id）
├── layer_service.py             # 分层学情（本次补了 subject_id + class_id）
├── power_options_service.py     # 级联筛选树（147 行，完整实现）
├── snapshot_schema.py           # ★ 本次新增：AI 诊断 snapshot + 输出 schema
├── ai_report_service.py         # AI 阅卷质量报告（7 区块，独立功能）
├── grade_service.py             # 年级聚合分析
├── report_service.py            # 趋势报告
├── segment_service.py           # 分数段配置
├── level_score_service.py       # 等级赋分（基础已有）
├── exporters.py                 # PDF/XLSX 导出
├── pipeline_service.py          # 考后数据流水线
├── models.py                    # ClassAnalysis / StudentAnalysis ORM
├── identity.py                  # 模块标识
├── __init__.py                  # get_effective_scores 核心函数
├── ai_grading_static_report.py  # 静态 AI 阅卷报告
└── prompts/                     # LLM prompt 模板
```

### 前端 analytics 组件（5 组件 + 4 测试）

```
frontend/src/components/analytics/
├── PowerOptionsSelector.vue     # ★ 本次新增：级联筛选（年级→班级→科目→考试）
├── KnowledgeDiagnosisPanel.vue  # ★ 本次新增：三维知识点诊断
├── LayerAnalysisPanel.vue       # ★ 本次新增：分层学情
├── TrendPanel.vue               # ★ 本次新增：趋势面板
├── ScoreSegmentSettings.vue     # 原有：分数段配置
└── __tests__/                   # 29 组件测试
```

### 前端页面

```
frontend/src/pages/
├── AnalyticsReportPage.vue      # ★ 本次重构：8 Tab 统一入口（770→~900 行）
├── AnalyticsPage.vue            # 单次考试快速分析（独立，未改）
├── AnalyticsTrendPage.vue       # 趋势独立页（保留，路由 redirect 到 Tab）
├── GradeAnalyticsPage.vue       # 年级分析（Phase 1 增强，路由 redirect）
└── AiGradingReportPage.vue      # AI 阅卷质量报告（独立，未改）
```

---

## 七、关键约束（ORC 不变量）

| ID | 约束 | 违反后果 |
|----|------|---------|
| ORC-001 | 有效分优先级链 confirmed > ai_done > human > scan | 成绩数据可信度崩溃 |
| ORC-002 | 原有 4 Tab 数据和功能完全保留 | 教师日常工作流中断 |
| ORC-003 | AI 诊断不替代模板诊断（exam_diagnosis） | 两者共存，各有场景 |
| ORC-004 | AI 缓存 key 精确包含 11 维度 | 同数据不同报告 = 信任崩溃 |
| ORC-005 | powerOptions 权限裁剪不可绕过 | 数据越权 |
| ORC-006 | API 参数补齐向后兼容 | 不传新参数 = 旧行为 |
| ORC-007 | `all` 班级 → scope=grade，不传 class_id | 全年级聚合 vs 单班过滤 |
| ORC-008 | AI 输出每项必须含 evidence_fact_ids + confidence | 无证据的 AI 建议不可信 |
| ORC-009 | 侧栏最终 2 入口 | 共识决策 |

---

## 八、GPT plan review 状态

- R1: FAIL（3 HIGH + 6 MED + 1 LOW）→ 全部处置
- R2: FAIL（2 HIGH + 5 MED）→ 文档精确性问题，非设计缺陷
- 用户决策：WONTFIX 剩余文档细节，直接执行

R2 遗留 finding（执行时自然解决）：
- R2-F-001: 缓存 key 字段名精确对齐（实现时按 ORC-004 走）
- R2-F-002: data_limits 的 fact_id vs evidence_fact_ids（实现时按 ORC-008 走）
- R3-F-002: db_migrate downgrade 语法（实现时按 scripts/db_migrate 实际接口走）

---

## 九、测试基线

| 范围 | 数量 | 说明 |
|------|------|------|
| 后端 pytest 全量 | ~2246 passed / ~33 failed（既有债） | 本次 0 新增失败 |
| 前端 vitest 全量 | ~2487 passed / ~8 failed（SubjectStatusCard 既有债） | 本次 0 新增失败 |
| snapshot_schema 测试 | 16 passed | `tests/test_services_exam/test_snapshot_schema.py` |
| API 参数补齐测试 | 13 passed | `tests/test_services_exam/test_analytics_filter_params.py` |
| 组件测试 | 29 passed | `frontend/src/components/analytics/__tests__/` |

---

## 十、好分数 clone 参考资料

位置：`~/projects/haofenshu-clone/`（28 表 / 45 页面 / 9 路由模块）

**可参考的**：
- 信息架构（页面布局、筛选交互模式）
- powerOptions 级联设计
- 知识点三维诊断面板 UI

**不可参考的**：
- study.js 的知识点数据是随机模拟，不是真实算法
- class name fallback 逻辑（edu-cloud 必须用 ID + 权限裁剪）

详细调研：`docs/research/2026-05-08-analytics-fusion-proposal.md`

---

## Goal

完成 Batch 2（AI 诊断后端 T4 + 前端 T5），让 Tab 8 "AI 综合报告"从占位变为可用。

## Must Preserve

- 有效分优先级链（ORC-001）
- 现有 8 Tab 功能（ORC-002，特别是前 4 个原有 Tab）
- 向后兼容的 API 参数（ORC-006）
- snapshot_schema.py 定义的输入输出 schema

## Must Not Change

- basic_report_service.py 的有效分聚合逻辑
- ai_report_service.py（阅卷质量报告，独立功能线）
- 已有 29 个后端测试 + 29 个组件测试的断言
