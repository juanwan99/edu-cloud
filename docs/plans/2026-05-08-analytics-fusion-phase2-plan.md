# 成绩分析融合 Phase 2 — 实施计划

> 基于 `docs/research/2026-05-08-analytics-fusion-proposal.md` Claude×GPT 共识
> Phase 1（激活存量）已完成：commit 95222e4

## 现有资产盘点（Evidence）

### 后端已有但前端未接入的 API（6 个）

| API | 后端实现 | 返回结构 |
|-----|---------|---------|
| `getLayerAnalysis` | `layer_service.py` 147行 | `{layers: [{label, students, knowledge_mastery}], maxDiffKnowledges}` |
| `getClassDiagnosis` | `diagnosis_service.py` 80行 | `{worstKnowledges, unmasterMaxCntKnowledges, maxScoreDiffKnowledges, weakKnpCount}` |
| `getClassErrorPatterns` | `ranking_service.py` | `{classes: [{name, patterns: [{type, count, rate}]}]}` |
| `getPowerOptions` | `power_options_service.py` 147行 | `{grades: [{classes: [{subjects: [{exams}]}]}]}` |
| `queryReport` | `analytics_report_router.py` | 自定义指标构建器 |
| `getQuestionInsights` | `analytics_report_router.py` | 题目难度+区分度+错因分类 |

### 现有页面结构

| 页面 | 行数 | Tab数 | 状态 |
|------|------|-------|------|
| AnalyticsReportPage | 605 | 4(总览/科目/班级/排名) | 完整 |
| AnalyticsPage | 308 | 5(分布/题目/排名/临界生/常错题) | 完整 |
| AnalyticsTrendPage | ~300 | 3维度(年级/班级/学生) | 完整 |
| GradeAnalyticsPage | 305 | 5卡片(对比/趋势/雷达/箱线/热力) | Phase 1 增强完成 |

### 组件库

仅 `ScoreSegmentSettings.vue` 1 个，其余统计展示逻辑内联在页面中。

---

## 设计决策（GPT 共识）

1. **页面结构**：侧栏保持 2 入口（成绩分析 + 阅卷质量报告），成绩分析页面内 6 Tab 共享筛选
2. **筛选器**：接入 powerOptions 级联筛选（年级→班级→科目→考试），替代现有多步级联
3. **AI 诊断**：预聚合快照为主，结构化 JSON 输入 LLM
4. **约束**：有效分优先级链不可破坏；赋分只能是派生视图

---

## 交付路径

- 目标目录：`frontend/src/`（Naive UI 主前端）
- 生产 serving：nginx 443 → `frontend/dist/`
- 用户访问：`https://mcu.asia`
- 构建命令：`cd frontend && npx vite build`

---

## Task 分解

### Batch 1: 统一工作台 + powerOptions 筛选（T1-T3）

#### T1: 成绩分析工作台 Tab 化重构

**目标**：将 AnalyticsReportPage 从 4 Tab 扩展为 6 Tab 统一入口

**现有 4 Tab**（保留）：总览、科目分析、班级对比、学生排名
**新增 2 Tab**：知识点诊断、AI 综合报告（占位）

**改动范围**：
- `AnalyticsReportPage.vue`：新增 2 个 n-tabs panel
- 知识点诊断 Tab：接入 `getClassDiagnosis` + `getClassErrorPatterns` + `getQuestionInsights`
- AI 综合报告 Tab：先放占位（Phase 3 实现）

**文件清单**：
- `frontend/src/pages/AnalyticsReportPage.vue` — 新增 2 Tab
- `frontend/src/components/analytics/KnowledgeDiagnosisPanel.vue` — 新组件：三维诊断面板
- `frontend/src/components/analytics/ErrorPatternPanel.vue` — 新组件：错误模式对比

**测试契约**：
- 入口：AnalyticsReportPage 渲染 6 个 Tab，切换无报错
- 反例：如果 Tab 名写错或组件未注册，切换会白屏
- 边界：无数据时显示空态提示
- 回归：现有 4 Tab 功能不受影响
- 命令：`npx vitest run src/pages/__tests__/AnalyticsReportPage.test.js`

#### T2: powerOptions 级联筛选器组件

**目标**：替代现有多步级联，实现好分数式一次加载

**改动范围**：
- 新建 `frontend/src/components/analytics/PowerOptionsSelector.vue`
- 调用 `getPowerOptions()` 一次获取全量筛选树
- 级联联动：选年级 → 过滤班级 → 过滤科目 → 过滤考试
- 自动选最近一次已完成考试

**文件清单**：
- `frontend/src/components/analytics/PowerOptionsSelector.vue` — 新组件
- `frontend/src/pages/AnalyticsReportPage.vue` — 替换现有筛选器

**测试契约**：
- 入口：PowerOptionsSelector 渲染 4 级下拉，级联联动正确
- 反例：如果不级联过滤，选年级后班级列表仍显示全部班级
- 边界：无考试数据时显示"暂无已完成考试"
- 回归：选考试后图表数据加载与现有行为一致
- 命令：`npx vitest run src/components/analytics/__tests__/PowerOptionsSelector.test.js`

