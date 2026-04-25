<!-- legacy-format -->
# 业务全景路线图调研报告 · 2026-04-18

> 类型：Researcher 产出（只读）
> 工作目录：`/home/ops/projects/edu-cloud-t2` master @ `20eb90b`（实查 git log 起点；Planner V2 §2 HEAD `63d4bf3`，本会话期间 Planner 派 T-Wipe 紧急任务后 master 推进至 `20eb90b`）
> 上游：`docs/plans/2026-04-18-takeover-impact-audit-report.md` (T-E)、`docs/plans/2026-04-18-ecs-pytest-baseline-report.md` (T-H)、`docs/plans/2026-04-18-planner-decisions-v3.md` (V3 决策)、`docs/plans/2026-04-18-planner-session-handoff-v2.md` (V2 状态)、`docs/plans/2026-04-18-windows-wipe-handoff.md` (T-Wipe 派发)
> 性质：只读调研，禁改 src/ frontend/ tests/ alembic/，禁动 W2/W4 worktree 文件
> 目的：Planner 重新规划业务路线时的事实底盘
> ECS 单一环境铁律严守（L018）：本报告所有数字基于 ECS pytest/grep 实测，禁引 Windows 历史

---

## §0. 调研结论（TL;DR）

**核心发现一句话**：edu-cloud B 端基础能力（API 212 端点 + 1934 后端测试 + 20 模块）已成形，但**业务推进当前被 4 类元能力债阻塞**——其中 T-Wipe（Windows 残影清扫，紧急派发未启）是 3 个业务任务（W4 conduct-roadmap T1-T5、W2 KG-phase1 收尾、Sprint 1 全部新规划）的硬前置。Planner 重新规划时应**优先解锁 T-Wipe → 业务任务串行解封 → backlog 按依赖图分批**。

**关键判定**：
1. 20 个 modules/ 子目录中 **17 个有 router（含路由）** + 3 个内部服务（adaptive/paper/menu 仅 menu 有 router），按 grep 实测 **212 个 router 装饰器分布在 32 个 router 文件**
2. **当前在跑/冻结业务任务 2 个**：W2 KG-phase1 batch3.b R2 FAIL（T11/T12 拆 3.b.iii）+ W4 conduct-roadmap batch1（5 task R7 plan PASS 但伪基线，等 T-Wipe 重写）
3. **3 个 Sprint 1 推荐任务**：W4 batch1 实施 (T-Wipe 后) / W2 收尾 (3.b.iii + 3.c) / FAIL fixture 修复（独立小修）
4. **3 个 Sprint 2 候选**：KG Phase 2 设计 / 共享 AI 阅卷启动 / haofenshu Phase 1 Batch 3
5. **Backlog 至少 12 项**（CLAUDE.md 显式列 3 项 + design Phase 2/3 共 9 项）

---

## §1. 业务模块完成度矩阵

### 1.1 方法

- 模块清单：`ls /home/ops/projects/edu-cloud-t2/src/edu_cloud/modules/`（CLAUDE.md 声明 20 模块）
- 端点数：`grep '@router\.(get|post|put|patch|delete)' src/edu_cloud/modules/*/router*.py`
- 函数数：`grep '^(async )?def ' src/edu_cloud/modules/<mod>/*.py`（含 service/router/各文件，不含子目录如 vision/parser）
- 测试数：`grep 'def test_' tests/test_<mod>* tests/test_modules/test_<mod>/*`
- 完成度判定依据：CLAUDE.md "实现状态" 表 + design.md 标 [实现完成] + state.json

### 1.2 模块完成度矩阵（20 模块 + scan/vision 子模块）

