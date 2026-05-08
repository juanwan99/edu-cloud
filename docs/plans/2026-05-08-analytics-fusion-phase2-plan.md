# 成绩分析融合 Phase 2 — 实施计划 v2

> 基于 `docs/research/2026-05-08-analytics-fusion-proposal.md` Claude×GPT 共识
> Phase 1（激活存量）已完成：commit 95222e4
> **R1 FAIL**（3 HIGH + 6 MED + 1 LOW）→ R2 修复版

## R1 Finding 处置

| ID | 级别 | 处置 |
|----|------|------|
| F-001 | HIGH | **resolved-correct**: Tab IA 重新对齐共识 6 Tab 定义，分层归入"学生/分层学情" |
| F-002 | HIGH | **resolved-correct**: 新增 T0（snapshot 契约定义）作为 AI 前置 |
| F-003 | HIGH | **resolved-correct**: 缓存 key 补全 10+ 维度 |
| F-004 | MED | **resolved-correct**: T0.5 补 class_diagnosis subject_id 生效 |
| F-005 | MED | **resolved-correct**: T0.5 补 questionInsights class_id 参数 |
| F-006 | MED | **resolved-correct**: T0.5 补 layerAnalysis subject_id/class_id 参数 |
| F-007 | MED | **resolved-correct**: T2 定义 powerOptions → 现有状态映射，含 `all` 虚拟节点处理 |
| F-008 | MED | **resolved-correct**: 所有 Task 测试契约补全 5 字段 |
| F-009 | MED | **resolved-correct**: 风险等级全面调整 |
| F-010 | LOW | **resolved-correct**: 事实更新（行数、返回结构） |

---

## 现有资产盘点（Evidence）

### 后端已有但前端未接入的 API（6 个）

| API | 后端实现 | 返回结构（GPT R1 验证） | 筛选参数缺失 |
|-----|---------|---------|------|
| `getLayerAnalysis` | `layer_service.py` | `{exam_id, layers: [{label, count, avgScoreRate, knowledgeMastery: [{knpId, avgRate}]}], maxDiffKnowledges: [{knpId, topLayerRate, bottomLayerRate, diff}]}` | **无 subject_id / class_id** |
| `getClassDiagnosis` | `diagnosis_service.py` | `{worstKnowledges, unmasterMaxCntKnowledges, maxScoreDiffKnowledges, weakKnpCount}` | **subject_id 签名有但未生效** |
| `getClassErrorPatterns` | `ranking_service.py` | `{classes: [{name, patterns: [{type, count, rate}]}]}` | **无 class_id** |
| `getPowerOptions` | `power_options_service.py` 147行 | `{grades: [{id, name, classes: [{id, name, subjects: [{code, name, exams: [{id, name, exam_date, student_count}]}]}]}]}` | 完整 |
| `queryReport` | `analytics_report_router.py` | 自定义指标构建器 | 完整 |
| `getQuestionInsights` | `analytics_report_router.py` | 题目难度+区分度+错因分类 | **无 class_id** |

### 现有页面结构

| 页面 | 行数 | Tab数 | 状态 |
|------|------|-------|------|
| AnalyticsReportPage | ~770 | 4(总览/科目/班级/排名) | 完整 |
| AnalyticsPage | 308 | 5(分布/题目/排名/临界生/常错题) | 完整 |
| AnalyticsTrendPage | ~300 | 3维度(年级/班级/学生) | 完整 |
| GradeAnalyticsPage | 305 | 5卡片(对比/趋势/雷达/箱线/热力) | Phase 1 增强 |

---

## 设计决策（GPT 共识 + R1 修正）

1. **6 Tab 定义**（F-001 修正）：
   - Tab 1: 考后总览（现有"总览"Tab 保留）
   - Tab 2: 班级/年级对比（现有"班级对比"Tab 扩展）
   - Tab 3: 知识点诊断（新增：三维诊断 + 错误模式 + 题目洞察）
   - Tab 4: 学生/分层学情（现有"学生排名"Tab + 分层分析合并）
   - Tab 5: 趋势追踪（嵌入 AnalyticsTrendPage 核心逻辑）
   - Tab 6: AI 综合报告（新增：LLM 诊断）
2. **现有 Tab 映射**：总览→Tab1, 科目分析→Tab1 内子面板, 班级对比→Tab2, 学生排名→Tab4
3. **筛选器**：powerOptions 级联，`all` 虚拟节点映射为 scope=grade（不传 class_id）
4. **AI 前置**：先定义 snapshot 契约，再实现 LLM 调用（F-002）
5. **缓存 key**（F-003 修正）：`exam_id + school_id + scope + subject_id + class_id + filters_hash + score_version + knowledge_version + prompt_version + model_version + role_scope`

---

## 交付路径

