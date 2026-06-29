# 附录 B：B 轴学情研究域调研报告

**Date**: 2026-04-24
**Agent**: Explore (thoroughness: thorough)
**Scope**: 好分数 study + research → edu-cloud knowledge_tree / adaptive / bank / profile
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)

---

## 业务能力对照表

| # | 能力 | 好分数实现机制 | 好分数证据 | edu-cloud 现状 | edu-cloud 证据 | 对齐状态 | 工作量 |
|---|------|-------------|---------|-------------|------------|---------|----------|
| 1 | **学情看板总览** | 数据看板模块（`:purpose/schoolManage`）展示学校级汇总卡片 | `/frontend/pages/study/dashboard.vue` L1-80 | DashboardPage + 角色scope聚合 | `/frontend/src/pages/DashboardPage.vue` | 🟡 部分对齐 | S |
| 2 | **班级学情分析** | ClassAnalysis 组件 + API聚合考试/知识点/错题数据 | `POST /proxy-fx/analysis/v1/homework/classAnalysis/overview` study.js L111 | AnalyticsPage(ECharts)整合班级维度 | `/frontend/src/pages/AnalyticsPage.vue` L7-100 | 🟡 部分对齐 | S |
| 3 | **学生学情档案** | 单生单科成绩趋势 + 知识点掌握度 + 错题反查 | `/:purpose/studentsAnalysis/singleStudent` + `getStudentAnalysisDetail` useApi.ts L286 | StudentTrend + StudentKnowledgeMap 表结构已建 | `/modules/profile/service.py` L26-41 `get_student_knowledge_map()` | 🟡 部分对齐 | M |
| 4 | **知识点掌握诊断** | `student_knp_mastery` 表存储掌握度 (%) + 趋势 | `schema.sql` L228-235; `getKnpMasterInfo` useApi.ts L271 | BKT 四参数 + 4 态分类 (solid/fragile/weak/unseen) | `/modules/adaptive/bkt_engine.py` L16-44 | 🟡 有价值差异 | M |
| 5 | **知识树/体系管理** | 编辑模式 CRUD 知识点树 | `knowledge.vue` L43-79 tree组件 + `/tk/konwledgeSetting/knowledge` | ConceptGraphNode+Edge(2113行) 含发布状态+审核流 | `/modules/knowledge_tree/service.py` L34-100 | 🟢 已对齐（超前） | L |
| 6 | **知识图谱可视化** | 暂无（TreeView + 简单拓扑，无 G6） | research/knowledge.vue L43 (el-tree) | AntV G6 力导向图 + 多模式 (heatmap/考频/掌握度) | KnowledgeTreePage.vue L1-8675 | 🟢 edu-cloud 超前 | L |
| 7 | **题库/组卷能力** | 题库选题 (64题库 + 教研模块) + 快捷/章节/知识点/蓝图/平行组卷 | `/tk/questions` `/tk/make/by/knowledges` `/tk/blueprintPaper` | 题库 skeleton (232行，error_book+question_stats) | `/modules/bank/service.py` L1-80 | 🔴 严重缺失 | L |
| 8 | **错题本管理** | QuestionBook 模块单独生成 (考试级/章节级) | `POST /proxy-fx/.../wrongQuestions`; `/questionBook/make` | error_book 表 + get_student_error_book() 查询 | `bank/service.py` L41-54 | 🟡 框架就位 | M |
| 9 | **班级共性错题** | ClassAnalysis → commonWrongQues 聚合同班错题 + 统计 | `POST /proxy-fx/.../commonWrongQues/list` useApi.ts L253 | 框架就位但无聚合逻辑 | bank/service.py | 🟡 框架就位 | M |
| 10 | **分层学情分析** | LayerAnalysis (tier 权限卡控：xq_basic 禁用) | `/:purpose/layerAnalysis` route-analysis.md L317 | AnalyticsTrendPage 支持班级/年级/学生 | AnalyticsTrendPage.vue L1-5352 | 🟡 部分对齐 | S |
| 11 | **学情诊断报告** | 考后讲评 → 考后智能跟踪 AI 生成诊断 + 建议 | `/lesson/afterExam/detail/overview`; AIGradeBooster-Student-Diagnosis | Student_Diagnosis agent 工具 + diagnose_and_recommend | `/modules/ai/tools/adaptive.py` | 🟢 edu-cloud 超前 | L |
| 12 | **自适应推荐路径** | 无（弱点清除作业仅基于错题） | `/work/publish/weakClean` homework.js L234 | DA 路径规划 + 选题器 (BKT 驱动) | `/modules/adaptive/path_planner.py` `/modules/adaptive/question_selector.py` | 🟢 edu-cloud 超前 | L |
| 13 | **考试分析报告** | FX 模块 (FenXi) 全景分析 + 多个维度表 | `/fx/common/overview` `/fx/common/ranking` | AnalyticsReportPage 多指标 + 分数段配置 + 自定义查询 | AnalyticsReportPage.vue; analytics/service.py | 🟢 已对齐 | S |
| 14 | **知识点统计** | ClassAnalysis + KnpList 按掌握率排序 | `POST /proxy-fx/.../knp/list` useApi.ts L221 | KnowledgeTree stats API 含 exam_frequency/coverage | knowledge_tree/stats_service.py L1-413 | 🟢 已对齐（超前） | S |
| 15 | **实时进度追踪** | 考试/作业多端点追踪 (progress/quality/scan) | `/yuejuan/monitor/exam/:examId/progress` | GradingDispatchPage 一体化流程（扫描→选判→校对→完成） | GradingDispatchPage.vue | 🟢 已对齐（超前） | S |