#### T3: 分层学情 Tab

**目标**：接入 layer_service，展示优秀/良好/待提升三层分析

**改动范围**：
- 新建 `frontend/src/components/analytics/LayerAnalysisPanel.vue`
- 调用 `getLayerAnalysis()` 获取分层数据
- 堆叠柱图（班级×层分布）+ 分层学生名单折叠面板

**文件清单**：
- `frontend/src/components/analytics/LayerAnalysisPanel.vue` — 新组件
- `frontend/src/pages/AnalyticsReportPage.vue` — Tab 内引入

**测试契约**：
- 入口：分层 Tab 渲染堆叠柱图和学生名单
- 反例：如果层边界算错，优秀层应 0 人但显示有人
- 边界：全部学生同一层时仍正确渲染
- 回归：其他 Tab 不受影响
- 命令：`npx vitest run src/components/analytics/__tests__/LayerAnalysisPanel.test.js`

### Batch 2: AI 诊断 MVP（T4-T5）

#### T4: AI 诊断后端 — 快照聚合 + LLM 调用

**目标**：新建 AI 成绩诊断服务，基于结构化快照调用 LLM

**改动范围**：
- 新建 `src/edu_cloud/modules/analytics/ai_diagnosis_service.py`
- 聚合 snapshot：exam_summary + class_stats + knowledge_mastery + layer_data
- 构建 prompt（GPT 共识 schema）
- 调用 Gemini（复用现有 LLM 配置）
- 返回结构化 JSON（summary + findings + teaching_actions + data_limits）
- 缓存：以 snapshot_hash + prompt_version 为 key，7 天软 TTL

**新增路由**：
- `POST /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 生成 AI 诊断报告
- `GET /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 获取已缓存报告

**文件清单**：
- `src/edu_cloud/modules/analytics/ai_diagnosis_service.py` — 新服务
- `src/edu_cloud/modules/analytics/analytics_report_router.py` — 新增 2 路由
- `tests/test_services_exam/test_ai_diagnosis.py` — 测试

**测试契约**：
- 入口：POST 请求返回结构化 AI 诊断 JSON
- 反例：如果 prompt 缺少 data_quality 字段，LLM 可能输出无证据的结论
- 边界：无知识点数据时 → data_limits 标注"知识点映射覆盖不足"
- 回归：不影响现有 diagnosis（模板拼接版）
- 命令：`.venv/bin/python -m pytest tests/test_services_exam/test_ai_diagnosis.py -v`

#### T5: AI 诊断前端 — AI 综合报告 Tab

**目标**：实现 AnalyticsReportPage 的"AI 综合报告"Tab

**改动范围**：
- 新建 `frontend/src/components/analytics/AiDiagnosisReport.vue`
- 调用后端 AI 诊断 API
- 展示：整体评价 + 关键发现（带 fact_id 引用）+ 教学建议 + 数据局限声明
- 按钮："重新生成"手动刷新

**文件清单**：
- `frontend/src/components/analytics/AiDiagnosisReport.vue` — 新组件
- `frontend/src/api/analytics.js` — 新增 2 个 API 方法
- `frontend/src/pages/AnalyticsReportPage.vue` — AI Tab 接入

**测试契约**：
- 入口：AI Tab 渲染诊断报告内容
- 反例：如果 API 超时，应显示"生成中"而非空白
- 边界：后端返回 data_limits 时，前端显示"数据局限"提示
- 回归：其他 Tab 不受影响
- 命令：`npx vitest run src/components/analytics/__tests__/AiDiagnosisReport.test.js`

---

## 批次划分

| Batch | Tasks | 依赖 | 预计工作量 |
|-------|-------|------|-----------|
| Batch 1 | T1-T3 | 无（后端已有） | 前端 ~2 天 |
| Batch 2 | T4-T5 | T1（Tab 占位）| 后端+前端 ~2 天 |

**可并行**：T1/T2/T3 相互独立，可并行开发
**不可并行**：T5 依赖 T4（前端需要后端 API）

---

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| powerOptions 全量树数据量过大 | LOW | 当前单校场景可控，多校场景留 cursor 扩展点 |
| AI 诊断 LLM 输出格式不稳定 | MED | 后端 JSON schema 校验 + 降级为"生成失败" |
| 箱线图/热力图 ECharts 组件打包体积 | LOW | 已按需 import，增量小 |
| Tab 化重构影响现有 AnalyticsReportPage 测试 | LOW | 现有测试检查 Tab 存在性，新增 Tab 不影响 |

---

## semantic_regression

- ORC-001: 有效分优先级链（confirmed > ai_done > human > scan）不可变更
- ORC-002: AnalyticsReportPage 现有 4 Tab 功能和数据完全保留
- ORC-003: AI 诊断不替代现有模板诊断（exam_diagnosis），两者共存
- ORC-004: AI 报告缓存 key 必须含 snapshot_hash，同数据同输出
- ORC-005: powerOptions 权限裁剪不可绕过（school_id + visible_class_ids + visible_subject_codes）