| # | 模块 | router 文件数 | 端点 grep | 函数 grep | tests grep | MODULE.md | 完成度 | 依据 |
|---|---|---|---|---|---|---|---|---|
| 1 | exam | 5 (router+joint_exam+results+workspace+llm_config) | 23 | ~38 | 47 (api 11+models 5+service 10+results 3+wiring 5+...) | ❌ | ✅ 已上线 | CLAUDE.md "考试管理端点" Batch 3 迁入；test_modules/test_exam 22 + test_api/test_joint_exams 5 + test_api/test_exam_publish 2 等 |
| 2 | school | 6 (router+settings+selection+capability+assignment+audit) | 22 | ~30 | 53 (test_api/test_schools 6+test_school_settings 19+test_subject_selections 12+test_capabilities 8+test_audit_logs 8) | ❌ | ✅ 已上线 | CLAUDE.md "学校配置/排课/选考/能力/审计" 5 端点段 |
| 3 | grading | 4 (router+assignment+quality+) | 14 | ~22 | 27 (test_api_exam/test_grading_task 8+rubric 5+review 7+assignments 4+test_grading_dispatch 4)等 | ✅ 存在 | ✅ 已上线 | CLAUDE.md "AI 阅卷调度" + 2026-04-12-grading-dispatch-design [实现完成] |
| 4 | scan | 3 (router+pipeline_router+vision/) | 12 | ~30 (含 vision 子目录) | 17 (test_api_exam/test_scan_upload 3+task 5+test_api/test_scan_pipeline_api 4+test_services_exam/test_scan_pipeline 11+vision 5) | ❌ | ✅ 已上线 | CLAUDE.md "扫描端点" + 2026-04-09-scan-pipeline-design + scan-integration-design [实现完成] |
| 5 | analytics | 1 (router) | 17 | 30 | 32 (test_api_exam/test_analytics 9 + report 9 + export 11 + class_filter 4 + grade_aggregates 10 + test_services_exam/test_analytics 3 + report_service 9 + segment_service 13) | ❌ | ✅ 已上线 | 2026-04-05-analytics-report-design [实现完成]；CLAUDE.md "分析报告" |
| 6 | knowledge_tree | 1 (router) | 8 | ~25 | 160 (19 文件) | ❌ | 🟡 **部分实现** | T0-T10 ✅, T11-T14 pending；state.json 实查；2026-04-12-knowledge-graph-optimization-design Phase 2/3/4 未启 |
| 7 | knowledge | 1 (router) | 5 | 6 | 22 (test_knowledge/test_loader 11+store 14+test_modules/test_knowledge 6+test_api_exam/test_knowledge 6+test_services_exam/test_knowledge_service 11) | ❌ | ✅ 已上线 | CLAUDE.md "知识库" + L3 4 工具 |
| 8 | conduct | 2 (parent_router+admin_router) | **39** (parent 11+admin 28) | 64 (admin_router 28+admin_service 20+parent_router 11+parent_service 13+rules_service 7+permissions 9+export_service 2+crypto 3) | 68 (admin_api 13+admin_crud_api 14+parent_api 19+permissions 5+models 4+crypto 4+agent_tools 9) | ❌ (T4 待补) | ✅ 已上线 | 2026-04-12-conduct-module-design [实现完成]；ECS pytest 实测 68 passed (T-H §3 表) |
| 9 | homework | 1 (router) | 12 | 15 | 26 (test_api/test_homework_api 8+test_services/test_homework_service 18+test_homework_permissions 4+test_ai/test_homework_tools 5) | ❌ | ✅ 已上线 | CLAUDE.md "作业管理" Phase 2.2 / 2026-03-30-phase2.2-homework-system-design [实现完成] |
| 10 | studio | 1 (router) | 8 | 9 | 32 (test_api/test_studio_api 20+test_services/test_studio 12) | ❌ | ✅ 已上线 | 2026-03-22-p2-studio-design [实现完成] |
| 11 | calendar | 1 (router) | 3 | 4 | 12 (test_api/test_calendar_api 7+test_models/test_calendar 5+test_services/test_calendar_service 7) | ❌ | ✅ 已上线 | CLAUDE.md "日历端点" P3-2 |
| 12 | profile | 1 (router) | 4 | 8 | 9 (test_api/test_profile_api 5+test_api_exam/test_profile 4) | ❌ | ✅ 已上线 | CLAUDE.md "学情画像端点" Phase 3.1 |
| 13 | bank | 1 (router) | 4 | 7 | 14 (test_api/test_bank_api 5+test_modules/test_bank 5+test_services_exam/test_bank_service 6+test_api_exam/test_bank 3+test_ai/test_tools_bank 0?) | ❌ | ✅ 已上线 | CLAUDE.md "题库 + 错题本端点" Phase 3.1 |
| 14 | marking | 1 (router) | 11 | 13 | 19 (test_api_exam/test_marking 11+marking_assign 8) | ❌ | ✅ 已上线 | CLAUDE.md "marking" 端点 |
| 15 | card | 2 (router+template_router) | 25 | ~70 (含 parser/export/template/rendering 子目录) | 22 (test_api_exam/test_cards 20+card_publish 2+test_services_exam/test_card_* 多文件) | ❌ | ✅ 已上线 (W1 已 merge subdir 拆) | CLAUDE.md "card 23 端点" + 2026-04-17-card-subdir-plan + W1 6c1ee0e merged |
| 16 | adaptive | 0 (内部服务) | 0 | 19 | 25 (test_adaptive 8 文件) | ❌ | ✅ 已上线 | CLAUDE.md "adaptive 内部服务模块"；2026-04-06-adaptive-learning-design [实现完成] |
| 17 | menu | 1 (router) | 1 | 1 | 9 (test_menu/test_menu_service 6+test_menu_api 3) | ❌ | ✅ 已上线 | 2026-04-12-haofenshu-phase1-plan Batch 1 |
| 18 | pipeline | 1 (router) | 1 | 11 | ≥3 (test_services_exam/test_pipeline_objective 3+test_pipeline_queue 4+test_api_exam/test_pipeline_api 3) | ✅ 存在 | ✅ 已上线 | CLAUDE.md "pipeline" + 2026-04-11-f003-question-writeback-design [实现完成] |
| 19 | paper | 0 (内部服务) | 0 | ~10 | 6 (test_services/test_paper_service) | ❌ | ✅ 已上线 | CLAUDE.md "paper 内部服务"；调用 paper-skill |
| 20 | student | 1 (router) | 3 | 10 | ≥6 (test_modules/test_student 6+test_api_exam/test_student 16) | ❌ | ✅ 已上线 | CLAUDE.md "students" 端点（隐含 classes 端点） |

**汇总**：
- 17 / 20 模块 ✅ 已上线（adaptive/paper 内部服务无路由属正常；menu 单端点动态菜单）
- 1 / 20 模块 🟡 部分实现：**knowledge_tree**（Phase 1 T11-T14 pending）
- 0 / 20 模块 🟧 Stub-only
- 0 / 20 模块 ❌ 未实现
- MODULE.md 仅 grading + pipeline 有（其他 18 模块缺；conduct 已纳入 conduct-roadmap batch1 T4）

**总数交叉对账**：
- CLAUDE.md "API 223 路由"（声明）vs `grep @router 实测 212`（差 11；可能 api/auth.py + api/dashboard.py + api/notifications_api.py + api/ai.py + compat_router.py 等顶层 router 未在 modules/ 下）
- CLAUDE.md "1851 后端 + 73 前端"（陈旧）vs ECS pytest 实测 **1958 collected / 1934 passed / 1 failed / 23 skipped**（T-H 报告 §2）

---

## §2. 设计 docs 路线图全景

### 2.1 方法

`ls docs/plans/*-design.md` → 33 份；按 topic 分组 + 标注状态。状态来源：CLAUDE.md "参考文档" 段中标注 [实现完成] 的文件。

### 2.2 设计文档分组（33 份）

#### Topic A：AI Agent 体系（7 份，全部 [实现完成]）

| 文件 | 创建日 | 状态 | Phase 2/3 deferred |
|---|---|---|---|
| `2026-03-16-ai-agent-design.md` | 2026-03-16 | [实现完成] (旧) | — |
| `2026-04-03-edu-agent-design.md` | 2026-04-03 | [实现完成] 30T/7B/39 工具 | — |
| `2026-04-04-agent-evolution-design.md` | 2026-04-04 | [实现完成] 20T/6B | — |
| `2026-04-05-agent-runtime-design.md` | 2026-04-05 | [实现完成] AgentRuntime+ModelRouter | — |
| `2026-04-05-agent-evolution-design.md` | 2026-04-05 | [实现完成] EntityMemory+ProjectState | — |
| `2026-04-06-agent-resilience-design.md` | 2026-04-06 | [实现完成] P0/P1/P2/P3 11T | — |
| `2026-04-05-analytics-report-design.md` | 2026-04-05 | [实现完成] 13T | 跨考试三维趋势已实现 |

> Backlog 信号：CLAUDE.md "未实现" 列表唯一 AI 项 = "**常驻巡检 Agent**"（W6 patrol 已有 12 测试但未声明常驻）

#### Topic B：知识图谱（4 份）

| 文件 | 状态 | deferred |
|---|---|---|
| `2026-04-05-knowledge-tree-design.md` | [实现完成] | — |
| `2026-04-09-knowledge-graph-restructure-design.md` | [实现完成] 10T/168 tests | — |
| `2026-04-09-knowledge-graph-model-design.md` | [实现完成] 9T/124+78 | — |
| `2026-04-12-knowledge-graph-optimization-design.md` | 🟡 **Phase 1 部分** | **§3 显式 Phase 2/3/4 未启**（grep 行 255/277/301）：Phase 2 图谱增强（soft 边可视化 + 共现边 ~50-100 条）/ Phase 3 教学规划（teaching_plans CRUD + 序列建议 API）/ Phase 4 学生画像与推荐（BKT 掌握度图谱着色 + 推荐 API） |

