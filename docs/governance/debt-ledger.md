# edu-cloud Foundation Debt Ledger（地基债务台账）

> 创建：2026-06-12（W3 governance context closeout，Yuanshou V2 合同
> `yc-20260612-899ea9ce`）
> 用途：**单一债务真源**——把散落在 audit / handoff / review 中的过程债与结构债
> 合并为一张台账，取代 finding 驱动 / 应激驱动的选题方式；元策每窗口从此「领一批」。
> 性质：只登记，不修业务代码。条目处置须经独立合同窗口，收口后在此更新状态。
> 更新纪律：每个合同窗口收口时报仪表盘 delta；数字不动 = 没深度。
> 证据底座：`docs/reviews/2026-06-11-edu-foundation-deep-investigation.md` +
> `docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6）+
> `docs/reviews/2026-06-12-w1-governance-acceptance.md` +
> `docs/reviews/2026-06-13-q3-foundation-debt-reconcile.md`（W2 后 Q3 校准：D-01/D-02
> 机械闸门 closed、历史 review-gap 13→16）。

## 深度仪表盘（每窗口收口报 delta）

| 指标 | 现值（2026-06-12） | 完工线 |
|---|---|---|
| 开放 HIGH 风险 | 3（R-H3 / R-H4 / R-H5） | 0 |
| 跨模块依赖环 | 0（11 edges）（D-03A 30/55→21/54、D-03B 21/54→13/53、D-03C 13/53→4/52、D-03D 4/52→0/51、D-03E 0/51→0/50；D-03F 0/50→0/50：occurrence 级，analytics 公共有效分读模型 + 3 处跨模块 import 上移共享层，边经其它文件保留；D-03G 0/50→0/49：analytics→studio 报告文档编排上移；D-03H 0/49→0/48：pipeline→bank 题库/错题本制品上移共享层；D-03I 0/48→0/41：pipeline 冷数据 owner 上移共享层，一次拆 7 条 pipeline→{exam,grading,knowledge,knowledge_tree,profile,scan,student} 边；D-03J 0/41→0/35：exam_import 导入写入链 owner 上移共享层，一次拆 6 条 exam_import→{exam,grading,pipeline,profile,scan,student} 边；D-03K 0/35→0/32：marking 阅卷工作流跨模块模型/解析助手访问上移共享层，一次拆 3 条 marking→{exam,grading,scan} 边；D-03L 0/32→0/29：scan 扫描工作流跨模块模型/常量访问上移共享层，一次拆 3 条 scan→{exam,card,student} 边；D-03M 0/29→0/26：grading 阅卷工作流跨模块模型/常量/工具访问上移共享层，一次拆 3 条 grading→{exam,card,scan} 边；D-03N 0/26→0/23：homework 考后补救工作流跨模块模型访问上移共享层，一次拆 3 条 homework→{exam,scan,bank} 边；D-03O 0/23→0/18：conduct 德育工作流跨模块模型/错题本服务访问上移共享层，一次拆 5 条 conduct→{academic,bank,exam,profile,student} 边；D-03P 0/18→0/11：bank/knowledge/portal/profile 小 owner 批次跨模块模型/服务访问上移共享层，一次拆 7 条边） | 持续下降 + gate 防回弹 |
| AI tool 语义错挂 | ~46 个挤 `exam` 码 | 按 owner 归位 |
| 测试基线口径 | 1 套（CI-aligned 单一真源，2026-06-17 D-07 收口；此前 3 套分裂） | 1 套、自动刷新 ✅ |
| 无 receipt 提交（历史债，L2） | 16（`3688f32..6b1bdd3`，W1 时为 13） | 0（补审后清零） |
| receipt/runtime-op 机械闸门（L1） | ✅ closed/gate-built（W2 live） | 已达成（机械不可再发生） |

> 仪表盘口径校准（Q3，2026-06-13，合同 `yc-20260614-39eac63d`）：洞 A/洞 B 的
> **机械闸门（L1）已 W2 gate-built closed**——「机械不可再发生」已达成；剩下的
> **历史 review-gap（L2）是独立债项**，从 W1 的 13 增至 16 commit，需独立补审才清零。
> 闸门关闭 ≠ 历史债清账，两层分开记。详见 `docs/reviews/2026-06-13-q3-foundation-debt-reconcile.md`。

地基完工判据（全绿即转常态开发）：① doctor 常态 READY ② commit 必带
receipt/waiver（机械强制，**W2 已达成**）③ 运行态操作必在合同窗口内（机械强制，
**W2 已达成**）④ 环数下降且 gate 防回弹 ⑤ 测试基线单一真源自动刷新。

## 债务条目

### D-01 runtime operation 未绑合同（洞 A）— HIGH · 过程

- 内容：运行态操作（restart / rebuild / deploy）不经 V2 合同即可执行，零兜底。
- **机械闸门（L1）**：W2（元守侧 writer，yuanshou 仓）已实现「运行态操作绑合同」
  机械硬闸并 live——`tests/v2/test_runtime_ops.py` + `test_boundary_guard_hook.py`
  绿（与 git_rules/review_receipt 合计 96 passed），`scripts/yc doctor` READY、
  source=origin=live 对齐。运行态操作此后机械强制在合同窗口内。
- **历史事故（L2，背景化）**：R-M2 已实际发生 2 次（06-10 `6f90994→c26379d` 对齐；
  06-11 21:19 紧跟 push 的 restart+rebuild，均无留痕），已在 NOW/audit 留痕；机械层
  关闭后不再新增，无补审动作需求。
- 状态：**closed/gate-built**（L1 闸门已建并 live；L2 历史事故背景化、不新增）。
  Q3 校准（2026-06-13，合同 `yc-20260614-39eac63d`）确认。

### D-02 review receipt 未绑 commit（洞 B）— HIGH · 过程

> **本条拆两层**：机械闸门（L1）已闭合；历史 review-gap（L2）仍开放。两层分开记，
> 闸门关闭 ≠ 历史债清账。

- **机械闸门（L1）= closed/gate-built**：W2（元守侧 writer，yuanshou 仓）已实现
  「receipt 绑 commit」机械硬闸并 live——`tests/v2/test_review_receipt.py` +
  `test_git_rules.py` 绿（合计 96 passed）。commit 落地此后机械强制带 receipt/waiver，
  零 receipt 的 commit 不可再发生。
- **历史 review-gap（L2）= open**：06-07 后零 receipt 的 commit 残留，**从 W1 记录的
  13 commit 增至 16 commit**（`3688f32..6b1bdd3`，W1 后新增 `3c2b7e2`/`c0057df`/
  `6b1bdd3`；含 coze provider +2,946 行、answer-card canonical +3,634 行）。
  `.review-receipts.jsonl` 末条仍 = 06-07 14:40 `PASS@3688f32`。
- 处置路径（L2）：按 `docs/reviews/2026-06-12-w1-governance-acceptance.md` §3 处置表
  （两次 `codex-review range` 补审 + waiver/留痕/签认），在**独立 review-gap 合同窗口**
  跑——**不在本 docs-only 校准窗，需带 review 授权的独立合同**。
- 状态：**机械闸门 closed/gate-built；历史 16 commit review-gap 仍 open**。
  Q3 校准（2026-06-13，合同 `yc-20260614-39eac63d`）确认计数 13→16，
  详见 `docs/reviews/2026-06-13-q3-foundation-debt-reconcile.md`。

### D-03 跨模块耦合 53 edges / 13 cycles（R-H4）— HIGH · 结构

- 内容：模块依赖基线跨模块边 + 历史环，gate
  （`scripts/governance/check_module_dependencies.py`）防新增 + 增量 burn-down。
  禁用模块代码可借其他模块端点执行（门控逃逸面）。
- burn-down 记录：
  - **D-03A（2026-06-17，合同 `yc-20260617-bdea249c`）**：学生个体 AI 诊断
    `student_ai_diagnosis` 所有权从 `analytics.insights_service` 迁回 profile 自有
    `diagnosis_service`（仅消费 profile 三表，无新增跨模块边），消除 `profile ->
    analytics` 依赖边。基线 **55→54 edges、30→21 cycles**（profile→analytics 参与的
    历史环随边消失）。profile MODULE.md `depends_on.modules` 同步删 analytics（仅余
    knowledge_tree）；`analytics -> profile` 边经 `report_service.py` 保留、不受影响。
  - **D-03B（2026-06-17，合同 `yc-20260617-28ad2a65`）**：考后编排上移至模块外应用
    服务 `services.post_exam_pipeline.run_post_exam_pipeline`——`pipeline.run_full_pipeline`
    去掉 `analytics.compute_exam_analysis` 调用、`_get_effective_scores_for_subject` 改
    pipeline 自有局部有效分查询（同 `_get_effective_score` 权威规则，不再 import
    `analytics.get_effective_scores`），消除 `pipeline -> analytics` 依赖边。基线
    **54→53 edges、21→13 cycles**（analytics↔pipeline 参与的 8 个环随边消失）。pipeline
    MODULE.md `depends_on.modules` 同步删 analytics；外部调用点（worker/exam service/
    pipeline router/seed_demo）改调编排服务，`run_full_pipeline` 仍由 pipeline 自有冷数据步骤组成。
  - **D-03B ask-fix（2026-06-17，合同 `yc-20260617-13bac327`）**：修复 D-03B 解耦时引入的
    canonical 身份回归——pipeline 自有的 `_get_effective_scores_for_subject` 按 raw
    `StudentAnswer.student_id` 分组，漏掉身份归一化映射，致同一学生的 UUID 答题与条码答题
    被拆成两个 `StudentExamSnapshot`。处置：把身份归一化抽到模块外共享层
    `services.student_identity`（`analytics.identity` 保留向后兼容 re-export），pipeline 与
    analytics 复用同一 resolver 后按 `canonical_student_id` 聚合。**不重新引入
    `pipeline -> analytics` 依赖边，基线 53 edges / 13 cycles 不变**；pipeline/analytics
    MODULE.md `depends_on.services` 登记 `student_identity`。
  - **D-03C（2026-06-17，合同 `yc-20260617-edu-d03c-exam-pipeline-cut`）**：考试发布后处理
    上移至模块外编排服务 `services.exam_publish_pipeline`（`publish_rankings` /
    `publish_error_books` 调用期局部 import pipeline owner 函数）——`exam.publish_service`
    的 `_calculate_rankings` / `_update_error_books` 改委托该服务，exam 不再直接
    import `edu_cloud.modules.pipeline`，消除 `exam -> pipeline` 依赖边。基线
    **53→52 edges、13→4 cycles**（exam↔pipeline 参与的 9 个环随边消失，仅余
    exam↔grading 的 4 环）。exam MODULE.md `depends_on.modules` 删 pipeline（仅余
    grading），`depends_on.services` 登记 `exam_publish_pipeline`；发布行为与测试不变。
  - **D-03D（2026-06-18，合同 `yc-20260618-d03d-exam-grading-cut`）**：考试发布前置检查
    上移至模块外服务 `services.exam_publish_checks`（`ensure_grading_complete` /
    `ensure_no_high_severity_issues` 调用期局部 import grading 模型）——`exam.publish_service`
    的阅卷完成度 + 高危质量问题前置检查改委托该服务，exam 不再直接 import
    `edu_cloud.modules.grading`，消除 `exam -> grading` 依赖边。基线
    **52→51 edges、4→0 cycles**（exam↔grading 参与的 4 环随边消失，跨模块环全部清零；
    至此 exam 模块零跨模块 import 依赖边）。exam MODULE.md `depends_on.modules` 删 grading
    （变空），`depends_on.services` 登记 `exam_publish_checks`；发布行为 / 异常类型
    （StateError）/ 错误信息语义与测试不变，新增 exam 模块禁直接 import grading 的静态守护。
  - **D-03E（2026-06-18，合同 `yc-20260618-d03e-pipeline-adaptive-cut`）**：考后 adaptive
    BKT 掌握度更新（原 `pipeline.service._update_adaptive_mastery`）上移至模块外服务
    `services.post_exam_adaptive.update_adaptive_mastery`（调用期局部 import adaptive +
    pipeline `_get_effective_score` 权威有效分规则）——pipeline 模块不再直接 import
    `edu_cloud.modules.adaptive`，消除 `pipeline -> adaptive` 依赖边。基线
    **51→50 edges、0 cycles 不变**（该边不参与任何环；adaptive 仍有 `knowledge_tree -> adaptive`
    入边，不孤立）。pipeline MODULE.md `depends_on.modules` 删 adaptive，`depends_on.services`
    登记 `post_exam_adaptive`；编排服务 `services.post_exam_pipeline` 与 `on_exam_published`
    event handler 改调该服务，`adaptive_mastery` 返回值、幂等（AnswerLog 存在性跳过）、
    非阻塞降级（event handler try/except）与行为不变；`run_full_pipeline` 自此只产 5 个冷数据步骤。
  - **D-03F（2026-06-18，合同 `yc-20260618-66960847`）**：analytics 有效分读模型
    （`get_effective_scores` / `get_effective_scores_batch`，原 `analytics.__init__`）上移至
    模块外共享服务 `services.effective_scores`，跨模块模型 import（grading/scan/exam）与
    身份归一化随之上移；`analytics.__init__` 仅作向后兼容 re-export，10 处 analytics 内部
    调用点（service/report/grade/layer/ranking×3/pipeline/insights/exporters）改 import
    共享服务，AI 工具经 `analytics.service` module-level 名兼容不变。基线
    **0/50→0/50 不变**（occurrence 级解耦：`analytics -> {grading,scan,exam}` 仅丢失
    `__init__.py:5/6/7` 三处 occurrence，三条边仍由其它 analytics 文件承载，故边数不降）。
    analytics MODULE.md `depends_on.services` 登记 `effective_scores`；有效分行为、canonical
    身份语义、AI 工具导入路径与测试不变，新增 re-export 等价性单测固定 D-03F 不变量。
  - **D-03G（2026-06-18，合同 `yc-20260618-bbc0bacb`）**：分析报告文档创建编排
    （`type=analysis_report`，draft → reviewed → executed）从 `analytics_report_router.export_report`
    上移至模块外应用服务 `services.analysis_report_documents.create_analysis_report_document`
    （调用期局部 import `StudioService`，与 `services.post_exam_pipeline` 同范式）——
    `analytics_report_router` 不再直接 import `edu_cloud.modules.studio`，消除
    `analytics -> studio` 依赖边。基线 **50→49 edges、0 cycles 不变**（该边不参与任何环；
    studio 仍有其它入边）。analytics MODULE.md `depends_on.modules` 删 studio，
    `depends_on.services` 登记 `analysis_report_documents`；content_json 结构、状态机流转
    与返回契约不变，新增 service 单测固定文档创建 + 状态流转不变量。
  - **D-03H（2026-06-18，合同 `yc-20260618-d03b4a11`）**：考后题库/错题本制品
    （`BankQuestion` / `StudentErrorBook`）的读写——原 `pipeline.service` 的
    `populate_bank_questions` / `populate_error_books` / `_compute_question_stats`
    及 `update_error_patterns` 的错题本读查询——上移至模块外服务
    `services.post_exam_bank_artifacts`（调用期局部 import bank/exam/scan/grading/knowledge
    模型 + pipeline `_get_effective_score` 权威有效分规则，与 `services.post_exam_adaptive`
    同范式）——pipeline 模块不再直接 import `edu_cloud.modules.bank`，消除
    `pipeline -> bank` 依赖边。基线 **49→48 edges、0 cycles 不变**（该边不参与任何环；
    bank 仍有 conduct/homework 等入边，不孤立）。pipeline MODULE.md `depends_on.modules`
    删 bank，`depends_on.services` 登记 `post_exam_bank_artifacts`；
    `populate_bank_questions` / `populate_error_books` 经 pipeline.service re-export 保持
    公共导入兼容（既有调用点 exam/exam_import/编排服务与测试 patch 命名空间不变），
    `update_error_patterns` 经错题本读模型聚合、`run_full_pipeline` 返回契约与幂等行为不变，
    新增结构守护单测固定 pipeline 无直接 bank import 不变量。
  - **D-03I（2026-06-19，合同 `yc-20260619-e87813e7`）**：考后冷数据生成 owner 逻辑
    （`generate_exam_snapshots` / `update_knowledge_mastery` / `update_error_patterns`、
    有效分权威规则 `_get_effective_score` / `_get_effective_scores_for_subject`、一键编排
    `run_full_pipeline`）上移至模块外服务 `services.post_exam_cold_data`（调用期局部 import
    exam/scan/grading/knowledge/knowledge_tree/profile/student 模型 + `services.student_identity`
    canonical 身份归一 + `services.post_exam_bank_artifacts` 制品函数，与 D-03E/D-03H 同范式）
    ——pipeline 模块不再直接 import 上述 7 个冷数据模块，一次性消除
    `pipeline -> {exam, grading, knowledge, knowledge_tree, profile, scan, student}` 7 条依赖边。
    基线 **48→41 edges、0 cycles 不变**（这 7 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。
    pipeline MODULE.md `depends_on.modules` 清零（7→0），`depends_on.services` 删 `student_identity`
    （已移入 cold_data）、登记 `post_exam_cold_data`；`pipeline.service` 退化为纯 re-export facade
    （冷数据各步骤经 cold_data re-export、题库/错题本经 bank_artifacts re-export），既有调用点
    （exam/exam_import/编排服务）与测试 patch（`pipeline.service.*` 命名空间）行为零变更；
    `services.post_exam_adaptive` / `services.post_exam_bank_artifacts` 对 `_get_effective_score`
    的依赖改自 `services.post_exam_cold_data`（避免 services 反向 import pipeline.service）。
    返回契约、有效分权威规则、canonical 身份归一、幂等（DF-007）与非阻塞降级不变，新增结构守护
    单测固定 pipeline 无直接冷数据模块 import + facade 纯 re-export 不变量。
  - **D-03J（2026-06-21，合同 `yc-20260621-6cd4ee6f`）**：考试成绩导入写入链 owner 逻辑
    （`match_students` / `commit_import` / `run_post_import_pipeline` 及私有 upsert 助手
    `_upsert_subject` / `_upsert_question` / `_upsert_student_answer` / `_upsert_grading_result`
    / `_upsert_grading_result_absent` / `_upsert_exam_result`）上移至模块外服务
    `services.exam_import_materialization`（目标模块模型 + pipeline owner 函数采用调用期局部
    import，与 D-03E/D-03H/D-03I 同范式）——exam_import 模块不再直接 import 上述 6 个模块，
    一次性消除 `exam_import -> {exam, grading, pipeline, profile, scan, student}` 6 条依赖边。
    基线 **41→35 edges、0 cycles 不变**（这 6 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。
    exam_import MODULE.md `depends_on.modules` 清零（6→0）、`depends_on.services` 登记
    `exam_import_materialization`；`exam_import.service` 退化为纯 re-export facade（学生匹配/写入链/
    导入后流水线及数据类经 facade re-export），既有调用点（`exam_import.router`）与测试
    （`exam_import.service.*` 命名空间）行为零变更。学生匹配策略、写入链 upsert 幂等、缺考/正常
    切换、导入后 snapshot/error_book/error_pattern 覆盖语义与历史完全一致，新增结构守护单测固定
    exam_import.service 无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03K（2026-06-21，合同 `yc-20260621-d03k-marking`）**：marking 人工阅卷工作流对
    `exam` / `grading` / `scan` 的跨模块 ORM 模型（`Exam` / `Subject` / `Question` /
    `StudentAnswer` / `GradingAssignment` / `GradingResult`）与 grading 详情解析助手
    （`flatten_llm_details` / `parse_raw_content`）访问上移至模块外服务 `services.marking_workflow`
    （纯 re-export facade，对外符号与 owner 模块同一对象，与 `services.effective_scores` /
    `services.exam_import_materialization` 同范式）——marking（router/scorer/importer/exporter）
    不再直接 import 上述 3 个模块，一次性消除 `marking -> {exam, grading, scan}` 3 条依赖边。
    基线 **35→32 edges、0 cycles 不变**（这 3 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。
    marking MODULE.md `depends_on.modules` 清零（3→0）、`depends_on.services` 登记 `marking_workflow`；
    既有路由/打分/导入导出调用点与测试（`marking.scorer.*` / `/api/v1/marking` 命名空间）行为零变更。
    阅卷分配/取下一份/打分 upsert/进度统计/CSV 导出语义与历史完全一致，新增结构守护单测固定
    marking 无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03L（2026-06-22，Codex 本地全授权小窗）**：scan 扫描上传/流水线/CV 模板端点对
    `exam` / `card` / `student` 的跨模块 ORM 模型与题型常量访问上移至模块外服务
    `services.scan_workflow`（纯 re-export facade，对外符号与 owner 模块同一对象，与
    `services.marking_workflow` / `services.exam_import_materialization` 同范式）——scan
    （router/pipeline_router/cv_detect_router）不再直接 import 上述 3 个模块，一次性消除
    `scan -> {exam, card, student}` 3 条依赖边。基线 **32→29 edges、0 cycles 不变**
    （这 3 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。scan MODULE.md
    `depends_on.modules` 清零（3→0）、`depends_on.services` 登记 `scan_workflow`；既有
    扫描上传、批量流水线、CV 模板保存/校验、客观题自动判分语义与历史完全一致，新增结构守护
    单测固定 scan 无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03M（2026-06-22，Codex 本地全授权小窗）**：grading 阅卷任务/调度状态端点对
    `exam` / `card` / `scan` 的跨模块 ORM 模型、题型常量、题号排序、LLM slot 选择与 scan
    pipeline 状态访问上移至模块外服务 `services.grading_workflow`（纯 re-export facade，
    对外符号与 owner 模块同一对象，与 D-03K/D-03L 同范式）——grading
    （router/grading_review_router）不再直接 import 上述 3 个模块，一次性消除
    `grading -> {exam, card, scan}` 3 条依赖边。基线 **29→26 edges、0 cycles 不变**。
    grading MODULE.md `depends_on.modules` 清零（3→0）、`depends_on.services` 登记
    `grading_workflow`；既有 Rubric、AI 阅卷任务、单份预览评分、调度状态阶段推导语义不变，新增
    结构守护单测固定 grading 无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03N（2026-06-22，Codex 本地全授权小窗）**：homework 考后补救作业生成与内容详情解析对
    `exam` / `scan` / `bank` 的跨模块 ORM 模型访问上移至模块外服务 `services.homework_workflow`
    （纯 re-export facade，对外符号与 owner 模块同一对象，与 D-03K/D-03M 同范式）——homework
    `service.py` 不再直接 import 上述 3 个模块，一次性消除 `homework -> {exam, scan, bank}`
    3 条依赖边。基线 **26→23 edges、0 cycles 不变**。homework MODULE.md
    `depends_on.modules` 清零（3→0）、`depends_on.services` 登记 `homework_workflow`；既有
    remedial 作业生成、错题筛选、题库练习题匹配、content-detail 展开语义不变，新增结构守护单测
    固定 homework 无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03O（2026-06-22，Codex 本地全授权小窗）**：conduct 德育管理/家长门户对
    `student` / `academic` / `exam` / `profile` / `bank` owner 模型与错题本服务的直接 import
    上移至模块外服务 `services.conduct_workflow`（纯 re-export facade；不改变查询、权限、导出、家长端语义）——conduct
    模块不再直接 import 上述 5 个模块，一次性消除 `conduct -> {student, academic, exam, profile, bank}`
    5 条依赖边。基线 **23→18 edges、0 cycles 不变**。conduct MODULE.md
    `depends_on.modules` 清零（5→0）、`depends_on.services` 登记 `conduct_workflow`；既有
    德育配置、规则、导出、通知、家长门户、scope 权限语义不变，新增结构守护单测固定 conduct
    无直接目标模块 import + facade 纯 re-export 不变量。
  - **D-03P（2026-06-22，Codex 本地全授权小窗）**：bank / knowledge / portal / profile
    四个小 owner 模块的跨模块模型/服务读取上移至模块外 facade：`services.bank_workflow`
    （exam/student）、`services.knowledge_workflow`（exam/knowledge_tree）、`services.portal_workflow`
    （calendar/homework）、`services.profile_workflow`（knowledge_tree）——一次性消除
    `bank -> {exam, student}`、`knowledge -> {exam, knowledge_tree}`、`portal -> {calendar, homework}`、
    `profile -> knowledge_tree` 共 7 条依赖边。基线 **18→11 edges、0 cycles 不变**。四个 MODULE.md
    `depends_on.modules` 清零并登记对应 workflow service；新增
    `tests/governance/test_d03p_small_owner_boundaries.py` 固定直接 import 禁止与 facade re-export 不变量；
    bank 36 个测试、portal 9 个测试、knowledge/profile 59 个测试、边界 2 个测试通过。
- 处置路径（剩余）：跨模块环已清零；剩余 11 条跨模块边继续 burn-down 批次（独占窗串行，
  附依赖图 diff 证据）；准备层在 `modular-arch-restore` worktree（Plan 1 边界 gate，见 D-09 Q3）。
- 状态：**open（burn-down 进行中，环已清零）**——D-03A/D-03B/D-03C/D-03D/D-03E/D-03F/D-03G/D-03H/D-03I/D-03J/D-03K/D-03L/D-03M/D-03N/D-03O/D-03P 已收口，
  基线 11 edges / 0 cycles。

### D-04 AI tool module_code 语义债 — MED · 结构

- 内容：~46 个 AI tool 挤 `module_code="exam"`（analytics/profile/bank/knowledge/
  student-facing 工具语义错挂），真源 `docs/governance/ai-tool-module-codes.yaml`。
  门控语义失真：模块开关对这些工具不表达真实归属。
- 处置路径：module-writer 并行批次重分类（foundation-boundaries.md「Next
  Governance Batches」第 2 条），按 owner 归位 + 同批 role/scope 测试。
- 状态：**open**。

### D-05 Coze required_action 死开关（R-M3）— MED · 配置

- 内容：`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未声明进 `config.py` Settings
  （pydantic `extra="ignore"` 静默吞 env）→ 文档承诺的「显式开启」不可达。方向
  安全（永远 fail-closed）但开关无效。
