# 附录 C：C 轴教学资源域调研报告

**Date**: 2026-04-24
**Agent**: Explore (thoroughness: thorough)
**Scope**: 好分数 work + lesson → edu-cloud homework / bank / paper / studio
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)

---

**重要**：本轴是 edu-cloud 最空白的域。好分数 work（作业）+ lesson（教学资源）模块丰富，edu-cloud homework 只有 588 行基础 CRUD，bank 只有 232 行骨架，paper 只有 53 行空壳，studio 是 440 行骨架。

## 业务能力对照表

| 能力维度 | 好分数现状 | edu-cloud 现状 | 差距评级 |
|---------|----------|-------------|--------|
| **作业布置闭环** | 5 类作业（同步/周清/备考/考后/常规）→ 发布 → 学生做 → 提交 → 批改 → 报告 | 基础 CRUD（create/publish/submit/grade），缺考后针对推送 | 🔴 中 |
| **作业内容编辑** | UI 步骤条（选班级→科目→编辑→确认），支持题目拖拽/模板 | content 字段纯 JSON 文本，无编辑器 UI | 🔴 高 |
| **错题本** | 错题追踪 → 知识点聚合 → 再推送，支持分类浏览 | bank 模块仅查询 + 统计，缺追踪→推送流程 | 🔴 高 |
| **备课资源库** | 4 个场景（我的资源/我的讲评/我的组卷/网盘），支持上传/收藏/分享 | paper/studio 为骨架，无 UI 层 + 权限体系 | 🔴 高 |
| **教学资源版本管理** | 隐含支持（空间内资源可分享/审核） | DocumentVersion 表存在，无 revision 发布/审核流 | 🔴 中 |
| **试卷库权限层级** | 3 层：教师自建 → 学校共享 → 区域共享 | paper 为纯 service（无 router），无权限分级 | 🔴 高 |
| **精准教学推送** | 基于考后数据 + 知识点掌握度推送个性化资源 | adaptive 模块存在，缺与 homework 链接 | 🔴 中 |
| **集体备课** | 多教师协同编辑 → 审核 → 发布 → 版本追踪 | studio 支持 draft→pending→approved→executed，缺协同编辑 UI | 🟡 中 |
| **题库数据模型** | question_bank（232 行 schema），支持源追踪 + 标签 + 难度 | bank_question（65 行 models），字段稀疏 | 🔴 高 |
| **教学计划管理** | teaching_plans 表（学期→周次→课时→知识点→资源绑定） | knowledge_tree 存在，缺 teaching_plans → resource 绑定 | 🔴 中 |

## Gap 清单

### 🔴 高价值缺失（本轴最多）

1. **作业内容编辑完整闭环缺失**
   - 好分数：UI 步骤条 + 题目选择器（从题库/考试试卷/自建试题拖拽）+ 富文本编辑
   - edu-cloud：homework_tasks.content 只是 JSON TEXT 字段，无前端编辑器
   - 文件位置：`haofenshu-clone/frontend/pages/work/publish.vue:351` vs edu-cloud homework 无对应组件
   - **影响**：教师无法直观编辑作业，降低使用意愿
   - **优先级**：P0（作业系统核心入口）

2. **错题本 → 知识点 → 推荐资源完整流程缺失**
   - 好分数：错题本（questionBook）→ 知识点聚合 → 精准教学控制台推荐资源 + 再推送作业
   - edu-cloud：
     - bank.error_book 仅支持查询 + 统计（router.py:71-94）
     - bank.service.py 无推荐逻辑（73 行空壳）
     - adaptive.py 有 diagnose_and_recommend 工具，但未与 homework 联动
   - 文件位置：edu-cloud/src/edu_cloud/modules/bank/service.py:0-73
   - **影响**：教学诊断的"最后一公里"缺失
   - **优先级**：P0（精准教学核心）

3. **备课资源库 UI 层及权限分级缺失**
   - 好分数：lesson/space/ 模块（课件/教案/组卷/视频/网盘），支持上传/分类/收藏/分享/权限设置
     - `/lesson/space/home`（主页），`/lesson/space/comment`（讲评），`/lesson/space/paper`（组卷）
     - 前端实现 554 行（space.vue）
   - edu-cloud：
     - paper 模块仅有 53 行 PaperService（REST 客户端调 paper-skill）
     - studio 有 Document 模型 + DocumentVersion，但无前端页面
     - 缺教师自己的资源库（"我的讲评"、"我的组卷"）
   - 文件位置：`haofenshu-clone/frontend/pages/lesson/space.vue:554` vs edu-cloud 无对应前端
   - **影响**：资源共享/沉淀机制缺失，集体备课无基础
   - **优先级**：P0（教学资源核心枢纽）