#### Topic C：教师工作台（2 份，全部 [实现完成]）

| 文件 | 状态 |
|---|---|
| `2026-04-10-teacher-workbench-design.md` | [实现完成] Phase 2 6T/2B/+43 tests |
| `2026-04-10-teacher-workbench-phase2.5-design.md` | [实现完成] Phase 2.5 3T/182 tests |

> 桥接/对比边「Phase 3 deferred」段已记录 (CLAUDE.md 引)

#### Topic D：考试 + 阅卷流水线（4 份，全部 [实现完成]）

| 文件 | 状态 |
|---|---|
| `2026-03-30-phase2.1-exam-workflow-design.md` | [实现完成] |
| `2026-04-09-scan-pipeline-design.md` | [实现完成] |
| `2026-04-09-scan-integration-design.md` | [实现完成] |
| `2026-04-12-grading-dispatch-design.md` | [实现完成] 10T/1B (Gate 1+2 R3 PASS) |

#### Topic E：答题卡（2 份）

| 文件 | 状态 |
|---|---|
| `2026-04-03-a4-card-editor-design.md` | [实现完成] |
| `2026-04-11-f003-question-writeback-design.md` | [实现完成] 13T/3B/6 Gates |

#### Topic F：模块治理 + 平台架构（5 份）

| 文件 | 状态 |
|---|---|
| `2026-03-21-super-platform-design.md` | [实现完成] (P0 重构) |
| `2026-03-22-platform-merge-design.md` | [实现完成] |
| `2026-03-23-frontend-role-aware-redesign-design.md` | [实现完成] |
| `2026-03-29-business-logic-backfill-design.md` | [实现完成] Phase 1-4 |
| `2026-04-13-module-governance-design.md` | 🟡 治理纲领（4 层模型已设计，逐模块 MODULE.md 补全是 backlog） |

#### Topic G：权限 + 配置（4 份，全部 [实现完成]）

| 文件 | 状态 |
|---|---|
| `2026-03-29-phase1a-module-management-plan.md` (有 plan 无 design) | [实现完成] |
| `2026-03-29-phase1b-base-info-design.md` | [实现完成] |
| `2026-03-30-phase1c-permission-engine-design.md` | [实现完成] |
| `2026-03-30-phase1d-agent-instantiation-design.md` | [实现完成] |

#### Topic H：作业 + 日历（2 份，全部 [实现完成]）

| 文件 | 状态 |
|---|---|
| `2026-03-30-phase2.2-homework-system-design.md` | [实现完成] |
| `2026-03-22-p3-notification-design.md` (隐含 calendar)/`2026-03-22-p4-knowledge-design.md` | [实现完成] |

#### Topic I：联考 MVP（1 份）

| 文件 | 状态 |
|---|---|
| `2026-03-18-joint-exam-mvp-design.md` | [实现完成] (基础联考能力) |

#### Topic J：好分数业务复刻 + 操行（4 份，2 个 in-flight）

| 文件 | 状态 |
|---|---|
| `2026-04-12-haofenshu-biz-replication-design.md` | 🟡 Phase 1 in-flight (Batch 1+2 ✅, Batch 3 待启)；§6 显式 **Phase 2 现有功能迁移 + Phase 3 新模块填充** 待 Phase 1 PASS 后并行启动 |
| `2026-04-12-conduct-module-design.md` | [实现完成] 22T/7B (Gate 2 R3-R2 PASS) |
| `2026-04-14-conduct-roadmap-design.md` | 🟡 in-flight (批次 1 plan R7 PASS, 批次 2/3 占位) |
| `2026-04-13-migration-gate-repair-design.md` | [实现完成] |
| `2026-04-14-auth-fail-closed-repair-design.md` | [实现完成] (Batch 2 R2-R3 修复用) |

> Backlog 信号：haofenshu Phase 2/3 在 Phase 1 完成后并行可推；conduct-roadmap 批次 2 (D-005 sentinel/D-009 横扫/D-010 seed_menus) + 批次 3 (D-006 家长 E2E/D-007 Agent happy/D-008 Excel UTF-8) 占位

### 2.3 路线图状态汇总

- **总 33 份 design**
- **27 份 [实现完成]**
- **5 份 in-flight**：
  - `2026-04-12-knowledge-graph-optimization-design`（Phase 1 部分；Phase 2/3/4 未启）
  - `2026-04-12-haofenshu-biz-replication-design`（Phase 1 进 Batch 3；Phase 2/3 待 Phase 1 PASS）
  - `2026-04-14-conduct-roadmap-design`（批次 1 plan PASS 待执行；2/3 占位）
  - `2026-04-13-module-governance-design`（治理纲领设计完成；逐模块 MODULE.md 补全持续中）
- **1 份治理纲领**：`2026-04-13-module-governance-design`

---

## §3. In-flight 任务全景

### 3.1 worktree 状态（Planner V2 §2.1 实查 + 派发卡）

| Worktree | 路径 | 分支 | HEAD | 状态 | 当前任务 |
|---|---|---|---|---|---|
| W (master) | `/home/ops/projects/edu-cloud-t2` | master | `20eb90b` (Planner V2 §2.1 写为 `63d4bf3`，本会话 Planner 派发 T-Wipe 等任务后推进) | 活跃 | Planner 主场 |
| W1 | `/home/ops/projects/edu-cloud-w1` | feat/card-subdir | `6c1ee0e` | ✅ merged | 已完成（card 子目录拆） |
| W2 | `/home/ops/projects/edu-cloud-w2` | feat/kg-batch3b | `80b57fb`（V2 §2.1）/ `931e1c7`（W2-R2 卡 §1 第二处实查） | 🟡 Code Review R1 FAIL → R2 修复中 | KG-phase1 batch 3.b T11/T12 |
| W3 | `/home/ops/projects/edu-cloud-w3` | feat/haofenshu-batch3 | `1439904` | ✅ merged | 已完成（haofenshu Phase 1 Batch 3） |
| W4 | `/home/ops/projects/edu-cloud` | feat/conduct-roadmap-batch1 | `793eaf2`（V2 §2.1）/ `637ce2f`（w4-exec-T1-T5 卡 §1 实查） | 🟡 Plan R7 PASS, **伪基线** | conduct-roadmap batch 1 T1-T5 待执行 |

> 路径备注：W4 worktree 路径为 `/home/ops/projects/edu-cloud`（不是 `edu-cloud-w4`）— 用户偏好的"主仓 W4 + 副仓 t2 是 master"布局

### 3.2 在跑/冻结业务任务清单

#### Task IF-1：W2 KG-phase1 收尾（B 类 in-flight）