## Gap 清单

### 🔴 高价值缺失

1. **题库 + 组卷生态**
   - 好分数实现：64 routes（题库选题/快速/章节/知识点/蓝图/平行/细目表/考情组卷）+ 智能推荐（基于考点掌握度）+ 学科网/校本资源联动 + 组卷参数（难度分布/题型占比）
   - 好分数证据：route-analysis.md L109-153；`/tk/make/by/knowledges`；`/tk/blueprintPaper`；research/paper-builder.vue L1-21741
   - edu-cloud 现状：bank 模块仅 232 行，无组卷逻辑；Question CRUD 存在但无高级筛选/推荐
   - **工作量**：L（3-4 weeks）
   - 价值说明：好分数核心价值链，直接影响教研/作业发布/诊断。edu-cloud 缺失组卷 = 教学流程断链

2. **知识点层级管理（L0/L1/L2/L3）**
   - 好分数实现：四层知识体系（学科→大单元→核心知识→具体知识点）；parent_id 层级；不同教学场景用不同粒度
   - 好分数证据：schema.sql L215-225 knowledge_points(parent_id/level/sort_order)；knowledge.vue L43-79 树形管理
   - edu-cloud 现状：ConceptGraphNode 仅 2 层(node_type=big_concept/concept)；无原生层级字段；缺 L3 层
   - **工作量**：M（2 weeks）
   - 价值说明：教研组卷、诊断推荐都依赖细粒度知识点；缺 L3 导致推荐精度下降

3. **考情分析/参数组卷**
   - 好分数实现：ExamTrend（考情组卷）+ TeachingAnalysis（考情雷达）+ 数据驱动参数推荐（难度分布/题型比例/知识点覆盖率）
   - 好分数证据：route-analysis.md L136-138；radar.vue L1-15578
   - edu-cloud 现状：concept_stats 含 exam_frequency/difficulty，但无考情趋势追踪/参数优化推荐
   - **工作量**：M（2 weeks）
   - 价值说明：精准教学核心——在历年考试数据上迭代学科教学策略；缺失则教学决策 ad-hoc

### 🟡 有价值优化

1. **学情画像深度（Profile 画像模块）**
   - 好分数：单生详情页 = 成绩趋势 + 知识点掌握 + 错题追踪 + 学业特征标签（优势/劣势科目/学习风格）
   - 好分数证据：`/:purpose/studentsAnalysis/singleStudent`；student.vue L1-17755 含多个 Tab
   - edu-cloud 现状：StudentExamSnapshot + StudentKnowledgeMastery + StudentErrorPattern 表结构齐全，但前端 UI 缺 StudentProfile 综合卡片
   - 工作量：M（2 weeks）
   - 价值：班主任/任课教师决策必需；现有表数据可直接复用，只需前端整合