- 目标目录：`frontend/src/`（Naive UI 主前端）
- 生产 serving：nginx 443 → `frontend/dist/`
- 用户访问：`https://mcu.asia`
- 构建命令：`cd frontend && npx vite build`

---

## Task 分解

### Batch 0: 后端参数补齐（T0-T0.5）

#### T0: Snapshot 契约定义

**目标**：定义 AI 诊断的数据快照 schema + fact_id 约定（F-002 修复）

**产出**：
- `src/edu_cloud/modules/analytics/snapshot_schema.py` — Pydantic schema 定义
- schema 含：context / snapshot_meta / data_quality / score_summary / comparison / knowledge_points / student_groups / constraints
- 每个数据条目带 `fact_id` 前缀（如 `kp:K031`, `layer:need_help`, `score:class_avg`）
- snapshot_hash 计算函数：基于 score_version + knowledge_version + filters 的确定性 hash

**文件清单**：
- `src/edu_cloud/modules/analytics/snapshot_schema.py` — 新文件
- `tests/test_services_exam/test_snapshot_schema.py` — schema 验证测试

**测试契约**：
- 入口：构建 DiagnosisSnapshot 实例，所有字段类型正确
- 反例：缺少 fact_id 的 knowledge_point 条目 → 验证报错
- 边界：zero-data（无学生/无知识点）仍能构建合法 snapshot（data_quality 标注覆盖率 0）
- 回归：不影响现有任何 service（纯新增）
- 命令：`.venv/bin/python -m pytest tests/test_services_exam/test_snapshot_schema.py -v`

#### T0.5: 后端 API 筛选参数补齐

**目标**：让 4 个 API 支持共享筛选上下文（F-004/005/006 修复）

**改动清单**（每项均为在已有 service 函数中增加 WHERE 条件）：

| API | 改动 | 文件 |
|-----|------|------|
| `class_diagnosis` | 让 subject_id 参数生效：通过 concept→subject 映射过滤 StudentKnpMastery | `diagnosis_service.py` |
| `question_insights` | 补 class_id 参数：按学生所属班级过滤答题记录 | `insights_service.py` + `analytics_report_router.py` |
| `layer_analysis` | 补 subject_id + class_id：subject_id 过滤科目，class_id 过滤学生 | `layer_service.py` + `analytics_report_router.py` |
| `class_error_patterns` | 补 class_id：单班错误模式（现有为跨可见班对比，保留 all 模式兼容） | `ranking_service.py` + `analytics_report_router.py` |

**文件清单**：
- `src/edu_cloud/modules/analytics/diagnosis_service.py` — subject_id 过滤
- `src/edu_cloud/modules/analytics/insights_service.py` — class_id 过滤
- `src/edu_cloud/modules/analytics/layer_service.py` — subject_id + class_id
- `src/edu_cloud/modules/analytics/ranking_service.py` — class_error_patterns class_id
- `src/edu_cloud/modules/analytics/analytics_report_router.py` — 4 路由补 Query 参数
- `tests/test_services_exam/test_analytics_filter_params.py` — 参数生效测试

**测试契约**：
- 入口：传 subject_id/class_id 参数后返回过滤后的数据子集
- 反例：不传参数时行为与改动前完全一致（向后兼容）
- 边界：传不存在的 class_id → 空结果，不报错
- 回归：现有 AnalyticsPage 调用这些 API 时不传新参数，行为不变
- 命令：`.venv/bin/python -m pytest tests/test_services_exam/test_analytics_filter_params.py -v`

### Batch 1: 统一工作台（T1-T3）

#### T1: 成绩分析工作台 6 Tab 重构

**目标**：将 AnalyticsReportPage 重构为共识定义的 6 Tab 统一入口

**6 Tab 映射**（F-001 修正）：
| Tab | 名称 | 数据来源 | 现有/新增 |
|-----|------|---------|----------|
| 1 | 考后总览 | getBasicReport overview + subjects | 现有"总览"+"科目分析"合并 |
| 2 | 班级/年级对比 | getBasicReport classes + getClassBoxplot | 现有"班级对比"扩展 |
| 3 | 知识点诊断 | getClassDiagnosis + getClassErrorPatterns + getQuestionInsights | **新增** |
| 4 | 学生/分层学情 | getBasicReport students + getLayerAnalysis | 现有"学生排名" + **新增分层** |
| 5 | 趋势追踪 | getGradeTrend / getClassTrend / getStudentTrend | **新增**（复用 TrendPage 逻辑） |
| 6 | AI 综合报告 | POST ai-diagnosis | **新增占位**（Batch 2 实现） |