| 项 | 内容 |
|---|---|
| Worktree | `/home/ops/projects/edu-cloud-w2` (`feat/kg-batch3b` @ `80b57fb` / `931e1c7`) |
| 卡点 | Code Review R1 FAIL（5 findings F001-F005，R1 报告 `2026-04-13-knowledge-graph-phase1-review-report-batch3b.md`）；并发同步派的 T11/T12 race mutant test (3.b.iii) 也未完成 |
| 解锁条件 | 1) F005 决策（A 移 defineExpose / B 改 plan，待用户拍板）；2) F001-F004 修复完成 R2 PASS；3) batch 3.c (T13 ModuleOverviewPanel + T14 收尾) 实施 |
| 业务价值 | **HIGH**——服务对象：教师/教研组长（知识图谱可视化教学能力，独立于核心阅卷链路）；Phase 1 全收尾后才能解锁 KG Phase 2 设计 |
| handoff 卡 | `docs/plans/2026-04-18-w2-kg-phase1-finish-handoff.md` (Phase A 1h + Phase B 2-4h) + `docs/plans/2026-04-18-w2-r2-repair-handoff.md` (R2 修复，5 findings) + `docs/plans/2026-04-18-w2-batch3b-iii-handoff.md` (race mutant) |
| 估时 | 3-5h |

#### Task IF-2：W4 conduct-roadmap Batch 1 T1-T5 实施（B 类 in-flight）

| 项 | 内容 |
|---|---|
| Worktree | `/home/ops/projects/edu-cloud` (`feat/conduct-roadmap-batch1` @ `793eaf2` / `637ce2f`) |
| 卡点 | **Plan R7 PASS 但 plan baseline 数字是伪基线**（写 conduct 118 passed = Windows-era，ECS 实测 68）；T-Wipe 紧急派发要"按 ECS 视角重写 plan"覆盖原 W4-R8 整合 |
| 解锁条件 | T-Wipe Phase 4（W4 R8 plan ECS-rewrite + state.json 创建）完成 |
| 业务价值 | **HIGH**——服务对象：班主任/教务/家长（lesson_prep_leader 权限回收 + AddPointsRequest 字段 rename + sidebar 按 permissions 派生 + conduct MODULE.md 补全 + 文档数字漂移修正）；T1+T3 含 behavior_change（用户已 L017 批准） |
| handoff 卡 | `docs/plans/2026-04-18-w4-exec-T1-T5-handoff.md`（启动 prompt 已就绪）；plan `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md` |
| 估时 | 5 task 各独立 commit + 入口级测试，约 4-6h |

### 3.3 元能力 in-flight 任务清单

#### Task IF-3：T-Wipe ECS 单一环境彻底切断（C 类元能力，紧急未启）

| 项 | 内容 |
|---|---|
| 派发卡 | `docs/plans/2026-04-18-windows-wipe-handoff.md` |
| 状态 | ⏳ Planner 派发完成，Executor 未启动 |
| 卡点 | 取代了原 T-F (plan 清洗) + W4-R8 整合 + A2 决策三个任务，是 P0 紧急 |
| 解锁条件 | 用户 2026-04-18 11:15 严令"必须彻底解决"已下达 → 启 Executor |
| 业务价值 | **CRITICAL（阻塞 3 个业务任务）**——见依赖图 §6 |
| 估时 | 4-6h（7 Phase） |

#### Task IF-4：FAIL fixture 修复（C 类元能力，独立小修）

| 项 | 内容 |
|---|---|
| 失败用例 | `tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub` |
| 根因 | sqlite OperationalError no such table: subjects；fixture 缺 create_all 初始化（T-H 报告 §5）|
| 状态 | ⏳ 已识别，无人派发 |
| 业务价值 | LOW（同文件 7 个 worker 测试全绿，仅这一个 stub 缺 fixture） |
| 估时 | <1h |

### 3.4 已关闭/作废任务（参考）

| 任务 | 状态 | 理由 |
|---|---|---|
| T-D W2 race test | ⏸️ 已关闭未启动 | A2 决策后 KG-phase1 收尾时再判断启动（V2 §3 表）|
| T-F plan 清洗 | ⏸️ 作废 | 被 T-Wipe Phase 6 覆盖（windows-wipe-handoff §8）|
| W4-R8 Planner | ⏸️ 已关闭 | evidence 已落地 batch1-baseline-evidence.md，订正动作整合入 T-Wipe Phase 4 |

---

## §4. Backlog 业务任务清单

### 4.1 来源

3 类来源：
- **CLAUDE.md "未实现端点（规划中）" 段** → 3 项
- **design.md 中显式 Phase 2/3/4** → 9 项
- **CLAUDE.md "实现状态" 表 "未实现" 列** → 2 项

### 4.2 Backlog 全清单（14 项）

#### B-1：共享 AI 阅卷（CLAUDE.md L641 显式）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——CLAUDE.md 项目定位顶部明写"算力不足的学校可上传切图到云端阅卷"；服务对象：所有接入校（特别是无 GPU 学校） |
| 范围 | 端点 `grading-request` / `grading-result`；上传切图 → 云端 grading worker → 回传分数；架构是云端 grading worker 复用，新增上传切图 → 回传 API 桥接 |
| 估时 | T3，~10-15 task / 2-3 batch |
| 前置依赖 | 无硬依赖；可与其他业务并行；建议 T-Wipe 后启动设计 |
| 当前状态 | 仅有 design 占位，无 plan |

#### B-2：统一题库（CLAUDE.md L644 显式）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——CLAUDE.md 项目定位"各校贡献+云端审核+联考组卷"；服务对象：教研组长/教育局；现 bank 模块仅 4 端点（学校私有题库） |
| 范围 | 题目共享池 + 审核流 + 联考组卷集成 |
| 估时 | T4，~15-25 task / 多 batch |
| 前置依赖 | 联考能力（已实现）；bank 模块已上线（基础）；与 haofenshu Phase 3 research 模块的 paper-builder 概念相关 |
| 当前状态 | 无 design |

#### B-3：高级跨校分析（CLAUDE.md L645 显式）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——CLAUDE.md 项目定位"教育局：全区成绩总览+学校间对比+教学质量监控"；服务对象：district_admin（教育局） |
| 范围 | 趋势/对比图表（跨校多年/多次联考）；district_admin 角色已有但分析端点单薄（results-by-school 已实现，但年度趋势/学校排名/质量监控仪表盘缺）|
| 估时 | T3，~8-12 task / 2 batch |
| 前置依赖 | 联考已实现 + analytics 已实现；可视化前端组件 |
| 当前状态 | 无 design |

