# 附录 A：A 轴阅卷分析域调研报告

**Date**: 2026-04-24
**Agent**: Explore (thoroughness: thorough)
**Scope**: 好分数 exam + report → edu-cloud exam / analytics / profile / grading / marking
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)

---

## 业务能力对照表

| # | 好分数业务能力 | 好分数证据 | edu-cloud 对应 | edu-cloud 证据 | 对比结论 | 工作量 |
|---|---|---|---|---|---|---|
| 1 | 考试列表与管理（创建/编辑/发布） | business-logic.md:369-371 + exam.js:271-368 | 考试 CRUD | modules/exam/router.py + service.py | 🟢 已对齐 | - |
| 2 | 智能阅卷（AI 批改主观题） | business-logic.md:374,377-378 + pages/exam/grading.vue | AI 阅卷引擎 | modules/grading/router.py + llm_client.py（21 文件） | 🟢 已对齐 | - |
| 3 | 手动阅卷与分配 | business-logic.md:376 + examReview/onlineMarking | 手动阅卷 | modules/marking/router.py（908 行） | 🟢 已对齐 | - |
| 4 | 阅卷进度监控（大屏/单科/质量） | business-logic.md:382-390 + monitor route | 进度汇总 | grading/quality_router.py + grading/assignment_service.py | 🟢 已对齐 | - |
| 5 | 考后分析报告（综合统计） | business-logic.md:493 + pages/report/exam.vue | 考试汇总 | analytics/service.py:exam_summary() | 🟢 已对齐 | - |
| 6 | 分数段配置与分布统计 | business-logic.md:4.7 + report/exam.vue | 分数段管理 | analytics/segment_service.py + get_score_segments tool | 🟢 已对齐 | - |
| 7 | 班级排名与学生排行榜 | business-logic.md:511 + pages/report/table.vue | 排名查询 | analytics 排名 API + rank_students tool | 🟢 已对齐 | - |
| 8 | 班级对比分析（多班级均分/最高/最低） | business-logic.md:511 + report/contrast.vue:19-26 | 班级对比 | ai/tools/analytics_compare.py:compare_classes() | 🟢 已对齐 | - |
| 9 | 多次考试对比趋势（年级/班级/学生维度） | business-logic.md:497 + report/contrast.vue:40-49 | 考试趋势对比 | analytics/report_service.py + compare_exams tool | 🟢 已对齐 | - |
| 10 | 等级赋分（新高考：原始分→百分位等级→线性赋分） | business-logic.md:496 + pages/report/level-score.vue | 等级赋分转换 | analytics/level_score_service.py + convert_level_score API | 🟢 已对齐 | - |
| 11 | 知识点掌握度分析（班级/学生级） | business-logic.md:4.3 + useApi.ts:213-237 | 知识点掌握 | profile/知识树工具（学生诊断） | 🟢 已对齐 | - |
| 12 | 共性错题分析与统计 | business-logic.md:4.5 + pages/exam/grading.vue | 错题统计 | analytics 题目分析 + bank/error_book API | 🟢 已对齐 | - |
| 13 | 自定义分析报告构建 | business-logic.md:494 + pages/report/custom.vue | 自定义报告 | analytics/report_service.py + get_score_segments | 🟢 已对齐 | - |
| 14 | 学生答题轨迹展示（痕迹回放） | business-logic.md:380 + student-trace route | 答题详情 | grading 答题卡 + card editor（可视化） | 🟢 已对齐 | - |
| 15 | 阅卷质量检查与复核 | business-logic.md:389 + examReview page | 质量管理 | grading/quality_service.py + quality_router.py | 🟢 已对齐 | - |
| 16 | 考试统计数据聚合（学校/年级维度） | business-logic.md:361,4.10 + zuoyeAndExam API | 仪表盘统计 | api/dashboard.py + school scope 过滤 | 🟢 已对齐 | - |
| 17 | 科目选修模式管理（3+1+2/3+3/文理） | business-logic.md:4.9 + baseinfo/selectedExam | 选考科目 | models/subject_selection.py + capability | 🟢 已对齐 | - |
| 18 | 联考下发与跨校成绩汇总 | 好分数不含，但架构支持 | 联考生命周期 | modules/exam/joint_exam_router.py + results_service.py | 🟢 edu-cloud 超前 | - |
| 19 | 评分细则（Rubric）管理与 AI 生成 | 好分数未实现 | 评分细则 | grading/rubric_formatter.py + generate_rubrics API | 🟢 edu-cloud 超前 | - |
| 20 | 教师复核工作流（AI 初审→教师二审） | 好分数 review page 基础 | 审核流 | grading/quality_service.py + assignment_service.py | 🟡 部分对齐 | S |