**改动范围**：
- AnalyticsReportPage.vue Tab 从 4→6，重命名现有 Tab
- Tab 3 知识点诊断：新建 KnowledgeDiagnosisPanel 组件
- Tab 4 分层学情：新建 LayerAnalysisPanel 组件，嵌入现有排名表下方
- Tab 5 趋势追踪：新建 TrendPanel 组件（从 AnalyticsTrendPage 提取核心逻辑）
- Tab 6 AI 报告：占位文案"选择考试后可生成 AI 分析报告"

**文件清单**：
- `frontend/src/pages/AnalyticsReportPage.vue` — Tab 重构
- `frontend/src/components/analytics/KnowledgeDiagnosisPanel.vue` — 三维诊断 + 错误模式
- `frontend/src/components/analytics/LayerAnalysisPanel.vue` — 分层堆叠图 + 学生名单
- `frontend/src/components/analytics/TrendPanel.vue` — 趋势折线图（年级/班级/学生维度）

**测试契约**：
- 入口：AnalyticsReportPage 渲染 6 个 Tab 标题，切换无白屏
- 反例：Tab 3 接收到 classDiagnosis 空数据时渲染空态，不抛异常
- 边界：权限过滤后仅 1 个班级时，对比类图表退化为单班展示
- 回归：Tab 1/2 数据与改动前的总览/班级对比 Tab 完全一致
- 命令：`npx vitest run src/pages/__tests__/AnalyticsReportPage.test.js`

#### T2: powerOptions 级联筛选器

**目标**：替代现有多步级联，实现好分数式一次加载

**状态映射**（F-007 修正）：
- powerOptions `class.id === "all"` → 不传 class_id（scope=grade）
- powerOptions `class.id !== "all"` → 传 class_id（scope=class）
- 选择变更时自动清空下游数据 + 触发重加载
- 默认选最近一次已完成考试

**改动范围**：
- 新建 PowerOptionsSelector 组件（4 级 n-cascader 或 4 个 n-select 级联）
- emit `change` 事件：`{ gradeId, classId, subjectId, examId, scope }`
- AnalyticsReportPage 顶栏替换为 PowerOptionsSelector

**文件清单**：
- `frontend/src/components/analytics/PowerOptionsSelector.vue` — 新组件
- `frontend/src/pages/AnalyticsReportPage.vue` — 替换筛选器

**测试契约**：
- 入口：渲染 4 级选择器，选年级后班级列表只显示该年级的班级
- 反例：不级联过滤→选年级后班级列表仍含其他年级班级（错误）
- 边界：无考试数据 → 显示"暂无已完成考试"；`all` 班级 → scope=grade
- 回归：选考试后数据加载流程与现有一致（传 examId 获取 basicReport）
- 命令：`npx vitest run src/components/analytics/__tests__/PowerOptionsSelector.test.js`

#### T3: 路由整合

**目标**：确保 6 Tab 与现有独立页面的路由兼容

**改动范围**：
- `/analytics/report` 渲染 6 Tab 工作台（主入口）
- `/analytics/trend` 重定向到 `/analytics/report?tab=trend`
- `/analytics/grade` 保留独立页面（年级维度专属，不合入 Tab）
- 侧栏"成绩趋势"改为跳转到 report Tab 5

**文件清单**：
- `frontend/src/router/index.js` — trend 路由 redirect
- `frontend/src/config/sidebarConfig.js` — 趋势入口调整

**测试契约**：
- 入口：访问 /analytics/trend 自动跳转到 /analytics/report?tab=trend
- 反例：直接修改 URL tab 参数可切换到对应 Tab
- 边界：无效 tab 参数 → 默认回到 Tab 1
- 回归：/analytics/grade 独立页面不受影响
- 命令：`npx vitest run src/router/__tests__/analytics-routes.test.js`

### Batch 2: AI 诊断 MVP（T4-T5）

#### T4: AI 诊断后端

**目标**：基于 T0 snapshot 契约，实现 LLM 诊断服务

**改动范围**：
- 新建 `ai_diagnosis_service.py`
  - `build_snapshot()` — 聚合 exam_summary + class_stats + knowledge_mastery + layer_data → DiagnosisSnapshot
  - `generate_diagnosis()` — snapshot → prompt → Gemini → 结构化 JSON 输出
  - `get_or_generate()` — 缓存查找 → 不存在则生成
- 缓存策略（F-003 修正）：
  - key: `sha256(exam_id + school_id + scope + subject_id + class_id + score_version + knowledge_version + prompt_version + model_version + role_scope)`
  - 存储：数据库表 `ai_diagnosis_cache`（exam_id, cache_key, result_json, created_at, expires_at）
  - 考试类报告 7 天 TTL；手动重生成忽略缓存