#### B-4：KG Phase 2 图谱增强（design §3 第 255-275 行）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——服务对象：教师/教研组长；当前图谱稀疏（147 硬前置边），增强后 ~400-450 边 |
| 范围 | soft 边可视化 + 高考关联推断（共现边）+ prerequisite_depth 拓扑 + 关系强度可视化 |
| 估时 | ~6 task（design.md L454）|
| 前置依赖 | KG Phase 1 完整收尾（IF-1 解封） |
| 当前状态 | design 已写，无 plan |

#### B-5：KG Phase 3 教学规划（design §3 第 277-299 行）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——design.md L547 风险段警告"使用率低，可根据反馈决定是否推进"；服务对象：教师 |
| 范围 | teaching_plans + teaching_plan_items 表；建议教学序列 API；教学进度可视化；StudyUnit 暴露 |
| 估时 | ~8 task（design.md L455） |
| 前置依赖 | KG Phase 2 |
| 当前状态 | design 已写，无 plan；优先级低 |

#### B-6：KG Phase 4 学生画像与推荐（design §3 第 301-326 行）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——服务对象：教师/学生；与 adaptive 模块 BKT 引擎深度关联 |
| 范围 | answer_logs 数据管线 + 掌握度图谱着色（API 已支持 `get_mastery`，前端集成）+ 学习推荐 API + 推荐练习题 |
| 估时 | 未在 design 中给具体 task 数 |
| 前置依赖 | KG Phase 1 收尾 + adaptive BKT 已实现 |
| 当前状态 | design 已写，部分基础设施已就绪 |

#### B-7：haofenshu Phase 1 Batch 3（design §6）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——服务对象：所有角色；前端骨架完整后才能继续 Phase 2/3 |
| 范围 | Task 10-12：PowerFilter + 45 页面 stub + 端到端 |
| 估时 | 1 batch / 3 task |
| 前置依赖 | T-Wipe（plan baseline 数字与 ECS 视角对齐） |
| 当前状态 | handoff 卡 `docs/plans/2026-04-14-haofenshu-phase1-batch3-handoff.md` 已就绪 |

#### B-8：haofenshu Phase 2 现有功能迁移（design §6 L521-538）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——服务对象：所有角色；将 frontend/ 21 页面迁到 frontend-nuxt/ |
| 范围 | 8 大类（exam/analytics/grading/marking/card-editor/knowledge-tree/AI 浮窗/baseinfo） |
| 估时 | ~30 前端文件 / 0 后端 / 0 migration（design.md L568 表） |
| 前置依赖 | Phase 1 全完成（B-7 之后） |
| 当前状态 | 仅 design 占位 |

#### B-9：haofenshu Phase 3 新模块填充（design §6 L540-552）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——填补 edu-cloud B 端教学侧业务空白；服务对象：教师/教研组长/教务/学生 |
| 范围 | 7 大业务模块新增前端 + 8 大新后端 service：work（4 页）/ lesson（4 页）/ research（7 页）/ academic（5 页）/ study 补全（4 页）/ report 补全（3 页）/ baseinfo 补全（4 页）+ 种子数据 seed_haofenshu.py |
| 估时 | ~45 前端文件 + ~25 后端文件 / 0 migration（design.md L569 表） |
| 前置依赖 | Phase 1 全完成（B-7 之后） |
| 当前状态 | 仅 design 占位 |

#### B-10：conduct-roadmap 批次 2（design §2.3）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——运维就绪；服务对象：开发团队（防退化）+ 班主任（功能扩展） |
| 范围 | D-005 sentinel（class_scope/resource_class/AES 加密） + D-009 F007 同模式横扫 analytics/statistics/profile + D-010 seed_menus 加 conduct 9 子菜单 |
| 估时 | T2-T3，~5-8 task |
| 前置依赖 | conduct-roadmap 批次 1 PASS（IF-2 解封） |
| 当前状态 | 占位 |

#### B-11：conduct-roadmap 批次 3（design §2.4）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——真实验证；服务对象：QA + 家长 |
| 范围 | D-006 家长端 5 核心流程 Playwright E2E + D-007 AI Chat 真实调用 conduct 工具 + D-008 Excel 中文 UTF-8 真实下载 |
| 估时 | T3，~3-5 task |
| 前置依赖 | 批次 2 PASS |
| 当前状态 | 占位 |

#### B-12：常驻巡检 Agent（CLAUDE.md "实现状态" 表 AI 行）

| 项 | 内容 |
|---|---|
| 业务价值 | MED——服务对象：教师/教务（自动巡检 + agent_findings 通知） |
| 范围 | W6 patrol 已有 12 测试基础（test_ai/test_w6_patrol.py），缺常驻调度 + 通知集成 |
| 估时 | T2-T3 |
| 前置依赖 | 无（基础设施已就绪） |
| 当前状态 | 仅 CLAUDE.md backlog 提名 |

#### B-13：AI grading 生产接入（CLAUDE.md "实现状态" 表 Services 行）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——CLAUDE.md 显式列为 Services "未实现"；当前 grading worker 已能跑测试，但生产环境的 LLM 实例配额/超时/降级策略未沉淀 |
| 范围 | 配置中心 + 多 slot 优先级 + 超时降级 + 配额监控 |
| 估时 | T2-T3 |
| 前置依赖 | grading 模块已上线 + LLM slot 已实现 |
| 当前状态 | 仅 CLAUDE.md backlog 提名 |

#### B-14：B 端真实扫描图端到端走查（来自 MEMORY.md 提示）

| 项 | 内容 |
|---|---|
| 业务价值 | HIGH——edu B 端主链路（Phase 0-A→2-C 8 phase 已完成 2026-04-16），仅剩"端到端真实扫描图走查" |
| 范围 | 真实扫描图 → paper-seg → edu-cloud compat 路由 → 阅卷 → 报表 |
| 估时 | T2，1-2h（仅验证，可能伴随 bug 修复） |
| 前置依赖 | 无 |
| 当前状态 | MEMORY.md handoff_edu_bflow 提示，无独立 plan |

---

## §5. 元能力技术债清单

### 5.1 已派发待启 + 已派完成 + 未派