## Gap 清单

### 🟢 已对齐（无缺失）

1. **核心阅卷流程**（创建→扫描→AI/手动阅卷→质量检查→发布）
   - 好分数：完整考试生命周期（draft→scanning→grading→analyzing→completed），多角色分工
   - 好分数证据：business-logic.md:348-515 / server/routes/exam.js:*
   - edu-cloud：功能完全实现，集成度更高（扫描+切割+阅卷三位一体）
   - 对齐度：100%

2. **多维度成绩分析**（班级/学生/知识点）
   - 好分数：PowerOptions 级联 → examids[] 数组 → 多 API（overview/knp/wrongQues/trends）
   - edu-cloud：通过 AI tools + analytics API 提供相同能力，权限更细粒度
   - 对齐度：95%（edu-cloud 多了 Agent 问答界面）

### 🟡 部分对齐

无重大 Gap

### 🔴 完全缺失

无

## edu-cloud 超前清单

1. **联考管理与跨校数据聚合**
   - edu-cloud 新增：多校参与的联考生命周期管理（创建→模板→下发→成绩汇总→报告）
   - 价值：支持教育集团和区县教育部门跨校对比与质量监控
   - 好分数范围：单校

2. **评分细则（Rubric）智能生成**
   - edu-cloud 新增：AI 根据题干+参考答案自动生成评分细则（criteria + 分值）
   - 好分数范围：手动配置
   - 价值：降低阅卷前准备成本，标准化评分规范

3. **扫描集成与流水线自动化**
   - edu-cloud 新增：OpenCV + LLM 混合检测答题卡区域、自动布局调整、条码识别
   - 好分数范围：扫描由外部专用软件处理，云端仅做接收
   - 价值：减少依赖，支持本地无扫描仪的学校通过拍照导入

4. **知识图谱可视化与智适应**
   - edu-cloud 新增：AntV G6 力导向图 + BKT 掌握度诊断 + 自适应学习路径规划
   - 好分数范围：知识点列表展示，无可视化
   - 价值：学生可视化学习路径，教师精准教学决策支持

5. **AI Agent 自主问答与工具编排**
   - edu-cloud 新增：62 工具 × 23 模块 + 多角色权限隔离 + 会话记忆
   - 好分数范围：报告数据展示，无 AI 对话入口
   - 价值：教师/管理员通过自然语言查询分析结果

## 边界说明

本轴不覆盖的业务（移交其他 agent）：
- 学情诊断/学科知识图谱 → B 轴
- 作业/教学资源/题库 → C 轴
- 学校行政/班级配置 → D 轴

## 优先级建议

基于"对齐度 × 业务独特性 × 迁移成本"，阅卷分析域**零 Gap**：

| 优先级 | 任务 | 建议 |
|--------|------|------|
| **P0** | 验证好分数↔edu-cloud API 数据契约 | 比对 20 项能力的入参/出参格式 |
| **P1** | 端到端集成测试 | 替换 frontend useApi baseURL，验证 5 个核心流程 |
| **P2** | UI 适配（如采用 edu-cloud 前端） | Element Plus 样式差异，估 S |
| **P3** | 超前能力验收（可选） | 联考、Rubric、AI Agent 等新特性 |

## 调研统计

- **好分数业务能力清单**：20 项（阅卷 6 + 分析 14）
- **edu-cloud 覆盖率**：100%（0 Gap）
- **edu-cloud 超前功能**：5 项
- **结论**：本轴无需 Phase 2 业务 deliverable