**新增路由**：
- `POST /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 生成（可选 force_refresh=true）
- `GET /api/v1/analytics/exam/{exam_id}/ai-diagnosis` — 获取缓存

**LLM 输出 schema**（结构化 JSON）：
```json
{
  "summary": "整体评价文本",
  "findings": [{"id": "F1", "text": "...", "evidence_fact_ids": ["kp:K031"], "confidence": "high"}],
  "risk_alerts": [{"text": "...", "evidence_fact_ids": [...]}],
  "teaching_actions": [{"text": "...", "target": "class_3", "priority": "high"}],
  "student_followups": [{"text": "...", "layer": "need_help"}],
  "data_limits": [{"text": "知识点映射覆盖率仅 62%", "fact_id": "quality:kp_coverage"}]
}
```

**文件清单**：
- `src/edu_cloud/modules/analytics/ai_diagnosis_service.py` — 新服务
- `src/edu_cloud/modules/analytics/snapshot_schema.py` — T0 已创建
- `src/edu_cloud/modules/analytics/analytics_report_router.py` — 新增 2 路由
- `tests/test_services_exam/test_ai_diagnosis.py` — 测试

**测试契约**：
- 入口：POST 请求返回结构化 AI 诊断 JSON，所有字段符合 schema
- 反例：prompt 缺少 data_quality → LLM 输出无证据结论（测试验证 data_quality 字段必须存在）
- 边界：无知识点数据 → data_limits 含"知识点映射覆盖不足"；缓存命中 → 跳过 LLM 调用
- 回归：现有 exam_diagnosis（模板版）不受影响，两者共存
- 命令：`.venv/bin/python -m pytest tests/test_services_exam/test_ai_diagnosis.py -v`

#### T5: AI 诊断前端

**目标**：实现 Tab 6 "AI 综合报告"

**改动范围**：
- 新建 AiDiagnosisReport 组件
- 调用 POST ai-diagnosis → 渲染结构化报告
- 展示：摘要 → 关键发现（带证据引用高亮）→ 教学建议 → 数据局限
- 交互："重新生成"按钮（force_refresh=true）、加载中状态

**文件清单**：
- `frontend/src/components/analytics/AiDiagnosisReport.vue` — 新组件
- `frontend/src/api/analytics.js` — 新增 generateAiDiagnosis / getAiDiagnosis
- `frontend/src/pages/AnalyticsReportPage.vue` — Tab 6 接入

**测试契约**：
- 入口：Tab 6 渲染 AI 诊断报告，含 summary/findings/actions 三区块
- 反例：API 超时 → 显示"生成超时，请重试"而非空白
- 边界：data_limits 非空 → 顶部显示黄色提示条；findings 为空 → 显示"暂无关键发现"
- 回归：其他 5 Tab 数据加载不受 AI 报告影响（独立请求）
- 命令：`npx vitest run src/components/analytics/__tests__/AiDiagnosisReport.test.js`

---

## 批次划分

| Batch | Tasks | 依赖 | 范围 | 预计工作量 |
|-------|-------|------|------|-----------|
| Batch 0 | T0, T0.5 | 无 | 后端 schema + 参数补齐 | ~1 天 |
| Batch 1 | T1, T2, T3 | T0.5（API 参数就绪）| 前端工作台重构 | ~2 天 |
| Batch 2 | T4, T5 | T0 + T1 | AI 后端 + 前端 | ~2 天 |

**可并行**：T0 和 T0.5 可并行（schema 定义与参数补齐无依赖）；T1/T2/T3 可并行
**不可并行**：Batch 1 依赖 T0.5；T5 依赖 T4

---

## 风险评估（F-009 修正）

| 风险 | 等级 | 缓解 |
|------|------|------|
| Tab 重构影响现有 AnalyticsReportPage 功能 | **MED** | 保留现有 4 Tab 数据流不变，仅扩展 |
| powerOptions 全量树 + `all` 节点状态映射 | **MED** | `all` 映射为 scope=grade，不传 class_id |
| 后端参数补齐可能影响现有 API 行为 | **MED** | 新参数均可选，不传时行为与改动前一致 |
| AI 诊断 LLM 输出格式不稳定 | **MED** | JSON schema 校验 + 降级为"生成失败" |
| snapshot 契约变更需前后端同步 | **LOW** | schema 版本化，前端读 schema_version 适配 |

---

## semantic_regression

- ORC-001: 有效分优先级链（confirmed > ai_done > human > scan）不可变更
- ORC-002: AnalyticsReportPage 现有 4 Tab 的数据和功能完全保留（映射到新 Tab 1/2/4）
- ORC-003: AI 诊断不替代现有模板诊断（exam_diagnosis），两者共存
- ORC-004: AI 缓存 key 必须含 10+ 维度确保同数据同输出
- ORC-005: powerOptions 权限裁剪不可绕过（school_id + visible_class_ids + visible_subject_codes）
- ORC-006: 后端 API 参数补齐必须向后兼容（不传新参数 = 旧行为）