4. **试卷库权限与组卷系统缺失**
   - 好分数：tk 模块（教研）包括：
     - 校本资源（/tk/schoolResource/home）：教师自建 + 学校共享 + 区域共享三层
     - 选题组卷（/tk/textbook）：从题库选题 → 自动组卷
     - 试卷编辑（/tk/edited）：拖拽编辑 + 预览 + 发布
     - 集体备课（/tk/collectionPreparation/list）：多教师编辑 + 审核发布
   - edu-cloud：
     - paper 服务仅与外部 paper-skill 通信
     - exam.models 有 Question/ExamSubject 但无组卷流程
     - 无"集体备课"工作流
   - 文件位置：`haofenshu-clone/frontend/pages/lesson/ 全 4 个场景` vs edu-cloud/modules/paper/service.py:54
   - **影响**：教研资源库无法建设
   - **优先级**：P1（中期建设）

5. **题库数据模型稀疏**
   - 好分数：question_bank 表（232 行）包含：
     - question_type, difficulty（0-1 难度系数）, content, answer, explanation
     - knowledge_point_ids（JSON 数组）, source（textbook/exam/custom）, grade, tags（JSON 数组）
   - edu-cloud：bank_question 表（65 行 models）仅包含：
     - question_id, exam_id, question_type, max_score, difficulty, discrimination
     - common_errors, attempt_count
   - 文件位置：`haofenshu-clone/server/config/schema.sql:232-245` vs `edu-cloud/src/edu_cloud/modules/bank/models.py:65`
   - **影响**：题库无法进行有效的知识点标签、来源追踪、难度分级
   - **优先级**：P1（题库质量）

6. **教学计划与资源绑定缺失**
   - 好分数：teaching_plans 表记录学期→周次→课时→知识点，可绑定资源
   - edu-cloud：
     - knowledge_tree 存在但仅是知识点映射
     - 无 teaching_plans 表或课程进度管理
     - knowledge_tree.concept_stats 有 textbook_chapters 但无进度绑定
   - 文件位置：`haofenshu-clone/server/config/schema.sql:284-302` vs edu-cloud 无对应
   - **影响**：备课无法按教学计划关联资源
   - **优先级**：P2（进阶功能）

### 🟡 有价值优化

1. **作业批改工具不完整**
   - 好分数：支持在线批改 + 扫描识别 + AI 辅助批改 + 讲评视频
   - edu-cloud：homework_submission 只有 score + feedback，无扫描识别/AI 识别接口
   - **建议**：接入扫描模块（已有 scan/pipeline）+ grading AI 工具

2. **集体备课协同编辑缺失**
   - 好分数：`/tk/collectionPreparation/list` 支持多教师同时编辑
   - edu-cloud：StudioService 只有版本管理，无协同锁机制
   - **建议**：基于 Document 表实现 simple lock（非 CRDT）

3. **资源审核流程粗糙**
   - 好分数：校本资源上传 → 审核 → 发布（隐含）
   - edu-cloud：studio Document 支持 draft→pending→approved→executed，但缺前端审核界面
   - **建议**：补全 studio 前端（审核人工作台）

4. **知识点掌握度与教学资源推荐未链接**
   - 好分数：精准教学控制台（/lesson/teachingDesk/home）基于错题数据推送资源
   - edu-cloud：
     - adaptive.diagnose_and_recommend 工具存在
     - homework_tasks.content 无法承载个性化资源列表
   - **建议**：扩展 homework_tasks 支持 ai_recommendation 字段

### 🟢 锦上添花

1. **AI 资源生成**：studio 调 paper-skill（论文生成），可扩展为教案/课件生成
2. **资源版本 diff 可视化**：DocumentVersion 表已有，可补充前端版本对比
3. **资源流量统计**：补充访问日志表，支持热门资源排行

## edu-cloud 超前清单

1. **知识图谱可视化**（knowledge_tree + AntV G6）
   - 好分数：知识体系管理相对静态
   - edu-cloud：concept_graph_nodes/edges 支持图谱编辑、审核状态机、mastery 着色
   - **应用**：教师可视化查看教学目标达成度