- 处置路径：等 Q2 裁定——接线进 Settings vs 裁定永久关闭并删开关叙述。
- 裁定（Q2，2026-06-13，合同 `yc-20260613-fca3212d`）：**接线进 Settings、默认
  fail-closed**。`config.py` 声明 `AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED: bool =
  False`，env 现可绑定（不再被 `extra="ignore"` 吞）；`.env.example` 补默认
  `false`；RUNBOOK 明确开关存在但默认 false，submit/resume 未 live-proven 前不得
  启用；provider 运行时逻辑不变、生产仍 fail-closed。
- 证据：`Settings(_env_file=None)` 默认 `False`、env=true 后为 `True`；
  `provider_status` 在显式开启下 `required_action_submit_enabled/ready` +
  `tool_modes.coze_required_action` 三者 `True`；新增 Settings 真实 env 绑定回归
  测试 + `test_provider_selection.py`/`test_coze_provider.py`/`test_ai_api.py`
  聚焦套件通过。
- 状态：**closed/resolved**（Q2 裁定接线落地，默认 fail-closed；未启用生产
  required_action submit）。

### D-06 known_drift = studio-frontend-entry-missing — LOW · 登记内

- 内容：`docs/governance/module-semantics.yaml` 仅存 1 条 known_drift：studio
  前端入口缺失（ux 级）。