2. **BKT 掌握度 vs 简单百分比**
   - 好分数：掌握度 = student_knp_mastery.mastery_level(%) 简单聚合；无 BKT 参数化
   - edu-cloud：BKT 四参数 + bkt_update() 动态更新；classify_da_state() 四态
   - 工作量：S（1 week，已有工具）
   - 价值：edu-cloud BKT 更科学，但好分数用户习惯百分比——迁移需平缓过渡

3. **教研资源体系（School Resources）**
   - 好分数：SchoolResource 模块（热点话题/集体备课资源/校本题库/校本教材）+ 个人空间（云盘/分享）
   - 好分数证据：route-analysis.md L155-174 `/tk/schoolResource/*`；plan.vue/group-prep.vue
   - edu-cloud：无对应模块；仅 Studio(文档) + Knowledge(知识库)，缺校本资源沉淀
   - 工作量：M（2 weeks，可选）
   - 价值：校本资源是教研质量的沉淀；缺失则学校无法沉淀教学知识产权

### 🟢 锦上添花

1. **平行组卷/细目表组卷** — 高阶用户需求
2. **学案管理** — 特定地区特定学科
3. **集体备课平台** — 组织级特性

## edu-cloud 超前清单

| 超前能力 | edu-cloud 实现 | 好分数缺失 | 价值/建议 |
|---------|-------------|----------|---------|
| **知识图谱 G6 可视化** | KnowledgeTreePage.vue (8675行) + AntV G6 力导向 + 多模式（考频热力/掌握度/审核状态）| 纯树形，无图可视 | 教研体验天壤之别；保留 |
| **BKT 自适应学习** | bkt_engine.py + adaptive/ 7 表完整生态 | 仅简单百分比 | 诊断精度 2-3 倍提升；保留但需迁移历史数据 |
| **知识图谱编辑/审核流** | ConceptGraphNode.review_status + editor.py 编辑同步 | 仅 CRUD，无审核 | 知识质量管理 |
| **Agent 诊断工具** | profile/tools/student_diagnosis.py 内置工具 | 无对应 | AI 自动化诊断报告 |
| **分数段配置** | score_segment_config 学校级+科目级 | 无多层配置 | 等级赋分/分数段统计 |
| **跨校成绩聚合** | JointExam + joint_exam_student_results | 单校孤立 | 集团/联考场景 |

## 边界说明

本轴不覆盖：
- 阅卷/成绩基础 → A 轴
- 作业系统 → C 轴
- 教学资源平台 → C 轴
- 学校行政 → D 轴

## 优先级建议

### 🔴 P0：必做（教学流程完整性）
1. **题库 + 组卷模块（3-4w）**：快速启动；优先级最高
2. **知识点 L3 层级补齐（2w）**：支撑组卷精度

### 🟡 P1：重做（诊断决策精准性）
3. **学情画像单生详情页（2w）**：复用现有表结构，仅需前端整合
4. **考情分析引擎（2w）**：exam_frequency 聚合 → 难度分布推荐 → 参数优化建议
5. **校本资源沉淀框架（2w）**：长期提升学校粘性

### 🟢 P2：优化
6. **BKT 平缓迁移方案（1w）**：并行展示百分比+BKT 掌握度
7. **Agent 诊断深化（ongoing）**

## 关键量化指标

| 指标 | 好分数 | edu-cloud | 差距 |
|-----|-------|----------|------|
| 知识树节点数 | ~200(L1-2) | 2113(concept+big_concept) | +906(深度不足) |
| 学情 API 端点数 | 15+ | 12+ | -3(缺考情/组卷/题库) |
| 组卷方式 | 7 种 | 0 | **缺失** |
| 自适应算法 | 简单掌握% | BKT 四参数 | edu-cloud 超前 |
| 前端学情页面 | 4 | 3 | -1(缺单生详情) |
| 知识图谱可视化 | 无(纯树) | G6 力导 | edu-cloud 超前 |

## 实现时间线建议

```
W1-W2: P0-1(题库+组卷) 平行启动
W3-W4: P0-2(知识点 L3) + P1-3(学情详情页)
W5-W6: P1-4(考情分析) + UI 整合
W7+:   P2 优化 + 长期迭代
```

全量迁移+优化预计 **8-10 周**。