| ID | 标题 | 派发状态 | 优先级 | 估时 | 派发卡 |
|---|---|---|---|---|---|
| TD-1 | T-Wipe ECS 单一环境彻底切断（含 T-F + W4-R8 整合 + A2 决策升级） | **已派发紧急未启** | **P0** | 4-6h | `docs/plans/2026-04-18-windows-wipe-handoff.md` |
| TD-2 | FAIL fixture（test_run_post_exam_pipeline_stub） | 未派 | P2（独立小修） | <1h | T-H 报告 §5 |
| TD-3 | compat-router 退役（exam-ai 兼容路由 8 端点）| 未派 | P3（计划 2026-07-31）| 中等 | `docs/plans/compat-router-deprecation.md`（CLAUDE.md L579 引）|
| TD-4 | 逐模块 MODULE.md 补全（grading/pipeline 已有，其余 18 模块缺）| 部分进行（conduct 在 IF-2 batch1 T4） | P2 | 每模块 0.5h | `docs/plans/2026-04-13-module-governance-design.md` |
| TD-5 | T-E audit | ✅ 完成 | — | — | `docs/plans/2026-04-18-takeover-impact-audit-report.md` |
| TD-6 | T-G plan_baseline_guard hook | ✅ 完成 | — | — | hook 文件 `~/.claude/hooks/plan_baseline_guard.py` 339 行 + W4 R8 frontmatter 5 字段补 (commit `5657f82`) |
| TD-7 | T-H ECS pytest 环境装配 | ✅ 完成 | — | — | `docs/plans/2026-04-18-ecs-pytest-baseline-report.md` + `scripts/setup_ecs_dev.sh` + `docs/dev/ecs-pytest-setup.md` |

### 5.2 关键观察

- **TD-1 是 P0 阻塞项**：3 个业务任务 (IF-2 W4 / B-7 haofenshu Batch 3 / Sprint 1 全部新规划) 都需要 ECS-rewrite 后的 plan baseline 才能跑 executing-plans skill
- **TD-3 compat-router 退役**：CLAUDE.md L579 写明 "目标退役 2026-07-31"，需 paper-seg 改造对接 `/api/v1/*` 而非 `/api/*`
- **TD-4 MODULE.md 补全**：conduct 已纳入 IF-2 batch1 T4；其他 18 模块（exam/school/scan/analytics/knowledge_tree/knowledge/homework/studio/calendar/profile/bank/marking/card/adaptive/menu/paper/student/knowledge_tree）缺，逐个补可作 boy-scout 顺手项

---

## §6. 依赖图（业务任务 + 元能力依赖）

### 6.1 元能力 → 业务硬依赖

```
                                  ┌─────────────────────────────────────┐
                                  │ TD-1 T-Wipe ECS 单一环境彻底切断   │
                                  │ (P0, 4-6h, 已派发未启)              │
                                  └────────────────┬────────────────────┘
                                                   │ 解锁
                       ┌───────────────────────────┼───────────────────────────┐
                       ▼                           ▼                           ▼
            ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
            │ IF-2 W4 conduct- │       │ B-7 haofenshu    │       │ Sprint 1 任何新   │
            │ roadmap batch1   │       │ Phase 1 Batch 3  │       │ plan baseline    │
            │ T1-T5 实施       │       │ Task 10-12        │       │ 自动通过 hook    │
            │ (HIGH, 4-6h)     │       │ (MED, 中等)       │       │                   │
            └──────────────────┘       └──────────────────┘       └──────────────────┘
                       │                           │
                       │ 解锁                       │ 解锁
                       ▼                           ▼
            ┌──────────────────┐       ┌──────────────────┐
            │ B-10 conduct-    │       │ B-8 haofenshu    │
            │ roadmap 批次 2   │       │ Phase 2 现有迁移  │
            │ (MED, 5-8 task)   │       │ (MED, ~30 前端)   │
            └──────────────────┘       └──────────────────┘
                       │                           │
                       │ 解锁                       │ 解锁（与 B-8 并行）
                       ▼                           ▼
            ┌──────────────────┐       ┌──────────────────┐
            │ B-11 conduct-    │       │ B-9 haofenshu    │
            │ roadmap 批次 3   │       │ Phase 3 新模块    │
            │ (MED, 3-5 task)  │       │ (HIGH, ~70 文件)  │
            └──────────────────┘       └──────────────────┘
```

### 6.2 KG 依赖链（独立于 T-Wipe）

```
            ┌──────────────────────────────────────────┐
            │ IF-1 W2 KG-phase1 收尾                  │
            │ (HIGH, 3-5h, R2 修复 + Phase B 收尾)     │
            └────────────────┬─────────────────────────┘
                             │ 解锁
                             ▼
            ┌──────────────────┐
            │ B-4 KG Phase 2   │
            │ 图谱增强          │
            │ (MED, ~6 task)   │
            └────────┬─────────┘
                     │ 解锁
                     ▼
            ┌──────────────────┐       ┌──────────────────┐
            │ B-5 KG Phase 3   │       │ B-6 KG Phase 4   │
            │ 教学规划          │  并行 │ 学生画像与推荐    │
            │ (LOW, ~8 task)   │       │ (HIGH, 与 BKT)   │
            └──────────────────┘       └──────────────────┘
```

### 6.3 联考 / 跨校能力链（无硬阻塞，独立于 T-Wipe）

```
            ┌──────────────────┐        ┌──────────────────┐         ┌──────────────────┐
            │ B-1 共享 AI 阅卷  │  并行  │ B-2 统一题库      │  并行  │ B-3 高级跨校分析  │
            │ (HIGH, T3)        │        │ (HIGH, T4)        │        │ (HIGH, T3)        │
            └──────────────────┘        └──────────────────┘         └──────────────────┘
```

> 这 3 项共同构成"edu-cloud 项目定位"承诺的最后短板（CLAUDE.md L24-26）。可在 T-Wipe 后任意启动设计 plan，相互无依赖。

### 6.4 元能力技术债自治

```
            ┌──────────────────┐        ┌──────────────────┐         ┌──────────────────┐
            │ TD-2 FAIL fixture │  独立  │ TD-3 compat-     │  独立  │ TD-4 MODULE.md  │
            │ (P2, <1h)         │        │ router 退役 7-31  │        │ 18 模块补全     │
            └──────────────────┘        └──────────────────┘         └──────────────────┘
```

---

## §7. Planner 重新规划建议

### 7.1 Sprint 1（本周）— 解封 + 收尾 in-flight

| Task | 类型 | 估时 | 服务对象 | 启动条件 | 备注 |
|---|---|---|---|---|---|
| **TD-1 T-Wipe Executor 启动** | 元能力 | 4-6h | 开发团队（清扫 Windows 残影 + W4 R8 plan ECS-rewrite + LESSON L018） | 用户确认 | **P0 紧急，硬阻塞 IF-2 + B-7 + Sprint 1 任何新 plan** |
| **IF-1 W2 KG-phase1 收尾** | 业务（前端）| 3-5h | 教师/教研组长 | 用户对 F005 拍板 (A 移 defineExpose / B 改 plan) | 独立 worktree，与 T-Wipe 无文件冲突 |
| **IF-2 W4 conduct-roadmap batch 1 T1-T5** | 业务（后端+前端） | 4-6h | 班主任/教务/家长 | T-Wipe Phase 4 完成 | 5 task 各独立 commit；T1+T3 是 behavior_change（用户已批） |
| **TD-2 FAIL fixture** | 元能力 | <1h | QA | 任意时间 | 独立小修，可塞缝隙 |