- 处置路径：设计者已裁定留待 Portal services 真正提供 studio 入口后关闭；
  不阻塞 Portal Phase 1 解锁。
- 状态：**open by design**（有意保留，禁提前修）。

### D-07 测试基线三口径分裂（R-M4）— MED · 过程 — **resolved**

- 内容（历史问题陈述，已闭合）：CLAUDE.md「12 failed」（05-19）/
  `.quality/known-pytest-failures.txt` 26 条（05-06 后未刷新，`pytest_delta` 闸门
  未持续运转）/ NOW.md 22 条 env 失败（0.7E 全量实跑）。失败集合无单一真源。
- 处置路径：W3 后续批次/独立小窗——重启 `pytest_delta`，刷新
  known-pytest-failures，统一为单一自动刷新口径。
- 状态：**resolved**（2026-06-17，合同 `yc-20260617-31ea6942`，独立测试基线统一小窗）。
  统一为单一 CI-aligned 真源：`.quality/known-pytest-failures.txt`（已刷新到 CI profile
  口径）== `.github/workflows/test.yml` backend job「Backend pytest (main suite)」过滤集
  == `scripts/codex-verify` 的 `CI_BACKEND_PROFILE`（无参 `codex-verify backend` 默认走此
  profile，`tests/governance/test_codex_scripts.py` 锁定三者不漂移），由
  `scripts/pytest_delta.py` 跑 no-new-failures。CLAUDE.md/NOW.md 旧硬编码失败数
  （12/22/26）已移除或标历史化；上文「内容」为已闭合的历史问题陈述，不再作为当前事实。