2. **自适应学习系统**（adaptive 模块）
   - 好分数：精准教学是规则推送，无个性化选题
   - edu-cloud：BKT 掌握度 + knowledge_point 难度阶跃 + da_catalog_snapshot
   - **应用**：为学生推荐难度梯进的错题练习

3. **跨会话 Agent 记忆**（entity_memory + project_state）
   - 好分数：无实现
   - edu-cloud：EntityMemory 表记录学生/教师特征，ProjectState 记录备课进度

4. **操行积分系统**（conduct 模块）
   - 好分数：无
   - edu-cloud：class_points + conduct_records + 家长端绑定

## 边界说明

本轴**不覆盖**：
- **成绩排名/对比分析** → A 轴
- **知识点掌握度诊断** → B 轴（虽涉及错题追踪，但诊断逻辑属 B）
- **班级/学校行政管理** → D 轴
- **阅卷工作流** → A 轴

本轴**核心边界**：教学资源的获取、编辑、共享、版本、推荐 → 作业系统的联动闭环

## 优先级建议

### 1. 基础层（必做）—— 3-4 周

- 作业内容编辑器（题目选择器 + 富文本）
  - 前端：homework/TaskEditor.vue（拖拽题库题目，富文本描述）
  - 后端：无改动（content JSON 已支持）
  - 文件点：new `edu-cloud/frontend/src/pages/HomeworkPublishPage.vue`

- bank 模块增强：错题本 → 知识点聚合
  - 后端：bank/service.py 补充 `get_error_pattern_by_knowledge_point()`
  - 前端：bank/StudentErrorBookPage.vue（知识点 tab 分类）
  - 文件点：edu-cloud/src/edu_cloud/modules/bank/service.py:73+

- 题库数据模型补全：question_bank → bank_question 字段扩展
  - 添加表字段：source, explanation, knowledge_points（JSON）
  - Alembic migration
  - 文件点：alembic/versions/xxx_extend_bank_question.py

### 2. 进阶层（次做）—— 4-5 周

- 备课资源库 UI（我的讲评/我的组卷）
  - 前端：studio/StudioDocumentList.vue + StudioEditor.vue
  - 后端：studio/router.py 已有，补充权限过滤
  - 文件点：edu-cloud/frontend/src/pages/teach/StudioPage.vue

- 错题追踪 → 作业推送（homework 与 adaptive 链动）
  - 后端：homework/service.py 补充 `create_remedial_homework_from_errors()`
  - 调用 adaptive 工具生成题目列表
  - 文件点：edu-cloud/src/edu_cloud/modules/homework/service.py:289+

- 集体备课工作流（studio document 前端审核）
  - 前端：studio/ApprovalWorkbench.vue
  - 后端：studio/approval_service.py 已有
  - 文件点：edu-cloud/frontend/src/pages/studio/ApprovalPage.vue

### 3. 高阶层（可选）—— 6+ 周

- 试卷库权限分级（自建/学校/区域）
  - 新增表：paper_access_policy（school_id, paper_id, access_level）
  - 需要区域管理员管理界面
  - 文件点：new modules/research/ 子模块

- 教学计划管理（teaching_plans 表 + 资源绑定）
  - 数据表：teaching_plans, teaching_plan_resources
  - 前端：calendar/TeachingPlanEditor.vue
  - 文件点：new modules/calendar/ 扩展

- 资源版本 diff + 分享审计
  - 前端：studio/DocumentDiffView.vue
  - 后端：studio 补充 `get_version_diff()`

## 关键依赖链

- 基础层 → 进阶层（错题推送需要基础编辑器支撑教师创建补充练习）
- 进阶层 → 高阶层（试卷库权限需要先有资源库，才能管理共享）

## 交付物梗概

| 阶段 | 新增表 | 修改表 | 前端新页面 | 后端新服务 |
|-----|------|------|---------|---------|
| 基础 | 无 | bank_question(扩字段) | HomeworkEditor, BankKnowledgeTab | bank.get_error_patterns |
| 进阶 | 无 | homework_tasks(ai_recommendation) | StudioDocumentList, ApprovalWorkbench | homework.create_remedial_from_errors |
| 高阶 | paper_access_policy, teaching_plans | teaching_plans_resources | TeachingPlanEditor, ResourcePolicyMgmt | research.list_accessible_papers |