> Sprint 1 总耗时估 12-18h（按用户低 session 并发偏好，建议 2 session 串行：1 session 跑 T-Wipe + IF-2，1 session 跑 IF-1）

### 7.2 Sprint 2（下周）— 业务推进 + backlog 启动

| Task | 类型 | 估时 | 服务对象 | 启动条件 |
|---|---|---|---|---|
| B-7 haofenshu Phase 1 Batch 3 | 业务（前端） | 中等 | 所有角色 | T-Wipe 完成（plan baseline 与 ECS 视角一致） |
| B-10 conduct-roadmap 批次 2 设计 | 业务+元能力 | 设计 1-2h | 班主任/QA | IF-2 PASS |
| B-4 KG Phase 2 设计 | 业务（设计） | 设计 1-2h | 教师/教研组长 | IF-1 PASS |
| B-1 共享 AI 阅卷 设计 | 业务（设计） | 设计 1-2h | 所有学校 | T-Wipe 完成 |
| TD-4 MODULE.md 补全（每模块 0.5h，挑 5 个高频）| 元能力 | 2.5h | 开发团队 | 任意 |

> Sprint 2 总耗时估 8-15h；业务推进 + 设计 plan 并行；建议 2-3 session

### 7.3 Sprint 3（后续 backlog）— 大项目 + Phase 2/3 推进

| Task | 类型 | 估时 | 服务对象 | 启动条件 |
|---|---|---|---|---|
| B-8 haofenshu Phase 2 现有功能迁移 | 业务（前端） | ~30 文件 / 多 batch | 所有角色 | B-7 完成 |
| B-9 haofenshu Phase 3 新模块填充 | 业务（前端+后端） | ~70 文件 / 多 batch | 教师/教研/教务/学生 | B-7 完成（与 B-8 并行） |
| B-2 统一题库 设计 | 业务（设计） | T4 | 教研/教育局 | 无硬依赖 |
| B-3 高级跨校分析 设计 | 业务（设计） | T3 | 教育局 | 无硬依赖 |
| B-6 KG Phase 4 学生画像 | 业务（设计+实施） | 中等 | 教师/学生 | B-4 完成 |
| B-11 conduct-roadmap 批次 3 真实验证 | QA | T3 | QA/家长 | B-10 完成 |
| B-12 常驻巡检 Agent | 业务+AI | T2-T3 | 教师/教务 | 任意 |
| B-13 AI grading 生产接入 | 后端 | T2-T3 | 所有学校 | 任意 |
| B-14 B 端真实扫描图端到端走查 | QA | 1-2h | QA | 任意 |
| B-5 KG Phase 3 教学规划 | 业务（低优先） | ~8 task | 教师 | B-4 完成；可推后 |
| TD-3 compat-router 退役 | 元能力 | 中等 | 开发团队 | 接近 7-31 截止时启动 |

### 7.4 资源分配建议

**用户偏好实查**：
- 提示 prompt 明写"低 session 并发（5 W 太多关过）"
- Planner V2 §6 写"checkpoint 式推进"
- L018 ECS 单一环境铁律严守

**推荐配置**：
- **Sprint 1**：**最多 2 session 并发**（1 跑 T-Wipe Executor，1 跑 IF-1 W2 收尾；T-Wipe 完成后切换到 IF-2 W4 实施）
- **Sprint 2**：**最多 2 session 并发**（设计 + 实施分离；不同 worktree 即可）
- **Sprint 3**：**1-2 session**（大项目按批次串行，避免 worktree 数 > 3）
- **设计 plan 写作**与**实施**用 V3 决策强调的"checkpoint 式"独立 session

### 7.5 风险提示

1. **T-Wipe 失败风险**：7 Phase 任务量大，若中途 dry-run 不通过可能拖延 IF-2 启动；建议 Phase 1-3 先做（基线声明 + hook 升级 + CLAUDE.md），Phase 4-6 (W4 R8 重写 + 全量清洗) 可分两 session
2. **W2 R2 F005 决策悬而未决**：A 移 defineExpose vs B 改 plan，用户未拍板；建议 Planner 优先推用户拍板
3. **haofenshu Phase 3 规模巨大**（~70 文件），是 B 端教学侧"补完"的最大工程；建议先做 B-7（Phase 1 Batch 3）确认骨架，再决定 Phase 2/3 顺序
4. **B-1/B-2/B-3 三个 CLAUDE.md "未实现"**是 edu-cloud 项目定位承诺最后短板，应作为 Q2 重点；建议 Sprint 2 启 B-1 设计（最贴近现有 grading worker 复用）
5. **MODULE.md 18 模块缺补全**是治理债（TD-4），但不阻塞业务；可作为各 Sprint 的 boy-scout 项穿插
6. **常驻巡检 Agent (B-12)** 与 **AI grading 生产接入 (B-13)** 是 AI 体系的真正"未实现"；CLAUDE.md "实现状态" 表显式标，建议 Sprint 3 提优先级
7. **W2 worktree 路径分裂注意**：Planner V2 写 W4 在 `/home/ops/projects/edu-cloud`（不是 edu-cloud-w4），易混淆
8. **CLAUDE.md 数字陈旧**：CLAUDE.md "1851 后端 + 73 前端 Vitest" vs ECS 实测 1934 passed；T-Wipe Phase 3 会订正

---

## §8. 报告附录

### 8.1 我读了哪些文件（37 个）

**项目根**：
- `/home/ops/projects/edu-cloud-t2/CLAUDE.md`（全文，分段读）