### D-08 Portal Phase 1 解锁前置条件 — 阻塞性 · 流程

- 内容：Portal Phase 1 = CONDITIONAL UNLOCK（`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`，
  sid:a4e5781a）。C1（DB 红→绿）✅、C2（四面 hash 对齐）✅；**未完成**：
  C3 线上 fail-closed 复验（带凭据验证非默认模块缺行 403 + portal services
  按校过滤）+ **R-H5 生产 SchoolModule 行完整性核查**（最易漏）+ 设计者签发留痕
  （executor does not self-unlock）。
- 处置路径：W4（C3 复验窗，read_only + 线上凭据）→ 设计者签发 → 解锁。
- 状态：**blocked on W4 + sign-off**。Q3 校准（2026-06-13）确认 C3 线上复验 +
  R-H5 生产 SchoolModule 行核查 + 设计者签发三项仍缺——**本 docs-only 校准窗不解锁
  Portal、不自解锁**（executor does not self-unlock）。

### D-09 其余开放风险（指针登记，真源在 audit/调查报告）

| 项 | 级别 | 一句话 | 处置路径 |
|---|---|---|---|
| R-H1 后半 | HIGH | guardian 对 worker 无版本/boot 新鲜度探针（stale 已闭合，盲区开放） | worker /version 探针小窗 |
| R-H2 | HIGH | 全量验证层休眠（CI 实跑证据缺） | push 后核验 CI 实跑 |
| R-H3 | HIGH | 前端门控面零全量回归记录（0.6→0.7A 收口全在 vitest） | 全量回归记录窗 |
| R-M1 | MED | portal 5 端点零消费者、过滤无守卫 | Portal Phase 1 实装时同批 |
| R-M5 | MED | 迁移备份 564MB/次无轮转、失败无自动回滚 | 与 Q5 周期备份一并 |
| R-M6 | MED | 守卫解析 src、交付面是 dist，commit 时不强制链上 | 靠 truth-status 弥补，待闸门化 |
| R-M7 | MED | `/uploads` StaticFiles 在门控分母外 | 门控分母补登记窗 |
| R-L1..L6 | LOW | coze resume 无测试 / ~~pgrep 噪音~~（D-10 闭合）/ 日志轮转序 / 0 字节 DB / ~~docs-only false BUILD_DRIFT~~（D-10 闭合）/ 前端守卫硬编码 | 批量小窗 |
| Q3 | 数据安全 | `modular-arch-restore` 7 commit 唯一副本（origin 无此分支，含 Plan 1 资产） | 一条 push，需用户授权 |
| Q4 | 卫生 | paper-seg pip 缓存事故（206 文件入仓 + .gitignore 缺条目） | 独立小窗 commit 删除 |
| Q5 | 数据安全 | DB 564MB 无周期性备份机制（仅 2 份 06-10 手动备份） | 备份机制设计窗 |