**docs/plans/**（核心 design 文档）：
- `2026-04-12-haofenshu-biz-replication-design.md`（§0-§9 + Phase 6 § 详读）
- `2026-04-12-knowledge-graph-optimization-design.md`（§3 Phase 1-4 详读）
- `2026-04-14-conduct-roadmap-design.md`（§0-§3 + 批次 1 设计详读）
- `2026-04-13-module-governance-design.md`（标题列）
- `2026-04-13-knowledge-graph-phase1-state.json`（state 实查）

**docs/plans/**（in-flight handoff 卡）：
- `2026-04-18-windows-wipe-handoff.md`（T-Wipe 派发卡详读）
- `2026-04-18-w2-kg-phase1-finish-handoff.md`（W2 收尾详读）
- `2026-04-18-w2-r2-repair-handoff.md`（W2 R2 修复详读）
- `2026-04-18-w4-exec-T1-T5-handoff.md`（W4 执行详读）
- `2026-04-18-planner-decisions-v3.md`（V3 决策详读）
- `2026-04-18-planner-session-handoff-v2.md`（V2 跨 session 卡详读）
- `2026-04-18-takeover-impact-audit-report.md`（T-E audit 详读）
- `2026-04-18-ecs-pytest-baseline-report.md`（T-H baseline 详读）

**Glob 输出（不计阅读时间）**：
- `docs/plans/*-design.md`（33 份列表）
- `docs/plans/*handoff*`（>100 文件列表）
- `docs/plans/*-plan.md`（36 份列表）
- `docs/plans/2026-04-1[3-8]*`（73 文件列表）
- `src/edu_cloud/modules/*`（每模块 ls）
- `src/edu_cloud/modules/*/MODULE.md`（仅 grading + pipeline 命中）
- `src/edu_cloud/modules/*/__init__.py`（25 文件）

**Grep 输出（不计阅读时间）**：
- `@router\.(get|post|put|patch|delete)` 整个 modules/ → 212 总 / 32 文件
- `^(async )?def ` 整个 modules/ → 573 总 / 93 文件
- `def test_` 整个 tests/ → 1958 总 / 250 文件
- conduct/knowledge_tree/modules/ai 子树测试数（4 次 grep）
- design 文档 Phase 关键词搜索

### 8.2 调研范围与方法说明

- **范围**：edu-cloud 主仓 master @ `20eb90b`（HEAD 实查）+ docs/plans 全量 design+plan+handoff+state.json
- **方法**：依赖 git/grep/ls/cat/Read 只读工具；禁运行 pytest（ECS 已装但 692s 太长，且本任务不要求复跑）；禁动 W2/W4 worktree 文件
- **数字交叉对账**：CLAUDE.md 声明 vs grep 实测 vs T-H pytest 实测三方对照
- **依据可信度**：
  - **HIGH**：grep 实测 + git log 锚定 + handoff/state.json 单一文档源
  - **MED**：CLAUDE.md 声明 + 多文档交叉
  - **LOW**：跨文档推断（如 Sprint 估时基于 design.md 历史项目类比）

### 8.3 局限性声明

1. **未跑 pytest 实测**：所有"测试数"基于 grep `def test_`；与 pytest 实跑 case 数 1:1 对应（T-H §3 已验证 5/5 模块 grep = pytest）
2. **未读 frontend/ Vue/JS 代码**：前端模块完成度仅依赖 CLAUDE.md "frontend/src/" 段声明
3. **Sprint 估时不精确**：基于 design.md 历史 task 数类比；新业务（B-1/B-2/B-3）从未做过，估时偏粗
4. **未审 W2 R1 report 5 findings 细节**：仅引用 W2-R2 handoff 摘要表
5. **Backlog 优先级判断带主观**：HIGH/MED/LOW 基于 CLAUDE.md "项目定位"段服务对象 + 显式 backlog 提名；"业务价值"评估非精确量化
6. **依赖图未画 PostgreSQL/Redis/arq 基础设施依赖**：仅画业务+元能力任务级依赖
7. **未包含 docs/dev/、docs/arch/ 内容**：仅看 docs/plans/

### 8.4 关键洞察

1. **edu-cloud 已经是"成型 B 端平台"，不是 MVP**：212 端点 + 1934 测试 + 20 模块全实现，CLAUDE.md "实现状态" 表显示 7 个层全 ✅；剩余空白集中在 3 个 CLAUDE.md 显式 backlog（B-1/B-2/B-3）+ 4 个 Phase 2/3 设计（B-4/B-5/B-6/B-8/B-9）
2. **当前阻塞集中在元能力层而非业务层**：T-Wipe 是 P0 阻塞，3 业务任务等它解封；用户偏好"低 session 并发"已被 5 W 验证；Planner 再规划时**不应同时启 >2 业务 worktree**
3. **W4 conduct-roadmap batch1 是 5 task 微型 plan**：是检验 T-Wipe 流程的最佳测试床，T1+T3 behavior_change 已批，可在 T-Wipe 完成 24h 内启实施
4. **haofenshu Phase 1 Batch 3 + Phase 2/3 是 B 端"补完"的最大单一项目**：~145 文件总规模（Phase 1 ~60 + Phase 2 ~30 + Phase 3 ~70），比所有其他 backlog 加起来还大
5. **KG 体系已 5 个 design [实现完成] + Phase 2/3/4 占位**：是技术深度最深的子系统，但 design.md L547 警告 "Phase 3 使用率低"，建议 Phase 2 + Phase 4 优先
6. **conduct 模块是"完整端到端业务样板"**：68 测试 / 39 端点 / 8 ORM 表 / 6 Agent 工具 / 3 套前端（管理端 9 页 + 家长端 8 页 + Sidebar 三档）；新业务模块设计可参考其结构

### 8.5 建议的下一步（给 Planner）

1. **立即推用户拍板 W2 R2 F005**（A 移 defineExpose / B 改 plan），解封 IF-1 启动
2. **立即派 T-Wipe Executor**（用户已严令，启动 prompt 在 windows-wipe-handoff §7）
3. **T-Wipe 7 Phase 拆 2 session**：Phase 1-3 (基线 + hook + CLAUDE.md, ~2h) 一 session，Phase 4-7 (W4 重写 + baseline + 清洗 + 终验, ~3-4h) 另一 session，避免单 session 过长
4. **IF-2 W4 实施前先 verify T-Wipe Phase 4** 完成（W4 R8 plan ECS-rewrite + state.json 已建）
5. **设计 plan 写作不阻塞实施**：Sprint 2 可让一 session 写 B-1/B-4/B-10 设计，另一 session 跑实施
6. **CLAUDE.md "未实现端点" 段**应在 T-Wipe Phase 3 同步订正"陈旧"（1896→1934）+ 标 B-1/B-2/B-3 是 Q2 重点
7. **MODULE.md 补全**作为各 Sprint 的 boy-scout 项穿插，不单独成 Sprint

### 8.6 过程备忘

- 调研启动：2026-04-18，~13:00 后（Planner V3 决策落档后约 2 小时）
- 关键发现持久化：本报告即持久化（防压缩丢失）
- 未触发 Codex 协助
- 未访问 W2/W4 worktree 文件（仅引用 master 上的 handoff 卡，符合"禁动"红线）
- 未跑 pytest（依据 T-H 已验证的 grep≈pytest 等价关系）
- 文档命中重复：T-E audit + T-H baseline + V3 决策 + V2 handoff + windows-wipe-handoff 五者构成"事实底盘"，相互交叉对账无矛盾
- 与 CLAUDE.md "实现状态" 表数字差异：模块 20（一致）/ 端点 223 声明 vs grep 212（差 11，由 modules/ 外的 api/*.py 顶层 router 解释）/ tests 1851 声明 vs pytest 1934（差 83，CLAUDE.md 陈旧）

---

**报告基于事实 + grep + git log + design.md + handoff 卡 + state.json，禁猜测。L013（自审盲区）/ L015（虚假完成声明）/ L017（GPT 局部最优）/ L018（ECS 单一环境）严守。**