### D-10 Guardian/Truthline 观测语义误报（P0E-1）— LOW · 过程 — **resolved**

- 内容（历史问题陈述，已闭合）：观测层把三类非问题伪装成红灯/活跃风险——
  ①docs/governance-only 的 HEAD 漂移（部署 hash trails HEAD，但区间只改 docs/治理/
  CI/测试/观测脚本，dist+backend 功能等价）触发 `BUILD_DRIFT`/`BACKEND_DRIFT`/
  `PARALLEL_VERSION_DRIFT` blocking red（R-L「docs-only false BUILD_DRIFT」）；
  ②`pgrep -af claude` 把 `.claude` 路径、`claude-meta` 仓库名、`yuanshou-claude`
  包装命令计入活跃 Claude（实测 10，真实 1，触发 `CLAUDE_SESSION_RISK`，R-L「pgrep
  噪音」）；③`codex-context` 把过期 `logs/meta-state.json`（2 天前 red）当当前事实展示。
- 处置路径：观测层最小修复，不动业务 runtime；docs-only 单独分类而非压制真漂移。
- 状态：**resolved**（2026-06-17，合同 `yc-20260617-953c086a`，P0E-1 观测语义窗）。
  新增 `codex_support.classify_hash_drift`（runtime/docs_only/unknown，`unknown`
  fail-safe 保持红，真源/构建输入/依赖/`deploy/`/worker 入口变更仍 blocking red）；
  guardian 把 docs-only 漂移降级为非阻断 yellow `*_DOCS`，`truth-status.sh` 同算法
  （`RUNTIME_PREFIXES` 镜像 `RUNTIME_DRIFT_PREFIXES`）保持 `ALL ALIGNED` exit 0。
  `is_claude_cli_process`/`count_claude_cli_processes` 按 `argv[0]` basename 精确识别
  真 Claude CLI（排除引用/包装/`--no-session-persistence` consult），`truth-doctor.sh`
  JSON+human 两面复用。`collect_meta_runtime_state` + `snapshot_freshness`
  （`META_STATE_FRESH_SECONDS=3600`）给 `codex-context` 加 age + `STALE` 标注。
  12 项治理回归测试锁定（`tests/governance/test_codex_scripts.py`）。

## 使用规则

1. 新发现的债务**先登记后处置**：写入本台账（含级别、证据指针、处置路径），
   由元策按「风险 × 批量 × 可并行性」排窗，不接受窗口内顺手扩 scope。
2. 条目收口必须引用合同窗口 + 证据命令，状态改为 closed 并在仪表盘更新 delta。
3. 本台账与 `docs/governance/debt-report.md`（模块合同生成物）互不替代：
   debt-report 是生成的模块债快照，本台账是跨域治理债的人工裁定真源。
